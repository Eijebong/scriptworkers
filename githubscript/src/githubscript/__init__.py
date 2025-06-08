import base64
from .scopes import extract_actions_from_scopes, extract_target_repo_from_scopes
from simple_github import AppClient
from .actions import ACTIONS


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

    async with AppClient(
        config["github"]["app_id"],
        base64.b64decode(config["github"]["private_key"]),
        owner,
        repositories=[repo],
    ) as github:
        context.github = github

        for (action, *args) in actions:
            await ACTIONS[action](context, args)
