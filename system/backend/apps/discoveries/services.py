from apps.jobs.services import enqueue_task, serialize_dt, serialize_job


class EnqueueUnavailable(Exception):
    pass


def enqueue_discovery(discovery) -> None:
    scope_value = discovery.scope_value or discovery.cidr
    enqueue_task(
        "discovery",
        {
            "discovery_id": discovery.id,
            "scope_type": discovery.scope_type,
            "scope_value": scope_value,
            "cidr": discovery.cidr,
            "ports": discovery.ports,
        },
        async_job=discovery.async_job,
    )


def serialize_discovery(discovery):
    scope_value = discovery.scope_value or discovery.cidr
    return {
        "id": discovery.id,
        "job_id": discovery.async_job_id,
        "status": discovery.status,
        "progress": discovery.async_job.progress,
        "scope_type": discovery.scope_type,
        "scope_value": scope_value,
        "cidr": discovery.cidr,
        "port_list": discovery.ports,
        "ports": discovery.ports,
        "include_default_ports": discovery.include_default_ports,
        "created_at": serialize_dt(discovery.created_at),
        "started_at": serialize_dt(discovery.started_at),
        "finished_at": serialize_dt(discovery.finished_at),
        "error": discovery.error,
    }


def serialize_endpoint(endpoint):
    return {
        "id": endpoint.id,
        "ip": endpoint.host,
        "host": endpoint.host,
        "port": endpoint.port,
        "transport": endpoint.transport,
        "detected_protocol": endpoint.detected_protocol,
        "banner_metadata": {},
        "suggested_protocol_hint": endpoint.suggested_protocol_hint,
        "suggested_host": endpoint.host,
        "promoted": endpoint.promoted,
        "target_id": endpoint.target_id,
    }


def discovery_job_envelope(discovery):
    return serialize_job(discovery.async_job)
