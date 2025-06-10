import pytest
from contextlib import nullcontext as does_not_raise
from githubscript import async_main
from pytest import raises
from scriptworker.client import Context
from scriptworker.exceptions import TaskVerificationError

from unittest.mock import AsyncMock, patch


async def call_main(repo, actions):
    context = Context()

    context.task = {
        "scopes": [
            f"ap:github:repo:{repo}",
            *[f"ap:github:action:{action}" for action in actions],
        ]
    }
    context.config = {
        "repos": {
            "archipelago-index": "Eijebong/Archipelago-index",
        },
        "github": {
            "app_id": "123",
            "private_key": "ZHVtbXkK",
        },
    }

    await async_main(context)

    assert context.config["target"]["owner"] == "Eijebong"
    assert context.config["target"]["repo"] == "Archipelago-index"
    return context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repo,action,expectation,verification",
    (
        pytest.param(
            "archipelago-index",
            "create-apdiff-comment-on-pr:97",
            does_not_raise(),
            lambda context, mocks: mocks[
                "create-apdiff-comment-on-pr"
            ].assert_called_with(context, ["97"]),
        ),
        pytest.param(
            "archipelago-index",
            "create-apdiff-comment-on-pr:97:98",
            does_not_raise(),
            lambda context, mocks: mocks[
                "create-apdiff-comment-on-pr"
            ].assert_called_with(context, ["97", "98"]),
        ),
        pytest.param(
            "archipelago-index",
            "apply-patch:main",
            does_not_raise(),
            lambda context, mocks: mocks["apply-patch"].assert_called_with(
                context, ["main"]
            ),
        ),
        pytest.param(
            "archipelago-index",
            "apply-patch",
            does_not_raise(),
            lambda context, mocks: mocks["apply-patch"].assert_called_with(context, []),
        ),
        pytest.param(
            "archipelago-index",
            "unknown-action",
            raises(TaskVerificationError),
            lambda: None,
        ),
    ),
)
async def test_one_action(repo, action, expectation, verification):
    mocked_actions = {
        "create-apdiff-comment-on-pr": AsyncMock(),
        "apply-patch": AsyncMock(),
    }

    with patch.dict("githubscript.actions.ACTIONS", mocked_actions), expectation as exc:
        context = await call_main(repo, [action])

    if exc is None:
        verification(context, mocked_actions)
