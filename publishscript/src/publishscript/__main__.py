import scriptworker.client
import os

from . import async_main


def get_default_config(base_dir=None):
    base_dir = base_dir or os.path.dirname(os.getcwd())

    default_config = {
        "work_dir": "/tmp/work",
        "artifact_dir": "/tmp/artifact",
        "schema_file": os.path.join(
            os.path.dirname(__file__), "data", "task_schema.json"
        ),
        "taskcluster_root_url": os.environ["TASKCLUSTER_ROOT_URL"],
    }

    return default_config


def main(config_path=None):
    return scriptworker.client.sync_main(
        async_main, config_path=config_path, default_config=get_default_config()
    )


if __name__ == "__main__":
    main()
