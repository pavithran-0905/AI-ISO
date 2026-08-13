"""Every persisted model.

All three modules are imported here so Alembic's autogenerate sees the
whole metadata. A model that is not imported is a table the migration
will not create -- and the failure surfaces as a missing relation at
runtime, long after the migration looked like it worked.
"""

from app.models.backup import (
    BackupArchive,
    BackupJob,
    BackupRetention,
    BackupSchedule,
    BackupSnapshot,
    BackupTarget,
    BackupVerification,
)
from app.models.operations import BackupAudit, BackupReport, BackupStatistic
from app.models.recovery import (
    DrPlan,
    DrTest,
    FailoverEvent,
    RecoveryReport,
    ReplicationJob,
    RestoreJob,
    RestorePoint,
)

__all__ = [
    "BackupArchive",
    "BackupAudit",
    "BackupJob",
    "BackupReport",
    "BackupRetention",
    "BackupSchedule",
    "BackupSnapshot",
    "BackupStatistic",
    "BackupTarget",
    "BackupVerification",
    "DrPlan",
    "DrTest",
    "FailoverEvent",
    "RecoveryReport",
    "ReplicationJob",
    "RestoreJob",
    "RestorePoint",
]
