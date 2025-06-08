from githubscript import scopes
import pytest
from pytest import raises
from contextlib import nullcontext as does_not_raise
from scriptworker.exceptions import TaskVerificationError
from scriptworker.client import Context


@pytest.mark.parametrize(
    "task_scopes,action,exception",
    (
        pytest.param(
            ["ap:github:action:create-apdiff-comment-on-pr:97"],
            [("create-apdiff-comment-on-pr", "97")],
            does_not_raise(),
        ),
        pytest.param(
            [
                "ap:weird:action:apply-patch:98",
                "ap:github:action:create-apdiff-comment-on-pr:97",
            ],
            [("create-apdiff-comment-on-pr", "97")],
            does_not_raise(),
        ),
        pytest.param(
            ["ap:github:action:unsupported-action:97"],
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
                "ap:github:action:create-apdiff-comment-on-pr:97",
                "ap:github:action:apply-patch:main",
            ],
            [("create-apdiff-comment-on-pr", "97"), ("apply-patch", "main")],
            does_not_raise(),
        ),
        pytest.param(
            [
                "ap:github:action:create-apdiff-comment-on-pr:97",
                "ap:github:action:create-apdiff-comment-on-pr:98",
            ],
            [
                ("create-apdiff-comment-on-pr", "97"),
                ("create-apdiff-comment-on-pr", "98"),
            ],
            does_not_raise(),
        ),
        pytest.param(
            ["ap:github:action:create-apdiff-comment-on-pr:"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:github:action:create-apdiff-comment-on-pr:97:"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:github:action:create-apdiff-comment-on-pr::"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:weird:action:create-apdiff-comment-on-pr:97"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:github:action:create-apdiff-comment-on-pr"],
            [("create-apdiff-comment-on-pr",)],
            does_not_raise(),
        ),
        pytest.param(
            ["ap:github:action:unknown"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:github:action:create-apdiff-comment-on-pr:97:98"],
            [("create-apdiff-comment-on-pr", "97", "98")],
            does_not_raise(),
        ),
    ),
)
def test_extract_actions(task_scopes, action, exception):
    with exception as exc:
        result = scopes.extract_actions_from_scopes(task_scopes)

    if exc is None:
        assert result == action


@pytest.mark.parametrize(
    "task_scopes,repo,exception",
    (
        pytest.param(
            ["ap:github:repo:archipelago-index"],
            "Eijebong/Archipelago-index",
            does_not_raise(),
        ),
        pytest.param(
            ["ap:github:repo:archipelago-index", "ap:weird:repo:archipelago-index"],
            "Eijebong/Archipelago-index",
            does_not_raise(),
        ),
        pytest.param(
            ["ap:github:repo:unknown"],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            [
                "ap:github:repo:archipelago-index",
                "ap:github:repo:staging-archipelago-index",
            ],
            None,
            raises(TaskVerificationError),
        ),
        pytest.param(
            ["ap:weird:repo:archipelago-index"],
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
