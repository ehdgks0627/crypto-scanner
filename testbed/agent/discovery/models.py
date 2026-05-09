from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DiscoveryEndpoint:
    host: str
    port: int
    transport: str
    detected_protocol: str
    suggested_protocol_hint: str
    availability_metrics: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)
