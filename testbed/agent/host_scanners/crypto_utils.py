import base64
import json
import os
import re
import struct
import subprocess
from pathlib import Path


def configured_paths(env_name: str, defaults: list[str]) -> list[Path]:
    raw = os.getenv(env_name, "")
    values = [item.strip() for item in raw.split(os.pathsep) if item.strip()] if raw else defaults
    return [Path(value) for value in values]


def iter_files(paths: list[Path], suffixes: tuple[str, ...], max_files: int = 200):
    yielded = 0
    seen = set()
    for root in paths:
        if yielded >= max_files:
            return
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if yielded >= max_files:
                return
            if not path.is_file() or path in seen:
                continue
            if suffixes and path.suffix.lower() not in suffixes and path.name.lower() not in suffixes:
                continue
            seen.add(path)
            yielded += 1
            yield path


def read_json_or_kv(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        data = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
            elif ":" in line:
                key, value = line.split(":", 1)
            else:
                continue
            data[key.strip()] = value.strip().strip("'\"")
        return data


def parse_certificate_algorithm(path: Path) -> str | None:
    try:
        text = subprocess.check_output(
            ["openssl", "x509", "-in", str(path), "-noout", "-text"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return certificate_algorithm_from_openssl_text(text)


def certificate_algorithm_from_openssl_text(text: str) -> str | None:
    if "Public Key Algorithm: rsaEncryption" in text:
        bits = _first_match(text, r"Public-Key: \((\d+) bit\)")
        return f"RSA-{bits}" if bits else "RSA"
    if "Public Key Algorithm: id-ecPublicKey" in text:
        curve = _first_match(text, r"ASN1 OID: ([A-Za-z0-9-]+)") or _first_match(text, r"NIST CURVE: ([A-Za-z0-9-]+)")
        return f"ECDSA-{normalize_curve(curve)}" if curve else "ECDSA"
    if "PUBLIC KEY ALGORITHM: ED25519" in text.upper():
        return "Ed25519"
    return None


def parse_public_key_algorithm(path: Path) -> str | None:
    metadata = read_json_or_kv(path)
    algorithm = metadata.get("algorithm")
    if algorithm:
        return str(algorithm)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = re.search(r"(RSA-\d+|ECDSA[-_]?P-?\d+|Ed25519|ML-KEM-\d+|ML-DSA-\d+)", text, re.IGNORECASE)
    if match:
        return normalize_algorithm(match.group(1))
    return None


def parse_pkcs12_algorithm(path: Path) -> str | None:
    metadata = read_json_or_kv(path)
    algorithm = metadata.get("algorithm")
    if algorithm:
        return str(algorithm)
    for password in ("testbed", ""):
        cmd = ["openssl", "pkcs12", "-in", str(path), "-nokeys", "-clcerts", "-passin", f"pass:{password}"]
        try:
            pem = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        with subprocess.Popen(
            ["openssl", "x509", "-noout", "-text"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ) as proc:
            stdout, _stderr = proc.communicate(pem, timeout=5)
            if proc.returncode == 0:
                return certificate_algorithm_from_openssl_text(stdout)
    return None


def algorithms_from_ssh_authorized_keys(path: Path) -> list[str]:
    algorithms = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return algorithms
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        algorithm = algorithm_from_ssh_key(fields[0], fields[1])
        if algorithm and algorithm not in algorithms:
            algorithms.append(algorithm)
    return algorithms


def algorithm_from_ssh_key(key_type: str, b64_blob: str) -> str | None:
    try:
        blob = base64.b64decode(b64_blob.encode("ascii"), validate=True)
    except ValueError:
        return None
    try:
        algorithm, offset = _read_ssh_string(blob, 0)
        algorithm_text = algorithm.decode("ascii")
        if algorithm_text == "ssh-rsa" or key_type.startswith("rsa-"):
            _exponent, offset = _read_ssh_mpint(blob, offset)
            modulus, _offset = _read_ssh_mpint(blob, offset)
            return f"RSA-{modulus.bit_length()}"
        if algorithm_text.startswith("ecdsa-sha2-"):
            curve, _offset = _read_ssh_string(blob, offset)
            return f"ECDSA-{normalize_ssh_curve(curve.decode('ascii'))}"
        if algorithm_text == "ssh-ed25519":
            return "Ed25519"
    except (ValueError, UnicodeDecodeError):
        return None
    return None


def parse_ssh_config_algorithms(path: Path) -> dict[str, list[str]]:
    policy = {}
    keys = {"KexAlgorithms", "Ciphers", "MACs", "HostKeyAlgorithms", "PubkeyAcceptedAlgorithms"}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return policy
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2 or parts[0] not in keys:
            continue
        policy[parts[0]] = [item.strip() for item in parts[1].split(",") if item.strip()]
    return policy


def parse_jwks_algorithms(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_algorithms = data.get("algorithms")
    if isinstance(raw_algorithms, list):
        return [str(item) for item in raw_algorithms]
    algorithms = []
    for key in data.get("keys", []):
        if not isinstance(key, dict):
            continue
        algorithm = key.get("algorithm") or key.get("alg")
        if algorithm:
            algorithms.append(normalize_algorithm(str(algorithm)))
            continue
        if key.get("kty") == "RSA" and key.get("bits"):
            algorithms.append(f"RSA-{key['bits']}")
        elif key.get("kty") == "EC" and key.get("crv"):
            algorithms.append(f"ECDSA-{normalize_curve(str(key['crv']))}")
    deduped = []
    for algorithm in algorithms:
        if algorithm and algorithm not in deduped:
            deduped.append(algorithm)
    return deduped


def normalize_algorithm(value: str) -> str:
    normalized = value.strip()
    upper = normalized.upper().replace("_", "-")
    if upper.startswith("ECDSAP"):
        return f"ECDSA-P{upper.rsplit('P', 1)[-1]}"
    if upper.startswith("ECDSA-P"):
        return f"ECDSA-P{upper.rsplit('P', 1)[-1]}"
    if upper == "ED25519":
        return "Ed25519"
    if upper.startswith("RSA-"):
        return upper
    return normalized


def normalize_curve(curve: str | None) -> str:
    if not curve:
        return ""
    return {
        "prime256v1": "P-256",
        "secp384r1": "P-384",
        "secp521r1": "P-521",
        "P-256": "P-256",
        "P-384": "P-384",
        "P-521": "P-521",
    }.get(curve, curve)


def normalize_ssh_curve(curve: str) -> str:
    return {"nistp256": "P256", "nistp384": "P384", "nistp521": "P521"}.get(curve, curve)


def _read_ssh_string(data: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(data):
        raise ValueError("truncated ssh string")
    length = struct.unpack("!I", data[offset : offset + 4])[0]
    start = offset + 4
    end = start + length
    if end > len(data):
        raise ValueError("truncated ssh string body")
    return data[start:end], end


def _read_ssh_mpint(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_ssh_string(data, offset)
    return int.from_bytes(raw, "big", signed=False), offset


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None
