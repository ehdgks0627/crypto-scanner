import json
import urllib.error
import urllib.request


class DiscoveryAgentClientError(Exception):
    pass


def post_discover(agent, payload: dict, timeout_sec: int = 60) -> dict:
    if not agent.agent_url:
        raise DiscoveryAgentClientError("discovery agent has no agent_url")
    if not agent.agent_runtime_token:
        raise DiscoveryAgentClientError("discovery agent has no runtime token")

    url = f"{agent.agent_url.rstrip('/')}/discover"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {agent.agent_runtime_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            raw = response.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise DiscoveryAgentClientError(f"discovery agent returned HTTP {exc.code}: {raw}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise DiscoveryAgentClientError(f"discovery agent request failed: {exc}") from exc
