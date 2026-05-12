from __future__ import annotations

from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from .models import Alert, ControlState, Device, DeviceCommand, DeviceState, Greenhouse, SensorData
from .serializers import (
    COMMAND_STATUS_VALUES,
    DEVICE_COMMAND_TEXT_MAX_LENGTH,
    DEVICE_FIRMWARE_MAX_LENGTH,
    KNOWN_SENSOR_ERROR_KEYS,
    MANUAL_REASON_MAX_LENGTH,
    DeviceCommandSerializer,
    validate_json_finite,
    validate_sensor_numeric_fields,
)


HEARTBEAT_TIMEOUT_SECONDS = 15
HEARTBEAT_SLOW_SECONDS = 30


def _clean_limited_text(field: str, value, max_length: int) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if len(text) > max_length:
        raise ValidationError({field: f'{field} must be at most {max_length} characters'})
    return text


def _clean_sensor_errors(value) -> dict:
    if value in (None, ''):
        return {}
    if not isinstance(value, dict):
        raise ValidationError({'sensor_errors': 'sensor_errors must be an object'})

    unknown = sorted(str(key) for key in value.keys() if str(key) not in KNOWN_SENSOR_ERROR_KEYS)
    if unknown:
        raise ValidationError({
            'sensor_errors': f"sensor_errors only supports keys: {', '.join(sorted(KNOWN_SENSOR_ERROR_KEYS))}"
        })
    return validate_json_finite(value, 'sensor_errors')


def get_controller(device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None) -> Device:
    queryset = Device.objects.filter(code=device_code)
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    existing = queryset.first()
    if existing is not None:
        return existing

    if greenhouse is not None:
        legacy = Device.objects.filter(code=device_code, greenhouse__isnull=True).first()
        if legacy is not None:
            legacy.greenhouse = greenhouse
            legacy.save(update_fields=['greenhouse', 'updated_at'])
            return legacy

    lookup = {'code': device_code}
    if greenhouse is not None:
        lookup['greenhouse'] = greenhouse

    controller, _ = Device.objects.get_or_create(
        **lookup,
        defaults={
            'name': 'ESP32 Main',
            'device_type': Device.DeviceType.CONTROLLER,
            'status': Device.DeviceStatus.OFFLINE,
        },
    )
    return controller


def sync_device_online(device: Device, firmware_version: str | None = None, metadata: dict | None = None):
    previous_status = device.status
    now = timezone.now()

    device.status = Device.DeviceStatus.ONLINE
    device.last_seen_at = now

    update_fields = ['status', 'last_seen_at', 'updated_at']

    firmware_version = _clean_limited_text(
        'firmware_version',
        firmware_version,
        DEVICE_FIRMWARE_MAX_LENGTH,
    )
    if firmware_version:
        device.firmware_version = firmware_version
        update_fields.append('firmware_version')

    if metadata:
        metadata = validate_json_finite(metadata, 'metadata')
        device.metadata = {**device.metadata, **metadata}
        update_fields.append('metadata')

    device.save(update_fields=update_fields)

    if previous_status != Device.DeviceStatus.ONLINE:
        Alert.objects.create(
            level=Alert.Level.SUCCESS,
            title=f'{device.name} online',
            message=f'{device.name} is back online.',
            device=device,
        )


def mark_device_offline(device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None):
    queryset = Device.objects.filter(code=device_code)
    if greenhouse is not None:
        queryset = queryset.filter(greenhouse=greenhouse)
    device = queryset.first()
    if not device:
        return

    if device.status != Device.DeviceStatus.OFFLINE:
        device.status = Device.DeviceStatus.OFFLINE
        device.save(update_fields=['status', 'updated_at'])
        Alert.objects.create(
            level=Alert.Level.ERROR,
            title=f'{device.name} offline',
            message=f'WebSocket connection from {device.name} disconnected.',
            device=device,
        )


def refresh_device_statuses(now=None, *, greenhouse: Greenhouse | None = None):
    now = now or timezone.now()
    timeout = timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)

    devices = Device.objects.all()
    if greenhouse is not None:
        devices = devices.filter(greenhouse=greenhouse)

    for device in devices:
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
                title=f'{device.name} offline',
                message=f'No heartbeat from {device.name} for more than {HEARTBEAT_TIMEOUT_SECONDS} seconds.',
                device=device,
            )
        elif previous_status != Device.DeviceStatus.ONLINE and new_status == Device.DeviceStatus.ONLINE:
            Alert.objects.create(
                level=Alert.Level.SUCCESS,
                title=f'{device.name} online',
                message=f'{device.name} is back online.',
                device=device,
            )


def build_uptime_hint(greenhouse: Greenhouse | None = None) -> str:
    refresh_device_statuses(greenhouse=greenhouse)

    controllers = Device.objects.filter(device_type=Device.DeviceType.CONTROLLER)
    if greenhouse is not None:
        controllers = controllers.filter(greenhouse=greenhouse)
    controller = controllers.first()
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


def _push_ws_group(group_name: str, event_type: str, data: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'ws_message',
            'event_type': event_type,
            'data': data,
        },
    )


def get_pending_commands(
    limit: int = 5,
    *,
    device: Device | None = None,
    greenhouse: Greenhouse | None = None,
):
    queryset = (
        DeviceCommand.objects
        .filter(status=DeviceCommand.CommandStatus.PENDING)
        .select_related('device')
    )
    if device is not None and device.device_type != Device.DeviceType.CONTROLLER:
        queryset = queryset.filter(device=device)
    elif greenhouse is not None:
        queryset = queryset.filter(device__greenhouse=greenhouse)

    commands = queryset.order_by('-updated_at', '-id')[:limit]
    return DeviceCommandSerializer(list(reversed(commands)), many=True).data


def notify_pending_commands(device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None):
    data = {'commands': get_pending_commands(greenhouse=greenhouse)}
    controllers = Device.objects.filter(device_type=Device.DeviceType.CONTROLLER)
    if greenhouse is not None:
        controllers = controllers.filter(greenhouse=greenhouse)

    delivered = False
    for controller in controllers:
        _push_ws_group(f'esp32.device.{controller.id}', 'pending_commands', data)
        delivered = True

    if not delivered:
        _push_ws_group(f'esp32.{device_code}', 'pending_commands', data)


def _force_manual_mode(reason: str, *, greenhouse: Greenhouse | None = None):
    reason = _clean_limited_text('manual_reason', reason, MANUAL_REASON_MAX_LENGTH)
    if greenhouse is None:
        control, _ = ControlState.objects.get_or_create(singleton_key='main')
    else:
        control, _ = ControlState.objects.get_or_create(
            greenhouse=greenhouse,
            defaults={'singleton_key': ControlState.singleton_key_for_greenhouse(greenhouse.id)},
        )

    if control.mode == ControlState.Mode.MANUAL and control.manual_reason == reason:
        return control

    control.mode = ControlState.Mode.MANUAL
    control.manual_reason = reason
    control.manual_changed_at = timezone.now()
    control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])
    return control


def sync_control_mode_from_payload(payload: dict, *, greenhouse: Greenhouse | None = None):
    if greenhouse is None:
        control, _ = ControlState.objects.get_or_create(singleton_key='main')
    else:
        control, _ = ControlState.objects.get_or_create(
            greenhouse=greenhouse,
            defaults={'singleton_key': ControlState.singleton_key_for_greenhouse(greenhouse.id)},
        )

    sensor_errors = _clean_sensor_errors(payload.get('sensor_errors'))
    if bool(sensor_errors.get('dht', False)):
        return _force_manual_mode('dht_sensor_error', greenhouse=greenhouse)

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
            control.manual_reason = _clean_limited_text(
                'manual_reason',
                payload.get('manual_reason') or 'esp_button_mode',
                MANUAL_REASON_MAX_LENGTH,
            )
            control.manual_changed_at = timezone.now()
            control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])

    return control


def sync_sensor_alerts(payload: dict, device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None):
    controller = get_controller(device_code=device_code, greenhouse=greenhouse)
    metadata = controller.metadata or {}

    previous_errors = metadata.get('sensor_errors') or {}
    current_errors = _clean_sensor_errors(payload.get('sensor_errors'))

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
                title=f'{sensor_name} sensor error',
                message=f'{sensor_name} sensor on {controller.name} is missing data or returning invalid values.',
                device=controller,
            )
        else:
            Alert.objects.create(
                level=Alert.Level.SUCCESS,
                title=f'{sensor_name} sensor recovered',
                message=f'{sensor_name} sensor on {controller.name} has recovered.',
                device=controller,
            )

    if bool(current_errors.get('dht', False)):
        _force_manual_mode('dht_sensor_error', greenhouse=greenhouse)

    if changed:
        metadata['sensor_errors'] = current_errors
        controller.metadata = metadata
        controller.save(update_fields=['metadata', 'updated_at'])


def ingest_sensor_payload(payload: dict, device_code: str = 'esp32-main', *, greenhouse: Greenhouse | None = None):
    validate_sensor_numeric_fields(payload)
    sensor_payload = validate_json_finite(payload.get('payload') or {}, 'payload')
    metadata = validate_json_finite(payload.get('metadata') or {}, 'metadata')
    sensor_errors = _clean_sensor_errors(payload.get('sensor_errors'))
    device_states = validate_json_finite(payload.get('device_states') or {}, 'device_states')
    firmware_version = _clean_limited_text(
        'firmware_version',
        payload.get('firmware_version'),
        DEVICE_FIRMWARE_MAX_LENGTH,
    )
    manual_reason = _clean_limited_text(
        'manual_reason',
        payload.get('manual_reason'),
        MANUAL_REASON_MAX_LENGTH,
    )
    payload = {**payload}
    payload['payload'] = sensor_payload
    payload['metadata'] = metadata
    payload['sensor_errors'] = sensor_errors
    payload['device_states'] = device_states
    if firmware_version:
        payload['firmware_version'] = firmware_version
    if manual_reason:
        payload['manual_reason'] = manual_reason

    recorded_raw = payload.get('recorded_at')
    recorded_at = parse_datetime(recorded_raw) if isinstance(recorded_raw, str) else recorded_raw
    recorded_at = recorded_at or timezone.now()

    reading = SensorData.objects.create(
        greenhouse=greenhouse,
        temperature=payload.get('temperature'),
        humidity=payload.get('humidity'),
        light=payload.get('light'),
        soil_moisture=payload.get('soil_moisture'),
        payload=sensor_payload,
        recorded_at=recorded_at,
    )

    controller = get_controller(device_code=device_code, greenhouse=greenhouse)
    metadata = {**metadata, 'transport': 'websocket'}
    sync_device_online(
        controller,
        firmware_version=payload.get('firmware_version'),
        metadata=metadata,
    )

    sync_control_mode_from_payload(payload, greenhouse=greenhouse)
    sync_sensor_alerts(payload, device_code=device_code, greenhouse=greenhouse)

    states = device_states
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
    metadata = validate_json_finite(payload.get('metadata') or {}, 'metadata')
    sensor_errors = _clean_sensor_errors(payload.get('sensor_errors'))
    firmware_version = _clean_limited_text(
        'firmware_version',
        payload.get('firmware_version'),
        DEVICE_FIRMWARE_MAX_LENGTH,
    )
    manual_reason = _clean_limited_text(
        'manual_reason',
        payload.get('manual_reason'),
        MANUAL_REASON_MAX_LENGTH,
    )
    payload = {**payload}
    payload['metadata'] = metadata
    payload['sensor_errors'] = sensor_errors
    if firmware_version:
        payload['firmware_version'] = firmware_version
    if manual_reason:
        payload['manual_reason'] = manual_reason

    controller = get_controller(device_code=device_code, greenhouse=greenhouse)
    metadata = {**metadata, 'uptime_ms': payload.get('uptime_ms'), 'free_heap': payload.get('free_heap')}
    metadata = validate_json_finite(metadata, 'metadata')
    sync_device_online(
        controller,
        firmware_version=firmware_version,
        metadata=metadata,
    )

    sync_control_mode_from_payload(payload, greenhouse=greenhouse)
    return controller


def enqueue_device_command(device: Device, command: str, value: str = '', payload: dict | None = None):
    command = _clean_limited_text('command', command, DEVICE_COMMAND_TEXT_MAX_LENGTH)
    value = _clean_limited_text('value', value, DEVICE_COMMAND_TEXT_MAX_LENGTH)
    payload = validate_json_finite(payload or {}, 'payload')
    cmd = DeviceCommand.objects.create(
        device=device,
        command=command,
        value=value,
        payload=payload,
    )
    return cmd


def ack_device_command_payload(
    payload: dict,
    *,
    device: Device | None = None,
    greenhouse: Greenhouse | None = None,
):
    command_id = payload.get('id') or payload.get('command_id')
    if not command_id:
        return None

    queryset = DeviceCommand.objects.select_related('device')
    if device is not None and device.device_type != Device.DeviceType.CONTROLLER:
        queryset = queryset.filter(device=device)
    elif greenhouse is not None:
        queryset = queryset.filter(device__greenhouse=greenhouse)

    try:
        cmd = queryset.get(pk=command_id)
    except DeviceCommand.DoesNotExist:
        return None

    next_status = payload.get('status') or DeviceCommand.CommandStatus.ACK
    if next_status not in COMMAND_STATUS_VALUES:
        raise ValidationError({'status': f"status must be one of: {', '.join(COMMAND_STATUS_VALUES)}"})

    cmd.status = next_status
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

    cmd.device.status = Device.DeviceStatus.ONLINE
    cmd.device.last_seen_at = timezone.now()
    cmd.device.save(update_fields=['status', 'last_seen_at', 'updated_at'])

    return cmd
