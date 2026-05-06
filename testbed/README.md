# Testbed Docker Compose

This compose project implements the isolated PQC scanner testbed described in
`../docs/02-testbed.md` and `../docs/12-tech-stack.md`.

The default compose now models a 200-300 person IT company PoC environment:

- 7 core protocol fixtures: web, PQC TLS reference, SSH, MQTT, IPsec, mail, PostgreSQL.
- 18 enterprise fixtures: API gateway, admin/mobile APIs, OIDC/SAML, data platform,
  service mesh, CI/CD, registry, artifact repository, Vault/KMS, backup, monitoring,
  logging, and a legacy Java app.
- 10 agent-enabled hosts: the original web/SSH/DB hosts plus representative
  API, identity, registry, vault, backup, and legacy app hosts. Host Agents
  read mounted fixture files instead of returning hard-coded findings.

## Configure

```bash
cp .env.example .env
```

Set these values before starting the testbed:

- `BOOTSTRAP_TOKEN`: same value as the system backend `AGENT_BOOTSTRAP_TOKEN`.
- `POSTGRES_PASSWORD` and `IPSEC_PSK`: local testbed-only secrets.
- `AGENT_PUBLIC_HOST`: use `127.0.0.1` when the backend/worker runs directly on the host. Use `host.docker.internal` when the system stack runs in Docker and set `TESTBED_BIND_ADDR=0.0.0.0` so that containerized workers can reach host-published agent ports.
- `*_AGENT_PORT`: host-published agent ports for the agent-enabled
  enterprise fixtures.

## Validate

```bash
./scripts/validate.sh
```

The validation script checks shell/Python syntax, generates local certificates,
rejects unchanged placeholder secrets, and validates the compose model.

## Run

Start the system stack first so the embedded web, SSH, and DB agents can
register against `BACKEND_URL`.

```bash
docker compose up -d
```

The backend fixture `system/backend/fixtures/initial_targets.json` contains the
matching internal testbed targets for scanner demos. It includes 31 targets
because some services expose multiple protocol endpoints.

Generated certificate material is ignored by git. Re-run with
`FORCE_CERT_REGEN=1 ./certs/generate.sh` to rotate fixtures.

## Notes

- Host ports bind to `127.0.0.1` by default because several services
  intentionally expose weak crypto or permissive demo authentication.
- Enterprise TLS fixture services are not host-published by default. They are
  intended to be reached through `dnsmasq` and the fixed Docker bridge subnet.
- The bridge subnet is fixed to `172.31.240.0/24` to keep dnsmasq records and
  static compose IPs deterministic while avoiding common Docker bridge ranges.
- The IPsec NAT-T host port defaults to `45000` to avoid collisions with local
  VPN software. Set `IPSEC_NATT_PORT=4500` for the exact plan port.
- `pqc-tls` currently exposes a TLS 1.3 reference endpoint using the normal
  OpenSSL/nginx path. The compose keeps the service boundary and hostname
  stable so the OQS-provider image can replace it without changing scanner
  targets.
- `mail` is a lightweight protocol fixture that exposes SMTP/STARTTLS and
  implicit TLS ports. It is intended for scanner handshakes, not mail delivery.
- `expected_assets.json` records the intended scanner coverage and marks the
  current PQC TLS service as a placeholder rather than a known-answer OQS
  endpoint.
