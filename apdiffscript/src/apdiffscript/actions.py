from . import apwm
from git import Repo
from scriptworker.exceptions import TaskVerificationError
from scriptworker_common import is_task_coming_from_pr
from semver import Version
from taskcluster import Queue
from zipfile import ZipFile

import json
import os
import tempfile

import logging

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

async def _handle_apworld_change(context, apworld_name, change, repo):
    if "Added" not in change:
        logger.info("Nothing to do for non addition")
        return

    version, checksum = change["Added"]
    version = Version.parse(version)

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = await apwm.download_apworld(context, apworld_name, version, tmpdir)

        with ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(repo.working_dir)

        repo.git.add('.')
        commit_message = f"{apworld_name} {version}\n\n{checksum}"
        repo.git.commit('-am', commit_message)


def _get_repo_cache_for_branch(context, owner, repo_name, branch_name, overwrite_branch=False):
    repo_cache = context.config['repo_cache']
    repo_path = os.path.join(repo_cache, f"{owner}_{repo_name}")

    os.makedirs(repo_path, exist_ok=True)

    if not os.path.exists(os.path.join(repo_path, '.git')):
        logger.info("Cloning %s/%s at %s" % (owner, repo_name, repo_path))
        repo = Repo.clone_from(f"https://github.com/{owner}/{repo_name}.git", repo_path)
    else:
        logger.info("Fetching %s/%s at %s" % (owner, repo_name, repo_path))
        repo = Repo(repo_path)
        repo.remotes.origin.fetch()

    config = repo.config_writer()
    config.set_value("user", "name", "Taskcluster")
    config.set_value("user", "email", "eijebong+taskcluster@bananium.fr")
    config.release()

    origin = repo.remotes.origin
    remote_branch_ref = f"refs/remotes/origin/{branch_name}"

    remote_exists = any(ref.name == branch_name for ref in origin.refs)
    local_exists = any(ref.name == branch_name for ref in repo.refs)

    if local_exists:
        repo.heads[branch_name].checkout(detach=True)
        logger.info("Deleting branch %s from local cache", branch_name)
        repo.delete_head(branch_name, force=True)

    if remote_exists and not overwrite_branch:
        logger.info("Creating local %s to match origin/%s" % (branch_name, branch_name))
        repo.create_head(branch_name, commit=remote_branch_ref)
        repo.heads[branch_name].checkout()
        repo.git.reset('--hard', remote_branch_ref)
    else:
        logger.info("%s does not exist, creating locally" % branch_name)
        repo.git.checkout('--orphan', branch_name)

    repo.git.reset('--hard')
    repo.git.clean('-fdx')

    return repo


async def diff_from_task(context, args):
    owner, repo_name, pr_number = _get_pr_info(context, args)

    payload = context.task["payload"]

    if "diff-task" not in payload:
        raise TaskVerificationError("Missing diff-task from payload")

    diff_task_id = payload["diff-task"]

    if not is_task_coming_from_pr(context, diff_task_id, owner, repo_name, pr_number):
        raise TaskVerificationError(
            f"This task was scheduled for pr {pr_number} but it doesn't seem to be coming from it"
        )

    logger.debug("Diff task ID is %s" % diff_task_id)
    queue = Queue(
        {
            "rootUrl": context.config["taskcluster_root_url"],
        }
    )

    artifact_url = queue.getLatestArtifact(diff_task_id, "public/diffs/apdiff.diff")["url"]
    async with context.session.get(artifact_url) as r:
        r.raise_for_status()
        apdiff_info = json.loads((await r.read()).decode())

    push_token = await context.github_auth.get_token()

    target_owner, target_repo_name = context.config['target_repos'][context.config['target']['key']].split('/', 1)

    for apworld_name, changes in apdiff_info.items():
        branch_name = f"pr-{pr_number}-{apworld_name}"
        repo = _get_repo_cache_for_branch(context, target_owner, target_repo_name, branch_name, overwrite_branch=True)
        repo.remotes.origin.set_url(f"https://git:{push_token}@github.com/{target_owner}/{target_repo_name}.git")

        for change in changes:
            await _handle_apworld_change(context, apworld_name, change, repo)

        repo.remotes.origin.push(branch_name, force=True)


async def merge_from_task():
    raise NotImplementedError("Not yet implemented")


ACTIONS = {
    "diff": diff_from_task,
    "merge": merge_from_task,
}
