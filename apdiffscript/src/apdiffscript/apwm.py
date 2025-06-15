import logging
from taskcluster import Queue
import os

logger = logging.getLogger(__name__)

async def download_apworld(context, name, version, output):
    diff_task_id = context.task['payload']['diff-task']

    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    artifact_name = f"public/diffs/{name}-{version}.apworld"
    result_path = os.path.join(output, f"{name}-{version}.apworld")
    artifact_url = queue.getLatestArtifact(diff_task_id, artifact_name)['url']

    async with context.session.get(artifact_url) as r:
        r.raise_for_status()
        with open(result_path, "wb") as fd:
            fd.write(await r.read())

    return result_path
