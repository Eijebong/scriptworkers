import pytest

from contextlib import nullcontext as does_not_raise
from githubscript.actions import create_aptest_comment_on_pr
from pytest import raises
from scriptworker.client import Context
from scriptworker.exceptions import TaskVerificationError
from unittest.mock import Mock, patch, AsyncMock


def _get_task_context():
    context = Context()
    payload = {"test-task": "abc"}

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
        pytest.param(["-1"], raises(TaskVerificationError)),
    ),
)
@patch("githubscript.actions.Queue", MOCK_QUEUE)
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@pytest.mark.asyncio
async def test_args(params, expectation):
    context = _get_task_context()
    with expectation:
        await create_aptest_comment_on_pr(context, params)


@patch("githubscript.actions.Queue", MOCK_QUEUE)
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@pytest.mark.asyncio
async def test_schema():
    context = _get_task_context()
    context.task["payload"] = {}
    with pytest.raises(TaskVerificationError):
        await create_aptest_comment_on_pr(context, ["97"])


@pytest.mark.asyncio
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
async def test_no_aptest():
    context = _get_task_context()
    MOCK_QUEUE.reset_mock()
    MOCK_QUEUE.return_value.listLatestArtifacts.return_value = {
        "artifacts": [{"name": "foo.log"}]
    }

    with patch("githubscript.actions.Queue", MOCK_QUEUE):
        await create_aptest_comment_on_pr(context, ["97"])

    context.github.post.assert_not_called()


@pytest.mark.asyncio
@patch("githubscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
async def test_aptest():
    context = _get_task_context()
    MOCK_QUEUE.reset_mock()
    MOCK_QUEUE.return_value.listLatestArtifacts.return_value = {
        "artifacts": [{"name": "foo.log"}, {"name": "foo.aptest"}]
    }

    MOCK_QUEUE.return_value.getLatestArtifact.return_value = {
        "url": "https://nowhere/artifact"
    }
    context.session = Mock()
    context.session.get.return_value = AsyncMock()
    context.session.get.return_value.__aenter__.return_value.raise_for_status = Mock()
    context.session.get.return_value.__aenter__.return_value.json.return_value = {
        "apworld": "foo",
        "version": "42.0.0",
    }

    with patch("githubscript.actions.Queue", MOCK_QUEUE):
        await create_aptest_comment_on_pr(context, ["97"])

    context.github.post.assert_called_with(
        "/repos/foo/bar/issues/97/comments",
        data={
            "body": "[Test failures for foo:42.0.0](https://apdiff.bananium.fr/tests/abc)"
        },
    )
