#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate --noinput

if [[ "${LOAD_INITIAL_TARGETS:-1}" == "1" ]]; then
  python manage.py shell <<'PY'
import json
from pathlib import Path

from apps.targets.models import Target

fixture = Path("fixtures/initial_targets.json")
if fixture.exists():
    for row in json.loads(fixture.read_text()):
        fields = row["fields"]
        Target.objects.update_or_create(
            pk=row["pk"],
            defaults={
                "host": fields["host"],
                "ip": fields["ip"],
                "port": fields["port"],
                "protocol_hint": fields["protocol_hint"],
                "sni": fields["sni"],
                "transport": fields["transport"],
                "agent_enabled": fields["agent_enabled"],
                "agent_url": fields["agent_url"],
                "context": fields["context"],
            },
        )
PY
fi

if [[ "$#" -gt 0 ]]; then
  exec "$@"
fi

exec python manage.py runserver 0.0.0.0:8000 --noreload
