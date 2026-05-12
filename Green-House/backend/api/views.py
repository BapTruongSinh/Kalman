from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (
    Alert,
    ControlState,
    Device,
    DeviceCommand,
    DeviceState,
    EstimationCycle,
    EvaluationSummary,
    ExperimentRun,
    Greenhouse,
    SensorData,
)
from .serializers import (
    AMPCRecommendationSerializer,
    AMPCSchedulerStateSerializer,
    AlertSerializer,
    ControlModeInputSerializer,
    ControlStateSerializer,
    DeviceCommandAckInputSerializer,
    DeviceCommandInputSerializer,
    DeviceCommandSerializer,
    DeviceSerializer,
    EstimationCycleSerializer,
    CycleSerializer,
    EvaluationSummarySerializer,
    GreenhouseControlProfileSerializer,
    IngestHeartbeatSerializer,
    IngestReadingSerializer,
    LegacyAMPCRecommendationSerializer,
    LiveSampleSerializer,
    LoginSerializer,
    RunListSerializer,
    SensorDataSerializer,
)
from .ampc import (
    default_greenhouse,
    get_greenhouse_control_profile,
    get_greenhouse_for_user,
    latest_recommendation_for_greenhouse,
    run_auto_recommendation,
)
from .ampc_scheduler import (
    get_scheduler_state,
    run_due_once,
    start_scheduler,
    stop_scheduler,
)
from .estimation import ensure_estimation_for_reading, latest_estimation
from .services import (
    ack_device_command_payload,
    build_uptime_hint,
    enqueue_device_command,
    get_pending_commands,
    ingest_heartbeat_payload,
    ingest_sensor_payload,
    notify_pending_commands,
    refresh_device_statuses,
)


def _check_ingest_token(request):
    header = request.headers.get('X-Device-Token') or ''
    auth = request.headers.get('Authorization') or ''
    bearer = auth.replace('Bearer ', '') if auth.startswith('Bearer ') else ''
    token = header or bearer

    if not token:
        raise PermissionDenied('Thiếu X-Device-Token cho ESP32')

    device = Device.objects.select_related('greenhouse').filter(api_token=token, is_enabled=True).first()
    if device is not None:
        return device

    if token == settings.INGEST_DEVICE_TOKEN:
        return None

    raise PermissionDenied('Sai X-Device-Token cho ESP32')


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {'1', 'true', 'on', 'yes'}


def _legacy_auto_settings_payload(profile):
    return {
        'crop_name': profile.crop_name,
        'crop_kc': profile.crop_kc,
        'latitude': profile.latitude,
        'longitude': profile.longitude,
        'soil_type': profile.soil_type,
        'theta_fc': profile.theta_fc,
        'theta_wp': profile.theta_wp,
        'theta_sat': profile.theta_sat,
        'root_depth_m': profile.root_depth_m,
        'depletion_fraction_p': profile.depletion_fraction_p,
        'pump_efficiency': profile.pump_efficiency,
        'pump_flow_lps': profile.pump_flow_lps,
        'irrigation_area_m2': profile.irrigation_area_m2,
        'target_low': profile.target_low,
        'target_high': profile.target_high,
        'step_seconds': profile.step_seconds,
        'horizon_steps': profile.horizon_steps,
        'pump_min_seconds': profile.pump_min_seconds,
        'pump_max_seconds': profile.pump_max_seconds,
        'pump_grid_seconds': profile.pump_grid_seconds,
        'soft_daily_pump_cap_seconds': profile.soft_daily_pump_cap_seconds,
        'weight_band': profile.cost_band_violation,
        'weight_water': profile.cost_water_use,
        'weight_switch': profile.cost_switching,
        'weight_daily': profile.cost_daily_cap_excess,
        'weight_terminal': profile.cost_terminal_band_violation,
        'adaptive_enabled': profile.adaptive_enabled,
        'adaptive_bias_window': profile.adaptive_bias_window,
        'adaptive_max_abs_bias': profile.adaptive_max_abs_bias,
        'stale_after_seconds': profile.safety_stale_after_seconds,
        'actuator_enabled': profile.actuator_enabled,
        'updated_at': profile.updated_at,
    }


def _legacy_auto_settings_patch(data) -> dict:
    mapping = {
        'weight_band': 'cost_band_violation',
        'weight_water': 'cost_water_use',
        'weight_switch': 'cost_switching',
        'weight_daily': 'cost_daily_cap_excess',
        'weight_terminal': 'cost_terminal_band_violation',
        'stale_after_seconds': 'safety_stale_after_seconds',
    }
    allowed = {
        'crop_name',
        'crop_kc',
        'latitude',
        'longitude',
        'soil_type',
        'theta_fc',
        'theta_wp',
        'theta_sat',
        'root_depth_m',
        'depletion_fraction_p',
        'pump_efficiency',
        'pump_flow_lps',
        'irrigation_area_m2',
        'target_low',
        'target_high',
        'step_seconds',
        'horizon_steps',
        'pump_min_seconds',
        'pump_max_seconds',
        'pump_grid_seconds',
        'soft_daily_pump_cap_seconds',
        'adaptive_enabled',
        'adaptive_bias_window',
        'adaptive_max_abs_bias',
        'actuator_enabled',
    }
    patch = {}
    for key, value in data.items():
        if key in mapping:
            patch[mapping[key]] = value
        elif key in allowed:
            patch[key] = value
    return patch


def _get_control_state(greenhouse: Greenhouse | None = None):
    if greenhouse is None:
        control, _ = ControlState.objects.get_or_create(singleton_key='main')
        return control
    control, _ = ControlState.objects.get_or_create(
        greenhouse=greenhouse,
        defaults={'singleton_key': ControlState.singleton_key_for_greenhouse(greenhouse.id)},
    )
    return control


def _turn_off_all_actuators(greenhouse: Greenhouse):
    actuators = Device.objects.filter(greenhouse=greenhouse).exclude(device_type=Device.DeviceType.CONTROLLER)

    for device in actuators:
        state, _ = DeviceState.objects.get_or_create(device=device)
        state.desired_on = False
        state.last_command = 'set_power'
        state.last_value = 'off'
        state.save(update_fields=['desired_on', 'last_command', 'last_value', 'updated_at'])

        DeviceCommand.objects.create(
            device=device,
            command='set_power',
            value='off',
            payload={'source': 'auto_mode_enable'},
        )

    notify_pending_commands(greenhouse=greenhouse)


def _esp32_online(greenhouse: Greenhouse) -> bool:
    refresh_device_statuses(greenhouse=greenhouse)
    return Device.objects.filter(
        greenhouse=greenhouse,
        device_type=Device.DeviceType.CONTROLLER,
        status=Device.DeviceStatus.ONLINE,
    ).exists()


def _alert_queryset(greenhouse: Greenhouse):
    return Alert.objects.filter(
        Q(sensor_data__greenhouse=greenhouse) | Q(device__greenhouse=greenhouse)
    )


def _forecast_reading_from_estimation(cycle: EstimationCycle) -> dict:
    return {
        'id': cycle.id,
        'temperature': cycle.raw_temperature,
        'humidity': cycle.raw_humidity,
        'light': cycle.raw_light,
        'soil_moisture': cycle.raw_soil_moisture,
        'payload': {
            'source': 'estimation_cycle',
            'cycle_index': cycle.cycle_index,
            'kf_x_posterior': cycle.kf_x_posterior,
        },
        'recorded_at': cycle.sample_ts,
    }


def _forecast_latest_and_history(greenhouse: Greenhouse, estimation: EstimationCycle | None):
    latest_sensor = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id').first()
    use_estimation_history = (
        estimation is not None
        and (
            latest_sensor is None
            or estimation.sample_ts > latest_sensor.recorded_at
        )
    )

    if use_estimation_history:
        cycles = (
            EstimationCycle.objects
            .filter(greenhouse=greenhouse)
            .exclude(raw_soil_moisture__isnull=True)
            .exclude(raw_temperature__isnull=True)
            .exclude(raw_humidity__isnull=True)
            .exclude(raw_light__isnull=True)
            .order_by('-sample_ts', '-id')[:6]
        )
        history = [_forecast_reading_from_estimation(item) for item in reversed(list(cycles))]
        return _forecast_reading_from_estimation(estimation), history

    history_rows = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id')[:6]
    history = [
        SensorDataSerializer(item).data
        for item in reversed(list(history_rows))
    ]
    return SensorDataSerializer(latest_sensor).data if latest_sensor else None, history


def _ingest_greenhouse(request, auth_device: Device | None) -> Greenhouse:
    greenhouse_id = request.data.get('greenhouse_id') or request.query_params.get('greenhouse_id')

    if auth_device is not None and auth_device.greenhouse_id is not None:
        if greenhouse_id is not None:
            try:
                requested_greenhouse_id = int(greenhouse_id)
            except (TypeError, ValueError):
                raise ValidationError({'greenhouse_id': 'greenhouse_id không hợp lệ'})
            if requested_greenhouse_id != auth_device.greenhouse_id:
                raise PermissionDenied('Device token không thuộc greenhouse được yêu cầu')
        return auth_device.greenhouse

    if greenhouse_id is not None:
        return generics.get_object_or_404(Greenhouse, pk=greenhouse_id, is_active=True)

    return default_greenhouse()


def _require_controller_token(device: Device | None) -> None:
    if device is not None and device.device_type != Device.DeviceType.CONTROLLER:
        raise PermissionDenied('Endpoint ingest telemetry yêu cầu controller token')


def _query_int(request, name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw_value = request.query_params.get(name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValidationError({name: f'{name} must be an integer'})
    return min(max(value, min_value), max_value)


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer


class DashboardOverviewView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        refresh_device_statuses(greenhouse=greenhouse)

        esp32_online = _esp32_online(greenhouse)
        latest = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id').first() if esp32_online else None
        recent_alerts = _alert_queryset(greenhouse).order_by('-happened_at', '-id')[:5]
        control = _get_control_state(greenhouse)
        devices = Device.objects.filter(greenhouse=greenhouse)

        payload = {
            'latest': SensorDataSerializer(latest).data if latest else None,
            'control': ControlStateSerializer(control).data,
            'device_count': devices.exclude(device_type=Device.DeviceType.CONTROLLER).count(),
            'online_devices': devices.exclude(device_type=Device.DeviceType.CONTROLLER).filter(
                status=Device.DeviceStatus.ONLINE
            ).count(),
            'unread_alerts': _alert_queryset(greenhouse).filter(is_read=False).count(),
            'uptime_hint': build_uptime_hint(greenhouse),
            'recent_alerts': AlertSerializer(recent_alerts, many=True).data,
            'esp32_online': esp32_online,
        }
        return Response(payload)


class LatestReadingView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        esp32_online = _esp32_online(greenhouse)
        if not esp32_online:
            return Response(None)

        latest = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id').first()
        if not latest:
            return Response(None)
        return Response(SensorDataSerializer(latest).data)


class ChartView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        metric = request.query_params.get('metric')
        hours = _query_int(request, 'hours', 24, min_value=1, max_value=24 * 30)

        if metric not in {'temperature', 'humidity', 'light', 'soil_moisture'}:
            raise ValidationError('metric không hợp lệ')

        esp32_online = _esp32_online(greenhouse)
        if not esp32_online:
            return Response({
                'metric': metric,
                'points': [],
            })

        since = timezone.now() - timedelta(hours=hours)
        points = []

        for item in SensorData.objects.filter(greenhouse=greenhouse, recorded_at__gte=since).order_by('recorded_at', 'id'):
            value = getattr(item, metric, None)
            points.append({'recorded_at': item.recorded_at, 'value': value})

        return Response({'metric': metric, 'points': points})


class SensorHistoryView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        page = _query_int(request, 'page', 1, min_value=1, max_value=1_000_000)
        page_size = _query_int(request, 'page_size', 20, min_value=5, max_value=100)

        queryset = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id')

        hours_raw = request.query_params.get('hours')
        date_from_raw = request.query_params.get('date_from')
        date_to_raw = request.query_params.get('date_to')

        if date_from_raw:
            date_from = parse_datetime(date_from_raw)
            if not date_from:
                raise ValidationError('date_from không hợp lệ')
            if timezone.is_naive(date_from):
                date_from = timezone.make_aware(date_from, timezone.get_current_timezone())
            queryset = queryset.filter(recorded_at__gte=date_from)

        if date_to_raw:
            date_to = parse_datetime(date_to_raw)
            if not date_to:
                raise ValidationError('date_to không hợp lệ')
            if timezone.is_naive(date_to):
                date_to = timezone.make_aware(date_to, timezone.get_current_timezone())
            queryset = queryset.filter(recorded_at__lte=date_to)

        if hours_raw and not date_from_raw and not date_to_raw:
            hours = _query_int(request, 'hours', 24, min_value=1, max_value=24 * 30)
            since = timezone.now() - timedelta(hours=hours)
            queryset = queryset.filter(recorded_at__gte=since)

        total = queryset.count()
        total_pages = max((total + page_size - 1) // page_size, 1)

        if page > total_pages:
            page = total_pages

        start = (page - 1) * page_size
        end = start + page_size
        rows = queryset[start:end]

        return Response({
            'items': SensorDataSerializer(rows, many=True).data,
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
        })


class ControlStateView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        control = _get_control_state(greenhouse)
        return Response(ControlStateSerializer(control).data)


class ControlModeView(APIView):
    def post(self, request):
        serializer = ControlModeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        greenhouse = default_greenhouse(request.user)
        mode = data['mode']
        if mode not in {'AUTO', 'MANUAL'}:
            raise ValidationError('mode phải là AUTO hoặc MANUAL')

        control = _get_control_state(greenhouse)
        control.mode = mode
        control.manual_reason = data.get('reason') or ''

        if mode == ControlState.Mode.AUTO:
            control.manual_changed_at = None
            control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])
            _turn_off_all_actuators(greenhouse)
        else:
            control.manual_changed_at = timezone.now()
            control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])

        return Response(ControlStateSerializer(control).data)


class ForecastView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        estimation = latest_estimation(greenhouse=greenhouse)
        recommendation = latest_recommendation_for_greenhouse(greenhouse)
        scheduler_state = get_scheduler_state(greenhouse=greenhouse)
        latest, history = _forecast_latest_and_history(greenhouse, estimation)

        return Response({
            'latest': latest,
            'estimation': EstimationCycleSerializer(estimation).data if estimation else None,
            'recommendation': AMPCRecommendationSerializer(recommendation).data if recommendation else None,
            'scheduler': AMPCSchedulerStateSerializer(scheduler_state).data,
            'history': history,
        })


class AutoSettingsView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        profile = get_greenhouse_control_profile(greenhouse)
        return Response(_legacy_auto_settings_payload(profile))

    def patch(self, request):
        greenhouse = default_greenhouse(request.user)
        profile = get_greenhouse_control_profile(greenhouse)
        serializer = GreenhouseControlProfileSerializer(
            profile,
            data=_legacy_auto_settings_patch(request.data),
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(_legacy_auto_settings_payload(profile))


class AutoRecommendationView(APIView):
    def post(self, request):
        recommendation = run_auto_recommendation(create_command_if_auto=True, user=request.user)
        status_code = status.HTTP_200_OK if recommendation.safety_status == 'safe' else status.HTTP_202_ACCEPTED
        return Response(AMPCRecommendationSerializer(recommendation).data, status=status_code)


class AMPCSchedulerView(APIView):
    def get(self, request):
        return Response(AMPCSchedulerStateSerializer(get_scheduler_state(user=request.user)).data)


class AMPCSchedulerStartView(APIView):
    def post(self, request):
        state = start_scheduler(user=request.user)
        state = run_due_once(force=True, state_id=state.id) or get_scheduler_state(user=request.user)
        return Response(AMPCSchedulerStateSerializer(state).data)


class AMPCSchedulerStopView(APIView):
    def post(self, request):
        state = stop_scheduler(user=request.user)
        return Response(AMPCSchedulerStateSerializer(state).data)


class RunListView(generics.ListAPIView):
    serializer_class = RunListSerializer

    def get_queryset(self):
        return (
            ExperimentRun.objects
            .filter(greenhouse__owner=self.request.user)
            .select_related('greenhouse')
            .order_by('-created_at', '-id')
        )


class RunSeriesView(APIView):
    def get(self, request, run_id: int):
        run = generics.get_object_or_404(
            ExperimentRun.objects.filter(greenhouse__owner=request.user),
            pk=run_id,
        )
        limit = _query_int(request, 'limit', 500, min_value=1, max_value=5000)
        cycles = (
            EstimationCycle.objects
            .filter(run=run)
            .order_by('-sample_ts', '-id')[:limit]
        )
        return Response(CycleSerializer(reversed(list(cycles)), many=True).data)


class RunMetricsView(APIView):
    def get(self, request, run_id: int):
        run = generics.get_object_or_404(
            ExperimentRun.objects.filter(greenhouse__owner=request.user),
            pk=run_id,
        )
        summary = EvaluationSummary.objects.filter(run=run).first()
        if summary is None:
            return Response({'detail': 'metrics_not_found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(EvaluationSummarySerializer(summary).data)


class GreenhouseControlProfileView(APIView):
    def get(self, request, greenhouse_id: int):
        greenhouse = get_greenhouse_for_user(request.user, greenhouse_id)
        profile = get_greenhouse_control_profile(greenhouse)
        return Response(GreenhouseControlProfileSerializer(profile).data)

    def patch(self, request, greenhouse_id: int):
        greenhouse = get_greenhouse_for_user(request.user, greenhouse_id)
        profile = get_greenhouse_control_profile(greenhouse)
        serializer = GreenhouseControlProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class GreenhouseAMPCRecommendationView(APIView):
    def post(self, request, greenhouse_id: int):
        get_greenhouse_for_user(request.user, greenhouse_id)
        recommendation = run_auto_recommendation(
            create_command_if_auto=True,
            user=request.user,
            greenhouse_id=greenhouse_id,
        )
        code = status.HTTP_200_OK if recommendation.safety_status == 'safe' else status.HTTP_202_ACCEPTED
        return Response(LegacyAMPCRecommendationSerializer(recommendation).data, status=code)


class GreenhouseAMPCLatestRecommendationView(APIView):
    def get(self, request, greenhouse_id: int):
        greenhouse = get_greenhouse_for_user(request.user, greenhouse_id)
        recommendation = latest_recommendation_for_greenhouse(greenhouse)
        if recommendation is None:
            return Response({'detail': 'recommendation_not_found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(LegacyAMPCRecommendationSerializer(recommendation).data)


class DeviceListView(generics.ListAPIView):
    serializer_class = DeviceSerializer

    def get_queryset(self):
        greenhouse = default_greenhouse(self.request.user)
        refresh_device_statuses(greenhouse=greenhouse)
        return Device.objects.filter(greenhouse=greenhouse).order_by('id')


class DeviceToggleView(APIView):
    def post(self, request, pk: int):
        greenhouse = default_greenhouse(request.user)
        device = generics.get_object_or_404(Device.objects.filter(greenhouse=greenhouse), pk=pk)

        if device.device_type == Device.DeviceType.CONTROLLER:
            raise ValidationError('ESP32 Main là bộ điều khiển trung tâm, không hỗ trợ bật/tắt kiểu actuator.')

        control = _get_control_state(greenhouse)
        control.mode = ControlState.Mode.MANUAL
        control.manual_reason = f'manual_toggle:{device.code}'
        control.manual_changed_at = timezone.now()
        control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])

        state, _ = DeviceState.objects.get_or_create(device=device)
        state.is_on = not state.is_on
        state.desired_on = state.is_on
        state.last_command = 'toggle'
        state.last_value = 'on' if state.is_on else 'off'
        state.save(update_fields=['is_on', 'desired_on', 'last_command', 'last_value', 'updated_at'])

        enqueue_device_command(device=device, command='set_power', value=state.last_value)
        notify_pending_commands(greenhouse=greenhouse)
        return Response(DeviceSerializer(device).data)


class DeviceCommandView(APIView):
    def post(self, request, pk: int):
        serializer = DeviceCommandInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        greenhouse = default_greenhouse(request.user)
        device = generics.get_object_or_404(Device.objects.filter(greenhouse=greenhouse), pk=pk)
        command = data['command']
        payload = data.get('payload') or {}
        value = data.get('value') or ''

        if not command:
            raise ValidationError('Thiếu command')

        if device.device_type == Device.DeviceType.CONTROLLER:
            raise ValidationError('Không gửi command actuator tới controller trung tâm.')

        control = _get_control_state(greenhouse)
        control.mode = ControlState.Mode.MANUAL
        control.manual_reason = f'manual_command:{device.code}:{command}'
        control.manual_changed_at = timezone.now()
        control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])

        cmd = enqueue_device_command(
            device=device,
            command=command,
            value=value,
            payload=payload,
        )

        state, _ = DeviceState.objects.get_or_create(device=device)
        state.last_command = command

        if value:
            state.last_value = value
            if value.lower() in {'on', 'off'}:
                state.desired_on = value.lower() == 'on'

        state.save(update_fields=['last_command', 'last_value', 'desired_on', 'updated_at'])
        notify_pending_commands(greenhouse=greenhouse)
        return Response(DeviceCommandSerializer(cmd).data, status=status.HTTP_201_CREATED)


class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer

    def get_queryset(self):
        greenhouse = default_greenhouse(self.request.user)
        refresh_device_statuses(greenhouse=greenhouse)
        return _alert_queryset(greenhouse).order_by('-happened_at', '-id')


class AlertMarkReadView(APIView):
    def post(self, request, pk: int):
        greenhouse = default_greenhouse(request.user)
        alert = generics.get_object_or_404(_alert_queryset(greenhouse), pk=pk)
        alert.is_read = True
        alert.save(update_fields=['is_read', 'updated_at'])
        return Response(AlertSerializer(alert).data)


class AlertMarkAllReadView(APIView):
    def post(self, request):
        greenhouse = default_greenhouse(request.user)
        updated = _alert_queryset(greenhouse).filter(is_read=False).update(is_read=True, updated_at=timezone.now())
        return Response({'updated': updated})


class LiveIngestSamplesView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        auth_device = _check_ingest_token(request)
        _require_controller_token(auth_device)
        serializer = LiveSampleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        run = generics.get_object_or_404(ExperimentRun, pk=data['run_id'])
        if auth_device is None and request.data.get('greenhouse_id') is None:
            greenhouse = run.greenhouse or default_greenhouse()
        else:
            greenhouse = _ingest_greenhouse(request, auth_device)
        if run.greenhouse_id is not None and run.greenhouse_id != greenhouse.id:
            raise PermissionDenied('Run không thuộc greenhouse của device token')
        if run.greenhouse_id is None:
            run.greenhouse = greenhouse
            run.save(update_fields=['greenhouse', 'updated_at'])

        payload = {
            'source': 'live_sample',
            'drip': data.get('drip'),
            'mist': data.get('mist'),
            'fan': data.get('fan'),
        }
        reading = SensorData.objects.create(
            greenhouse=greenhouse,
            temperature=data.get('temperature'),
            humidity=data.get('humidity'),
            light=data.get('light'),
            soil_moisture=data.get('soil_moisture'),
            payload=payload,
            recorded_at=data['timestamp'],
        )
        estimation = ensure_estimation_for_reading(reading, greenhouse=greenhouse, run=run)

        return Response({
            'id': estimation.id,
            'run_id': run.id,
            'greenhouse_id': greenhouse.id,
            'cycle_index': estimation.cycle_index,
            'preprocess_status': estimation.preprocess_status,
            'cycle_status': estimation.cycle_status,
            'adaptive_status': estimation.adaptive_status,
            'kf_x_posterior': estimation.kf_x_posterior,
            'kf_innovation': estimation.kf_innovation,
            'sample_ts': estimation.sample_ts,
        }, status=status.HTTP_201_CREATED)


class IngestReadingsView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        auth_device = _check_ingest_token(request)
        _require_controller_token(auth_device)
        serializer = IngestReadingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = {**request.data, **serializer.validated_data}
        greenhouse = _ingest_greenhouse(request, auth_device)
        device_code = auth_device.code if auth_device is not None else 'esp32-main'
        reading = ingest_sensor_payload(payload, device_code=device_code, greenhouse=greenhouse)
        estimation = ensure_estimation_for_reading(reading, greenhouse=greenhouse)

        return Response({
            'id': reading.id,
            'estimation_id': estimation.id,
            'recommendation_id': None,
            'message': 'Đã nhận dữ liệu cảm biến',
        })


class IngestHeartbeatView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        auth_device = _check_ingest_token(request)
        _require_controller_token(auth_device)
        serializer = IngestHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = {**request.data, **serializer.validated_data}
        greenhouse = _ingest_greenhouse(request, auth_device)
        device_code = auth_device.code if auth_device is not None else 'esp32-main'
        ingest_heartbeat_payload(payload, device_code=device_code, greenhouse=greenhouse)
        return Response({'message': 'heartbeat ok'})


class IngestPendingCommandsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        auth_device = _check_ingest_token(request)
        greenhouse = _ingest_greenhouse(request, auth_device)
        commands = get_pending_commands(device=auth_device, greenhouse=greenhouse)

        return Response(commands)


class IngestCommandAckView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk: int):
        auth_device = _check_ingest_token(request)
        serializer = DeviceCommandAckInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        greenhouse = _ingest_greenhouse(request, auth_device)
        payload = {**serializer.validated_data, 'id': pk}
        cmd = ack_device_command_payload(payload, device=auth_device, greenhouse=greenhouse)
        if cmd is None:
            raise Http404('command_not_found_or_forbidden')

        return Response({'message': 'ack ok'})
