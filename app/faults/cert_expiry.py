"""
IncidentOps - TLS Certificate Expiry Fault

Certificate expired or about to expire.
Connection refused / SSL errors in logs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import FaultScenario, FaultType

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class CertExpiryFault(BaseFault):
    """
    TLS certificate expiry fault.

    Certificate expired or about to expire.
    Connection refused / SSL errors in logs.

    Symptoms:
    - SSL handshake failures
    - Connection refused errors
    - Certificate expired warnings
    - No traffic change (connection fails before routing)

    Correct fix: apply_fix (renew certificate)
    """

    name = "cert_expiry"
    difficulty_range = (1, 3)
    affected_services_hint = [
        "api-gateway",
        "payment-service",
        "auth-service",
        "user-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a certificate expiry scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Root cause is typically a frontend-facing service
        root_candidates = [
            s for s in services
            if any(keyword in s for keyword in ["gateway", "payment", "auth", "user"])
        ]
        if not root_candidates:
            root_candidates = services[:3]

        root_cause = rng.choice(root_candidates)

        # Only the root cause service is directly affected
        affected = [root_cause]

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals - point to network or service issues
        misleading_signals = [
            f"{rng.choice(services)}: WARNING: Connection timeout",
            f"{rng.choice(services)}: ERROR: Service unavailable",
        ]

        if difficulty >= 2:
            # Some certificate warnings in other places
            misleading_signals.append(
                f"{rng.choice(services)}: WARNING: Certificate expiring in 7 days"
            )

        return FaultScenario(
            fault_type=FaultType.CERT_EXPIRY,
            root_cause_service=root_cause,
            affected_services=affected,
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_logs:ssl_error",
                "query_logs:certificate",
                "check_certificate_expiry",
                "renew_certificate",
            ],
            correct_fix=f"apply_fix:{root_cause}",
            difficulty=difficulty,
        )

    def get_symptoms(self) -> list[str]:
        """Get certificate expiry symptoms"""
        return [
            "SSL handshake failures",
            "Connection refused errors",
            "Certificate expired warnings in logs",
            "No traffic increase (fails before routing)",
            "External calls failing with SSL errors",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "ERROR: SSLHandshakeException: PKIX path validation failed",
            "ERROR: CertificateExpired: Certificate expired on 2024-01-01",
            "WARNING: SSL certificate about to expire in 2 hours",
            "ERROR: Connection refused: SSL context initialization failed",
            "ERROR: Remote certificate is invalid",
            "WARNING: TLS handshake timeout",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "error_rate spikes due to SSL failures",
            "request_rate unchanged (fails before routing)",
            "no CPU/memory change",
        ]
