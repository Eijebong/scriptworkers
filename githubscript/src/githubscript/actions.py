from scriptworker.exceptions import TaskVerificationError
from taskcluster import Queue
import logging
from .utils import is_task_coming_from_pr

logger = logging.getLogger(__name__)


def _get_pr_info(context, args):
    if len(args) != 1:
        raise TaskVerificationError("You should provide one, and only one PR number")

    try:
        pr_number = int(args[0])
    except ValueError:
        raise TaskVerificationError("The given PR number isn't an int")

    if pr_number <= 0:
        raise TaskVerificationError(f"The PR number {pr_number} is wrong")

    owner = context.config["target"]["owner"]
    repo = context.config["target"]["repo"]
    task_id = context.task["taskGroupId"]

    if not is_task_coming_from_pr(context, task_id, owner, repo, pr_number):
        raise TaskVerificationError(
            f"This task was scheduled for pr {pr_number} but it doesn't seem to be coming from it"
        )

    return owner, repo, pr_number


async def _create_github_comment(context, owner, repo, pr_number, comment):
    path = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"

    logging.info(
        "Creating github comment on %s/%s with content %s" % (owner, repo, comment)
    )

    data = {"body": comment}

    resp = await context.github.post(path, data=data)
    resp.raise_for_status()


async def create_apdiff_comment_on_pr(context, args):
    owner, repo, pr_number = _get_pr_info(context, args)

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

    await _create_github_comment(context, owner, repo, pr_number, comment)


def apply_patch(context, args):
    raise NotImplemented("Not implemented yet")


async def create_aptest_comment_on_pr(context, args):
    owner, repo, pr_number = _get_pr_info(context, args)

    logger.info("Creating aptest comment for PR %s" % pr_number)
    payload = context.task["payload"]
    if "test-task" not in payload:
        raise TaskVerificationError("test-task is missing from the payload")

    test_task_id = payload["test-task"]

    logger.debug("Test task ID is %s" % test_task_id)
    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    artifacts = queue.listLatestArtifacts(test_task_id)["artifacts"]
    found_test = None
    for artifact in artifacts:
        if artifact["name"].endswith(".aptest"):
            found_test = artifact
            break

    if found_test:
        aptest_url = queue.getLatestArtifact(test_task_id, found_test)["url"]
        async with context.session.get(aptest_url) as r:
            r.raise_for_status()
            aptest_info = await r.json()
            apworld_name = aptest_info["apworld"]
            apworld_version = aptest_info["version"]

        comment = f"[Test failures for {apworld_name}:{apworld_version}](https://apdiff.bananium.fr/tests/{test_task_id})"
        await _create_github_comment(context, owner, repo, pr_number, comment)


ACTIONS = {
    "create-apdiff-comment-on-pr": create_apdiff_comment_on_pr,
    "create-aptest-comment-on-pr": create_aptest_comment_on_pr,
    "apply-patch": apply_patch,
}
