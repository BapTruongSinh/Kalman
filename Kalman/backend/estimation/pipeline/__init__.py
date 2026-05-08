"""
``estimation.pipeline`` — pipeline storage and run lifecycle management.

Public API
----------
``map_result_to_cycle``  — pure mapper: ``CycleResult`` → unsaved ``PipelineCycle``
``bulk_save_cycles``     — bulk-insert a batch of ``PipelineCycle`` rows
``begin_run``            — transition ``ExperimentRun`` PENDING → RUNNING
``end_run``              — transition ``ExperimentRun`` RUNNING → COMPLETED | FAILED | ABORTED
``RunStateError``        — raised on invalid status transitions
"""

from .store import RunStateError, begin_run, bulk_save_cycles, end_run, map_result_to_cycle

__all__ = [
    "map_result_to_cycle",
    "bulk_save_cycles",
    "begin_run",
    "end_run",
    "RunStateError",
]
