import os
import subprocess
import jsone

CONFIG = """provisioner_id: scriptworker
worker_group: scriptworker
worker_type: {worker_type}
worker_id: {worker_id}
taskcluster_root_url: https://taskcluster.bananium.fr


artifact_upload_timeout: 1200
task_max_timeout: 1200

task_script: ["bash", "-c", "cd {task_script} && ./run.sh config.json"]

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

script_name = os.environ["WORKER_TYPE"]
trust_level = os.environ.get("TRUST_LEVEL")
worker_type = f"{script_name}-{trust_level}" if trust_level else script_name

with open("scriptworker.yaml", "w") as fd:
    fd.write(
        CONFIG.format(
            worker_type=worker_type,
            worker_id=worker_type,
            task_script=script_name,
        )
    )


if os.path.isfile(os.path.join(script_name, "config.json.tpl")):
    with open(os.path.join(script_name, "config.json.tpl")) as fd:
        context = os.environ.copy()
        rendered_config = jsone.render(fd.read(), context)

    with open(os.path.join(script_name, "config.json"), "w") as fd:
        fd.write(rendered_config)

subprocess.run("scriptworker")
