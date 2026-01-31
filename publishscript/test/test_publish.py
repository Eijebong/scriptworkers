import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from publishscript.publish import publish
from scriptworker.exceptions import TaskVerificationError


MOCK_PR_CHECK = "publishscript.publish.is_task_coming_from_pr"


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.config = {
        "target": {"owner": "Eijebong", "repo": "Archipelago-index"},
        "taskcluster_root_url": "https://taskcluster.bananium.fr",
    }
    ctx.task = {
        "taskGroupId": "task-group-123",
        "payload": {
            "pr-number": 42,
            "head-rev": "abc123",
            "diff-task": "diff-task-id",
        },
    }

    github = AsyncMock()
    merge_resp = AsyncMock()
    merge_resp.raise_for_status = MagicMock()
    github.put = AsyncMock(return_value=merge_resp)

    token_resp = AsyncMock()
    token_resp.raise_for_status = MagicMock()
    token_resp.json = MagicMock(return_value={"token": "fake-token"})
    github.post = AsyncMock(return_value=token_resp)
    github._installation_id = 12345

    ctx.github = github
    return ctx


def _common_patches():
    return [
        patch(MOCK_PR_CHECK, return_value=True),
        patch("publishscript.publish._ensure_repo", new_callable=AsyncMock, return_value="/tmp/fake-repo"),
        patch("publishscript.publish._run_git", new_callable=AsyncMock),
        patch("publishscript.publish._download_artifact", new_callable=AsyncMock, return_value="/tmp/fake.diff"),
        patch("publishscript.publish._run_patch", new_callable=AsyncMock),
        patch("os.path.getsize", return_value=100),
        patch("os.unlink"),
    ]


@pytest.mark.asyncio
async def test_publish_rejects_unrelated_task(context):
    with patch(MOCK_PR_CHECK, return_value=False):
        with pytest.raises(TaskVerificationError):
            await publish(context)


@pytest.mark.asyncio
async def test_publish_merges_pr(context):
    with contextmanager_stack(_common_patches()):
        await publish(context)

        context.github.put.assert_called_once_with(
            "/repos/Eijebong/Archipelago-index/pulls/42/merge",
            data={"merge_method": "squash", "sha": "abc123"},
        )


@pytest.mark.asyncio
async def test_publish_applies_lock_diff(context):
    patches = _common_patches()
    with contextmanager_stack(patches) as mocks:
        mock_git = mocks[2]
        mock_patch = mocks[4]

        await publish(context)

        mock_patch.assert_called_once_with("/tmp/fake.diff", "/tmp/fake-repo")
        mock_git.assert_any_call(["add", "index.lock"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_publish_with_expectations(context):
    context.task["payload"]["expectations-task"] = "expectations-task-id"

    patches = _common_patches()
    with contextmanager_stack(patches) as mocks:
        mock_git = mocks[2]
        mock_patch = mocks[4]

        await publish(context)

        assert mock_patch.call_count == 2
        mock_git.assert_any_call(["add", "meta"], cwd="/tmp/fake-repo")
        mock_git.assert_any_call(["add", "index.lock"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_publish_pushes_to_main(context):
    patches = _common_patches()
    with contextmanager_stack(patches) as mocks:
        mock_git = mocks[2]

        await publish(context)

        mock_git.assert_any_call(["push", "origin", "main"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_publish_skips_empty_lock_diff(context):
    patches = _common_patches()
    with contextmanager_stack(patches) as mocks:
        mock_getsize = mocks[5]
        mock_patch = mocks[4]
        mock_git = mocks[2]
        mock_getsize.return_value = 0

        await publish(context)

        mock_patch.assert_not_called()
        mock_git.assert_any_call(["push", "origin", "main"], cwd="/tmp/fake-repo")


from contextlib import contextmanager


@contextmanager
def contextmanager_stack(cms):
    if not cms:
        yield []
        return
    with cms[0] as val:
        with contextmanager_stack(cms[1:]) as rest:
            yield [val] + rest
