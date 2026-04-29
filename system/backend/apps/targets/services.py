class EnqueueUnavailable(Exception):
    pass


def enqueue_target_recompute(async_job) -> None:
    from apps.jobs.services import enqueue_task

    enqueue_task("recompute", async_job.request_payload, async_job=async_job)
