"""
IncidentOps - Production Incident Response RL Environment

Version: 12.0.0

A Gym-style OpenEnv for training incident response agents.

Key Features:
- Anti-brute-force detection
- Advanced deceptive signals
- Reasoning-quality rewards
- Human SRE expert grading
- Partial observability
- Full determinism
- Comprehensive validation

Quick Start:
    from app.environment import make_env
    
    env = make_env(seed=42, difficulty=3)
    obs = env.reset()
    
    action = {"action_type": "query_service", "target_service": "api-gateway"}
    response = env.step(action)
"""

__version__ = "15.0"

# Core models
from app.models import (
    ActionType,
    ServiceStatus,
    Severity,
    StepRequest,
    StepResponse,
    RewardBreakdown,
    VALID_SERVICES,
)

# Environment
from app.environment import (
    IncidentEnv,
    EnvironmentConfig,
    make_env,
)

# Fault injection
from app.fault_injector import (
    FaultType,
    FaultInjector,
    FaultScenario,
    FaultSimulator,
    LogNoiseGenerator,
    MetricNoiseGenerator,
    PartialObservabilityManager,
    DependencyPropagator,
)

# Extended fault registry (10 new fault types)
try:
    from app.faults import (
        FaultRegistry,
        BaseFault,
        DeployEvent,
    )
except ImportError:
    FaultRegistry = None
    BaseFault = None
    DeployEvent = None

# Database layer
try:
    from app.db import (
        get_db,
        init_db,
        close_db,
        User,
        Episode,
        LeaderboardEntry,
        UserRepository,
        EpisodeRepository,
        LeaderboardRepository,
    )
except ImportError:
    get_db = None
    init_db = None
    close_db = None
    User = None
    Episode = None
    LeaderboardEntry = None
    UserRepository = None
    EpisodeRepository = None
    LeaderboardRepository = None

# Reward systems
from app.reward import (
    RewardCalculator,
    RewardConfig,
    ProgressiveRewardShaping,
)

from app.reasoning_reward import (
    ReasoningRewardCalculator,
    ReasoningRewardBreakdown,
    ReasoningWeights,
    create_reasoning_reward,
)

# Memory system
from app.memory import (
    IncidentMemory,
    IncidentRecord,
    MemoryMatch,
    MemoryIntegrator,
)

# Grading systems
from app.grader import (
    ScoreGrade,
    DeepTrajectoryGrader,
    DetailedScore,
    TrajectoryAnalysis,
    grade_trajectory,
    grade_multiple_trajectories,
)

from app.human_sre_grader import (
    SREGrade,
    HumanSREGrader,
    HumanSREEvaluation,
    MisleadingPathAnalysis,
    MisleadingPathType,
    grade_like_human_sre,
)

# Tracking systems
from app.information_tracker import (
    EnhancedActionTracker,
    InformationState,
    ActionResult,
    AntiGuessingPenalties,
    InformationType,
)

# Deceptive signals
from app.deceptive_signals import (
    DeceptiveSignalGenerator,
    DeceptivePattern,
    DeceptionType,
    DelayedLogConfig,
    ConflictingMetricConfig,
)

# Frontier tasks
from app.frontier_task import (
    FrontierTaskGenerator,
    FrontierScenario,
    DualLayerFailure,
    DeceptiveSignal,
    create_frontier_scenario,
)

# Baseline agent
from app.baseline import (
    AgentStrategy,
    AgentConfig,
    BaselineAgent,
    run_baseline_episode,
    tune_agent_performance,
)

# Determinism
from app.determinism import (
    DeterministicRNG,
    DeterminismAudit,
    run_reproducibility_test,
)

# Validation
from app.comprehensive_validation import (
    ComprehensiveValidator,
    ValidationReport,
    TestResult,
    run_comprehensive_validation,
)

__all__ = [
    # Version
    "__version__",
    
    # Models
    "ActionType",
    "ServiceStatus",
    "Severity",
    "StepRequest",
    "StepResponse",
    "RewardBreakdown",
    "VALID_SERVICES",
    
    # Environment
    "IncidentEnv",
    "EnvironmentConfig",
    "make_env",
    
    # Fault Injection
    "FaultType",
    "FaultInjector",
    "FaultScenario",
    "FaultSimulator",
    "LogNoiseGenerator",
    "MetricNoiseGenerator",
    "PartialObservabilityManager",
    "DependencyPropagator",

    # Extended Fault Registry
    "FaultRegistry",
    "BaseFault",
    "DeployEvent",

    # Database Layer
    "get_db",
    "init_db",
    "close_db",
    "User",
    "Episode",
    "LeaderboardEntry",
    "UserRepository",
    "EpisodeRepository",
    "LeaderboardRepository",

    # Reward
    "RewardCalculator",
    "RewardConfig",
    "ProgressiveRewardShaping",
    "ReasoningRewardCalculator",
    "ReasoningRewardBreakdown",
    "ReasoningWeights",
    
    # Memory
    "IncidentMemory",
    "IncidentRecord",
    "MemoryMatch",
    "MemoryIntegrator",
    
    # Grading
    "ScoreGrade",
    "DeepTrajectoryGrader",
    "DetailedScore",
    "TrajectoryAnalysis",
    "grade_trajectory",
    "grade_multiple_trajectories",
    
    # Human SRE Grading
    "SREGrade",
    "HumanSREGrader",
    "HumanSREEvaluation",
    "MisleadingPathAnalysis",
    "MisleadingPathType",
    "grade_like_human_sre",
    
    # Information Tracking
    "EnhancedActionTracker",
    "InformationState",
    "ActionResult",
    "AntiGuessingPenalties",
    "InformationType",
    
    # Deceptive Signals
    "DeceptiveSignalGenerator",
    "DeceptivePattern",
    "DeceptionType",
    "DelayedLogConfig",
    "ConflictingMetricConfig",
    
    # Frontier Tasks
    "FrontierTaskGenerator",
    "FrontierScenario",
    "DualLayerFailure",
    "DeceptiveSignal",
    
    # Baseline Agent
    "AgentStrategy",
    "AgentConfig",
    "BaselineAgent",
    "run_baseline_episode",
    "tune_agent_performance",
    
    # Determinism
    "DeterministicRNG",
    "DeterminismAudit",
    "run_reproducibility_test",
    
    # Validation
    "ComprehensiveValidator",
    "ValidationReport",
    "TestResult",
    "run_comprehensive_validation",
]
