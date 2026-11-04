"""Dependencies. The Supervisor implementation is injected by the gateway (ADR 0005)."""

from credassure.core.ports import SupervisorPort, UnavailableSupervisor


def get_supervisor() -> SupervisorPort:
    return UnavailableSupervisor()
