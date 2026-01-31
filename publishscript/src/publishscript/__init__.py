from .scopes import extract_target_repo_from_scopes
from .publish import publish
from simple_github import AppClient


async def async_main(context):
    task_scopes = context.task["scopes"]
    config = context.config

    target_repo = extract_target_repo_from_scopes(task_scopes, context)
    owner, repo = target_repo.split("/", 1)

    context.config["target"] = {
        "owner": owner,
        "repo": repo,
    }

    async with AppClient(
        config["github"]["app_id"],
        config["github"]["private_key"],
        owner,
        repositories=[repo],
    ) as github:
        context.github = github
        await publish(context)
