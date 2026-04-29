def list_protocols():
    return ["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"]


def list_scanners():
    return [
        {"id": "network", "label": "Network Scanner", "requires_agent": False},
        {"id": "agent.cert_store", "label": "System CA Store", "requires_agent": True},
        {"id": "agent.pkg_keyring", "label": "Package Repository Keys", "requires_agent": True},
        {"id": "agent.ssh_userkey", "label": "SSH User Keys", "requires_agent": True},
        {"id": "agent.ssh_config", "label": "SSH Config Policy", "requires_agent": True},
        {"id": "agent.keystore", "label": "Keystore Files", "requires_agent": True},
        {"id": "agent.app_cert_files", "label": "Application Cert Files", "requires_agent": True},
        {"id": "agent.app_config", "label": "Application Config Policy", "requires_agent": True},
    ]


def get_algorithm_risk_table():
    return [
        {"algorithm": "RSA-1024, DSA-1024, DH-1024", "factor_a": 1.0, "quantum_vulnerable": True},
        {"algorithm": "RSA-2048, DSA-2048, DH-2048 (modp14)", "factor_a": 0.95, "quantum_vulnerable": True},
        {"algorithm": "RSA-3072, DH-3072 (modp15)", "factor_a": 0.9, "quantum_vulnerable": True},
        {"algorithm": "RSA-4096+", "factor_a": 0.85, "quantum_vulnerable": True},
        {"algorithm": "ECDSA P-256, ECDH P-256", "factor_a": 0.95, "quantum_vulnerable": True},
        {"algorithm": "ECDSA P-384, ECDH P-384", "factor_a": 0.9, "quantum_vulnerable": True},
        {"algorithm": "ECDSA P-521, ECDH P-521", "factor_a": 0.85, "quantum_vulnerable": True},
        {"algorithm": "Ed25519, Ed448", "factor_a": 0.9, "quantum_vulnerable": True},
        {"algorithm": "X25519, X448", "factor_a": 0.9, "quantum_vulnerable": True},
        {"algorithm": "SHA-1 (signing)", "factor_a": 1.0, "quantum_vulnerable": False},
        {"algorithm": "SHA-256, SHA-384, SHA-512 (hash only)", "factor_a": 0.05, "quantum_vulnerable": False},
        {"algorithm": "AES-128", "factor_a": 0.1, "quantum_vulnerable": False},
        {"algorithm": "AES-192/256", "factor_a": 0.05, "quantum_vulnerable": False},
        {"algorithm": "ChaCha20", "factor_a": 0.05, "quantum_vulnerable": False},
        {"algorithm": "HMAC-*", "factor_a": 0.05, "quantum_vulnerable": False},
        {"algorithm": "ML-KEM-512/768/1024", "factor_a": 0.0, "quantum_vulnerable": False},
        {"algorithm": "ML-DSA-44/65/87", "factor_a": 0.0, "quantum_vulnerable": False},
        {"algorithm": "SLH-DSA-*", "factor_a": 0.0, "quantum_vulnerable": False},
        {"algorithm": "Falcon-*", "factor_a": 0.0, "quantum_vulnerable": False},
        {"algorithm": "Hybrid (X25519+ML-KEM-768)", "factor_a": 0.1, "quantum_vulnerable": True},
        {"algorithm": "Unknown", "factor_a": 0.5, "quantum_vulnerable": True},
    ]
