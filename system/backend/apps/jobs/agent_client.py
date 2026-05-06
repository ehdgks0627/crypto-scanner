import json
import urllib.error
import urllib.request


class HostAgentClientError(Exception):
    pass


def post_scan(agent, capabilities: list[str], timeout_sec: int = 60) -> dict:
    if not agent.agent_url:
        raise HostAgentClientError("host agent has no agent_url")
    if not agent.agent_runtime_token:
        raise HostAgentClientError("host agent has no runtime token")

    request = urllib.request.Request(
        f"{agent.agent_url.rstrip('/')}/scan",
        data=json.dumps({"capabilities": capabilities, "options": {}}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {agent.agent_runtime_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise HostAgentClientError(f"host agent returned HTTP {exc.code}: {raw}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise HostAgentClientError(f"host agent request failed: {exc}") from exc
