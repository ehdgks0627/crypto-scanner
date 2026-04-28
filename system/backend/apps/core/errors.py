from django.http import JsonResponse
from ninja.errors import ValidationError


def error_response(error: str, message: str, details: dict | None = None, status: int = 400):
    return JsonResponse(
        {
            "error": error,
            "message": message,
            "details": details or {},
        },
        status=status,
    )


def validation_error_handler(request, exc: ValidationError):
    return error_response(
        "unprocessable",
        "Request validation failed.",
        {"validation_errors": exc.errors},
        status=422,
    )


def register_exception_handlers(api) -> None:
    api.add_exception_handler(ValidationError, validation_error_handler)
