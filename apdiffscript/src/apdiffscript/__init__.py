import base64
from .scopes import extract_action_from_scopes, extract_target_repo_from_scopes
from simple_github import AppAuth, AppInstallationAuth
from .actions import ACTIONS


async def async_main(context):
    task_scopes = context.task["scopes"]
    config = context.config

    target_repo, key = extract_target_repo_from_scopes(task_scopes, context)
    owner, repo = target_repo.split("/", 1)

    context.config["target"] = {
        "key": key,
        "owner": owner,
        "repo": repo,
    }

    action, *args = extract_action_from_scopes(task_scopes)

    _, review_repo_name = context.config['target_repos'][context.config['target']['key']].split('/', 1)

    app_auth = AppAuth(config["github"]["app_id"], base64.b64decode(config["github"]["private_key"]))
    inst_auth = AppInstallationAuth(app_auth, owner, repositories=[review_repo_name])
    context.github_auth = inst_auth

    await ACTIONS[action](context, args)
