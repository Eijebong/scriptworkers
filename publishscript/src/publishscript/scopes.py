from scriptworker.exceptions import TaskVerificationError

SCOPE_PREFIX = "ap:publish"


def _extract_scope(prefix, scopes):
    full_prefix = f"{SCOPE_PREFIX}:{prefix}"
    if not scopes:
        raise TaskVerificationError(
            f"You should pass at least one scope with the prefix {full_prefix}"
        )

    relevant_scopes = [scope for scope in scopes if scope.startswith(full_prefix)]

    if not relevant_scopes:
        raise TaskVerificationError(f"No {prefix} scope found")

    if len(relevant_scopes) > 1:
        raise TaskVerificationError(f"More than one {prefix} scope found")

    value = relevant_scopes[0][len(full_prefix) + 1:]
    if not value:
        raise TaskVerificationError("Cannot pass empty argument in scope value")

    return value


def extract_target_repo_from_scopes(scopes, context):
    allowed_repos = context.config["repos"]
    repo = _extract_scope("repo", scopes)

    if repo not in allowed_repos:
        raise TaskVerificationError(f"Unknown repository {repo}")

    return allowed_repos[repo]
