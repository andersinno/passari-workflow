import datetime
from collections import namedtuple

import pytest
from passari.exceptions import PreservationError
from passari_workflow.db.models import FreezeSource, MuseumObject
from passari_workflow.queue.queues import QueueType, get_queue

MockMuseumPackage = namedtuple(
    "MockMuseumPackage", ["sip_filename", "museum_object"]
)
MockMuseumObject = namedtuple(
    "MockMuseumObject", ["modified_date", "attachment_ids"]
)


TEST_DATE = datetime.datetime(
    2019, 1, 2, 10, 0, 0, 0, tzinfo=datetime.timezone.utc
)


@pytest.fixture(scope="function")
def download_object(monkeypatch, museum_packages_dir):
    def mock_download_object(object_id, package_dir, sip_id=None):
        sip_id = f"-{sip_id}" if sip_id else ""
        sip_filename = f"fake_package{sip_id}.tar"

        attachment_ids = [object_id*10, object_id*20]

        return MockMuseumPackage(
            sip_filename=sip_filename,
            museum_object=MockMuseumObject(
                modified_date=TEST_DATE,
                attachment_ids=attachment_ids
            )
        )

    monkeypatch.setattr(
        "passari_workflow.jobs.download_object.main",
        mock_download_object
    )
    monkeypatch.setattr(
        "passari_workflow.jobs.utils.PACKAGE_DIR",
        str(museum_packages_dir)
    )


    from passari_workflow.jobs.download_object import download_object
    yield download_object


def test_museum_package_missing(
        redis, session, download_object, museum_object, freeze_time):
    """
    Download a museum object when the museum object directory doesn't exist
    yet
    """
    # Do the 'download_object' job.
    freeze_time("2019-02-03 12:00:00")
    download_object(123456)

    # MuseumPackage should be created
    db_museum_object = session.query(
        MuseumObject
    ).filter(MuseumObject.id == 123456).first()

    latest_package = db_museum_object.latest_package
    assert latest_package in db_museum_object.packages

    # The current time is used as the SIP ID
    assert latest_package.sip_filename == "fake_package-20190203-120000.tar"
    # The current time "2019-02-03 12:00:00" is used as the sip ID
    assert latest_package.sip_id == "20190203-120000"
    assert latest_package.downloaded
    assert not latest_package.packaged
    # Metadata hashes are copied from the latest version of the object
    assert latest_package.metadata_hash == museum_object.metadata_hash
    assert latest_package.attachment_metadata_hash == \
        museum_object.attachment_metadata_hash
    # MuseumAttachments are added
    assert len(latest_package.attachments) == 2
    assert latest_package.attachments[0].id == 1234560
    assert latest_package.attachments[1].id == 2469120

    # New job should be enqueued
    queue = get_queue(QueueType.CREATE_SIP)
    assert queue.jobs[0].id == "create_sip_123456"
    assert queue.jobs[0].kwargs == {
        "object_id": 123456, "sip_id": "20190203-120000"
    }


def test_museum_package_repeat(
        freeze_time, redis, session, museum_object, download_object):
    """
    Repeating museum object download creates a different SIP
    """
    freeze_time("2019-02-03 12:00:00")
    download_object(123456)
    freeze_time("2019-02-03 13:15:15")
    download_object(123456)

    db_museum_object = session.query(MuseumObject).filter(
        MuseumObject.id == 123456
    ).first()
    assert len(db_museum_object.packages) == 2
    assert db_museum_object.latest_package.downloaded
    assert db_museum_object.latest_package.sip_filename == \
        "fake_package-20190203-131515.tar"
    assert db_museum_object.latest_package.sip_id == \
        "20190203-131515"
    assert len(db_museum_object.latest_package.attachments) == 2
    assert db_museum_object.latest_package.attachments[0].id == 1234560
    assert db_museum_object.latest_package.attachments[1].id == 2469120


def test_museum_package_identical_disallowed(
        freeze_time, redis, session, museum_object, download_object):
    """
    Try downloading the museum object twice at the same second.
    This is not allowed as it would make the SIP ID not unique.
    """
    freeze_time("2019-01-01 12:00:00")
    download_object(123456)
    with pytest.raises(EnvironmentError) as exc:
        download_object(123456)

    assert (
        "Package with filename fake_package-20190101-120000.tar "
        "already exists"
    ) in str(exc.value)


@pytest.mark.parametrize("with_existing_package", [True, False])
def test_preservation_error(
        session, download_object, monkeypatch, museum_packages_dir,
        archive_dir, museum_object, museum_package_factory,
        with_existing_package):
    """
    Test that encountering a PreservationError during a 'download_object'
    job will freeze the object and remove the object from the workflow.

    The test case has been parametrized with two different scenarios:
    one where a MuseumObject already has one preserved package,
    and a second one where no package has been created yet
    """
    def mock_download_object(object_id, package_dir, sip_id):
        raise PreservationError(
            detail="Mock detailed error message",
            error="Filename was not supported"
        )

    # Create the fake museum package directory
    (museum_packages_dir / "123456" / "data").mkdir(parents=True)

    monkeypatch.setattr(
        "passari_workflow.jobs.download_object.main",
        mock_download_object
    )

    # For the test case with an existing package, create a museum package that
    # was uploaded successfully earlier.
    # The PreservationError should *not* affect this package.
    if with_existing_package:
        db_museum_package = museum_package_factory(
            sip_filename="fake_package-testID2.tar",
            created_date=datetime.datetime(
                2018, 9, 1, 12, 0, 0, 0, tzinfo=datetime.timezone.utc
            ),
            preserved=True,
            museum_object=museum_object
        )
        museum_object.latest_package = db_museum_package

    session.commit()

    download_object(123456)

    # Database should be updated
    db_museum_object = session.query(MuseumObject).get(123456)

    assert db_museum_object.frozen
    assert db_museum_object.freeze_reason == "Filename was not supported"
    assert db_museum_object.freeze_source == FreezeSource.AUTOMATIC

    # The previous successful package was not updated.
    # This is because a new package is not created unless the 'download_object'
    # job is successful
    if with_existing_package:
        latest_package = db_museum_object.latest_package

        assert not latest_package.cancelled
        assert latest_package.preserved
        assert latest_package.sip_filename == "fake_package-testID2.tar"
    else:
        assert not db_museum_object.latest_package

    # No new job was enqueued
    queue = get_queue(QueueType.CREATE_SIP)
    assert not queue.job_ids

    # The museum package directory was deleted
    assert not (museum_packages_dir / "123456").is_dir()
