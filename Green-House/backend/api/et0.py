from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import Greenhouse, GreenhouseControlProfile


logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
OPEN_METEO_ET0_VARIABLE = 'et0_fao_evapotranspiration'
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_RECENT_CACHE_SECONDS = 6 * 60 * 60
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 512 * 1024


class OpenMeteoError(Exception):
    """Bounded external API failure suitable for fail-closed handling."""


@dataclass(frozen=True)
class ET0Reading:
    greenhouse_id: int | None
    requested_hour: datetime
    et0_hour_mm: float
    et0_step_mm: float
    step_seconds: int
    source: Literal['open_meteo', 'cache', 'recent_cache']
    fetched_at: datetime


@dataclass(frozen=True)
class ET0Failure:
    greenhouse_id: int | None
    requested_hour: datetime
    reason: str
    detail: str
    fail_closed: bool = True
    pump_seconds: float = 0.0


ET0Result = ET0Reading | ET0Failure


class OpenMeteoClient:
    def fetch_hourly_et0(
        self,
        *,
        latitude: float,
        longitude: float,
        target_hour: datetime,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        params = urlencode(
            {
                'latitude': f'{latitude:.6f}',
                'longitude': f'{longitude:.6f}',
                'hourly': OPEN_METEO_ET0_VARIABLE,
                'timezone': 'UTC',
                'start_date': target_hour.date().isoformat(),
                'end_date': target_hour.date().isoformat(),
            }
        )
        url = f'{OPEN_METEO_FORECAST_URL}?{params}'
        request = Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': 'smart-greenhouse-et0/1.0',
            },
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise OpenMeteoError(f'http_{exc.code}') from exc
        except (OSError, TimeoutError, URLError) as exc:
            raise OpenMeteoError(exc.__class__.__name__) from exc

        if len(raw) > MAX_RESPONSE_BYTES:
            raise OpenMeteoError('response_too_large')
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenMeteoError('invalid_json') from exc
        if not isinstance(payload, dict):
            raise OpenMeteoError('invalid_payload')
        return payload


def get_hourly_et0(
    greenhouse: Greenhouse,
    when: datetime,
    *,
    step_seconds: int,
    client: OpenMeteoClient | None = None,
    now: datetime | None = None,
) -> ET0Result:
    requested_hour = _hour_bucket(when)
    current_time = _aware_utc(now or timezone.now())
    greenhouse_id = getattr(greenhouse, 'id', None)

    try:
        latitude, longitude = _greenhouse_coordinates(greenhouse)
        step_seconds = _validate_step_seconds(step_seconds)
    except ValueError as exc:
        return ET0Failure(
            greenhouse_id=greenhouse_id,
            requested_hour=requested_hour,
            reason='invalid_et0_config',
            detail=str(exc),
        )

    exact_key = _hour_cache_key(greenhouse_id, latitude, longitude, requested_hour)
    cached = cache.get(exact_key)
    if cached is not None:
        try:
            return _reading_from_cache(cached, requested_hour, step_seconds, source='cache')
        except ValueError:
            cache.delete(exact_key)

    client = client or OpenMeteoClient()
    try:
        payload = client.fetch_hourly_et0(
            latitude=latitude,
            longitude=longitude,
            target_hour=requested_hour,
            timeout_seconds=_timeout_seconds(),
        )
        et0_hour = _extract_et0(payload, requested_hour)
    except (OpenMeteoError, ValueError) as exc:
        logger.warning(
            'open_meteo_et0_failure',
            extra={
                'greenhouse_id': greenhouse_id,
                'requested_hour': requested_hour.isoformat(),
                'reason': exc.__class__.__name__,
                'detail': str(exc),
            },
        )
        fallback = _recent_cache_reading(
            greenhouse_id,
            latitude,
            longitude,
            requested_hour,
            step_seconds,
            current_time,
        )
        if fallback is not None:
            return fallback
        return ET0Failure(
            greenhouse_id=greenhouse_id,
            requested_hour=requested_hour,
            reason='open_meteo_et0_unavailable',
            detail=str(exc),
        )

    entry = {
        'greenhouse_id': greenhouse_id,
        'requested_hour': requested_hour.isoformat(),
        'et0_hour_mm': et0_hour,
        'fetched_at': current_time.isoformat(),
    }
    cache_ttl = _cache_ttl_seconds()
    cache.set(exact_key, entry, cache_ttl)
    cache.set(_recent_cache_key(greenhouse_id, latitude, longitude), entry, cache_ttl)
    return _reading_from_cache(entry, requested_hour, step_seconds, source='open_meteo')


def _greenhouse_coordinates(greenhouse: Greenhouse) -> tuple[float, float]:
    try:
        profile = greenhouse.control_profile
    except GreenhouseControlProfile.DoesNotExist:
        profile, _ = GreenhouseControlProfile.objects.get_or_create(greenhouse=greenhouse)
    latitude = _finite_float('latitude', profile.latitude)
    longitude = _finite_float('longitude', profile.longitude)
    if not -90.0 <= latitude <= 90.0:
        raise ValueError('latitude_out_of_range')
    if not -180.0 <= longitude <= 180.0:
        raise ValueError('longitude_out_of_range')
    return latitude, longitude


def _extract_et0(payload: dict[str, Any], requested_hour: datetime) -> float:
    hourly = payload.get('hourly')
    if not isinstance(hourly, dict):
        raise ValueError('missing_hourly_payload')
    times = hourly.get('time')
    values = hourly.get(OPEN_METEO_ET0_VARIABLE)
    if not isinstance(times, list) or not isinstance(values, list):
        raise ValueError('missing_hourly_et0')
    if len(times) != len(values):
        raise ValueError('hourly_et0_length_mismatch')

    wanted = requested_hour.strftime('%Y-%m-%dT%H:%M')
    for timestamp, raw_value in zip(times, values):
        if timestamp in {wanted, f'{wanted}:00'}:
            et0 = _finite_float('et0_hour_mm', raw_value)
            if et0 < 0.0:
                raise ValueError('et0_negative')
            return et0
    raise ValueError('requested_hour_not_found')


def _reading_from_cache(
    entry: dict[str, Any],
    requested_hour: datetime,
    step_seconds: int,
    *,
    source: Literal['open_meteo', 'cache', 'recent_cache'],
) -> ET0Reading:
    et0_hour = _finite_float('et0_hour_mm', entry.get('et0_hour_mm'))
    if et0_hour < 0.0:
        raise ValueError('et0_negative')
    fetched_at = _parse_cached_datetime(entry.get('fetched_at'))
    return ET0Reading(
        greenhouse_id=entry.get('greenhouse_id'),
        requested_hour=requested_hour,
        et0_hour_mm=et0_hour,
        et0_step_mm=et0_hour * step_seconds / 3600.0,
        step_seconds=step_seconds,
        source=source,
        fetched_at=fetched_at,
    )


def _recent_cache_reading(
    greenhouse_id: int | None,
    latitude: float,
    longitude: float,
    requested_hour: datetime,
    step_seconds: int,
    current_time: datetime,
) -> ET0Reading | None:
    entry = cache.get(_recent_cache_key(greenhouse_id, latitude, longitude))
    if entry is None:
        return None
    try:
        fetched_at = _parse_cached_datetime(entry.get('fetched_at'))
        age_seconds = (current_time - fetched_at).total_seconds()
        if age_seconds < 0 or age_seconds > _recent_cache_seconds():
            return None
        return _reading_from_cache(entry, requested_hour, step_seconds, source='recent_cache')
    except ValueError:
        return None


def _hour_bucket(value: datetime) -> datetime:
    return _aware_utc(value).replace(minute=0, second=0, microsecond=0)


def _aware_utc(value: datetime) -> datetime:
    if timezone.is_naive(value):
        value = timezone.make_aware(value, datetime_timezone.utc)
    return value.astimezone(datetime_timezone.utc)


def _finite_float(name: str, value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name}_invalid') from exc
    if not math.isfinite(numeric):
        raise ValueError(f'{name}_not_finite')
    return numeric


def _validate_step_seconds(value: int) -> int:
    try:
        step_seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('step_seconds_invalid') from exc
    if step_seconds <= 0:
        raise ValueError('step_seconds_invalid')
    return step_seconds


def _parse_cached_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError('cached_datetime_invalid')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('cached_datetime_invalid') from exc
    return _aware_utc(parsed)


def _hour_cache_key(greenhouse_id: int | None, latitude: float, longitude: float, requested_hour: datetime) -> str:
    return (
        f'et0:open-meteo:gh:{greenhouse_id or "none"}:'
        f'lat:{latitude:.4f}:lon:{longitude:.4f}:hour:{requested_hour:%Y%m%dT%H%MZ}'
    )


def _recent_cache_key(greenhouse_id: int | None, latitude: float, longitude: float) -> str:
    return f'et0:open-meteo:gh:{greenhouse_id or "none"}:lat:{latitude:.4f}:lon:{longitude:.4f}:recent'


def _cache_ttl_seconds() -> int:
    return int(getattr(settings, 'OPEN_METEO_ET0_CACHE_SECONDS', DEFAULT_CACHE_TTL_SECONDS))


def _recent_cache_seconds() -> int:
    return int(getattr(settings, 'OPEN_METEO_ET0_RECENT_CACHE_SECONDS', DEFAULT_RECENT_CACHE_SECONDS))


def _timeout_seconds() -> float:
    timeout_seconds = float(getattr(settings, 'OPEN_METEO_ET0_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS))
    if timeout_seconds <= 0.0:
        raise OpenMeteoError('timeout_invalid')
    return timeout_seconds
