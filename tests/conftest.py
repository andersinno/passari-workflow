import datetime
import re
import subprocess
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists, drop_database

import fakeredis
import freezegun
import pytest
from passari.config import CONFIG as PAS_CONFIG
from passari_workflow.config import CONFIG
from passari_workflow.db import DBSession
from passari_workflow.db.connection import connect_db, get_connection_uri
from passari_workflow.db.models import (Base, MuseumAttachment,
                                               MuseumObject, MuseumPackage,
                                               SyncStatus)


@pytest.fixture(scope="function", autouse=True)
def redis(monkeypatch):
    server = fakeredis.FakeServer()
    conn = fakeredis.FakeStrictRedis(server=server)

    monkeypatch.setattr(
        "passari_workflow.queue.queues.get_redis_connection",
        lambda: conn
    )
    monkeypatch.setattr(
        "passari_workflow.jobs.utils.get_redis_connection",
        lambda: conn
    )
    monkeypatch.setattr(
        "passari_workflow.heartbeat.get_redis_connection",
        lambda: conn
    )

    yield conn


@pytest.fixture(scope="session")
def database(request):
    db_url = get_connection_uri(default="postgresql:///passari")
    test_db_url = re.sub(r"^([^?]*[^/?])(/?[?]?.*)$", r"\1_test\2", db_url)
    assert "_test" in test_db_url
    if database_exists(test_db_url):
        drop_database(test_db_url)
    create_database(test_db_url)
    yield create_engine(test_db_url)


@pytest.fixture(scope="function")
def engine(database, monkeypatch):
    monkeypatch.setitem(CONFIG["db"], "url", str(database.url))
    for item in ("user", "password", "host", "port", "name"):
        monkeypatch.setitem(CONFIG["db"], item, "")

    engine = connect_db()
    engine.echo = True

    # pg_trgm extension must exist
    engine.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session(engine, database):
    conn = engine.connect()
    session = DBSession(bind=conn)

    yield session

    session.close()
    conn.close()


@pytest.fixture(scope="function", autouse=True)
def museum_session_key(monkeypatch):
    """
    Mock MuseumPlus session key to prevent having to mock the session
    initialization
    """
    async def mock_get_museum_session_key():
        return "fakefakefakefakefakefakefakefake"

    monkeypatch.setattr(
        "passari.museumplus.connection.get_museum_session_key",
        mock_get_museum_session_key
    )


@pytest.fixture(scope="function", autouse=True)
def museum_packages_dir(tmpdir, monkeypatch):
    path = Path(tmpdir) / "MuseumPackages"
    path.mkdir(exist_ok=True)

    monkeypatch.setattr(
        "passari_workflow.config.PACKAGE_DIR",
        str(path)
    )
    monkeypatch.setattr(
        "passari_workflow.db.models.PACKAGE_DIR",
        str(path)
    )
    return path


TEST_DATE = datetime.datetime(
    2019, 1, 2, 10, 0, 0, 0, tzinfo=datetime.timezone.utc
)


@pytest.fixture(scope="function")
def museum_object_factory(session):
    def func(**kwargs):
        if not kwargs.get("created_date"):
            kwargs["created_date"] = TEST_DATE
        if not kwargs.get("modified_date"):
            kwargs["modified_date"] = TEST_DATE

        museum_object = MuseumObject(**kwargs)
        session.add(museum_object)
        session.commit()

        return museum_object

    return func


@pytest.fixture(scope="function")
def museum_object(museum_object_factory):
    return museum_object_factory(
        id=123456, preserved=False,
        metadata_hash=(
            "1568e677140ab834ebdbd98ffa092a273af66084eb04e13b9d07be493847b94f"
        ),
        attachment_metadata_hash=(
            "a7c4f6c82ab5ed73a359c5d875a9870d899a0642922b6f852539d048676dac74"
        )
    )


@pytest.fixture(scope="function")
def museum_package_factory(session):
    def func(**kwargs):
        if not kwargs.get("object_modified_date"):
            kwargs["object_modified_date"] = TEST_DATE
        museum_package = MuseumPackage(**kwargs)
        session.add(museum_package)
        session.commit()

        return museum_package

    return func


@pytest.fixture(scope="function")
def museum_package(session, museum_object, museum_package_factory):
    museum_package = museum_package_factory(
        sip_filename="fake_package-testID.tar",
        sip_id="testID",
        museum_object=museum_object
    )
    museum_object.latest_package = museum_package

    session.add(museum_object)
    session.commit()

    return museum_package


@pytest.fixture(scope="function")
def sync_status_factory(session):
    def func(**kwargs):
        sync_status = SyncStatus(**kwargs)
        session.add(sync_status)
        session.commit()

        return sync_status

    return func


OBJECT_XML_TEMPLATE = """
<?xml version="1.0" encoding="UTF-8"?>
<application xmlns="http://www.zetcom.com/ria/ws/module">
    <modules>
        <module name="Object">
            <moduleItem hasAttachments="false" id="{object_id}" uuid="">
                <systemField dataType="Long" name="__id">
                    <value>{object_id}</value>
                </systemField>
                <systemField dataType="Varchar" name="__lastModifiedUser">
                    <value>fakeUser</value>
                </systemField>
                <systemField dataType="Timestamp" name="__lastModified">
                    <value>2018-11-16 00:20:00.00</value>
                </systemField>
                <systemField dataType="Varchar" name="__createdUser">
                    <value>fakeUser</value>
                </systemField>
                <systemField dataType="Timestamp" name="__created">
                    <value>2018-11-16 00:20:00.00</value>
                </systemField>
            </moduleItem>
        </module>
    </modules>
</application>
"""[1:]


@pytest.fixture(scope="function")
def local_museum_package_factory(museum_package_factory, museum_packages_dir):
    def func(**kwargs):
        package = museum_package_factory(**kwargs)

        # Create the local directory
        package_dir = museum_packages_dir / str(package.museum_object.id)
        (package_dir / "data" / "reports").mkdir(parents=True)
        (package_dir / "logs").mkdir()
        (package_dir / "data" / "reports" / "Object.xml").write_text(
            OBJECT_XML_TEMPLATE.format(object_id=package.museum_object.id)
        )

        return package

    return func


@pytest.fixture(scope="function")
def local_museum_package(session, museum_object, local_museum_package_factory):
    museum_package = local_museum_package_factory(
        sip_filename="fake_package-testID.tar",
        museum_object=museum_object
    )
    museum_object.latest_package = museum_package

    session.add(museum_object)
    session.commit()

    return museum_package


@pytest.fixture(scope="function")
def museum_attachment_factory(session):
    def func(**kwargs):
        museum_attachment = MuseumAttachment(**kwargs)
        session.add(museum_attachment)
        session.commit()

        return museum_attachment

    return func


@pytest.fixture(scope="function", autouse=True)
def archive_dir(tmpdir, monkeypatch):
    path = Path(tmpdir) / "Archive"
    path.mkdir(exist_ok=True)

    monkeypatch.setattr(
        "passari_workflow.config.ARCHIVE_DIR",
        str(path)
    )
    monkeypatch.setattr(
        "passari_workflow.db.models.ARCHIVE_DIR",
        str(path)
    )
    return path


PRIVATE_KEY_PATH = Path(__file__).parent.resolve() / "data" / "test_id_rsa"


def run_sftp_server(path, port):
    key_file_path = Path(__file__).parent / "data" / "test_rsa.key"
    key_file_path = key_file_path.resolve()

    process = subprocess.Popen([
        "sftpserver", "--port", str(port), "--keyfile", str(key_file_path)
    ], cwd=str(path), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return process


@pytest.fixture(scope="function")
def sftp_dir(tmpdir, unused_tcp_port, monkeypatch):
    """
    Returns a SFTP directory that is served by a local test SFTP server
    """
    monkeypatch.setitem(PAS_CONFIG["ssh"], "host", "127.0.0.1")
    monkeypatch.setitem(PAS_CONFIG["ssh"], "port", unused_tcp_port)
    monkeypatch.setitem(
        PAS_CONFIG["ssh"], "private_key", str(PRIVATE_KEY_PATH)
    )

    sftp_dir = Path(tmpdir) / "sftp"
    sftp_dir.mkdir(exist_ok=True)

    sftp_dir.joinpath("transfer").mkdir(exist_ok=True)

    process = run_sftp_server(path=sftp_dir, port=unused_tcp_port)
    # Sleep to allow the SFTP server to start up
    time.sleep(0.5)
    yield sftp_dir

    process.terminate()


@pytest.fixture(scope="function")
def freeze_time():
    """
    Returns a function that allows freezing the time
    """
    freezers = []

    def func(time):
        # Stop the existing freezer if one exists
        try:
            freezers.pop().stop()
        except IndexError:
            pass

        freezer = freezegun.freeze_time(time)
        freezers.append(freezer)
        freezer.start()

        return freezer

    yield func

    if freezers:
        freezers[0].stop()
