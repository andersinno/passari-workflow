"""
Enqueue objects to be downloaded in the background.

Similar to 'enqueue-objects', but objects are enqueued using a background RQ
job, ensuring the command returns immediately
"""
import click

from passari_workflow.queue.queues import QueueType, get_queue
from passari_workflow.jobs.enqueue_objects import enqueue_objects


def deferred_enqueue_objects(object_count=None, object_ids=None):
    """
    Enqueue given number of objects to the preservation workflow using a
    background RQ job

    :param int object_count: How many objects to enqueue at most
    :param list object_ids: Specific object IDs to enqueue
    """
    queue = get_queue(QueueType.ENQUEUE_OBJECTS)

    if object_ids:
        queue.enqueue(enqueue_objects, kwargs={"object_ids": object_ids})
        print(f"{len(object_ids)} object(s) with IDs {object_ids} will be enqueued")
    else:
        queue.enqueue(enqueue_objects, kwargs={"object_count": object_count})
        print(f"{object_count} object(s) will be enqueued")

    return object_count or len(object_ids)


@click.command()
@click.option(
    "--object-count", type=int, default=None,
    help="How many objects to enqueue"
)
@click.option(
    "--object-ids", type=str, default=None,
    help="Comma-separated list of specific object IDs to enqueue, e.g., '1,2,3,4'"
)
def cli(object_count, object_ids):
    if object_count and object_ids:
        raise click.UsageError(
            "You cannot use both --object-count and --object-ids at the same time."
        )

    if not object_count and not object_ids:
        raise click.UsageError(
            "You must provide either --object-count or --object-ids."
        )

    object_ids_list = object_ids.split(",") if object_ids else None
    deferred_enqueue_objects(
        object_count=object_count,
        object_ids=object_ids_list
    )


if __name__ == "__name__":
    cli()
