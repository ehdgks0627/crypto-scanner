# API Contract Artifacts

This directory contains the machine-readable API contract for the PQC Risk
Assessment System.

## Source of Truth

- `openapi.yaml` is the design source of truth.
- `../08-api-contract.md` explains API intent, semantics, and edge cases.
- Django Ninja must expose an equivalent `/api/openapi.json` after backend
  implementation.

## Examples

`examples/*.json` contains representative request and response payloads for
frontend mocks, contract tests, and documentation examples.

## Validation

Recommended checks:

```bash
npx @redocly/cli lint docs/api/openapi.yaml
npx openapi-typescript docs/api/openapi.yaml -o /tmp/pqc-api-types.d.ts
for f in docs/api/examples/*.json; do python -m json.tool "$f" >/dev/null; done
```
