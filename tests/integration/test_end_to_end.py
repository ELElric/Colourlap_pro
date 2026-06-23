"""End-to-end integration tests across repository/service/export layers."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import Base
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.exporters.csv_exporter import export_spectrum as export_csv
from colorlab_pro.exporters.csv_exporter import import_spectrum as import_csv
from colorlab_pro.exporters.json_exporter import export_spectrum as export_json
from colorlab_pro.exporters.json_exporter import import_spectrum as import_json
from colorlab_pro.repositories import project_repository
from colorlab_pro.services.spectrum_service import SpectrumService


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def test_create_project_import_spectrum_analyze_export(session_factory, tmp_path):
    service = SpectrumService(session_factory)

    with session_factory() as session:
        project = project_repository.create(session, "Integration Project")
        session.commit()
        project_id = int(project.id)

    spectrum = Spectrum(
        wavelengths=np.arange(380.0, 781.0, 10.0),
        values=np.ones(41),
        unit="mW/nm",
        meta={"name": "Equal Energy"},
    )

    sid = service.import_spectrum(project_id, spectrum)
    loaded = service.get_spectrum(sid)
    assert loaded is not None
    np.testing.assert_array_equal(loaded.wavelengths, spectrum.wavelengths)

    analysis = service.analyze(sid)
    assert analysis is not None
    assert "xyz" in analysis
    assert "xy" in analysis

    csv_path = tmp_path / "out.csv"
    export_csv(loaded, csv_path)
    assert csv_path.exists()

    reloaded_csv = import_csv(csv_path)
    np.testing.assert_array_almost_equal(reloaded_csv.wavelengths, spectrum.wavelengths)

    json_path = tmp_path / "out.json"
    export_json(loaded, json_path)
    assert json_path.exists()

    reloaded_json = import_json(json_path)
    np.testing.assert_array_equal(reloaded_json.wavelengths, spectrum.wavelengths)

    assert service.delete_spectrum(sid) is True
    assert service.get_spectrum(sid) is None
