from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DiscoveryEndpoint:
    host: str
    port: int
    transport: str
    detected_protocol: str
    suggested_protocol_hint: str

    def as_dict(self) -> dict:
        return asdict(self)
