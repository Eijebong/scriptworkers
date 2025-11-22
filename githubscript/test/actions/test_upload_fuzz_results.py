import pytest

from contextlib import nullcontext as does_not_raise
from githubscript.actions import upload_fuzz_results
from pytest import raises
from scriptworker.exceptions import TaskVerificationError
from unittest.mock import Mock, patch


@pytest.mark.parametrize(
    "params,expectation",
    (
        pytest.param([], raises(TaskVerificationError)),
        pytest.param(["pr"], raises(TaskVerificationError)),
        pytest.param(["pr", "1", "extra"], raises(TaskVerificationError)),
        pytest.param(["invalid", "123"], raises(TaskVerificationError)),
        pytest.param(["pr", "abc"], raises(TaskVerificationError)),
        pytest.param(["pr", "-1"], raises(TaskVerificationError)),
        pytest.param(["pr", "0"], raises(TaskVerificationError)),
        pytest.param(["pr", "1"], does_not_raise()),
        pytest.param(["branch", "main"], does_not_raise()),
        pytest.param(["branch", "feature-branch"], does_not_raise()),
    ),
)
@patch.dict("os.environ", {"APDIFF_API_KEY": "test-api-key"})
@pytest.mark.asyncio
async def test_args(
    fuzz_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_fuzz_report,
    mock_apdiff,
    params,
    expectation,
):
    fuzz_context.session.get = Mock(
        side_effect=[mock_response(mock_fuzz_report), mock_response(mock_apdiff)]
    )
    fuzz_context.session.post = Mock(return_value=mock_response({}))

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            with expectation:
                await upload_fuzz_results(fuzz_context, params)


@pytest.mark.asyncio
async def test_missing_payload_fields(
    fuzz_context, mock_queue, mock_is_task_coming_from_pr
):
    fuzz_context.task["payload"] = {}

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            with pytest.raises(TaskVerificationError, match="fuzz-task is missing"):
                await upload_fuzz_results(fuzz_context, ["pr", "97"])


@patch.dict("os.environ", {"APDIFF_API_KEY": "test-api-key"})
@pytest.mark.asyncio
async def test_missing_checksum(
    fuzz_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_fuzz_report,
    mock_apdiff_no_checksum,
):
    fuzz_context.session.get = Mock(
        side_effect=[
            mock_response(mock_fuzz_report),
            mock_response(mock_apdiff_no_checksum),
        ]
    )

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            with pytest.raises(TaskVerificationError, match="Could not find checksum"):
                await upload_fuzz_results(fuzz_context, ["pr", "97"])


@pytest.mark.asyncio
async def test_missing_api_key(
    fuzz_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_fuzz_report,
    mock_apdiff,
):
    fuzz_context.session.get = Mock(
        side_effect=[mock_response(mock_fuzz_report), mock_response(mock_apdiff)]
    )

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(TaskVerificationError, match="APDIFF_API_KEY"):
                    await upload_fuzz_results(fuzz_context, ["pr", "97"])


@patch.dict(
    "os.environ",
    {"APDIFF_API_KEY": "test-api-key", "APDIFF_VIEWER_URL": "https://test.example.com"},
)
@pytest.mark.asyncio
async def test_upload_for_pr(
    fuzz_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_fuzz_report,
    mock_apdiff,
):
    fuzz_context.session.get = Mock(
        side_effect=[mock_response(mock_fuzz_report), mock_response(mock_apdiff)]
    )
    fuzz_context.session.post = Mock(return_value=mock_response({}))

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            await upload_fuzz_results(fuzz_context, ["pr", "97"])

    fuzz_context.session.post.assert_called_once_with(
        "https://test.example.com/api/fuzz-results",
        json={
            "task_id": "fuzz-task-id",
            "pr_number": 97,
            "results": [
                {
                    "world_name": "test_apworld",
                    "version": "1.0.0",
                    "checksum": "abc123checksum",
                    "total": 5000,
                    "success": 3480,
                    "failure": 0,
                    "timeout": 0,
                    "ignored": 1520,
                }
            ],
        },
        headers={"X-Api-Key": "test-api-key"},
    )


@patch.dict("os.environ", {"APDIFF_API_KEY": "test-api-key"})
@pytest.mark.asyncio
async def test_upload_for_main_branch(
    fuzz_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_fuzz_report,
    mock_apdiff,
):
    fuzz_context.session.get = Mock(
        side_effect=[mock_response(mock_fuzz_report), mock_response(mock_apdiff)]
    )
    fuzz_context.session.post = Mock(return_value=mock_response({}))

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            await upload_fuzz_results(fuzz_context, ["branch", "main"])

    fuzz_context.session.post.assert_called_once()
    assert fuzz_context.session.post.call_args[1]["json"]["pr_number"] is None


@patch.dict("os.environ", {"APDIFF_API_KEY": "test-api-key"})
@pytest.mark.asyncio
async def test_skip_upload_for_non_main_branch(
    fuzz_context, mock_queue, mock_response, mock_fuzz_report, mock_apdiff
):
    fuzz_context.session.get = Mock(
        side_effect=[mock_response(mock_fuzz_report), mock_response(mock_apdiff)]
    )
    fuzz_context.session.post = Mock(return_value=mock_response({}))

    with patch("githubscript.actions.Queue", mock_queue):
        await upload_fuzz_results(fuzz_context, ["branch", "feature-branch"])

    fuzz_context.session.post.assert_not_called()


@patch.dict("os.environ", {"APDIFF_API_KEY": "test-api-key"})
@pytest.mark.asyncio
async def test_upload_with_extra_args(
    fuzz_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_fuzz_report,
    mock_apdiff,
):
    fuzz_context.task["payload"]["extra-args"] = "no-restrictive-starts"
    fuzz_context.session.get = Mock(
        side_effect=[mock_response(mock_fuzz_report), mock_response(mock_apdiff)]
    )
    fuzz_context.session.post = Mock(return_value=mock_response({}))

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            await upload_fuzz_results(fuzz_context, ["pr", "97"])

    assert (
        fuzz_context.session.post.call_args[1]["json"]["extra_args"]
        == "no-restrictive-starts"
    )
