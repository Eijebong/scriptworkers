from apdiffscript import scopes
import pytest
from pytest import raises
from contextlib import nullcontext as does_not_raise
from scriptworker.exceptions import TaskVerificationError
from scriptworker.client import Context


@pytest.mark.parametrize(
    "task_scopes,action,exception",
    (
        pytest.param(
            ["ap:apdiff:action:diff"],
            ("diff",),
            does_not_raise(),
        ),
        pytest.param(
            [
                "ap:weird:action:diff",
                "ap:apdiff:action:diff",
            ],
            ("diff",),
            does_not_raise(),
        ),
        pytest.param(
            ["ap:apdiff:action:unsupported-action"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            [],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            [
                "ap:apdiff:action:diff",
                "ap:apdiff:action:merge",
            ],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap::apdiff:action:diff:"],
            None,
            raises(TaskVerificationError),
        ),
    ),
)
def test_extract_actions(task_scopes, action, exception):
    with exception as exc:
        result = scopes.extract_action_from_scopes(task_scopes)

    if exc is None:
        assert result == action


@pytest.mark.parametrize(
    "task_scopes,repo,exception",
    (
        pytest.param(
            ["ap:apdiff:repo:archipelago-review"],
            "Eijebong/Archipelago-review",
            does_not_raise(),
        ),
        pytest.param(
            ["ap:apdiff:repo:archipelago-review", "ap:weird:repo:archipelago-review"],
            "Eijebong/Archipelago-review",
            does_not_raise(),
        ),
        pytest.param(
            ["ap:apdiff:repo:unknown"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            [
                "ap:apdiff:repo:archipelago-review",
                "ap:apdiff:repo:staging-archipelago-review",
            ],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:weird:repo:archipelago-review"],
            None,
            raises(TaskVerificationError),
        ),
    ),
)
def test_extract_repo(task_scopes, repo, exception):
    context = Context()
    context.config = {
        "repos": {
            "archipelago-review": "Eijebong/Archipelago-review",
            "staging-archipelago-review": "Eijebong/staging-archipelago-review",
        }
    }
    with exception as exc:
        result = scopes.extract_target_repo_from_scopes(task_scopes, context)

    if exc is None:
        assert result == repo
