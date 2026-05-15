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
  The web, SSH, and DB Host Agents also scan private key files and report only
  path/algorithm/fingerprint metadata, never private key material.

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

## Minimal Actual Environment

For a clean environment with no demo seed data and only one web server plus one
SSH server, run:

```bash
# from the repository root
DOCKER_CMD="sudo -n docker" ./scripts/start-minimal-actual-env.sh
```

This starts the system stack with `LOAD_INITIAL_TARGETS=0`, resets the system
database volume by default, and starts only the minimal testbed services:

- `web`: HTTP on host `8080`, HTTPS on host `4430`, Host Agent on `9101`.
- `ssh`: SSH on host `2222`, Host Agent on `9102`.
- `discovery-agent`: Discovery Agent on host `9118`.
- `dns` and `certgen`: support services for deterministic names and TLS certs.

Set `RESET_SYSTEM_DB=0` to keep the current system DB, or override ports with
`BACKEND_PORT`, `SYSTEM_WEB_PORT`, `SYSTEM_WEB_HTTPS_PORT`, `WEB_HTTP_PORT`,
`WEB_HTTPS_PORT`, `SSH_PORT`, and `DISCOVERY_AGENT_PORT`. The system backend
defaults to `18000`, and the system frontend defaults to `8088`/`8444`, so the
minimal stack can run beside a local dev server on `8000` or an existing reverse
proxy on `80`/`443`.

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
- `pqc-tls` exposes a TLS 1.3 PQC reference endpoint using the normal
  OpenSSL/nginx path plus `/.well-known/pqc-readiness.json`. The scanner
  records the endpoint's ML-KEM/ML-DSA readiness metadata as PQC assets, while
  the hostname and port remain stable for a future OQS-provider image swap.
- `mail` is a lightweight protocol fixture that exposes SMTP/STARTTLS and
  implicit TLS ports. It is intended for scanner handshakes, not mail delivery.
- `expected_assets.json` records the intended scanner coverage, including the
  PQC readiness assets exposed by the `pqc-tls` fixture.
