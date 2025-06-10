from taskcluster import Github, Queue
import os


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
