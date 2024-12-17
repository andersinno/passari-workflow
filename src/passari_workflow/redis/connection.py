import os
from urllib.parse import quote

from passari_workflow.config import CONFIG

from redis import Redis


def get_redis_connection():
    """
    Get Redis connection used for the workflow, distributed locks and other
    miscellaneous tasks
    """
    redis_url = get_redis_url()
    return Redis.from_url(redis_url)


def get_redis_url():
    redis_config = CONFIG.get("redis", {})
    url = redis_config.get("url")
    host = redis_config.get("host")
    port = redis_config.get("port")
    db = redis_config.get("db") or 0
    password = redis_config.get("password") or None

    if not url and not host:  # Get URL from environment
        return os.getenv(
            "PASSARI_WORKFLOW_REDIS_URL",
            os.getenv("REDIS_URL", "redis://localhost/0"),
        )
    elif url and (host or port or db or password):
        raise EnvironmentError("The 'url' config for Redis is exclusive")

    password_part = f":{quote(password)}@" if password else ""
    port_part = f":{port}" if port else ""
    return f"redis://{password_part}{host}{port_part}/{db}"
