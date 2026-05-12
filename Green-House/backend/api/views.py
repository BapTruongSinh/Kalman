from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (
    AMPCRecommendation,
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
    ControlStateSerializer,
    DeviceCommandSerializer,
    DeviceSerializer,
    EstimationCycleSerializer,
    CycleSerializer,
    EvaluationSummarySerializer,
    GreenhouseControlProfileSerializer,
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
    build_uptime_hint,
    enqueue_device_command,
    ingest_sensor_payload,
    notify_pending_commands,
    refresh_device_statuses,
)


def _check_ingest_token(request):
    header = request.headers.get('X-Device-Token') or ''
    auth = request.headers.get('Authorization') or ''
    bearer = auth.replace('Bearer ', '') if auth.startswith('Bearer ') else ''

    if header == settings.INGEST_DEVICE_TOKEN or bearer == settings.INGEST_DEVICE_TOKEN:
        return True

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


def _get_control_state():
    control, _ = ControlState.objects.get_or_create(singleton_key='main')
    return control


def _turn_off_all_actuators():
    actuators = Device.objects.exclude(device_type=Device.DeviceType.CONTROLLER)

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

    notify_pending_commands()


def _esp32_online() -> bool:
    refresh_device_statuses()
    return Device.objects.filter(
        device_type=Device.DeviceType.CONTROLLER,
        status=Device.DeviceStatus.ONLINE,
    ).exists()


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer


class DashboardOverviewView(APIView):
    def get(self, request):
        refresh_device_statuses()

        esp32_online = _esp32_online()
        latest = SensorData.objects.order_by('-recorded_at', '-id').first() if esp32_online else None
        recent_alerts = Alert.objects.order_by('-happened_at', '-id')[:5]
        control = _get_control_state()

        payload = {
            'latest': SensorDataSerializer(latest).data if latest else None,
            'control': ControlStateSerializer(control).data,
            'device_count': Device.objects.exclude(device_type=Device.DeviceType.CONTROLLER).count(),
            'online_devices': Device.objects.exclude(device_type=Device.DeviceType.CONTROLLER).filter(
                status=Device.DeviceStatus.ONLINE
            ).count(),
            'unread_alerts': Alert.objects.filter(is_read=False).count(),
            'uptime_hint': build_uptime_hint(),
            'recent_alerts': AlertSerializer(recent_alerts, many=True).data,
            'esp32_online': esp32_online,
        }
        return Response(payload)


class LatestReadingView(APIView):
    def get(self, request):
        esp32_online = _esp32_online()
        if not esp32_online:
            return Response(None)

        latest = SensorData.objects.order_by('-recorded_at', '-id').first()
        if not latest:
            return Response(None)
        return Response(SensorDataSerializer(latest).data)


class ChartView(APIView):
    def get(self, request):
        metric = request.query_params.get('metric')
        hours = int(request.query_params.get('hours', '24'))

        if metric not in {'temperature', 'humidity', 'light', 'soil_moisture'}:
            raise ValidationError('metric không hợp lệ')

        esp32_online = _esp32_online()
        if not esp32_online:
            return Response({
                'metric': metric,
                'points': [],
            })

        since = timezone.now() - timedelta(hours=hours)
        points = []

        for item in SensorData.objects.filter(recorded_at__gte=since).order_by('recorded_at', 'id'):
            value = getattr(item, metric, None)
            points.append({'recorded_at': item.recorded_at, 'value': value})

        return Response({'metric': metric, 'points': points})


class SensorHistoryView(APIView):
    def get(self, request):
        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = min(max(int(request.query_params.get('page_size', 20)), 5), 100)

        queryset = SensorData.objects.order_by('-recorded_at', '-id')

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
            hours = max(int(hours_raw), 1)
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
        control = _get_control_state()
        return Response(ControlStateSerializer(control).data)


class ControlModeView(APIView):
    def post(self, request):
        mode = str(request.data.get('mode') or '').upper().strip()
        if mode not in {'AUTO', 'MANUAL'}:
            raise ValidationError('mode phải là AUTO hoặc MANUAL')

        control = _get_control_state()
        control.mode = mode
        control.manual_reason = str(request.data.get('reason') or '').strip()

        if mode == ControlState.Mode.AUTO:
            control.manual_changed_at = None
            control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])
            _turn_off_all_actuators()
        else:
            control.manual_changed_at = timezone.now()
            control.save(update_fields=['mode', 'manual_reason', 'manual_changed_at', 'updated_at'])

        return Response(ControlStateSerializer(control).data)


class ForecastView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        latest = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id').first()
        estimation = latest_estimation(greenhouse=greenhouse)
        recommendation = latest_recommendation_for_greenhouse(greenhouse)
        scheduler_state = get_scheduler_state(greenhouse=greenhouse)

        history_rows = SensorData.objects.filter(greenhouse=greenhouse).order_by('-recorded_at', '-id')[:6]
        history = [
            SensorDataSerializer(item).data
            for item in reversed(list(history_rows))
        ]

        return Response({
            'latest': SensorDataSerializer(latest).data if latest else None,
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
        limit = min(max(int(request.query_params.get('limit', '500')), 1), 5000)
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


class KalmanTestSeriesView(APIView):
    def get(self, request):
        if not settings.DEBUG and not request.user.is_staff:
            raise PermissionDenied('kalman_test_series_staff_only')

        limit = min(max(int(request.query_params.get('limit', '100000')), 1), 100000)
        database_name = getattr(settings, 'KALMAN_TEST_DB_NAME', 'kalman_greenhouse')
        table_name = 'pipeline_cycles'
        quoted_database = database_name.replace('`', '``')

        query = f"""
            SELECT
                id,
                greenhouse_id,
                run_id,
                sample_ts,
                cycle_index,
                slice_type,
                source_type,
                raw_soil_moisture,
                raw_temperature,
                raw_humidity,
                raw_light,
                raw_drip,
                raw_mist,
                raw_fan,
                preprocess_status,
                arx_predicted,
                kf_x_prior,
                kf_P_prior,
                kf_innovation,
                kf_R,
                kf_K,
                kf_x_posterior,
                kf_P_posterior,
                cycle_status,
                error_message,
                adaptive_status,
                latency_ms
            FROM (
                SELECT *
                FROM `{quoted_database}`.`{table_name}`
                WHERE raw_soil_moisture IS NOT NULL
                  AND kf_x_posterior IS NOT NULL
                ORDER BY sample_ts DESC, id DESC
                LIMIT %s
            ) recent
            ORDER BY sample_ts ASC, id ASC
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, [limit])
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except DatabaseError as exc:
            return Response(
                {
                    'detail': 'kalman_test_source_unavailable',
                    'source_database': database_name,
                    'source_table': table_name,
                    'error': str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            'source_database': database_name,
            'source_table': table_name,
            'limit': limit,
            'total_selected': len(rows),
            'points': rows,
        })


class MPCTestSeriesView(APIView):
    def get(self, request):
        greenhouse = default_greenhouse(request.user)
        limit = min(max(int(request.query_params.get('limit', '5000')), 1), 100000)
        queryset = (
            AMPCRecommendation.objects
            .filter(
                greenhouse=greenhouse,
                config_snapshot__mpc_test_source='manual_mpc_test_seed',
            )
            .select_related('sensor_data')
            .order_by('created_at', 'id')[:limit]
        )

        rows = list(queryset)
        points = []
        for audit in rows:
            state = audit.state_snapshot or {}
            sensor = audit.sensor_data
            sample_ts = (
                state.get('sample_ts')
                or (sensor.recorded_at.isoformat() if sensor else None)
                or audit.created_at.isoformat()
            )
            actual = state.get('actual_soil_moisture')
            if actual is None and sensor is not None and sensor.soil_moisture is not None:
                actual = float(sensor.soil_moisture)
            points.append({
                'timestamp': sample_ts,
                'actual_soil_moisture': actual,
                'mpc_soil_moisture': state.get('mpc_soil_moisture'),
                'rule_based_soil_moisture': state.get('rule_based_soil_moisture'),
                'mpc_pump_seconds': audit.pump_seconds,
                'rule_based_pump_seconds': state.get('rule_based_pump_seconds'),
                'target_low': audit.target_band.get('low', 55.0),
                'target_high': audit.target_band.get('high', 65.0),
                'safety_status': audit.safety_status,
                'reason': audit.reason,
            })

        return Response({
            'greenhouse_id': greenhouse.id,
            'source_table': 'ampc_recommendations',
            'total_selected': len(points),
            'points': points,
        })


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
        refresh_device_statuses()
        return Device.objects.order_by('id')


class DeviceToggleView(APIView):
    def post(self, request, pk: int):
        device = generics.get_object_or_404(Device, pk=pk)

        if device.device_type == Device.DeviceType.CONTROLLER:
            raise ValidationError('ESP32 Main là bộ điều khiển trung tâm, không hỗ trợ bật/tắt kiểu actuator.')

        control = _get_control_state()
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
        notify_pending_commands()
        return Response(DeviceSerializer(device).data)


class DeviceCommandView(APIView):
    def post(self, request, pk: int):
        device = generics.get_object_or_404(Device, pk=pk)
        command = (request.data.get('command') or '').strip()
        payload = request.data.get('payload') or {}
        value = str(request.data.get('value') or '')

        if not command:
            raise ValidationError('Thiếu command')

        if device.device_type == Device.DeviceType.CONTROLLER:
            raise ValidationError('Không gửi command actuator tới controller trung tâm.')

        control = _get_control_state()
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
        notify_pending_commands()
        return Response(DeviceCommandSerializer(cmd).data, status=status.HTTP_201_CREATED)


class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer

    def get_queryset(self):
        refresh_device_statuses()
        return Alert.objects.order_by('-happened_at', '-id')


class AlertMarkReadView(APIView):
    def post(self, request, pk: int):
        alert = generics.get_object_or_404(Alert, pk=pk)
        alert.is_read = True
        alert.save(update_fields=['is_read', 'updated_at'])
        return Response(AlertSerializer(alert).data)


class AlertMarkAllReadView(APIView):
    def post(self, request):
        updated = Alert.objects.filter(is_read=False).update(is_read=True, updated_at=timezone.now())
        return Response({'updated': updated})


class LiveIngestSamplesView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        _check_ingest_token(request)
        serializer = LiveSampleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        run = generics.get_object_or_404(ExperimentRun, pk=data['run_id'])
        greenhouse = run.greenhouse or default_greenhouse()
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
        _check_ingest_token(request)
        greenhouse_id = request.data.get('greenhouse_id')
        greenhouse = (
            generics.get_object_or_404(Greenhouse, pk=greenhouse_id, is_active=True)
            if greenhouse_id is not None
            else default_greenhouse()
        )
        reading = ingest_sensor_payload(request.data, device_code='esp32-main', greenhouse=greenhouse)
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
        _check_ingest_token(request)

        controller, _ = Device.objects.get_or_create(
            code='esp32-main',
            defaults={
                'name': 'ESP32 Main',
                'device_type': Device.DeviceType.CONTROLLER,
                'status': Device.DeviceStatus.OFFLINE,
            },
        )

        controller.status = Device.DeviceStatus.ONLINE
        controller.last_seen_at = timezone.now()
        firmware = request.data.get('firmware_version')
        if firmware:
            controller.firmware_version = firmware
        controller.metadata = {**controller.metadata, **(request.data.get('metadata') or {})}

        update_fields = ['status', 'last_seen_at', 'metadata', 'updated_at']
        if firmware:
            update_fields.append('firmware_version')

        controller.save(update_fields=update_fields)
        return Response({'message': 'heartbeat ok'})


class IngestPendingCommandsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        _check_ingest_token(request)

        commands = (
            DeviceCommand.objects
            .filter(status=DeviceCommand.CommandStatus.PENDING)
            .select_related('device')
            .order_by('created_at', 'id')[:5]
        )

        return Response(DeviceCommandSerializer(commands, many=True).data)


class IngestCommandAckView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk: int):
        _check_ingest_token(request)

        cmd = generics.get_object_or_404(DeviceCommand, pk=pk)
        cmd.status = request.data.get('status') or DeviceCommand.CommandStatus.ACK
        cmd.acked_at = timezone.now()
        cmd.save(update_fields=['status', 'acked_at', 'updated_at'])

        state, _ = DeviceState.objects.get_or_create(device=cmd.device)

        if 'actual_state' in request.data:
            actual_state = _to_bool(request.data.get('actual_state'))
            state.is_on = actual_state
            state.desired_on = actual_state
        elif cmd.value.lower() in {'on', 'off'}:
            state.is_on = cmd.value.lower() == 'on'
            state.desired_on = state.is_on

        state.last_command = cmd.command
        state.last_value = cmd.value
        state.save(update_fields=['is_on', 'desired_on', 'last_command', 'last_value', 'updated_at'])

        cmd.device.status = Device.DeviceStatus.ONLINE
        cmd.device.last_seen_at = timezone.now()
        cmd.device.save(update_fields=['status', 'last_seen_at', 'updated_at'])

        return Response({'message': 'ack ok'})
