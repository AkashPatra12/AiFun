def enqueue_job(job: dict) -> None:
    """Push a render-job.schema.json job onto the Redis queue."""
    raise NotImplementedError


def run_worker() -> None:
    """Pull jobs off the queue, run the render pipeline, call notify_complete."""
    raise NotImplementedError
