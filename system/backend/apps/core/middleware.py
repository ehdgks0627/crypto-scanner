import uuid
from secrets import compare_digest

from django.conf import settings
from django.http import JsonResponse


class HostValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.get_host()
        return self.get_response(request)


class RequestIdMiddleware:
    header_name = "X-Request-Id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.request_id = request_id

        response = self.get_response(request)
        response[self.header_name] = request_id
        return response


class APIKeyMiddleware:
    header_name = "X-API-Token"
    exempt_prefixes = (
        "/api/health",
        "/api/meta/",
        "/api/openapi",
        "/api/docs",
        "/api/agents/register",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expected_token = getattr(settings, "API_AUTH_TOKEN", "")
        if expected_token and not self._is_exempt(request.path):
            provided_token = request.headers.get(self.header_name)
            if not provided_token or not compare_digest(provided_token, expected_token):
                return JsonResponse(
                    {
                        "error": "invalid_token",
                        "message": "Invalid API token.",
                        "details": {},
                    },
                    status=401,
                )
        return self.get_response(request)

    def _is_exempt(self, path: str) -> bool:
        if path.startswith("/api/agents/") and path.endswith("/heartbeat"):
            return True
        return any(path.startswith(prefix) for prefix in self.exempt_prefixes)
