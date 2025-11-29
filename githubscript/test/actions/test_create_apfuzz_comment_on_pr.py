import pytest

from contextlib import nullcontext as does_not_raise
from githubscript.actions import create_apfuzz_comment_on_pr
from pytest import raises
from scriptworker.exceptions import TaskVerificationError
from unittest.mock import Mock, patch


MOCK_FUZZ_REPORT_WITH_FAILURES = {
    "stats": {
        "total": 5000,
        "success": 3480,
        "failure": 10,
        "timeout": 5,
        "ignored": 1505,
    },
    "errors": {},
}

MOCK_PREVIOUS_RESULTS = {
    "previous_results": [
        {
            "match_type": "main",
            "success": 3400,
            "failure": 15,
            "timeout": 10,
            "total": 5000,
        },
        {
            "match_type": "same_version",
            "success": 3450,
            "failure": 12,
            "timeout": 8,
            "total": 5000,
        },
    ]
}


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
@pytest.mark.asyncio
async def test_args(
    fuzz_comment_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_apdiff,
    params,
    expectation,
):
    fuzz_comment_context.session.get = Mock(
        side_effect=[
            mock_response(mock_apdiff),
            mock_response(MOCK_FUZZ_REPORT_WITH_FAILURES),
            mock_response(MOCK_PREVIOUS_RESULTS),
        ]
    )

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            with expectation:
                await create_apfuzz_comment_on_pr(fuzz_comment_context, params)


@pytest.mark.asyncio
async def test_missing_payload_fields(
    fuzz_comment_context, mock_queue, mock_is_task_coming_from_pr
):
    fuzz_comment_context.task["payload"] = {}

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            with pytest.raises(TaskVerificationError, match="fuzz-tasks is missing"):
                await create_apfuzz_comment_on_pr(fuzz_comment_context, ["97"])


@pytest.mark.asyncio
async def test_missing_checksum(
    fuzz_comment_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_apdiff_no_checksum,
):
    fuzz_comment_context.session.get = Mock(
        side_effect=[
            mock_response(mock_apdiff_no_checksum),
        ]
    )

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            with pytest.raises(TaskVerificationError, match="Could not find checksum"):
                await create_apfuzz_comment_on_pr(fuzz_comment_context, ["97"])


@pytest.mark.asyncio
async def test_comment_with_baselines(
    fuzz_comment_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_apdiff,
):
    fuzz_comment_context.session.get = Mock(
        side_effect=[
            mock_response(mock_apdiff),
            mock_response(MOCK_FUZZ_REPORT_WITH_FAILURES),
            mock_response(MOCK_PREVIOUS_RESULTS),
        ]
    )

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            await create_apfuzz_comment_on_pr(fuzz_comment_context, ["97"])

    fuzz_comment_context.github.post.assert_called_once()
    call_args = fuzz_comment_context.github.post.call_args
    assert call_args[0][0] == "/repos/foo/bar/issues/97/comments"

    body = call_args[1]["data"]["body"]
    assert "test_apworld" in body
    assert "v1.0.0" in body
    assert "#### default" in body
    assert "**Success**: 3480" in body
    assert "**Ignored**: 1505" in body
    assert "0.4%" in body
    assert "main" in body
    assert "same_version" in body
    assert "Success: +80" in body


@pytest.mark.asyncio
async def test_comment_without_baselines(
    fuzz_comment_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_apdiff,
):
    fuzz_comment_context.session.get = Mock(
        side_effect=[
            mock_response(mock_apdiff),
            mock_response(MOCK_FUZZ_REPORT_WITH_FAILURES),
            mock_response({"previous_results": []}),
        ]
    )

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            await create_apfuzz_comment_on_pr(fuzz_comment_context, ["97"])

    fuzz_comment_context.github.post.assert_called_once()
    call_args = fuzz_comment_context.github.post.call_args
    body = call_args[1]["data"]["body"]
    assert "No previous results found" in body


@pytest.mark.asyncio
async def test_comment_with_multiple_configs(
    fuzz_comment_context,
    mock_queue,
    mock_is_task_coming_from_pr,
    mock_response,
    mock_apdiff,
):
    fuzz_comment_context.task["payload"]["fuzz-tasks"] = [
        {"task-id": "fuzz-task-default"},
        {"task-id": "fuzz-task-extra", "extra-args": "no-restrictive-starts"},
    ]

    mock_fuzz_report_extra = {
        "stats": {
            "total": 5000,
            "success": 3200,
            "failure": 50,
            "timeout": 10,
            "ignored": 1740,
        },
        "errors": {},
    }

    fuzz_comment_context.session.get = Mock(
        side_effect=[
            mock_response(mock_apdiff),
            mock_response(MOCK_FUZZ_REPORT_WITH_FAILURES),
            mock_response(MOCK_PREVIOUS_RESULTS),
            mock_response(mock_fuzz_report_extra),
            mock_response({"previous_results": []}),
        ]
    )

    with patch("githubscript.actions.Queue", mock_queue):
        with patch(
            "githubscript.actions.is_task_coming_from_pr", mock_is_task_coming_from_pr
        ):
            await create_apfuzz_comment_on_pr(fuzz_comment_context, ["97"])

    fuzz_comment_context.github.post.assert_called_once()
    call_args = fuzz_comment_context.github.post.call_args
    body = call_args[1]["data"]["body"]

    assert "#### default" in body
    assert "#### no-restrictive-starts" in body
    assert "**Success**: 3480" in body
    assert "**Success**: 3200" in body
