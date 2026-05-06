from collections.abc import Callable
from dataclasses import dataclass

from .models import DiscoveryEndpoint


ProbeCallable = Callable[[str, int, float], DiscoveryEndpoint | None]


@dataclass(frozen=True)
class ProbeSpec:
    name: str
    transport: str
    ports: frozenset[int] | None
    run: ProbeCallable
    fallback: bool = False

    def matches(self, port: int, transport: str) -> bool:
        if self.transport != transport:
            return False
        return self.ports is None or port in self.ports


class ProbeRegistry:
    def __init__(self) -> None:
        self._probes: list[ProbeSpec] = []

    def register(self, probe: ProbeSpec) -> None:
        self._probes.append(probe)

    def probes_for(self, port: int, transport: str) -> list[ProbeSpec]:
        exact = [probe for probe in self._probes if probe.matches(port, transport) and not probe.fallback]
        fallback = [probe for probe in self._probes if probe.matches(port, transport) and probe.fallback]
        return [*exact, *fallback]


def build_default_registry() -> ProbeRegistry:
    from . import protocol_ike
    from . import protocol_imap
    from . import protocol_pop3
    from . import protocol_postgresql
    from . import protocol_smtp
    from . import protocol_ssh
    from . import protocol_tcp
    from . import protocol_tls

    registry = ProbeRegistry()
    for module in (
        protocol_ssh,
        protocol_smtp,
        protocol_imap,
        protocol_pop3,
        protocol_postgresql,
        protocol_tls,
        protocol_ike,
        protocol_tcp,
    ):
        module.register(registry)
    return registry
