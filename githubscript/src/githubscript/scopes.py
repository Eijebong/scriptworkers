from scriptworker.exceptions import TaskVerificationError
from .actions import ACTIONS

SCOPE_PREFIX = "ap:github"


def _extract_scopes(prefix, scopes, *, only_one=True):
    full_prefix = f"{SCOPE_PREFIX}:{prefix}"
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


def extract_actions_from_scopes(scopes):
    actions = _extract_scopes("action", scopes, only_one=False)

    for (action, *_) in actions:
        if action not in ACTIONS:
            raise TaskVerificationError(f"The action {action} is not valid")

    return actions


def extract_target_repo_from_scopes(scopes, context):
    allowed_repos = context.config["repos"]
    repo = _extract_scopes("repo", scopes, only_one=True)[0]

    if repo not in allowed_repos:
        raise TaskVerificationError(f"Unknown repository {repo}")

    return allowed_repos[repo]
