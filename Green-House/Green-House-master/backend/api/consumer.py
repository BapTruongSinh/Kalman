import asyncio
import json
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .models import Alert, ControlState, Device, SensorData
from .serializers import (
    AlertSerializer,
    ControlStateSerializer,
    DeviceSerializer,
    SensorDataSerializer,
)
from .services import (
    ack_device_command_payload,
    enqueue_device_command,
    get_controller,
    get_pending_commands,
    ingest_heartbeat_payload,
    ingest_sensor_payload,
    mark_device_offline,
    refresh_device_statuses,
)

frontend_group = "frontend"
FRONTEND_POLL_SECONDS = 3


def _control_state():
    control, _ = ControlState.objects.get_or_create(singleton_key="main")
    return control


def _esp32_online():
    refresh_device_statuses()
    return Device.objects.filter(
        device_type=Device.DeviceType.CONTROLLER,
        status=Device.DeviceStatus.ONLINE,
    ).exists()


def _current_sensor_errors():
    controller = Device.objects.filter(device_type=Device.DeviceType.CONTROLLER).first()
    if not controller:
        return {
            "dht": False,
            "soil": False,
            "light": False,
            "gas": False,
        }

    metadata = controller.metadata or {}
    sensor_errors = metadata.get("sensor_errors") or {}

    return {
        "dht": bool(sensor_errors.get("dht", False)),
        "soil": bool(sensor_errors.get("soil", False)),
        "light": bool(sensor_errors.get("light", False)),
        "gas": bool(sensor_errors.get("gas", False)),
    }


def _dashboard_packet():
    control = _control_state()
    alerts = list(Alert.objects.order_by("-happened_at", "-id")[:20])
    esp32_online = _esp32_online()
    sensor_errors = _current_sensor_errors()

    latest = None
    latest_data = None

    if esp32_online:
        latest = SensorData.objects.order_by("-recorded_at", "-id").first()
        latest_data = SensorDataSerializer(latest).data if latest else None

    return {
        "type": "state",
        "data": {
            "latest": latest_data,
            "control": ControlStateSerializer(control).data,
            "devices": DeviceSerializer(Device.objects.order_by("id"), many=True).data,
            "alerts": AlertSerializer(alerts, many=True).data,
            "sensor_errors": sensor_errors,
            "esp32_online": esp32_online,
            "updated_at": timezone.now().isoformat(),
        },
    }


def _set_manual_mode(reason: str = ""):
    control = _control_state()
    control.mode = ControlState.Mode.MANUAL
    control.manual_reason = reason
    control.manual_changed_at = timezone.now()
    control.save(
        update_fields=["mode", "manual_reason", "manual_changed_at", "updated_at"]
    )


def _set_mode(mode: str):
    control = _control_state()
    mode = mode.upper().strip()

    if mode not in {ControlState.Mode.AUTO, ControlState.Mode.MANUAL}:
        raise ValueError("mode phải là AUTO hoặc MANUAL")

    if mode == ControlState.Mode.AUTO and _current_sensor_errors().get("dht", False):
        raise ValueError("Không thể bật AUTO khi cảm biến DHT đang lỗi")

    control.mode = mode
    if mode == ControlState.Mode.AUTO:
        control.manual_reason = ""
        control.manual_changed_at = None
        control.save(
            update_fields=["mode", "manual_reason", "manual_changed_at", "updated_at"]
        )
    else:
        control.manual_changed_at = timezone.now()
        if not control.manual_reason:
            control.manual_reason = "frontend_mode_change"
        control.save(
            update_fields=["mode", "manual_reason", "manual_changed_at", "updated_at"]
        )


@database_sync_to_async
def auth_device(device_code: str, token: str | None):
    device = Device.objects.filter(code=device_code).first()
    if not device:
        device = get_controller(device_code=device_code)

    if token and device.api_token and device.api_token != token:
        return False
    return True


@database_sync_to_async
def build_state_packet():
    return _dashboard_packet()


@database_sync_to_async
def ingest_telemetry(data: dict, device_code: str):
    ingest_sensor_payload(data, device_code=device_code)


@database_sync_to_async
def ingest_heartbeat(data: dict, device_code: str):
    ingest_heartbeat_payload(data, device_code=device_code)


@database_sync_to_async
def ack_command(data: dict):
    ack_device_command_payload(data)


@database_sync_to_async
def pending_commands():
    return get_pending_commands()


@database_sync_to_async
def queue_manual_command(device_code: str, state: str):
    device = Device.objects.filter(code=device_code).first()
    if not device:
        device = Device.objects.filter(device_type=device_code).first()
    if not device:
        raise ValueError(f"Không tìm thấy device {device_code}")

    _set_manual_mode(reason=f"manual_ws:{device.code}")
    enqueue_device_command(device=device, command="set_power", value=state.lower())


@database_sync_to_async
def update_mode_only(mode: str):
    _set_mode(mode)


class FrontendConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.monitor_task = None
        self.last_esp32_online = None

        await self.channel_layer.group_add(frontend_group, self.channel_name)
        await self.accept()

        packet = await build_state_packet()
        packet["type"] = "bootstrap"
        self.last_esp32_online = packet["data"].get("esp32_online")

        await self.send(text_data=json.dumps(packet, cls=DjangoJSONEncoder))

        self.monitor_task = asyncio.create_task(self.monitor_status_changes())

    async def disconnect(self, close_code):
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        await self.channel_layer.group_discard(frontend_group, self.channel_name)

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps({"type": "error", "reason": "invalid_json"})
            )
            return

        msg_type = payload.get("type")

        try:
            if msg_type == "mode":
                mode_value = str(payload.get("value") or "").upper().strip()
                await update_mode_only(mode_value)

                esp_group = "esp32.esp32-main"
                await self.channel_layer.group_send(
                    esp_group,
                    {
                        "type": "ws_message",
                        "event_type": "mode",
                        "data": {
                            "value": mode_value,
                        },
                    },
                )

                await self.send_state({"packet": await build_state_packet()})
                return

            if msg_type == "device_control":
                device = str(payload.get("device") or "").strip().lower()
                state = str(payload.get("state") or "").strip().lower()

                if device not in {"fan", "pump", "light"} or state not in {"on", "off"}:
                    raise ValueError("device_control không hợp lệ")

                await queue_manual_command(device, state)

                esp_group = "esp32.esp32-main"
                await self.channel_layer.group_send(
                    esp_group,
                    {
                        "type": "ws_message",
                        "event_type": "pending_commands",
                        "data": {
                            "commands": await pending_commands(),
                        },
                    },
                )

                await self.send_state({"packet": await build_state_packet()})
                return

            if msg_type in {"alert_mark_read", "alert_mark_all_read"}:
                return

            await self.send(
                text_data=json.dumps(
                    {"type": "error", "reason": f"unsupported:{msg_type}"}
                )
            )

        except Exception as exc:
            await self.send(text_data=json.dumps({"type": "error", "reason": str(exc)}))
            await self.send_state({"packet": await build_state_packet()})

    async def send_state(self, event):
        packet = event["packet"]
        self.last_esp32_online = packet.get("data", {}).get("esp32_online")
        await self.send(text_data=json.dumps(packet, cls=DjangoJSONEncoder))

    async def monitor_status_changes(self):
        try:
            while True:
                await asyncio.sleep(FRONTEND_POLL_SECONDS)

                packet = await build_state_packet()
                current_online = packet["data"].get("esp32_online")

                if current_online != self.last_esp32_online:
                    self.last_esp32_online = current_online
                    await self.send(
                        text_data=json.dumps(packet, cls=DjangoJSONEncoder)
                    )
        except asyncio.CancelledError:
            pass


class ESPConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.device_code = (
            self.scope.get("url_route", {}).get("kwargs", {}).get("device_code")
            or "esp32-main"
        )

        raw_qs = (self.scope.get("query_string") or b"").decode()
        token = parse_qs(raw_qs).get("token", [None])[0]

        ok = await auth_device(self.device_code, token)
        if ok is False:
            await self.close(code=4003)
            return

        self.group_name = f"esp32.{self.device_code}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send_pending_commands()
        await self.push_state_to_frontend()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        await sync_to_async(mark_device_offline)(self.device_code)
        await self.push_state_to_frontend()

    async def receive(self, text_data):
        try:
            packet = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps({"type": "error", "message": "invalid_json"})
            )
            return

        msg_type = packet.get("type")
        data = packet.get("data") or {}

        try:
            if msg_type == "telemetry":
                await ingest_telemetry(data, self.device_code)
                await self.push_state_to_frontend()
                return

            if msg_type == "heartbeat":
                await ingest_heartbeat(data, self.device_code)
                return

            if msg_type == "ack":
                await ack_command(data)
                return

            if msg_type == "sync_commands":
                await self.send_pending_commands()
                return

            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": f"unsupported_type:{msg_type}"}
                )
            )

        except Exception as exc:
            await self.send(
                text_data=json.dumps({"type": "error", "message": str(exc)})
            )

    async def send_pending_commands(self):
        commands = await pending_commands()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "pending_commands",
                    "data": {"commands": commands},
                }
            )
        )

    async def push_state_to_frontend(self):
        packet = await build_state_packet()
        await self.channel_layer.group_send(
            frontend_group,
            {
                "type": "send_state",
                "packet": packet,
            },
        )

    async def ws_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": event["event_type"],
                    "data": event["data"],
                }
            )
        )