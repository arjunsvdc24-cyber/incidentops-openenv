"""
IncidentOps - Pydantic Models with Strict Validation
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime


class ActionType(str, Enum):
    """Valid action types for incident response"""
    QUERY_SERVICE = "query_service"
    QUERY_METRICS = "query_metrics"
    QUERY_LOGS = "query_logs"
    QUERY_DEPENDENCIES = "query_dependencies"
    QUERY_DEPLOYMENTS = "query_deployments"
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    QUERY_MEMORY = "query_memory"
    IDENTIFY_ROOT_CAUSE = "identify_root_cause"
    APPLY_FIX = "apply_fix"


class AgentRole(str, Enum):
    """Roles for multi-agent system"""
    INVESTIGATOR = "investigator"  # Gathers evidence, queries services
    FIXER = "fixer"               # Applies remediations
    ANALYST = "analyst"           # Reads memory, analyzes patterns


class ServiceStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Valid service names in the system
VALID_SERVICES = {
    "api-gateway",
    "user-service",
    "auth-service",
    "payment-service",
    "order-service",
    "inventory-service",
    "recommendation-service",
    "notification-service",
    "cache-service",
    "database-primary",
    "database-replica",
    "search-service",
    "analytics-service",
    "email-service",
    "shipping-service",
}


class StepRequest(BaseModel):
    """Request model for /step endpoint with strict validation"""
    action_type: str
    target_service: Optional[str] = None
    parameters: Optional[dict] = None

    @field_validator('action_type')
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        valid_actions = [a.value for a in ActionType]
        if v not in valid_actions:
            raise ValueError(
                f"Invalid action_type '{v}'. Valid actions: {valid_actions}"
            )
        return v

    @field_validator('target_service')
    @classmethod
    def validate_target_service(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SERVICES:
            raise ValueError(
                f"Invalid target_service '{v}'. Valid services: {sorted(VALID_SERVICES)}"
            )
        return v

    @model_validator(mode='after')
    def validate_service_required_actions(self) -> 'StepRequest':
        """Validate that target_service is provided for actions that require it"""
        service_required = {
            ActionType.QUERY_SERVICE.value,
            ActionType.QUERY_METRICS.value,
            ActionType.QUERY_LOGS.value,
            ActionType.RESTART_SERVICE.value,
            ActionType.SCALE_SERVICE.value,
            ActionType.ROLLBACK_DEPLOYMENT.value,
            ActionType.IDENTIFY_ROOT_CAUSE.value,
            ActionType.APPLY_FIX.value,
        }
        if self.action_type in service_required and not self.target_service:
            raise ValueError(
                f"target_service is required for action_type '{self.action_type}'"
            )
        return self


class StepResponse(BaseModel):
    """Response model for /step endpoint"""
    observation: dict
    reward: float
    terminated: bool
    truncated: bool
    info: dict


class ServiceInfo(BaseModel):
    """Service information model"""
    name: str
    status: ServiceStatus
    latency_ms: float
    error_rate: float
    cpu_percent: float
    memory_percent: float
    last_deployment: Optional[str] = None
    version: Optional[str] = None


class MetricPoint(BaseModel):
    """Single metric data point"""
    timestamp: datetime
    value: float
    labels: dict = {}


class LogEntry(BaseModel):
    """Log entry model"""
    timestamp: datetime
    service: str
    level: Severity
    message: str
    metadata: dict = {}


class Alert(BaseModel):
    """Alert model"""
    id: str
    service: str
    severity: Severity
    message: str
    timestamp: datetime
    resolved: bool = False


class IncidentState(BaseModel):
    """Complete incident state snapshot"""
    step: int
    services: dict[str, ServiceInfo]
    alerts: list[Alert]
    metrics: dict[str, list[MetricPoint]]
    logs: list[LogEntry]
    deploy_history: list[dict]


class RewardBreakdown(BaseModel):
    """Detailed breakdown of reward components"""
    health_improvement: float = 0.0
    latency_improvement: float = 0.0
    correct_investigation: float = 0.0
    root_cause_identified: float = 0.0
    correct_fix: float = 0.0
    minimal_actions: float = 0.0
    unnecessary_restart_penalty: float = 0.0
    redundant_query_penalty: float = 0.0
    random_action_penalty: float = 0.0
    memory_usage_bonus: float = 0.0
    total: float = 0.0
