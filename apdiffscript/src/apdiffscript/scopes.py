from scriptworker.exceptions import TaskVerificationError
from scriptworker_common import extract_scopes
from .actions import ACTIONS

SCOPE_PREFIX = "ap:apdiff"


def extract_action_from_scopes(scopes):
    actions = extract_scopes(SCOPE_PREFIX, "action", scopes, only_one=False)
    if len(actions) != 1:
        raise TaskVerificationError("apdiffscript can only execute one action at a time")

    action, *_ = actions[0]

    if action not in ACTIONS.keys():
        raise TaskVerificationError(f"The action {action} is not valid")

    return actions[0]


def extract_target_repo_from_scopes(scopes, context):
    allowed_repos = context.config["repos"]
    repo = extract_scopes(SCOPE_PREFIX, "repo", scopes, only_one=True)[0]

    if repo not in allowed_repos:
        raise TaskVerificationError(f"Unknown repository {repo}")

    return allowed_repos[repo], repo
