"""
IncidentOps - Fault Generators Package

A collection of 10 fault type generators for the IncidentOps RL environment.

Fault Types:
1. network_partition - Split-brain network isolation
2. data_corruption - Silent data corruption
3. config_drift - Configuration drift/misconfiguration
4. ddos - DDoS / traffic spike
5. slow_downstream - Slow downstream dependency
6. version_mismatch - API version mismatch
7. cert_expiry - TLS certificate expiry
8. memory_leak - Gradual memory leak
9. zombie_process - Zombie orphaned processes
10. thundering_herd - Cache stampede / thundering herd

Usage:
    from app.faults import FaultRegistry

    # List all faults
    FaultRegistry.list()

    # Generate a scenario
    from app.determinism import DeterministicRNG
    rng = DeterministicRNG(seed=42)
    scenario = FaultRegistry.generate("network_partition", rng, 3, services)
"""

# Import base classes
from app.faults.base import BaseFault, DeployEvent

# Import registry
from app.faults.registry import FaultRegistry

# Import all fault generators
from app.faults.network_partition import NetworkPartitionFault
from app.faults.data_corruption import DataCorruptionFault
from app.faults.config_drift import ConfigDriftFault
from app.faults.ddos import DdosFault
from app.faults.slow_downstream import SlowDownstreamFault
from app.faults.version_mismatch import VersionMismatchFault
from app.faults.cert_expiry import CertExpiryFault
from app.faults.memory_leak import MemoryLeakFault
from app.faults.zombie_process import ZombieProcessFault
from app.faults.thundering_herd import ThunderingHerdFault
from app.faults.noisy_neighbor import NoisyNeighborFault

# Register all faults with the registry
# This happens at import time to ensure all faults are available
FaultRegistry.register(NetworkPartitionFault)
FaultRegistry.register(DataCorruptionFault)
FaultRegistry.register(ConfigDriftFault)
FaultRegistry.register(DdosFault)
FaultRegistry.register(SlowDownstreamFault)
FaultRegistry.register(VersionMismatchFault)
FaultRegistry.register(CertExpiryFault)
FaultRegistry.register(MemoryLeakFault)
FaultRegistry.register(ZombieProcessFault)
FaultRegistry.register(ThunderingHerdFault)
FaultRegistry.register(NoisyNeighborFault)

# Register ZOMBIE as alias for zombie_process
FaultRegistry.register(ZombieProcessFault)  # registers under "zombie_process"
# Alias "zombie" -> ZombieProcessFault
FaultRegistry._faults["zombie"] = ZombieProcessFault

__all__ = [
    # Base classes
    "BaseFault",
    "DeployEvent",

    # Registry
    "FaultRegistry",

    # Fault generators
    "NetworkPartitionFault",
    "DataCorruptionFault",
    "ConfigDriftFault",
    "DdosFault",
    "SlowDownstreamFault",
    "VersionMismatchFault",
    "CertExpiryFault",
    "MemoryLeakFault",
    "ZombieProcessFault",
    "ThunderingHerdFault",
    "NoisyNeighborFault",
]
