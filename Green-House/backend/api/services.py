from __future__ import annotations

from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Alert, ControlState, Device, DeviceCommand, DeviceState, Greenhouse, SensorData
from .serializers import DeviceCommandSerializer


HEARTBEAT_TIMEOUT_SECONDS = 15
HEARTBEAT_SLOW_SECONDS = 30


def get_controller(device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None) -> Device:
    queryset = Device.objects.filter(code=device_code)
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    existing = queryset.first()
    if existing is not None:
        return existing

    controller, _ = Device.objects.get_or_create(
        code=device_code,
        defaults={
            'name': 'ESP32 Main',
            'greenhouse': greenhouse,
            'device_type': Device.DeviceType.CONTROLLER,
            'status': Device.DeviceStatus.OFFLINE,
        },
    )
    if greenhouse is not None and controller.greenhouse_id is None:
        controller.greenhouse = greenhouse
        controller.save(update_fields=['greenhouse', 'updated_at'])
    return controller


def sync_device_online(device: Device, firmware_version: str | None = None, metadata: dict | None = None):
    previous_status = device.status
    now = timezone.now()

    device.status = Device.DeviceStatus.ONLINE
    device.last_seen_at = now

    update_fields = ['status', 'last_seen_at', 'updated_at']

    if firmware_version:
        device.firmware_version = firmware_version
        update_fields.append('firmware_version')

    if metadata:
        device.metadata = {**device.metadata, **metadata}
        update_fields.append('metadata')

    device.save(update_fields=update_fields)

    if previous_status != Device.DeviceStatus.ONLINE:
        Alert.objects.create(
            level=Alert.Level.SUCCESS,
            title=f'{device.name} online',
            message=f'{device.name} đã kết nối lại hệ thống.',
            device=device,
        )


def mark_device_offline(device_code: str = 'esp32-main'):
    device = Device.objects.filter(code=device_code).first()
    if not device:
        return

    if device.status != Device.DeviceStatus.OFFLINE:
        device.status = Device.DeviceStatus.OFFLINE
        device.save(update_fields=['status', 'updated_at'])
        Alert.objects.create(
            level=Alert.Level.ERROR,
            title=f'{device.name} mất kết nối',
            message=f'Kết nối WebSocket từ {device.name} đã ngắt.',
            device=device,
        )


def refresh_device_statuses(now=None):
    now = now or timezone.now()
    timeout = timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)

    for device in Device.objects.all():
        previous_status = device.status

        if not device.last_seen_at:
            new_status = Device.DeviceStatus.OFFLINE
        elif now - device.last_seen_at > timeout:
            new_status = Device.DeviceStatus.OFFLINE
        else:
            new_status = Device.DeviceStatus.ONLINE

        if new_status == previous_status:
            continue

        device.status = new_status
        device.save(update_fields=['status', 'updated_at'])

        if previous_status == Device.DeviceStatus.ONLINE and new_status == Device.DeviceStatus.OFFLINE:
            Alert.objects.create(
                level=Alert.Level.ERROR,
                title=f'{device.name} mất kết nối',
                message=f'Không nhận heartbeat từ {device.name} trong hơn {HEARTBEAT_TIMEOUT_SECONDS} giây.',
                device=device,
            )
        elif previous_status != Device.DeviceStatus.ONLINE and new_status == Device.DeviceStatus.ONLINE:
            Alert.objects.create(
                level=Alert.Level.SUCCESS,
                title=f'{device.name} online',
                message=f'{device.name} đã kết nối lại hệ thống.',
                device=device,
            )


def build_uptime_hint() -> str:
    refresh_device_statuses()

    controller = Device.objects.filter(device_type=Device.DeviceType.CONTROLLER).first()
    if not controller or not controller.last_seen_at:
        return 'Chưa có heartbeat từ ESP32'

    delta = timezone.now() - controller.last_seen_at

    if delta <= timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS):
        return 'ESP32 đang online'
    if delta <= timedelta(seconds=HEARTBEAT_SLOW_SECONDS):
        return 'ESP32 phản hồi chậm'
    return 'ESP32 đang mất kết nối'


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {'1', 'true', 'on', 'yes'}


def _push_ws_message(device_code: str, event_type: str, data: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f'esp32.{device_code}',
        {
            'type': 'ws_message',
            'event_type': event_type,
            'data': data,
        },
    )


def get_pending_commands(limit: int = 5):
    commands = (
        DeviceCommand.objects
        .filter(status=DeviceCommand.CommandStatus.PENDING)
        .select_related('device')
        .order_by('-updated_at', '-id')[:limit]
    )
    return DeviceCommandSerializer(list(reversed(commands)), many=True).data


def notify_pending_commands(device_code: str = 'esp32-main'):
    _push_ws_message(
        device_code=device_code,
        event_type='pending_commands',
        data={'commands': get_pending_commands()},
    )


def _force_manual_mode(reason: str):
    control, _ = ControlState.objects.get_or_create(singleton_key='main')

    if control.mode == ControlState.Mode.MANUAL and control.manual_reason == reason:
        return control

    control.mode = ControlState.Mode.MANUAL
    control.manual_reason = reason
    control.manual_changed_at = timezone.now()
    control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])
    return control


def sync_control_mode_from_payload(payload: dict):
    control, _ = ControlState.objects.get_or_create(singleton_key='main')

    sensor_errors = payload.get('sensor_errors') or {}
    if isinstance(sensor_errors, dict) and bool(sensor_errors.get('dht', False)):
        return _force_manual_mode('dht_sensor_error')

    mode = payload.get('mode')
    auto_mode = payload.get('auto_mode')

    resolved_mode = None

    if isinstance(mode, str):
        mode = mode.strip().upper()
        if mode in {ControlState.Mode.AUTO, ControlState.Mode.MANUAL}:
            resolved_mode = mode

    if resolved_mode is None and auto_mode is not None:
        resolved_mode = ControlState.Mode.AUTO if _to_bool(auto_mode) else ControlState.Mode.MANUAL

    if resolved_mode is None:
        return control

    if control.mode != resolved_mode:
        control.mode = resolved_mode

        if resolved_mode == ControlState.Mode.AUTO:
            control.manual_reason = ''
            control.manual_changed_at = None
            control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])
        else:
            control.manual_reason = payload.get('manual_reason') or 'esp_button_mode'
            control.manual_changed_at = timezone.now()
            control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])

    return control


def sync_sensor_alerts(payload: dict, device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None):
    controller = get_controller(device_code=device_code, greenhouse=greenhouse)
    metadata = controller.metadata or {}

    previous_errors = metadata.get('sensor_errors') or {}
    current_errors = payload.get('sensor_errors') or {}

    if not isinstance(current_errors, dict):
        return

    sensor_titles = {
        'dht': 'Cảm biến DHT lỗi',
        'soil': 'Cảm biến độ ẩm đất lỗi',
        'light': 'Cảm biến ánh sáng lỗi',
        'gas': 'Cảm biến khí lỗi',
    }

    changed = False

    for sensor_name, current_value in current_errors.items():
        current_value = bool(current_value)
        previous_value = bool(previous_errors.get(sensor_name, False))

        if current_value == previous_value:
            continue

        changed = True

        if current_value:
            Alert.objects.create(
                level=Alert.Level.ERROR,
                title=sensor_titles.get(sensor_name, f'Cảm biến {sensor_name} lỗi'),
                message=f'{sensor_titles.get(sensor_name, sensor_name)} trên {controller.name} đang mất dữ liệu hoặc trả giá trị bất thường.',
                device=controller,
            )
        else:
            Alert.objects.create(
                level=Alert.Level.SUCCESS,
                title=f'{sensor_titles.get(sensor_name, sensor_name)} đã hồi phục',
                message=f'Cảm biến {sensor_name} trên {controller.name} đã hoạt động lại bình thường.',
                device=controller,
            )

    if bool(current_errors.get('dht', False)):
        _force_manual_mode('dht_sensor_error')

    if changed:
        metadata['sensor_errors'] = current_errors
        controller.metadata = metadata
        controller.save(update_fields=['metadata', 'updated_at'])


def ingest_sensor_payload(payload: dict, device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None):
    recorded_raw = payload.get('recorded_at')
    recorded_at = parse_datetime(recorded_raw) if isinstance(recorded_raw, str) else recorded_raw
    recorded_at = recorded_at or timezone.now()

    reading = SensorData.objects.create(
        greenhouse=greenhouse,
        temperature=payload.get('temperature'),
        humidity=payload.get('humidity'),
        light=payload.get('light'),
        soil_moisture=payload.get('soil_moisture'),
        payload=payload.get('payload') or {},
        recorded_at=recorded_at,
    )

    controller = get_controller(device_code=device_code, greenhouse=greenhouse)
    metadata = payload.get('metadata') or {}
    metadata = {**metadata, 'transport': 'websocket'}
    sync_device_online(
        controller,
        firmware_version=payload.get('firmware_version'),
        metadata=metadata,
    )

    sync_control_mode_from_payload(payload)
    sync_sensor_alerts(payload, device_code=device_code, greenhouse=greenhouse)

    states = payload.get('device_states') or {}
    state_map = {'fan_on': 'fan', 'pump_on': 'pump', 'light_on': 'light'}

    for field_name, device_type in state_map.items():
        if field_name not in states:
            continue

        devices = Device.objects.filter(device_type=device_type)
        if greenhouse is not None:
            devices = devices.filter(greenhouse=greenhouse)
        device = devices.first()
        if not device:
            continue

        sync_device_online(device)

        current_value = _to_bool(states[field_name])

        state, _ = DeviceState.objects.get_or_create(device=device)
        state.is_on = current_value
        state.desired_on = current_value
        state.last_command = 'telemetry_sync'
        state.last_value = 'on' if current_value else 'off'
        state.save(update_fields=['is_on', 'desired_on', 'last_command', 'last_value', 'updated_at'])

    return reading


def ingest_heartbeat_payload(payload: dict, device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None):
    controller = get_controller(device_code=device_code, greenhouse=greenhouse)
    metadata = payload.get('metadata') or {}
    metadata = {**metadata, 'uptime_ms': payload.get('uptime_ms'), 'free_heap': payload.get('free_heap')}
    sync_device_online(
        controller,
        firmware_version=payload.get('firmware_version'),
        metadata=metadata,
    )

    sync_control_mode_from_payload(payload)
    return controller


def enqueue_device_command(device: Device, command: str, value: str = '', payload: dict | None = None):
    cmd = DeviceCommand.objects.create(
        device=device,
        command=command,
        value=value,
        payload=payload or {},
    )
    return cmd


def ack_device_command_payload(payload: dict):
    command_id = payload.get('id') or payload.get('command_id')
    if not command_id:
        return None

    try:
        cmd = DeviceCommand.objects.select_related('device').get(pk=command_id)
    except DeviceCommand.DoesNotExist:
        return None

    cmd.status = payload.get('status') or DeviceCommand.CommandStatus.ACK
    cmd.acked_at = timezone.now()
    cmd.save(update_fields=['status', 'acked_at', 'updated_at'])

    state, _ = DeviceState.objects.get_or_create(device=cmd.device)

    actual_state = payload.get('actual_state')
    if actual_state is not None:
        actual_on = _to_bool(actual_state)
        state.is_on = actual_on
    else:
        actual_on = str(cmd.value).lower() == 'on'
        state.is_on = actual_on

    state.desired_on = actual_on
    state.last_command = cmd.command
    state.last_value = cmd.value
    state.save(update_fields=['is_on', 'desired_on', 'last_command', 'last_value', 'updated_at'])

    return cmd
