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

    context.task = {"payload": payload, "taskGroupId": "UCy202ZHSL-t1AIHG9f2aw"}

    context.config = {
        "taskcluster_root_url": "http://nowhere",
        "target": {
            "owner": "foo",
            "repo": "bar",
        },
    }

    context.github = AsyncMock()
    context.github.post.return_value = Mock()

    return context


MOCK_QUEUE = Mock()
MOCK_QUEUE.return_value.listLatestArtifacts.return_value = {"artifacts": []}

MOCK_UTILS_IS_TASK_COMING_FROM_PR = Mock()
MOCK_UTILS_IS_TASK_COMING_FROM_PR.return_value = True


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
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@pytest.mark.asyncio
async def test_args(params, expectation):
    context = _get_task_context()
    with expectation:
        await create_apdiff_comment_on_pr(context, params)


@patch("githubscript.actions.Queue", MOCK_QUEUE)
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@pytest.mark.asyncio
async def test_schema():
    context = _get_task_context()
    context.task["payload"] = {}
    with pytest.raises(TaskVerificationError):
        await create_apdiff_comment_on_pr(context, ["97"])


@pytest.mark.asyncio
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
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
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
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


@pytest.mark.asyncio
async def test_refuse_for_wrong_pr():
    context = _get_task_context()
    MOCK_QUEUE.reset_mock()

    task_not_coming_from_pr = Mock()
    task_not_coming_from_pr.return_value = False

    with patch("githubscript.actions.Queue", MOCK_QUEUE), patch(
        "githubscript.actions.is_task_coming_from_pr", task_not_coming_from_pr
    ), pytest.raises(TaskVerificationError):
        await create_apdiff_comment_on_pr(context, ["97"])

    task_not_coming_from_pr.assert_called_with(
        context, "UCy202ZHSL-t1AIHG9f2aw", "foo", "bar", 97
    )
    MOCK_QUEUE.return_value.listLatestArtifacts.assert_not_called()
    context.github.post.assert_not_called()
