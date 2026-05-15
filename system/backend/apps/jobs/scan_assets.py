from dataclasses import dataclass, field
from hashlib import sha256


@dataclass(frozen=True)
class AssetCandidate:
    target_id: int
    scanner_kind: str
    name: str
    asset_type: str
    algorithm: str
    algorithm_family: str
    bom_ref: str
    metadata: dict = field(default_factory=dict)


def family_from_algorithm(algorithm: str | None) -> str:
    value = (algorithm or "").upper()
    if "ML-KEM" in value:
        return "ML-KEM"
    if "ML-DSA" in value:
        return "ML-DSA"
    if "SLH-DSA" in value:
        return "SLH-DSA"
    if "ECDSA" in value or "P-256" in value or "P-384" in value or "P-521" in value or "SECP" in value:
        return "ECDSA"
    if "ED25519" in value or "ED448" in value:
        return "EdDSA"
    if "RSA" in value:
        return "RSA"
    if "HMAC" in value:
        return "HMAC"
    if "MODP" in value or "GROUP14" in value or "DIFFIE-HELLMAN" in value or value == "DH":
        return "DH"
    if "ECDH" in value or "X25519" in value or "X448" in value or "CURVE25519" in value or "CURVE448" in value or "ECP-" in value:
        return "ECDH"
    if "AES" in value:
        return "AES"
    if "CHACHA" in value:
        return "ChaCha20"
    return ""


def stable_bom_ref(*parts: object) -> str:
    text = "|".join(str(part) for part in parts if part is not None)
    return sha256(text.encode("utf-8")).hexdigest()[:24]
