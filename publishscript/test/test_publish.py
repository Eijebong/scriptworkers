import pytest
from contextlib import contextmanager, ExitStack
from unittest.mock import AsyncMock, MagicMock, patch, call
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


@contextmanager
def _enter_patches(cms):
    with ExitStack() as stack:
        yield [stack.enter_context(cm) for cm in cms]


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
    with _enter_patches(_common_patches()):
        await publish(context)

        context.github.put.assert_called_once_with(
            "/repos/Eijebong/Archipelago-index/pulls/42/merge",
            data={"merge_method": "squash", "sha": "abc123"},
        )


@pytest.mark.asyncio
async def test_publish_does_dry_run_before_merge(context):
    patches = _common_patches()
    with _enter_patches(patches) as mocks:
        mock_git = mocks[2]
        mock_run_patch = mocks[4]

        await publish(context)

        # Dry run patch should happen before the merge API call
        mock_run_patch.assert_any_call("/tmp/fake.diff", "/tmp/fake-repo", dry_run=True)

        # Verify squash merge simulation happened
        mock_git.assert_any_call(["fetch", "origin", "pull/42/head:pr-head"], cwd="/tmp/fake-repo")
        mock_git.assert_any_call(["merge", "--squash", "pr-head"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_publish_applies_lock_diff(context):
    patches = _common_patches()
    with _enter_patches(patches) as mocks:
        mock_git = mocks[2]
        mock_run_patch = mocks[4]

        await publish(context)

        # Real apply (without dry_run)
        mock_run_patch.assert_any_call("/tmp/fake.diff", "/tmp/fake-repo")
        mock_git.assert_any_call(["add", "index.lock"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_publish_with_expectations(context):
    context.task["payload"]["expectations-task"] = "expectations-task-id"

    patches = _common_patches()
    with _enter_patches(patches) as mocks:
        mock_git = mocks[2]
        mock_run_patch = mocks[4]

        await publish(context)

        # 2 dry runs + 2 real applies = 4
        assert mock_run_patch.call_count == 4
        mock_git.assert_any_call(["add", "meta"], cwd="/tmp/fake-repo")
        mock_git.assert_any_call(["add", "index.lock"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_publish_pushes_to_main(context):
    patches = _common_patches()
    with _enter_patches(patches) as mocks:
        mock_git = mocks[2]

        await publish(context)

        mock_git.assert_any_call(["push", "origin", "main"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_publish_skips_empty_lock_diff(context):
    patches = _common_patches()
    with _enter_patches(patches) as mocks:
        mock_getsize = mocks[5]
        mock_run_patch = mocks[4]
        mock_git = mocks[2]
        mock_getsize.return_value = 0

        await publish(context)

        mock_run_patch.assert_not_called()
        mock_git.assert_any_call(["push", "origin", "main"], cwd="/tmp/fake-repo")


@pytest.mark.asyncio
async def test_dry_run_failure_prevents_merge(context):
    patches = _common_patches()
    with _enter_patches(patches) as mocks:
        mock_run_patch = mocks[4]
        mock_run_patch.side_effect = RuntimeError("patch dry-run failed")

        with pytest.raises(RuntimeError, match="patch dry-run failed"):
            await publish(context)

        # Merge should never have been called
        context.github.put.assert_not_called()
