import asyncio
import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication

from .ampc import default_greenhouse
from .models import Alert, ControlState, Device, Greenhouse, SensorData
from .serializers import (
    AlertSerializer,
    ControlStateSerializer,
    DeviceSerializer,
    SensorDataSerializer,
)
from .services import (
    ack_device_command_payload,
    enqueue_device_command,
    get_pending_commands,
    ingest_heartbeat_payload,
    ingest_sensor_payload,
    mark_device_offline,
    refresh_device_statuses,
)

FRONTEND_POLL_SECONDS = 3


def _frontend_group(greenhouse_id: int) -> str:
    return f"frontend.{greenhouse_id}"


def _esp_group(device_id: int) -> str:
    return f"esp32.device.{device_id}"


def _control_state(greenhouse_id: int | None = None):
    if greenhouse_id is None:
        control, _ = ControlState.objects.get_or_create(singleton_key="main")
        return control
    control, _ = ControlState.objects.get_or_create(
        greenhouse_id=greenhouse_id,
        defaults={"singleton_key": ControlState.singleton_key_for_greenhouse(greenhouse_id)},
    )
    return control


def _esp32_online(greenhouse_id: int) -> bool:
    greenhouse = Greenhouse.objects.get(pk=greenhouse_id)
    refresh_device_statuses(greenhouse=greenhouse)
    return Device.objects.filter(
        greenhouse_id=greenhouse_id,
        device_type=Device.DeviceType.CONTROLLER,
        status=Device.DeviceStatus.ONLINE,
    ).exists()


def _current_sensor_errors(greenhouse_id: int) -> dict:
    controller = (
        Device.objects
        .filter(greenhouse_id=greenhouse_id, device_type=Device.DeviceType.CONTROLLER)
        .first()
    )
    if not controller:
        return {"dht": False, "soil": False, "light": False, "gas": False}

    sensor_errors = (controller.metadata or {}).get("sensor_errors") or {}
    return {
        "dht": bool(sensor_errors.get("dht", False)),
        "soil": bool(sensor_errors.get("soil", False)),
        "light": bool(sensor_errors.get("light", False)),
        "gas": bool(sensor_errors.get("gas", False)),
    }


def _dashboard_packet(greenhouse_id: int) -> dict:
    control = _control_state(greenhouse_id)
    alerts = list(
        Alert.objects
        .filter(Q(sensor_data__greenhouse_id=greenhouse_id) | Q(device__greenhouse_id=greenhouse_id))
        .distinct()
        .order_by("-happened_at", "-id")[:20]
    )
    esp32_online = _esp32_online(greenhouse_id)
    sensor_errors = _current_sensor_errors(greenhouse_id)

    latest_data = None
    if esp32_online:
        latest = (
            SensorData.objects
            .filter(greenhouse_id=greenhouse_id)
            .order_by("-recorded_at", "-id")
            .first()
        )
        latest_data = SensorDataSerializer(latest).data if latest else None

    return {
        "type": "state",
        "data": {
            "latest": latest_data,
            "control": ControlStateSerializer(control).data,
            "devices": DeviceSerializer(
                Device.objects.filter(greenhouse_id=greenhouse_id).order_by("id"),
                many=True,
            ).data,
            "alerts": AlertSerializer(alerts, many=True).data,
            "sensor_errors": sensor_errors,
            "esp32_online": esp32_online,
            "updated_at": timezone.now().isoformat(),
        },
    }


def _set_manual_mode(greenhouse_id: int, reason: str = ""):
    control = _control_state(greenhouse_id)
    control.mode = ControlState.Mode.MANUAL
    control.manual_reason = reason
    control.manual_changed_at = timezone.now()
    control.save(update_fields=["mode", "manual_reason", "manual_changed_at", "updated_at"])


def _set_mode(greenhouse_id: int, mode: str):
    control = _control_state(greenhouse_id)
    mode = mode.upper().strip()

    if mode not in {ControlState.Mode.AUTO, ControlState.Mode.MANUAL}:
        raise ValueError("mode must be AUTO or MANUAL")
    if mode == ControlState.Mode.AUTO and _current_sensor_errors(greenhouse_id).get("dht", False):
        raise ValueError("cannot enable AUTO while DHT sensor is in error")

    control.mode = mode
    if mode == ControlState.Mode.AUTO:
        control.manual_reason = ""
        control.manual_changed_at = None
    else:
        control.manual_changed_at = timezone.now()
        if not control.manual_reason:
            control.manual_reason = "frontend_mode_change"
    control.save(update_fields=["mode", "manual_reason", "manual_changed_at", "updated_at"])


def auth_device_sync(device_code: str, token: str | None):
    if not token or token == settings.INGEST_DEVICE_TOKEN:
        return None

    device = (
        Device.objects
        .select_related("greenhouse")
        .filter(api_token=token, is_enabled=True, device_type=Device.DeviceType.CONTROLLER)
        .first()
    )
    if device is None or (device_code and device.code != device_code):
        return None

    if device.greenhouse_id is None:
        greenhouse = default_greenhouse()
        device.greenhouse = greenhouse
        device.save(update_fields=["greenhouse", "updated_at"])

    return {"id": device.id, "code": device.code, "greenhouse_id": device.greenhouse_id}


@database_sync_to_async
def auth_device(device_code: str, token: str | None):
    return auth_device_sync(device_code, token)


def auth_frontend_token_sync(token: str | None):
    if not token:
        return None
    try:
        authenticator = JWTAuthentication()
        validated = authenticator.get_validated_token(token)
        user = authenticator.get_user(validated)
    except Exception:
        return None
    if not user or not user.is_authenticated:
        return None
    greenhouse = default_greenhouse(user)
    return {"user_id": user.id, "greenhouse_id": greenhouse.id}


@database_sync_to_async
def auth_frontend_token(token: str | None):
    return auth_frontend_token_sync(token)


@database_sync_to_async
def frontend_scope_for_user(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    greenhouse = default_greenhouse(user)
    return {"user_id": user.id, "greenhouse_id": greenhouse.id}


@database_sync_to_async
def build_state_packet(greenhouse_id: int):
    return _dashboard_packet(greenhouse_id)


@database_sync_to_async
def ingest_telemetry(data: dict, device_id: int):
    device = Device.objects.select_related("greenhouse").get(pk=device_id)
    ingest_sensor_payload(data, device_code=device.code, greenhouse=device.greenhouse)


@database_sync_to_async
def ingest_heartbeat(data: dict, device_id: int):
    device = Device.objects.select_related("greenhouse").get(pk=device_id)
    ingest_heartbeat_payload(data, device_code=device.code, greenhouse=device.greenhouse)


@database_sync_to_async
def ack_command(data: dict, greenhouse_id: int):
    greenhouse = Greenhouse.objects.get(pk=greenhouse_id)
    return ack_device_command_payload(data, greenhouse=greenhouse)


@database_sync_to_async
def pending_commands(greenhouse_id: int):
    greenhouse = Greenhouse.objects.get(pk=greenhouse_id)
    return get_pending_commands(greenhouse=greenhouse)


@database_sync_to_async
def controller_group_names(greenhouse_id: int):
    return [
        _esp_group(device_id)
        for device_id in Device.objects.filter(
            greenhouse_id=greenhouse_id,
            device_type=Device.DeviceType.CONTROLLER,
        ).values_list("id", flat=True)
    ]


@database_sync_to_async
def queue_manual_command(greenhouse_id: int, device_code: str, state: str):
    device = Device.objects.filter(greenhouse_id=greenhouse_id, code=device_code).first()
    if not device:
        device = Device.objects.filter(greenhouse_id=greenhouse_id, device_type=device_code).first()
    if not device:
        raise ValueError(f"device not found: {device_code}")

    _set_manual_mode(greenhouse_id, reason=f"manual_ws:{device.code}")
    enqueue_device_command(device=device, command="set_power", value=state.lower())


@database_sync_to_async
def update_mode_only(greenhouse_id: int, mode: str):
    _set_mode(greenhouse_id, mode)


@database_sync_to_async
def mark_connected_device_offline(device_code: str, greenhouse_id: int):
    greenhouse = Greenhouse.objects.get(pk=greenhouse_id)
    mark_device_offline(device_code, greenhouse=greenhouse)


class FrontendConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.monitor_task = None
        self.last_esp32_online = None
        self.greenhouse_id = None

        raw_qs = (self.scope.get("query_string") or b"").decode()
        token = parse_qs(raw_qs).get("token", [None])[0]

        scope = await frontend_scope_for_user(self.scope.get("user"))
        if scope is None:
            scope = await auth_frontend_token(token)
        if scope is None:
            await self.close(code=4003)
            return

        self.greenhouse_id = scope["greenhouse_id"]
        self.group_name = _frontend_group(self.greenhouse_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        packet = await build_state_packet(self.greenhouse_id)
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

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "reason": "invalid_json"}))
            return

        msg_type = payload.get("type")

        try:
            if msg_type == "mode":
                mode_value = str(payload.get("value") or "").upper().strip()
                await update_mode_only(self.greenhouse_id, mode_value)

                for group_name in await controller_group_names(self.greenhouse_id):
                    await self.channel_layer.group_send(
                        group_name,
                        {
                            "type": "ws_message",
                            "event_type": "mode",
                            "data": {"value": mode_value},
                        },
                    )

                await self.send_state({"packet": await build_state_packet(self.greenhouse_id)})
                return

            if msg_type == "device_control":
                device = str(payload.get("device") or "").strip().lower()
                state = str(payload.get("state") or "").strip().lower()

                if device not in {"fan", "pump", "light", "mist"} or state not in {"on", "off"}:
                    raise ValueError("invalid device_control")

                await queue_manual_command(self.greenhouse_id, device, state)

                commands = await pending_commands(self.greenhouse_id)
                for group_name in await controller_group_names(self.greenhouse_id):
                    await self.channel_layer.group_send(
                        group_name,
                        {
                            "type": "ws_message",
                            "event_type": "pending_commands",
                            "data": {"commands": commands},
                        },
                    )

                await self.send_state({"packet": await build_state_packet(self.greenhouse_id)})
                return

            if msg_type in {"alert_mark_read", "alert_mark_all_read"}:
                return

            await self.send(text_data=json.dumps({"type": "error", "reason": f"unsupported:{msg_type}"}))

        except Exception as exc:
            await self.send(text_data=json.dumps({"type": "error", "reason": str(exc)}))
            await self.send_state({"packet": await build_state_packet(self.greenhouse_id)})

    async def send_state(self, event):
        packet = event["packet"]
        self.last_esp32_online = packet.get("data", {}).get("esp32_online")
        await self.send(text_data=json.dumps(packet, cls=DjangoJSONEncoder))

    async def monitor_status_changes(self):
        try:
            while True:
                await asyncio.sleep(FRONTEND_POLL_SECONDS)

                packet = await build_state_packet(self.greenhouse_id)
                current_online = packet["data"].get("esp32_online")

                if current_online != self.last_esp32_online:
                    self.last_esp32_online = current_online
                    await self.send(text_data=json.dumps(packet, cls=DjangoJSONEncoder))
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

        device = await auth_device(self.device_code, token)
        if device is None:
            await self.close(code=4003)
            return

        self.device_id = device["id"]
        self.device_code = device["code"]
        self.greenhouse_id = device["greenhouse_id"]
        self.group_name = _esp_group(self.device_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send_pending_commands()
        await self.push_state_to_frontend()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if hasattr(self, "greenhouse_id"):
            await mark_connected_device_offline(self.device_code, self.greenhouse_id)
            await self.push_state_to_frontend()

    async def receive(self, text_data):
        try:
            packet = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "invalid_json"}))
            return

        msg_type = packet.get("type")
        data = packet.get("data") or {}

        try:
            if msg_type == "telemetry":
                await ingest_telemetry(data, self.device_id)
                await self.push_state_to_frontend()
                return

            if msg_type == "heartbeat":
                await ingest_heartbeat(data, self.device_id)
                return

            if msg_type == "ack":
                cmd = await ack_command(data, self.greenhouse_id)
                if cmd is None:
                    await self.send(text_data=json.dumps({"type": "error", "message": "command_not_found"}))
                return

            if msg_type == "sync_commands":
                await self.send_pending_commands()
                return

            await self.send(text_data=json.dumps({"type": "error", "message": f"unsupported_type:{msg_type}"}))

        except Exception as exc:
            await self.send(text_data=json.dumps({"type": "error", "message": str(exc)}))

    async def send_pending_commands(self):
        commands = await pending_commands(self.greenhouse_id)
        await self.send(text_data=json.dumps({"type": "pending_commands", "data": {"commands": commands}}))

    async def push_state_to_frontend(self):
        packet = await build_state_packet(self.greenhouse_id)
        await self.channel_layer.group_send(
            _frontend_group(self.greenhouse_id),
            {
                "type": "send_state",
                "packet": packet,
            },
        )

    async def ws_message(self, event):
        await self.send(text_data=json.dumps({"type": event["event_type"], "data": event["data"]}))
