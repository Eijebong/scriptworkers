from scriptworker.exceptions import TaskVerificationError
from taskcluster import Queue
import logging

logger = logging.getLogger(__name__)


async def create_apdiff_comment_on_pr(context, args):
    if len(args) != 1:
        raise TaskVerificationError("You should provide one, and only one PR number")

    try:
        pr_number = int(args[0])
    except ValueError:
        raise TaskVerificationError("The given PR number isn't an int")

    logger.info("Creating apdiff comment for PR %s" % pr_number)

    payload = context.task["payload"]
    if "diff-task" not in payload:
        raise TaskVerificationError("diff-task is missing from the payload")

    diff_task_id = payload["diff-task"]

    logger.debug("Diff task ID is %s" % diff_task_id)
    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    artifacts = queue.listLatestArtifacts(diff_task_id)["artifacts"]
    found_diff = None
    for artifact in artifacts:
        if artifact["name"].endswith(".apdiff"):
            found_diff = artifact
            break

    if found_diff:
        comment = f"[Review changes](https://apdiff.bananium.fr/{diff_task_id})"
    else:
        comment = "No reviewable change"


    owner = context.config["target"]["owner"]
    repo = context.config["target"]["repo"]
    path = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"

    logging.info("Creating github comment on %s/%s with content %s" % (owner, repo, comment))

    data = {"body": comment}

    resp = await context.github.post(path, data=data)
    resp.raise_for_status()



def apply_patch(context, args):
    raise NotImplemented("Not implemented yet")


ACTIONS = {
    "create-apdiff-comment-on-pr": create_apdiff_comment_on_pr,
    "apply-patch": apply_patch,
}
