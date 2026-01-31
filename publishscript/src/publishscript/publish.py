import asyncio
import logging
import os
import tempfile

from scriptworker.exceptions import TaskVerificationError
from taskcluster import Queue

from .utils import is_task_coming_from_pr

logger = logging.getLogger(__name__)

CACHE_DIR = "/home/worker/repo-cache"


async def _run_git(args, cwd, env=None, allow_failure=False):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        env=merged_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={proc.returncode}): {stderr.decode()}"
        )
    return stdout.decode().strip()


async def _run_patch(patch_path, cwd, dry_run=False):
    args = ["patch", "-p1", "-i", patch_path]
    if dry_run:
        args.append("--dry-run")

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        mode = "dry-run" if dry_run else "apply"
        raise RuntimeError(
            f"patch -p1 {mode} failed (rc={proc.returncode}): {stderr.decode()}"
        )
    return stdout.decode().strip()


async def _get_installation_token(github):
    return await github.auth.get_token()


async def _merge_pr(github, owner, repo, pr_number, head_rev):
    logger.info("Merging PR #%s on %s/%s", pr_number, owner, repo)
    path = f"/repos/{owner}/{repo}/pulls/{pr_number}/merge"
    resp = await github.put(
        path,
        data={
            "merge_method": "squash",
            "sha": head_rev,
        },
    )
    resp.raise_for_status()
    logger.info("PR #%s merged successfully", pr_number)


async def _ensure_repo(owner, repo, token):
    """Clone or fetch the repo using HTTPS + installation token."""
    repo_dir = os.path.join(CACHE_DIR, owner, repo)
    clone_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"

    if os.path.isdir(os.path.join(repo_dir, ".git")):
        logger.info("Fetching %s/%s", owner, repo)
        await _run_git(["remote", "set-url", "origin", clone_url], cwd=repo_dir)
        await _run_git(["fetch", "origin"], cwd=repo_dir)
    else:
        logger.info("Cloning %s/%s", owner, repo)
        os.makedirs(repo_dir, exist_ok=True)
        await _run_git(
            ["clone", clone_url, repo_dir],
            cwd=CACHE_DIR,
        )

    return repo_dir


async def _download_artifact(session, queue, task_id, artifact_name):
    url = queue.getLatestArtifact(task_id, artifact_name)["url"]
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".diff")

    async with session.get(url) as r:
        r.raise_for_status()
        tmpfile.write(await r.read())
    tmpfile.close()

    return tmpfile.name


async def publish(context):
    payload = context.task["payload"]
    owner = context.config["target"]["owner"]
    repo = context.config["target"]["repo"]

    pr_number = payload["pr-number"]
    head_rev = payload["head-rev"]
    diff_task_id = payload["diff-task"]
    expectations_task_id = payload.get("expectations-task")

    task_id = context.task["taskGroupId"]
    if not is_task_coming_from_pr(context, task_id, owner, repo, pr_number):
        raise TaskVerificationError(
            f"This task was scheduled for PR #{pr_number} but it doesn't seem to be coming from it"
        )

    github = context.github
    queue = Queue({"rootUrl": context.config["taskcluster_root_url"]})

    token = await _get_installation_token(github)
    repo_dir = await _ensure_repo(owner, repo, token)

    # Download artifacts
    patch_files = []
    expectations_patch = None
    lock_patch = None

    if expectations_task_id:
        expectations_patch = await _download_artifact(
            context.session, queue, expectations_task_id, "public/expectations.patch"
        )
        patch_files.append(expectations_patch)

    lock_patch = await _download_artifact(context.session, queue, diff_task_id, "public/build/lock.diff")
    patch_files.append(lock_patch)

    try:
        # Dry run: simulate squash merge + patches locally before touching anything
        logger.info("Starting dry run: simulating merge + patches")
        await _run_git(["fetch", "origin", f"pull/{pr_number}/head:pr-head"], cwd=repo_dir)
        await _run_git(["checkout", "main"], cwd=repo_dir)
        await _run_git(["reset", "--hard", "origin/main"], cwd=repo_dir)
        await _run_git(["merge", "--squash", "pr-head"], cwd=repo_dir)

        if expectations_patch and os.path.getsize(expectations_patch) > 0:
            await _run_patch(expectations_patch, repo_dir, dry_run=True)
        if os.path.getsize(lock_patch) > 0:
            await _run_patch(lock_patch, repo_dir, dry_run=True)

        logger.info("Dry run succeeded, proceeding with real merge")

        # Clean up dry run state
        await _run_git(["reset", "--hard", "origin/main"], cwd=repo_dir)
        await _run_git(["branch", "-D", "pr-head"], cwd=repo_dir, allow_failure=True)

        # Real merge via GitHub API
        await _merge_pr(github, owner, repo, pr_number, head_rev)

        # Fetch the merged main
        await _run_git(["fetch", "origin"], cwd=repo_dir)
        await _run_git(["reset", "--hard", "origin/main"], cwd=repo_dir)

        git_env = {
            "GIT_AUTHOR_NAME": "Taskcluster",
            "GIT_AUTHOR_EMAIL": "eijebong+taskcluster@bananium.fr",
            "GIT_COMMITTER_NAME": "Taskcluster",
            "GIT_COMMITTER_EMAIL": "eijebong+taskcluster@bananium.fr",
        }

        if expectations_patch and os.path.getsize(expectations_patch) > 0:
            logger.info("Applying expectations patch")
            await _run_patch(expectations_patch, repo_dir)
            await _run_git(["add", "meta"], cwd=repo_dir)
            await _run_git(
                ["commit", "-m", "Update expectations"],
                cwd=repo_dir, env=git_env, allow_failure=True,
            )

        if os.path.getsize(lock_patch) > 0:
            logger.info("Applying lock.diff")
            await _run_patch(lock_patch, repo_dir)
            await _run_git(["add", "index.lock"], cwd=repo_dir)
            await _run_git(
                ["commit", "-m", "Update index lock"],
                cwd=repo_dir, env=git_env, allow_failure=True,
            )

        logger.info("Pushing to main")
        await _run_git(["push", "origin", "main"], cwd=repo_dir)
        logger.info("Publish complete")
    finally:
        safe_url = f"https://github.com/{owner}/{repo}.git"
        await _run_git(["remote", "set-url", "origin", safe_url], cwd=repo_dir)
        for f in patch_files:
            os.unlink(f)
