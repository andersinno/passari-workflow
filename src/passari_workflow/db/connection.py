from passari_workflow.db import DBSession

from sqlalchemy import create_engine

from urllib.parse import quote_plus

from passari_workflow.config import CONFIG


def get_connection_uri():
    """
    Get the connection URI used to connect to the database
    """
    url = CONFIG["db"].get("url")
    user = CONFIG["db"].get("user")
    password = CONFIG["db"].get("password", "")
    host = CONFIG["db"].get("host")
    port = CONFIG["db"].get("port")
    name = CONFIG["db"].get("name")

    if url and not name:
        return url
    elif not url and not name:
        raise EnvironmentError("Either 'url' or 'name' is required for db")
    elif url and name:
        raise EnvironmentError("The db 'url' and 'name' are exclusive")

    if user and host and port:
        return f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{name}"
    elif user or host or port or password:
        raise EnvironmentError(
            "If 'host' is given in PostgreSQL config,"
            " also 'user' and 'port' are required"
        )
    return f"postgresql:///{name}"


def connect_db():
    """
    Connect to the database, ensuring that functions that return database
    connections work.
    """
    engine = create_engine(get_connection_uri())
    DBSession.configure(bind=engine)

    return engine
