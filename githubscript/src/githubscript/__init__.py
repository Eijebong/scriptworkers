import base64
import os
from scriptworker.exceptions import TaskVerificationError
from .scopes import extract_actions_from_scopes, extract_target_repo_from_scopes
from simple_github import AppClient
from .actions import ACTIONS


def _check_requirements(actions, config):
    requirements = set()
    for (action, *_) in actions:
        requirements.add(ACTIONS[action]["requires"])

    github_config = config.get("github", {})
    has_github = github_config.get("app_id") and github_config.get("private_key")
    if "github" in requirements and not has_github:
        raise TaskVerificationError(
            "This worker is not configured with GitHub credentials, "
            f"cannot run actions: {', '.join(a for a, *_ in actions if ACTIONS[a]['requires'] == 'github')}"
        )

    if "apdiff" in requirements and not os.environ.get("APDIFF_API_KEY"):
        raise TaskVerificationError(
            "This worker is not configured with APDIFF_API_KEY, "
            f"cannot run actions: {', '.join(a for a, *_ in actions if ACTIONS[a]['requires'] == 'apdiff')}"
        )

    return requirements


async def async_main(context):
    task_scopes = context.task["scopes"]
    config = context.config

    target_repo = extract_target_repo_from_scopes(task_scopes, context)
    owner, repo = target_repo.split("/", 1)

    context.config["target"] = {
        "owner": owner,
        "repo": repo,
    }

    actions = extract_actions_from_scopes(task_scopes)
    requirements = _check_requirements(actions, config)

    if "github" in requirements:
        async with AppClient(
            config["github"]["app_id"],
            base64.b64decode(config["github"]["private_key"]),
            owner,
            repositories=[repo],
        ) as github:
            context.github = github

            for (action, *args) in actions:
                await ACTIONS[action]["handler"](context, args)
    else:
        for (action, *args) in actions:
            await ACTIONS[action]["handler"](context, args)
