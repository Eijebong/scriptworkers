import pytest

from contextlib import nullcontext as does_not_raise
from githubscript.actions import create_apdiff_comment_on_pr
from pytest import raises
from scriptworker.client import Context
from scriptworker.exceptions import TaskVerificationError
from unittest.mock import Mock, patch, AsyncMock


def _get_task_context():
    context = Context()
    payload = {"diff-task": "abc"}

    context.task = {"payload": payload}

    context.config = {
        "taskcluster_root_url": "http://nowhere",
        "target": {
            "owner": "foo",
            "repo": "bar",
        },
    }

    context.github = AsyncMock()

    return context


MOCK_QUEUE = Mock()
MOCK_QUEUE.return_value.listLatestArtifacts.return_value = {"artifacts": []}


@pytest.mark.parametrize(
    "params,expectation",
    (
        pytest.param([], raises(TaskVerificationError)),
        pytest.param(["1", "2"], raises(TaskVerificationError)),
        pytest.param(["a"], raises(TaskVerificationError)),
        pytest.param(["1"], does_not_raise()),
    ),
)
@patch("githubscript.actions.Queue", MOCK_QUEUE)
@pytest.mark.asyncio
async def test_args(params, expectation):
    context = _get_task_context()
    with expectation:
        await create_apdiff_comment_on_pr(context, params)


@patch("githubscript.actions.Queue", MOCK_QUEUE)
@pytest.mark.asyncio
async def test_schema():
    context = _get_task_context()
    context.task["payload"] = {}
    with pytest.raises(TaskVerificationError):
        await create_apdiff_comment_on_pr(context, ["97"])


@pytest.mark.asyncio
async def test_empty_diff():
    context = _get_task_context()
    MOCK_QUEUE.reset_mock()
    MOCK_QUEUE.return_value.listLatestArtifacts.return_value = {
        "artifacts": [{"name": "foo.log"}]
    }

    with patch("githubscript.actions.Queue", MOCK_QUEUE):
        await create_apdiff_comment_on_pr(context, ["97"])

    context.github.post.assert_called_with(
        "/repos/foo/bar/issues/97/comments", data={"body": "No reviewable change"}
    )


@pytest.mark.asyncio
async def test_normal_diff():
    context = _get_task_context()
    MOCK_QUEUE.reset_mock()
    MOCK_QUEUE.return_value.listLatestArtifacts.return_value = {
        "artifacts": [{"name": "foo.log"}, {"name": "foo.apdiff"}]
    }

    with patch("githubscript.actions.Queue", MOCK_QUEUE):
        await create_apdiff_comment_on_pr(context, ["97"])

    context.github.post.assert_called_with(
        "/repos/foo/bar/issues/97/comments",
        data={"body": "[Review changes](https://apdiff.bananium.fr/abc)"},
    )
