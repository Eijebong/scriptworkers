from publishscript import scopes
import pytest
from pytest import raises
from contextlib import nullcontext as does_not_raise
from scriptworker.exceptions import TaskVerificationError
from scriptworker.client import Context


@pytest.mark.parametrize(
    "task_scopes,repo,exception",
    (
        pytest.param(
            ["ap:publish:repo:archipelago-index"],
            "Eijebong/Archipelago-index",
            does_not_raise(),
        ),
        pytest.param(
            ["ap:publish:repo:archipelago-index", "ap:weird:repo:archipelago-index"],
            "Eijebong/Archipelago-index",
            does_not_raise(),
        ),
        pytest.param(
            ["ap:publish:repo:unknown"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            [
                "ap:publish:repo:archipelago-index",
                "ap:publish:repo:staging-archipelago-index",
            ],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:weird:repo:archipelago-index"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            [],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:publish:repo:"],
            None,
            raises(TaskVerificationError),
        ),
    ),
)
def test_extract_repo(task_scopes, repo, exception):
    context = Context()
    context.config = {
        "repos": {
            "archipelago-index": "Eijebong/Archipelago-index",
            "staging-archipelago-index": "Eijebong/staging-archipelago-index",
        }
    }
    with exception as exc:
        result = scopes.extract_target_repo_from_scopes(task_scopes, context)

    if exc is None:
        assert result == repo
