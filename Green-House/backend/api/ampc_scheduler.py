from __future__ import annotations

import logging
import os
import sys
import threading
import time
from datetime import timedelta

from django.db import OperationalError, ProgrammingError, close_old_connections, transaction
from django.utils import timezone

from .ampc import default_greenhouse, run_auto_recommendation
from .models import AMPCSchedulerState

logger = logging.getLogger(__name__)

SCHEDULER_KEY = 'main'
DEFAULT_INTERVAL_SECONDS = 300
POLL_SECONDS = 5
STALE_EXECUTION_FACTOR = 2

_thread_started = False
_thread_lock = threading.Lock()


def _scheduler_key_for_greenhouse(greenhouse_id: int) -> str:
    return f'greenhouse:{greenhouse_id}'


def get_scheduler_state(user=None, greenhouse=None) -> AMPCSchedulerState:
    if greenhouse is None and user is not None:
        greenhouse = default_greenhouse(user)

    key = _scheduler_key_for_greenhouse(greenhouse.id) if greenhouse is not None else SCHEDULER_KEY
    state, _ = AMPCSchedulerState.objects.get_or_create(
        singleton_key=key,
        defaults={
            'greenhouse': greenhouse,
            'interval_seconds': DEFAULT_INTERVAL_SECONDS,
            'is_enabled': False,
        },
    )
    if greenhouse is not None and state.greenhouse_id != greenhouse.id:
        state.greenhouse = greenhouse
        state.save(update_fields=['greenhouse', 'updated_at'])
    return state


def start_scheduler(user=None) -> AMPCSchedulerState:
    greenhouse = default_greenhouse(user)
    now = timezone.now()
    state = get_scheduler_state(greenhouse=greenhouse)
    state.greenhouse = greenhouse
    state.is_enabled = True
    state.is_executing = False
    state.interval_seconds = state.interval_seconds or DEFAULT_INTERVAL_SECONDS
    state.last_started_at = now
    state.next_run_at = now
    state.last_error = ''
    state.save(update_fields=[
        'greenhouse',
        'is_enabled',
        'is_executing',
        'interval_seconds',
        'last_started_at',
        'next_run_at',
        'last_error',
        'updated_at',
    ])
    return state


def stop_scheduler(user=None) -> AMPCSchedulerState:
    now = timezone.now()
    state = get_scheduler_state(user=user)
    state.is_enabled = False
    state.is_executing = False
    state.last_stopped_at = now
    state.next_run_at = None
    state.save(update_fields=[
        'is_enabled',
        'is_executing',
        'last_stopped_at',
        'next_run_at',
        'updated_at',
    ])
    return state


def _execution_is_stale(state: AMPCSchedulerState, now) -> bool:
    interval = max(state.interval_seconds or DEFAULT_INTERVAL_SECONDS, 1)
    stale_after = timedelta(seconds=interval * STALE_EXECUTION_FACTOR)
    return state.updated_at <= now - stale_after


def run_due_once(*, force: bool = False, state_id: int | None = None) -> AMPCSchedulerState | None:
    now = timezone.now()

    try:
        if state_id is not None:
            state = AMPCSchedulerState.objects.get(pk=state_id)
        else:
            state = AMPCSchedulerState.objects.get(singleton_key=SCHEDULER_KEY)
    except AMPCSchedulerState.DoesNotExist:
        return None

    if not state.is_enabled:
        return state
    if state.is_executing and not _execution_is_stale(state, now):
        return state
    if not force and state.next_run_at and state.next_run_at > now:
        return state

    with transaction.atomic():
        state = AMPCSchedulerState.objects.select_for_update().get(pk=state.pk)
        if not state.is_enabled:
            return state
        if state.is_executing and not _execution_is_stale(state, now):
            return state
        if not force and state.next_run_at and state.next_run_at > now:
            return state

        state.is_executing = True
        state.save(update_fields=['is_executing', 'updated_at'])

    status = ''
    error = ''
    try:
        recommendation = run_auto_recommendation(
            create_command_if_auto=True,
            greenhouse_id=state.greenhouse_id,
        )
        status = recommendation.safety_status
        if recommendation.safety_status != 'safe':
            error = recommendation.reason or recommendation.safety_status
    except Exception as exc:  # pragma: no cover - verified through service boundary behavior.
        logger.exception('AMPC scheduler run failed')
        status = 'error'
        error = str(exc)
    finally:
        finished_at = timezone.now()
        next_run_at = finished_at + timedelta(seconds=max(state.interval_seconds, 1))
        AMPCSchedulerState.objects.filter(pk=state.pk).update(
            is_executing=False,
            last_run_at=finished_at,
            next_run_at=next_run_at,
            last_status=status,
            last_error=error,
            updated_at=finished_at,
        )

    return AMPCSchedulerState.objects.get(pk=state.pk)


def run_all_due() -> None:
    state_ids = list(
        AMPCSchedulerState.objects
        .filter(is_enabled=True)
        .values_list('id', flat=True)
    )
    for state_id in state_ids:
        run_due_once(state_id=state_id)


def _should_start_background_thread() -> bool:
    if sys.argv and sys.argv[0].endswith('manage.py') and 'runserver' not in sys.argv:
        return False
    if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
        return False
    return True


def _scheduler_loop() -> None:
    while True:
        try:
            close_old_connections()
            run_all_due()
        except (OperationalError, ProgrammingError):
            logger.debug('AMPC scheduler skipped because database is not ready', exc_info=True)
        except Exception:
            logger.exception('AMPC scheduler loop failed')
        finally:
            close_old_connections()
        time.sleep(POLL_SECONDS)


def start_background_scheduler() -> None:
    global _thread_started

    if not _should_start_background_thread():
        return

    with _thread_lock:
        if _thread_started:
            return
        thread = threading.Thread(
            target=_scheduler_loop,
            name='ampc-scheduler',
            daemon=True,
        )
        thread.start()
        _thread_started = True
