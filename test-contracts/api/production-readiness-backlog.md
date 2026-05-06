# Backend Production Readiness Backlog

This backlog tracks the hardening work needed to move the Django backend from
contract-test skeleton to production-grade service. It complements
`django-test-backlog.md`, which covers API behavior contracts.

## Phase PR-1: Runtime Configuration And Security

- [x] `PR-CFG-001` Environment-driven `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, database, and deployment security settings.
- [x] `PR-CFG-002` Fail closed when `DEBUG=false` uses an unsafe default secret.
- [x] `PR-AUTH-001` Optional API token middleware for protected deployments, without blocking health/meta/OpenAPI endpoints.
- [x] `PR-AGT-001` Agent tokens stored with Django password hashing and verified with constant-time hasher checks.

## Phase PR-2: Request Validation And Error Contracts

- [x] `PR-VAL-001` Mutation payloads reject unknown fields.
- [x] `PR-ERR-001` Standard JSON error responses are preserved for auth, validation, not-found, conflict, and queue-unavailable cases.
- [x] `PR-REQ-001` Request IDs are generated, echoed, and exposed on protected and unprotected endpoints.

## Phase PR-3: Data Integrity And Query Safety

- [x] `PR-DB-001` Domain models declare indexes for lifecycle/status and common filter fields.
- [x] `PR-DB-002` Natural uniqueness is enforced for `Target`, `Agent`, and `Asset(snapshot, natural_key)`.
- [x] `PR-DB-003` Numeric risk weights and scores have database-level range constraints.
- [x] `PR-DB-004` Query helpers use bounded pagination and explicit sort allowlists.

## Phase PR-4: Async Boundary And Transaction Safety

- [x] `PR-JOB-001` Job envelope serialization is centralized.
- [x] `PR-JOB-002` Queue-unavailable paths rollback domain rows and jobs.
- [x] `PR-JOB-003` Cancel policies are centralized and tested by job kind/status.
- [x] `PR-JOB-004` Replace no-op queue stubs with durable queued task records and enqueue assertions.

## Phase PR-5: Observability And Operations

- [x] `PR-OPS-001` Health check performs an actual database connectivity check.
- [x] `PR-OPS-002` Production settings expose secure proxy/HTTPS/HSTS controls.
- [x] `PR-OPS-003` Add structured JSON logging with operational correlation fields.
- [x] `PR-OPS-004` Add CI pipeline for migrations, pytest, and deployment security checks.
- [ ] `PR-OPS-005` Add metrics exporter once the deployment monitoring stack is selected.

## Phase PR-6: Product Logic Integration

- [ ] `PR-SCAN-001` Replace scanner/risk/CBOM placeholder services with real scanner, CBOM, and risk engines.
- [ ] `PR-SCAN-002` Run worker integration tests against a real broker and disposable database.
- [x] `PR-SCAN-003` Network scanner records SSH host keys for RSA, ECDSA, and Ed25519 when they are advertised.
- [x] `PR-SCAN-004` Network scanner parses IKEv2 SA proposal responses instead of emitting a fixed placeholder proposal.
- [x] `PR-SCAN-005` Network scanner records TLS version policy and negotiated cipher suite assets.
- [x] `PR-SCAN-006` Network scanner records application protocol assets for MQTT over TLS endpoints.
- [x] `PR-SCAN-007` Network scanner retries known SNI aliases for the same endpoint and records distinct certificates.
- [x] `PR-SCAN-008` Network scanner records every certificate sent in the TLS chain, not only the leaf certificate.
- [x] `PR-SCAN-009` Network scanner emits a protocol asset for generic open TCP fallback endpoints.
- [x] `PR-OPENAPI-001` Add generated OpenAPI drift test for static contract path coverage.
