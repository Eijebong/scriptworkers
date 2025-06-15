
import os
from unittest.mock import MagicMock, patch, Mock, AsyncMock

import pytest
from aiohttp import ClientResponseError
from apdiffscript.apwm import download_apworld
from semver import Version

@pytest.fixture
def context():
    mock_context = MagicMock()
    mock_context.config = {}
    mock_context.config['diff-task'] = 'task_id_example'
    mock_context.config["taskcluster_root_url"] = "https://nowher"

    session_mock = Mock()
    session_response_mock = AsyncMock()
    session_mock.get.return_value = session_response_mock
    context.session = session_mock

    return mock_context

@pytest.fixture
def mock_open():
    with patch('builtins.open', new_callable=MagicMock) as mocked_open:
        yield mocked_open

@pytest.mark.asyncio
async def test_download_apworld_success(context, mock_open):
    name = 'test_world'
    version = Version.parse('1.0.0')
    output = '/path/to/output'

    artifact_url = "https://example.com/artifacts/public/diff/test_world-1.0.0.apworld"
    mock_response = MagicMock()
    mock_response.url = artifact_url
    mock_response.read = AsyncMock(return_value = b'dummy apworld content')
    context.session.get.return_value.__aenter__.return_value = mock_response

    with patch('apdiffscript.apwm.Queue', new_callable=MagicMock) as MockQueue:
        queue_mock = MockQueue.return_value
        queue_mock.getLatestArtifact.return_value = {'url': artifact_url}

        result_path = await download_apworld(context, name, version, output)

    context.session.get.assert_called_once_with(artifact_url)
    mock_open.assert_called_once_with(os.path.join(output, f"{name}-{version}.apworld"), 'wb')
    mock_open().__enter__().write.assert_called_once_with(b'dummy apworld content')
    assert os.path.join(output, f"{name}-{version}.apworld") == result_path

@pytest.mark.asyncio
async def test_download_apworld_not_found(context):
    with patch('apdiffscript.apwm.Queue', new_callable=MagicMock) as MockQueue:
        queue_mock = MockQueue.return_value
        queue_mock.getLatestArtifact.side_effect = Exception("Artifact not found")

        name = 'test_world'
        version = '1.0.0'
        output = '/path/to/output'

        with pytest.raises(Exception) as excinfo:
            await download_apworld(context, name, version, output)

        assert "Artifact not found" in str(excinfo.value)

@pytest.mark.asyncio
async def test_download_apworld_http_error(context):
    artifact_url = "https://example.com/artifacts/public/diff/test_world-1.0.0.apworld"

    context.session.get().__aenter__.return_value.raise_for_status = Mock(side_effect=ClientResponseError(request_info=None, history=None))

    with patch('apdiffscript.apwm.Queue', new_callable=MagicMock) as MockQueue:
        queue_mock = MockQueue.return_value
        queue_mock.getLatestArtifact.return_value = {'url': artifact_url}

        name = 'test_world'
        version = '1.0.0'
        output = '/path/to/output'

        with pytest.raises(ClientResponseError):
            await download_apworld(context, name, version, output)

