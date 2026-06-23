"""Unit tests for ProjectRepository."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import Base, Project
from colorlab_pro.database.models import Spectrum as SpectrumORM
from colorlab_pro.repositories import project_repository as repo


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    with session_factory() as s:
        yield s


def test_create_returns_project(session):
    project = repo.create(session, "Test Project", "A description")
    session.commit()

    assert project.id is not None
    assert project.name == "Test Project"
    assert project.description == "A description"


def test_get_by_id_roundtrip(session):
    project = repo.create(session, "Find Me")
    session.commit()

    loaded = repo.get_by_id(session, project.id)
    assert loaded is not None
    assert loaded.id == project.id
    assert loaded.name == "Find Me"


def test_get_by_id_missing(session):
    assert repo.get_by_id(session, 9999) is None


def test_list_all_orders_by_creation(session):
    first = repo.create(session, "First")
    second = repo.create(session, "Second")
    session.commit()

    projects = repo.list_all(session)
    assert len(projects) == 2
    assert projects[0].id == first.id
    assert projects[1].id == second.id


def test_list_all_empty(session):
    assert repo.list_all(session) == []


def test_update_name_and_description(session):
    project = repo.create(session, "Old Name", "Old Desc")
    session.commit()

    updated = repo.update(session, project.id, name="New Name", description="New Desc")
    session.commit()

    assert updated is not None
    assert updated.name == "New Name"
    assert updated.description == "New Desc"

    loaded = repo.get_by_id(session, project.id)
    assert loaded.name == "New Name"
    assert loaded.description == "New Desc"


def test_update_partial(session):
    project = repo.create(session, "Name", "Desc")
    session.commit()

    updated = repo.update(session, project.id, name="Only Name")
    session.commit()

    assert updated.description == "Desc"
    assert updated.name == "Only Name"


def test_update_missing_returns_none(session):
    assert repo.update(session, 9999, name="X") is None


def test_delete_removes_project(session):
    project = repo.create(session, "To Delete")
    session.commit()

    assert repo.delete(session, project.id) is True
    session.commit()

    assert repo.get_by_id(session, project.id) is None


def test_delete_cascades_to_spectra(session):
    project = repo.create(session, "Cascade Test")
    spectrum = SpectrumORM(
        project_id=project.id,
        name="Child Spectrum",
        unit="a.u.",
        point_count=2,
    )
    session.add(spectrum)
    session.commit()

    assert repo.delete(session, project.id) is True
    session.commit()

    assert session.get(Project, project.id) is None
    assert session.get(SpectrumORM, spectrum.id) is None


def test_delete_missing_returns_false(session):
    assert repo.delete(session, 9999) is False
