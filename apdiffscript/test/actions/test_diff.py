import json
import pytest

from apdiffscript.actions import diff_from_task, _get_repo_cache_for_branch, _handle_apworld_change
from contextlib import nullcontext as does_not_raise
from scriptworker.client import Context
from scriptworker.exceptions import TaskVerificationError
from unittest.mock import Mock, patch, AsyncMock, call, MagicMock
from pytest import raises
from semver import Version

MOCK_UTILS_IS_TASK_COMING_FROM_PR = Mock(return_value=True)

MOCK_HANDLE_APWORLD_CHANGE = AsyncMock()

MOCK_QUEUE = Mock()
MOCK_QUEUE().getLatestArtifact.return_value = {"url": "https://nowhere/artifact"}

MOCK_GET_REPO_CACHE_FOR_BRANCH = Mock()

@pytest.fixture
def task_context():
    context = Context()
    payload = {"diff-task": "abc"}
    context.task = {
        "payload": payload,
        "taskGroupId": "UCy202ZHSL-t1AIHG9f2aw"
    }
    context.config = {
        "taskcluster_root_url": "http://nowhere",
        "target": {
            "owner": "foo",
            "repo": "bar",
        },
        'repo_cache': '/mock/cache/path',
    }
    context.github_auth = AsyncMock()
    context.github_auth.get_token.return_value = "abc"

    session_mock = Mock()
    session_response_mock = AsyncMock()
    session_response_mock.__aenter__.return_value.raise_for_status = Mock()
    session_response_mock.__aenter__.return_value.read.return_value = json.dumps({}).encode()
    session_mock.get.return_value = session_response_mock

    context.session = session_mock

    return context


@pytest.fixture
def mock_repo():
    return MagicMock()


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
@patch("apdiffscript.actions.Queue", MOCK_QUEUE)
@patch("apdiffscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@patch("apdiffscript.actions._get_repo_cache_for_branch", MOCK_GET_REPO_CACHE_FOR_BRANCH)
@pytest.mark.asyncio
async def test_args(task_context, params, expectation):
    with expectation:
        await diff_from_task(task_context, params)

@patch("apdiffscript.actions.Queue", MOCK_QUEUE)
@patch("apdiffscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@patch("apdiffscript.actions._get_repo_cache_for_branch", MOCK_GET_REPO_CACHE_FOR_BRANCH)
@pytest.mark.asyncio
async def test_schema(task_context):
    task_context.task["payload"] = {"foo": "bar"}
    with pytest.raises(TaskVerificationError):
        await diff_from_task(task_context, ["97"])

@patch("apdiffscript.actions.Queue", MOCK_QUEUE)
@patch("apdiffscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@patch("apdiffscript.actions._handle_apworld_change", MOCK_HANDLE_APWORLD_CHANGE)
@patch("apdiffscript.actions._get_repo_cache_for_branch", MOCK_GET_REPO_CACHE_FOR_BRANCH)
@pytest.mark.asyncio
async def test_empty_diff(task_context):
    await diff_from_task(task_context, ["97"])

    MOCK_HANDLE_APWORLD_CHANGE.assert_not_called()

@patch("apdiffscript.actions.Queue", MOCK_QUEUE)
@patch("apdiffscript.actions.is_task_coming_from_pr", MOCK_UTILS_IS_TASK_COMING_FROM_PR)
@patch("apdiffscript.actions._handle_apworld_change", MOCK_HANDLE_APWORLD_CHANGE)
@patch("apdiffscript.actions._get_repo_cache_for_branch", MOCK_GET_REPO_CACHE_FOR_BRANCH)
@pytest.mark.asyncio
async def test_normal_diff(task_context):
    MOCK_HANDLE_APWORLD_CHANGE.reset_mock()
    MOCK_QUEUE.reset_mock()
    MOCK_GET_REPO_CACHE_FOR_BRANCH.reset_mock()

    apdiff_info = {
        "pokemon_crystal": [
            {"Added": ["4.0.0-beta.8", "44bc633b96a22da00db1fb60cc7f5a89031a9f907cc974bd4aa481624dec03e5"]},
            {"Added": ["4.0.0-beta.9", "400eab47b8601d6d5babe76d8d13279b9eab7aa0ede3fc2f053a47fc99f85185"]}
        ],
        "pokemon_frlg": [
            {"Added": ["42.0.0", "45bc633b96a22da00db1fb60cc7f5a89031a9f907cc974bd4aa481624dec03e5"]},
        ]
    }

    task_context.session.get.return_value.__aenter__.return_value.read.return_value = json.dumps(apdiff_info).encode()

    await diff_from_task(task_context, ["97"])

    MOCK_QUEUE.return_value.getLatestArtifact.assert_called_once_with('abc', 'public/diff/apdiff.diff')
    task_context.session.get.assert_called_once_with("https://nowhere/artifact")
    task_context.session.get.return_value.__aenter__.return_value.raise_for_status.assert_called_once()

    expected_handle_apworlds_calls = [
        call(task_context, "pokemon_crystal", {"Added": ["4.0.0-beta.8", "44bc633b96a22da00db1fb60cc7f5a89031a9f907cc974bd4aa481624dec03e5"]}, MOCK_GET_REPO_CACHE_FOR_BRANCH.return_value),
        call(task_context, "pokemon_crystal", {"Added": ["4.0.0-beta.9", "400eab47b8601d6d5babe76d8d13279b9eab7aa0ede3fc2f053a47fc99f85185"]}, MOCK_GET_REPO_CACHE_FOR_BRANCH.return_value),
        call(task_context, "pokemon_frlg", {"Added": ["42.0.0", "45bc633b96a22da00db1fb60cc7f5a89031a9f907cc974bd4aa481624dec03e5"]}, MOCK_GET_REPO_CACHE_FOR_BRANCH.return_value),
    ]

    expected_get_repo_cache_for_branch_calls = [
        call(task_context, 'foo', 'bar', 'pr-97-pokemon_crystal', overwrite_branch=True),
        call().remotes.origin.set_url('https://git:abc@github.com:/foo/bar'),
        call().remotes.origin.push('pr-97-pokemon_crystal', force=True),
        call(task_context, 'foo', 'bar', 'pr-97-pokemon_frlg', overwrite_branch=True),
        call().remotes.origin.set_url('https://git:abc@github.com:/foo/bar'),
        call().remotes.origin.push('pr-97-pokemon_frlg', force=True),
    ]

    MOCK_HANDLE_APWORLD_CHANGE.assert_has_calls(expected_handle_apworlds_calls)
    MOCK_GET_REPO_CACHE_FOR_BRANCH.assert_has_calls(expected_get_repo_cache_for_branch_calls)


@patch('os.makedirs')
@patch('os.path.exists', return_value=False)
@patch('apdiffscript.actions.Repo.clone_from')
def test_clone_repository(mock_clone_from, mock_exists, mock_makedirs, task_context):
    _get_repo_cache_for_branch(task_context, 'owner', 'repo_name', 'branch')

    mock_makedirs.assert_called_once_with('/mock/cache/path/owner_repo_name', exist_ok=True)
    mock_clone_from.assert_called_once_with('https://github.com/owner/repo_name.git', '/mock/cache/path/owner_repo_name')

@patch('os.makedirs')
@patch('os.path.exists', return_value=True)
@patch('apdiffscript.actions.Repo')
def test_fetch_existing_repository(mock_repo_class, mock_exists, mock_makedirs, task_context, mock_repo):
    mock_repo_class.return_value = mock_repo

    _get_repo_cache_for_branch(task_context, 'owner', 'repo_name', 'branch')

    mock_makedirs.assert_called_once_with('/mock/cache/path/owner_repo_name', exist_ok=True)
    mock_repo.remotes.origin.fetch.assert_called_once()


@patch('os.makedirs')
@patch('os.path.exists', return_value=True)
@patch('apdiffscript.actions.Repo')
def test_create_local_branch(mock_repo_class, mock_exists, mock_makedirs, task_context, mock_repo):
    branch_name = 'branch'

    mock_ref = MagicMock()
    mock_ref.name = f'refs/remotes/origin/{branch_name}'
    mock_local_ref = MagicMock()
    mock_local_ref.name = f'refs/heads/{branch_name}'
    mock_origin = MagicMock()
    mock_origin.refs = [mock_ref]

    mock_repo.remotes.origin = mock_origin
    mock_repo.refs = [mock_local_ref]

    mock_repo_class.return_value = mock_repo

    _get_repo_cache_for_branch(task_context, 'owner', 'repo_name', branch_name)

    mock_makedirs.assert_called_once_with('/mock/cache/path/owner_repo_name', exist_ok=True)
    mock_repo.delete_head.assert_called_once_with(branch_name, force=True)
    mock_repo.create_head.assert_called_once_with(branch_name, commit=mock_ref.name)
    mock_repo.heads[branch_name].checkout.assert_called_once()
    mock_repo.git.reset.assert_any_call('--hard', mock_ref.name)


@patch('os.makedirs')
@patch('os.path.exists', return_value=True)
@patch('apdiffscript.actions.Repo')
def test_create_local_branch_non_existent(mock_repo_class, mock_exists, mock_makedirs, task_context, mock_repo):
    branch_name = 'branch'

    mock_origin = MagicMock()

    mock_origin.refs = []
    mock_repo.remotes.origin = mock_origin
    mock_repo_class.return_value = mock_repo

    _get_repo_cache_for_branch(task_context, 'owner', 'repo_name', branch_name)

    mock_makedirs.assert_called_once_with('/mock/cache/path/owner_repo_name', exist_ok=True)
    mock_repo.git.checkout.assert_called_once_with('--orphan', branch_name)
    mock_repo.git.reset.assert_any_call('--hard')


@patch('os.makedirs')
@patch('os.path.exists', return_value=True)
@patch('apdiffscript.actions.Repo')
def test_cleanup(mock_repo_class, mock_exists, mock_makedirs, task_context, mock_repo):
    mock_ref = MagicMock()
    mock_origin = MagicMock()
    mock_origin.refs = [mock_ref]

    mock_repo.remotes.origin = mock_origin
    mock_repo_class.return_value = mock_repo

    _get_repo_cache_for_branch(task_context, 'owner', 'repo_name', 'branch')

    mock_makedirs.assert_called_once_with('/mock/cache/path/owner_repo_name', exist_ok=True)
    mock_repo.git.clean.assert_called_once_with('-fdx')


@pytest.mark.asyncio
@patch('apdiffscript.actions.tempfile.TemporaryDirectory')
@patch('apdiffscript.actions.apwm.download_apworld', return_value='/tmp/downloaded.zip')
@patch('apdiffscript.actions.ZipFile')
async def test_handle_apworld_change_success(mock_zipfile, mock_download_apworld, mock_tempdir, mock_repo, task_context):
    apworld_name = 'test_world'
    change = {"Added": ("1.0.0", "abcdef123456")}
    version = Version.parse("1.0.0")

    mock_tempdir().__enter__.return_value = '/tmp/tmpdir'
    mock_zipfile.return_value.__enter__().extractall = MagicMock()

    await _handle_apworld_change(task_context, apworld_name, change, mock_repo)

    mock_download_apworld.assert_called_once_with(task_context, apworld_name, version, '/tmp/tmpdir')
    mock_zipfile.return_value.__enter__().extractall.assert_called_once_with(mock_repo.working_dir)
    mock_repo.git.add.assert_called_once_with('.')
    mock_repo.git.commit.assert_called_once_with('-am', f"{apworld_name} {version}\n\nabcdef123456")


@pytest.mark.asyncio
@patch('apdiffscript.actions.tempfile.TemporaryDirectory')
@patch('apdiffscript.actions.apwm.download_apworld', return_value='/tmp/downloaded.zip')
@patch('apdiffscript.actions.ZipFile')
async def test_handle_apworld_change_no_added_key(mock_zipfile, mock_download_apworld, mock_tempdir, mock_repo, task_context):
    change = {"Updated": ("1.0.0", "abcdef123456")}

    await _handle_apworld_change(task_context, 'test_world', change, mock_repo)

    mock_download_apworld.assert_not_called()
    mock_zipfile.assert_not_called()

