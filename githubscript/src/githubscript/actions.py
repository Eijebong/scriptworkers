from scriptworker.exceptions import TaskVerificationError
from taskcluster import Queue
import logging
import os
from .utils import is_task_coming_from_pr
import json

logger = logging.getLogger(__name__)


def _get_pr_info(context, args):
    if len(args) != 1:
        raise TaskVerificationError("You should provide one, and only one PR number")

    try:
        pr_number = int(args[0])
    except ValueError:
        raise TaskVerificationError("The given PR number isn't an int")

    if pr_number <= 0:
        raise TaskVerificationError(f"The PR number {pr_number} is wrong")

    owner = context.config["target"]["owner"]
    repo = context.config["target"]["repo"]
    task_id = context.task["taskGroupId"]

    if not is_task_coming_from_pr(context, task_id, owner, repo, pr_number):
        raise TaskVerificationError(
            f"This task was scheduled for pr {pr_number} but it doesn't seem to be coming from it"
        )

    return owner, repo, pr_number


async def _create_github_comment(context, owner, repo, pr_number, comment):
    path = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"

    logging.info(
        "Creating github comment on %s/%s with content %s" % (owner, repo, comment)
    )

    data = {"body": comment}

    resp = await context.github.post(path, data=data)
    resp.raise_for_status()


async def create_apdiff_comment_on_pr(context, args):
    owner, repo, pr_number = _get_pr_info(context, args)

    logger.info("Creating apdiff comment for PR %s" % pr_number)

    payload = context.task["payload"]
    if "diff-task" not in payload:
        raise TaskVerificationError("diff-task is missing from the payload")

    diff_task_id = payload["diff-task"]

    logger.debug("Diff task ID is %s" % diff_task_id)
    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    artifacts = queue.listLatestArtifacts(diff_task_id)["artifacts"]
    found_diff = None
    for artifact in artifacts:
        if artifact["name"].endswith(".apdiff"):
            found_diff = artifact
            break

    if found_diff:
        comment = f"[Review changes](https://apdiff.bananium.fr/{diff_task_id})"
    else:
        comment = "No reviewable change"

    await _create_github_comment(context, owner, repo, pr_number, comment)


def apply_patch(context, args):
    raise NotImplemented("Not implemented yet")


async def create_aptest_comment_on_pr(context, args):
    owner, repo, pr_number = _get_pr_info(context, args)

    logger.info("Creating aptest comment for PR %s" % pr_number)
    payload = context.task["payload"]
    if "test-task" not in payload:
        raise TaskVerificationError("test-task is missing from the payload")

    test_task_id = payload["test-task"]

    logger.debug("Test task ID is %s" % test_task_id)
    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    artifacts = queue.listLatestArtifacts(test_task_id)["artifacts"]
    found_test = None
    for artifact in artifacts:
        if artifact["name"].endswith(".aptest"):
            found_test = artifact["name"]
            break

    if found_test:
        aptest_url = queue.getLatestArtifact(test_task_id, found_test)["url"]
        async with context.session.get(aptest_url) as r:
            r.raise_for_status()
            aptest_info = json.loads((await r.read()).decode())
            apworld_name = aptest_info["apworld"]
            apworld_version = aptest_info["version"]

        comment = f"[Test failures for {apworld_name}:{apworld_version}](https://apdiff.bananium.fr/tests/{test_task_id})"
        await _create_github_comment(context, owner, repo, pr_number, comment)


def _get_fuzz_target_info(context, args):
    if len(args) != 2:
        raise TaskVerificationError(
            "Expected two arguments: type (pr/branch) and value"
        )

    target_type, target_value = args

    if target_type not in ("pr", "branch"):
        raise TaskVerificationError(f"Invalid target type '{target_type}'")

    if target_type == "pr":
        _, _, pr_number = _get_pr_info(context, [target_value])
        return ("pr", pr_number)
    else:
        return ("branch", target_value)


def _extract_checksum_from_apdiff(apdiff, version):
    for version_range, diff in apdiff.get("diffs", {}).items():
        if "..." not in version_range:
            continue
        _, to_version = version_range.split("...", 1)
        if to_version != version:
            continue
        if "VersionAdded" not in diff:
            continue
        return diff["VersionAdded"]["checksum"]
    return None


async def upload_fuzz_results(context, args):
    target_type, target_value = _get_fuzz_target_info(context, args)
    payload = context.task["payload"]

    for field in ("fuzz-task", "diff-task", "world-name", "world-version"):
        if field not in payload:
            raise TaskVerificationError(f"{field} is missing from the payload")

    if target_type == "branch" and target_value != "main":
        logger.info(
            "Skipping upload for branch %s (only main publishes)" % target_value
        )
        return

    api_key = os.environ.get("APDIFF_API_KEY")
    if not api_key:
        raise TaskVerificationError("APDIFF_API_KEY environment variable is not set")

    logger.info("Uploading fuzz results for %s %s" % (target_type, target_value))

    fuzz_task_id = payload["fuzz-task"]
    diff_task_id = payload["diff-task"]
    world_name = payload["world-name"]
    world_version = payload["world-version"]
    extra_args = payload.get("extra-args")

    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    logger.debug("Getting fuzz artifact from task %s" % fuzz_task_id)
    fuzz_report_url = queue.getLatestArtifact(fuzz_task_id, "public/report.json")["url"]
    async with context.session.get(fuzz_report_url) as r:
        r.raise_for_status()
        fuzz_report = json.loads((await r.read()).decode())
    stats = fuzz_report["stats"]

    logger.debug("Getting apdiff artifact from task %s" % diff_task_id)
    apdiff_url = queue.getLatestArtifact(
        diff_task_id, f"public/diffs/{world_name}.apdiff"
    )["url"]
    async with context.session.get(apdiff_url) as r:
        r.raise_for_status()
        apdiff = json.loads((await r.read()).decode())
    checksum = _extract_checksum_from_apdiff(apdiff, world_version)

    if not checksum:
        raise TaskVerificationError(
            f"Could not find checksum for version {world_version} in apdiff"
        )

    apdiff_viewer_url = os.environ.get(
        "APDIFF_VIEWER_URL", "https://apdiff.bananium.fr"
    )
    pr_number = target_value if target_type == "pr" else None

    request_body = {
        "task_id": fuzz_task_id,
        "pr_number": pr_number,
        "results": [
            {
                "world_name": world_name,
                "version": world_version,
                "checksum": checksum,
                "total": stats["total"],
                "success": stats["success"],
                "failure": stats["failure"],
                "timeout": stats["timeout"],
                "ignored": stats["ignored"],
            }
        ],
    }

    if extra_args:
        request_body["extra_args"] = extra_args

    logger.info("Posting fuzz results to API")
    async with context.session.post(
        f"{apdiff_viewer_url}/api/fuzz-results",
        json=request_body,
        headers={"X-Api-Key": api_key},
    ) as r:
        r.raise_for_status()


def _format_diff(val):
    return f"+{val}" if val > 0 else str(val)


def _format_pct(count, total, ignored):
    effective = total - ignored
    if effective == 0:
        return "N/A"
    return f"{100 * count / effective:.1f}%"


async def _build_fuzz_comment_section(
    context, queue, fuzz_task, world_name, world_version, checksum, apdiff_viewer_url
):
    fuzz_task_id = fuzz_task["task-id"]
    extra_args = fuzz_task.get("extra-args")

    logger.debug("Getting fuzz artifact from task %s" % fuzz_task_id)
    fuzz_report_url = queue.getLatestArtifact(fuzz_task_id, "public/report.json")["url"]
    async with context.session.get(fuzz_report_url) as r:
        r.raise_for_status()
        fuzz_report = json.loads((await r.read()).decode())
    current_stats = fuzz_report["stats"]

    total = current_stats["total"]
    ignored = current_stats["ignored"]
    failure = current_stats["failure"] + current_stats["timeout"]
    failure_pct = _format_pct(failure, total, ignored)

    config_name = extra_args if extra_args else "default"

    results_link = ""
    runs = queue.status(fuzz_task_id)["status"]["runs"]
    run_id = runs[-1]["runId"]
    artifacts = queue.listArtifacts(fuzz_task_id, run_id).get("artifacts", [])
    for artifact in artifacts:
        if artifact["name"].startswith("public/fuzz_output"):
            tc_root = context.config["taskcluster_root_url"]
            results_url = f"{tc_root}/tasks/{fuzz_task_id}/runs/{run_id}/{artifact['name']}"
            results_link = f" ([results]({results_url}))"
            break

    is_check = extra_args and extra_args.startswith("check-")

    if is_check:
        if total == ignored:
            status_icon = "🤷"
        elif failure > 0:
            status_icon = "❌"
        else:
            status_icon = "✅"
        section = f"\n### {status_icon} {config_name}{results_link}\n\n"
    else:
        section = f"\n### {config_name}{results_link}\n\n"

    body = "```\n"
    body += f"Success: {current_stats['success']}\n"
    body += f"Failure: {current_stats['failure']}\n"
    body += f"Timeout: {current_stats['timeout']}\n"
    body += f"Ignored: {ignored}\n"
    body += f"Total: {total}\n"
    body += "```\n"
    body += f"**Failure rate**: {failure_pct}\n"

    url = f"{apdiff_viewer_url}/api/fuzz-results/{world_name}/previous"
    params = {"version": world_version, "checksum": checksum}
    if extra_args:
        params["extra_args"] = extra_args

    async with context.session.get(url, params=params) as r:
        r.raise_for_status()
        response = json.loads((await r.read()).decode())
        previous_results = response.get("previous_results", [])

    if previous_results:
        body += "\n**Comparison with baselines:**\n"
        for baseline in previous_results:
            success_diff = current_stats["success"] - baseline["success"]
            failure_diff = current_stats["failure"] - baseline["failure"]
            timeout_diff = current_stats["timeout"] - baseline["timeout"]

            body += f"\n*{baseline['match_type']}:*\n"
            body += f"- Success: {_format_diff(success_diff)}\n"
            body += f"- Failure: {_format_diff(failure_diff)}\n"
            body += f"- Timeout: {_format_diff(timeout_diff)}\n"
    else:
        body += "\nNo previous results found for comparison.\n"

    if is_check:
        task_desc = queue.task(fuzz_task_id).get("metadata", {}).get("description", "")
        details_body = ""
        if task_desc:
            details_body += f"{task_desc}\n\n"
        details_body += body
        section += f"<details>\n<summary>Details</summary>\n\n{details_body}\n</details>\n"
    else:
        section += body

    return section


async def create_apfuzz_comment_on_pr(context, args):
    owner, repo, pr_number = _get_pr_info(context, args)

    logger.info("Creating apfuzz comment for PR %s" % pr_number)
    payload = context.task["payload"]

    for field in ("fuzz-tasks", "diff-task", "world-name", "world-version"):
        if field not in payload:
            raise TaskVerificationError(f"{field} is missing from the payload")

    fuzz_tasks = payload["fuzz-tasks"]
    diff_task_id = payload["diff-task"]
    world_name = payload["world-name"]
    world_version = payload["world-version"]

    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    apdiff_url = queue.getLatestArtifact(
        diff_task_id, f"public/diffs/{world_name}.apdiff"
    )["url"]
    async with context.session.get(apdiff_url) as r:
        r.raise_for_status()
        apdiff = json.loads((await r.read()).decode())
    checksum = _extract_checksum_from_apdiff(apdiff, world_version)

    if not checksum:
        raise TaskVerificationError(
            f"Could not find checksum for version {world_version} in apdiff"
        )

    apdiff_viewer_url = os.environ.get(
        "APDIFF_VIEWER_URL", "https://apdiff.bananium.fr"
    )

    comment = f"## Fuzz results for {world_name} v{world_version}\n"
    fuzz_tasks = sorted(
        fuzz_tasks,
        key=lambda t: (t.get("extra-args", "").startswith("check-"), t.get("extra-args", "")),
    )
    for fuzz_task in fuzz_tasks:
        comment += await _build_fuzz_comment_section(
            context,
            queue,
            fuzz_task,
            world_name,
            world_version,
            checksum,
            apdiff_viewer_url,
        )

    await _create_github_comment(context, owner, repo, pr_number, comment)


ACTIONS = {
    "create-apdiff-comment-on-pr": {"handler": create_apdiff_comment_on_pr, "requires": "github"},
    "create-aptest-comment-on-pr": {"handler": create_aptest_comment_on_pr, "requires": "github"},
    "apply-patch": {"handler": apply_patch, "requires": "github"},
    "upload-fuzz-results": {"handler": upload_fuzz_results, "requires": "apdiff"},
    "create-apfuzz-comment-on-pr": {"handler": create_apfuzz_comment_on_pr, "requires": "github"},
}
