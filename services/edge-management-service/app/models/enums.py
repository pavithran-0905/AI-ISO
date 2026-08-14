"""Enumerations for the edge management service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every other
AI-IOS service's convention), and comparable with ``==`` against a value
freshly loaded from the database, which comes back as a plain ``str``
rather than the enum instance itself -- see
``services/multi-cluster-management-service``'s own hard-won lesson on
why ``is`` comparison against such a value is unsafe.
"""

from __future__ import annotations

from enum import StrEnum


class EdgeDeviceType(StrEnum):
    INDUSTRIAL_GATEWAY = "industrial_gateway"
    INDUSTRIAL_PC = "industrial_pc"
    EDGE_SERVER = "edge_server"
    PLC = "plc"
    RTU = "rtu"
    SCADA_GATEWAY = "scada_gateway"
    SENSOR_HUB = "sensor_hub"
    IOT_GATEWAY = "iot_gateway"
    MINI_PC = "mini_pc"
    RASPBERRY_PI = "raspberry_pi"
    JETSON = "jetson"
    INTEL_NUC = "intel_nuc"
    CUSTOM = "custom"


class SiteHierarchyLevel(StrEnum):
    """A site's position in the physical hierarchy docs/067 names --
    ``FACTORY`` down to ``ROOM``, with a ``GEO_LOCATION`` leaf for a site
    that is not part of a facility hierarchy at all (a standalone remote
    kiosk, a vehicle, a field installation)."""

    FACTORY = "factory"
    PLANT = "plant"
    BUILDING = "building"
    FLOOR = "floor"
    PRODUCTION_LINE = "production_line"
    CELL = "cell"
    ZONE = "zone"
    RACK = "rack"
    ROOM = "room"
    GEO_LOCATION = "geo_location"


class DeviceLifecycleState(StrEnum):
    """A device's position in its own lifecycle -- see
    ``app.devices.engine`` for the transition table this drives."""

    DISCOVERED = "discovered"
    REGISTERED = "registered"
    PROVISIONING = "provisioning"
    PROVISIONED = "provisioned"
    CONFIGURING = "configuring"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    SUSPENDED = "suspended"
    REPLACING = "replacing"
    RETIRING = "retiring"
    RETIRED = "retired"
    SECURE_WIPING = "secure_wiping"
    FAILED = "failed"


class DeviceHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ComponentHealthStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DeviceComponent(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    TEMPERATURE = "temperature"
    POWER = "power"
    NETWORK = "network"


class SyncKind(StrEnum):
    INCREMENTAL = "incremental"
    FULL = "full"
    CONFIGURATION = "configuration"
    POLICY = "policy"
    INVENTORY = "inventory"
    TELEMETRY = "telemetry"
    WORKFLOW = "workflow"
    KNOWLEDGE = "knowledge"


class SyncStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolutionStrategy(StrEnum):
    SERVER_WINS = "server_wins"
    DEVICE_WINS = "device_wins"
    LAST_WRITE_WINS = "last_write_wins"
    MANUAL = "manual"


class UpdateKind(StrEnum):
    SOFTWARE = "software"
    FIRMWARE = "firmware"
    CONTAINER = "container"
    SECURITY_PATCH = "security_patch"


class UpdateStrategy(StrEnum):
    STAGED = "staged"
    CANARY = "canary"
    ROLLING = "rolling"


class UpdateStatus(StrEnum):
    PLANNED = "planned"
    DOWNLOADING = "downloading"
    STAGING = "staging"
    APPLYING = "applying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ApplicationDeploymentStrategy(StrEnum):
    ROLLING = "rolling"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class AiModelStatus(StrEnum):
    STAGED = "staged"
    DEPLOYED = "deployed"
    AB_TESTING = "ab_testing"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class InferenceTarget(StrEnum):
    CPU = "cpu"
    GPU = "gpu"


class ProtocolKind(StrEnum):
    OPC_UA = "opc_ua"
    MQTT = "mqtt"
    MODBUS_TCP = "modbus_tcp"
    MODBUS_RTU = "modbus_rtu"
    BACNET = "bacnet"
    PROFINET = "profinet"
    ETHERNET_IP = "ethernet_ip"
    DNP3 = "dnp3"
    IEC_61850 = "iec_61850"
    REDFISH = "redfish"
    SNMP = "snmp"
    CUSTOM = "custom"


class ProtocolHealthStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    UNKNOWN = "unknown"


class ReportKind(StrEnum):
    FLEET = "fleet"
    SITE = "site"
    DEVICE = "device"
    HEALTH = "health"
    UPDATE = "update"
    SYNCHRONIZATION = "synchronization"
    SECURITY = "security"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"


class ReportStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(StrEnum):
    """What was done, for the immutable edge fleet audit trail."""

    SITE_REGISTERED = "site_registered"
    DEVICE_REGISTERED = "device_registered"
    CONFIGURATION_CHANGED = "configuration_changed"
    OTA_UPDATED = "ota_updated"
    REMOTE_ACCESS = "remote_access"
    POLICY_CHANGED = "policy_changed"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "AiModelStatus",
    "ApplicationDeploymentStrategy",
    "ApplicationStatus",
    "AuditAction",
    "ComponentHealthStatus",
    "ConflictResolutionStrategy",
    "DeviceComponent",
    "DeviceHealthStatus",
    "DeviceLifecycleState",
    "EdgeDeviceType",
    "InferenceTarget",
    "ProtocolHealthStatus",
    "ProtocolKind",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "SiteHierarchyLevel",
    "SyncKind",
    "SyncStatus",
    "UpdateKind",
    "UpdateStatus",
    "UpdateStrategy",
]
