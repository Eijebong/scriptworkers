import json
import pytest

from scriptworker.client import Context
from unittest.mock import Mock, AsyncMock


def _mock_response(data):
    mock = AsyncMock()
    mock.__aenter__.return_value.raise_for_status = Mock()
    mock.__aenter__.return_value.read.return_value = json.dumps(data).encode()
    return mock


@pytest.fixture
def mock_response():
    return _mock_response


@pytest.fixture
def mock_queue():
    mock = Mock()
    mock.return_value.getLatestArtifact.side_effect = lambda task_id, artifact: {
        "url": f"https://nowhere/{task_id}/{artifact}"
    }
    mock.return_value.status.side_effect = lambda task_id: {
        "status": {"runs": [{"runId": 0}]}
    }
    mock.return_value.listArtifacts.side_effect = lambda task_id, run_id: {
        "artifacts": [
            {"name": "public/report.json"},
            {"name": f"public/fuzz_output_{task_id}.zip"},
        ]
    }
    mock.return_value.task.side_effect = lambda task_id: {
        "metadata": {"description": f"Fuzz task {task_id}"}
    }
    return mock


@pytest.fixture
def mock_is_task_coming_from_pr():
    mock = Mock()
    mock.return_value = True
    return mock


@pytest.fixture
def fuzz_context():
    context = Context()
    context.task = {
        "payload": {
            "fuzz-task": "fuzz-task-id",
            "diff-task": "diff-task-id",
            "world-name": "test_apworld",
            "world-version": "1.0.0",
        },
        "taskGroupId": "UCy202ZHSL-t1AIHG9f2aw",
    }
    context.config = {
        "taskcluster_root_url": "http://nowhere",
        "target": {
            "owner": "foo",
            "repo": "bar",
        },
        "apdiff": {
            "api_key": "test-api-key",
            "viewer_url": "https://apdiff.bananium.fr",
        },
    }
    context.session = Mock()
    context.github = AsyncMock()
    context.github.post.return_value = Mock()
    return context


@pytest.fixture
def mock_fuzz_report():
    return {
        "stats": {
            "total": 5000,
            "success": 3480,
            "failure": 0,
            "timeout": 0,
            "ignored": 1520,
        },
        "errors": {},
    }


@pytest.fixture
def mock_apdiff():
    return {
        "world_name": "Test Apworld",
        "apworld_name": "test_apworld",
        "diffs": {
            "0.9.0...1.0.0": {
                "VersionAdded": {
                    "content": "diff content here",
                    "checksum": "abc123checksum",
                }
            }
        },
    }


@pytest.fixture
def mock_apdiff_no_checksum():
    return {"world_name": "Test", "apworld_name": "test", "diffs": {}}


@pytest.fixture
def fuzz_comment_context():
    context = Context()
    context.task = {
        "payload": {
            "fuzz-tasks": [
                {"task-id": "fuzz-task-id"},
            ],
            "diff-task": "diff-task-id",
            "world-name": "test_apworld",
            "world-version": "1.0.0",
        },
        "taskGroupId": "UCy202ZHSL-t1AIHG9f2aw",
    }
    context.config = {
        "taskcluster_root_url": "http://nowhere",
        "target": {
            "owner": "foo",
            "repo": "bar",
        },
    }
    context.session = Mock()
    context.github = AsyncMock()
    context.github.post.return_value = Mock()
    return context
