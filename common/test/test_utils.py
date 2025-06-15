import pytest
from unittest.mock import Mock, patch
import uuid
from scriptworker_common import is_task_coming_from_pr
from scriptworker.client import Context


GITHUB_MOCK = Mock()
GITHUB_MOCK.return_value.builds.return_value = {
    "builds": [
        {"taskGroupId": "GRKcd87oQ4qFB9SnyH02wg"},
        {"taskGroupId": "UCy202ZHSL-t1AIHG9f2aw"},
    ]
}


@pytest.mark.parametrize(
    "task_group_id,expectation",
    (
        pytest.param("GRKcd87oQ4qFB9SnyH02wg", True),
        pytest.param("GRKcd87oQ4qFB9SnyH03wg", False),
    ),
)
def test_is_task_coming_from_pr(task_group_id, expectation):
    owner = str(uuid.uuid4())
    repo = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    context = Context()

    context.config = {
        "taskcluster_root_url": "https://nowhere",
        "repos": {
            "archipelago-index": "Eijebong/Archipelago-index",
        },
        "github": {
            "app_id": "123",
            "private_key": "ZHVtbXkK",
        },
    }

    queue_mock = Mock()
    queue_mock.return_value.task.return_value = {"taskGroupId": task_group_id}

    GITHUB_MOCK.reset_mock()

    with patch("scriptworker_common.Queue", queue_mock), patch(
        "scriptworker_common.Github", GITHUB_MOCK
    ):
        assert (
            is_task_coming_from_pr(context, task_id, owner, repo, 5)
            == expectation
        )

    queue_mock.return_value.task.assert_called_with(task_id)
    GITHUB_MOCK.return_value.builds.assert_called_with(
        query={"pullRequest": 5, "organization": owner, "repository": repo}
    )
