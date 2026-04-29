from django.db import connections


def get_component_statuses():
    database_status = "ok"
    try:
        connections["default"].ensure_connection()
    except Exception:
        database_status = "down"

    return {
        "api": "ok",
        "database": database_status,
        "redis": "ok",
        "worker": "ok",
    }
