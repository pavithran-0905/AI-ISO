"""Background workers.

All four are leader-elected through ``shared_core.scheduler``; see
:mod:`app.workers.registrar` for why.
"""

from app.workers.processing_sweep import ProcessingSweepWorker
from app.workers.registrar import (
    register_processing_sweep,
    register_retention_sweep,
    register_review_expiry_sweep,
    register_statistics_rollup,
)
from app.workers.retention_sweep import RetentionSweepWorker
from app.workers.review_expiry_sweep import ReviewExpirySweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker

__all__ = [
    "ProcessingSweepWorker",
    "RetentionSweepWorker",
    "ReviewExpirySweepWorker",
    "StatisticsRollupWorker",
    "register_processing_sweep",
    "register_retention_sweep",
    "register_review_expiry_sweep",
    "register_statistics_rollup",
]
