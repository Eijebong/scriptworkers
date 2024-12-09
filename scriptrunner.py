import os.path
import subprocess

CONFIG = """provisioner_id: scriptworker
worker_group: scriptworker
worker_type: {worker_type}
worker_id: {worker_id}
taskcluster_root_url: https://taskcluster.bananium.fr


artifact_upload_timeout: 1200
task_max_timeout: 1200

task_script: ["bash", "./{task_script}.sh"]

verbose: true

sign_chain_of_trust: false
verify_chain_of_trust: false
verify_cot_signature: false
cot_job_type: scriptworker
cot_product: firefox
ed25519_private_key_path: /tmp/ed25519_privkey
# Calls to Github API are limited to 60 an hour. Using an API token allows to raise the limit to
# 5000 per hour. https://developer.github.com/v3/#rate-limiting
# github_oauth_token: somegithubtoken


log_dir: "/tmp/log"
work_dir: "/tmp/work"
artifact_dir: "/tmp/artifact"
task_log_dir: "/tmp/artifact/public/logs"
"""

script_name=os.environ["WORKER_TYPE"]

with open(os.path.expanduser("~/scriptworker.yaml"), "w") as fd:
    fd.write(CONFIG.format(
        worker_type=script_name,
        worker_id=script_name,
        task_script=script_name,
    ))

subprocess.run("scriptworker")
