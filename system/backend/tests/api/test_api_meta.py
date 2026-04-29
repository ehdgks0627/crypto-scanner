def test_api_meta_001_static_reference_endpoints_are_cacheable(client):
    protocols_response = client.get("/api/meta/protocols")
    scanners_response = client.get("/api/meta/scanners")
    risk_table_response = client.get("/api/meta/algorithm-risk-table")

    for response in (protocols_response, scanners_response, risk_table_response):
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "max-age=600"

    assert protocols_response.json() == {
        "protocols": ["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"]
    }
    assert scanners_response.json() == {
        "scanners": [
            {"id": "network", "label": "Network Scanner", "requires_agent": False},
            {"id": "agent.cert_store", "label": "System CA Store", "requires_agent": True},
            {"id": "agent.pkg_keyring", "label": "Package Repository Keys", "requires_agent": True},
            {"id": "agent.ssh_userkey", "label": "SSH User Keys", "requires_agent": True},
            {"id": "agent.ssh_config", "label": "SSH Config Policy", "requires_agent": True},
            {"id": "agent.keystore", "label": "Keystore Files", "requires_agent": True},
            {"id": "agent.app_cert_files", "label": "Application Cert Files", "requires_agent": True},
            {"id": "agent.app_config", "label": "Application Config Policy", "requires_agent": True},
        ]
    }
    risk_table = risk_table_response.json()
    assert set(risk_table) == {"items"}
    assert len(risk_table["items"]) == 21
    assert risk_table["items"][0] == {
        "algorithm": "RSA-1024, DSA-1024, DH-1024",
        "factor_a": 1.0,
        "quantum_vulnerable": True,
    }
    assert risk_table["items"][-1] == {
        "algorithm": "Unknown",
        "factor_a": 0.5,
        "quantum_vulnerable": True,
    }
