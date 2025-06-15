from scriptworker.exceptions import TaskVerificationError
from taskcluster import Github, Queue
import os


def extract_scopes(global_prefix, prefix, scopes, *, only_one=True):
    full_prefix = f"{global_prefix}:{prefix}"
    if not scopes:
        raise TaskVerificationError(
            f"You should pass at least one scope with the prefix {full_prefix}"
        )

    relevant_scopes = list(scope for scope in scopes if scope.startswith(full_prefix))

    if not relevant_scopes:
        raise TaskVerificationError(f"No {prefix} scope found")

    if only_one and len(relevant_scopes) > 1:
        raise TaskVerificationError("More than one {prefix} scope found")

    scopes = [
        tuple(scope[len(full_prefix) + 1 :].split(":")) for scope in relevant_scopes
    ]

    if any(part == "" for scope in scopes for part in scope):
        raise TaskVerificationError("Cannot pass empty argument in scope value")

    if only_one:
        return scopes[0]

    return scopes


def is_task_coming_from_pr(context, task_id, owner, repo, pr_number):
    tc_config = {
        "rootUrl": context.config["taskcluster_root_url"],
        "credentials": {
            "accessToken": os.environ.get("TASKCLUSTER_ACCESS_TOKEN"),
            "clientId": os.environ.get("TASKCLUSTER_CLIENT_ID"),
        },
    }

    gh = Github(tc_config)
    queue = Queue(tc_config)

    task_group_id = queue.task(task_id)["taskGroupId"]
    builds_for_pr = gh.builds(
        query={"pullRequest": pr_number, "organization": owner, "repository": repo}
    )["builds"]

    return any(build["taskGroupId"] == task_group_id for build in builds_for_pr)
