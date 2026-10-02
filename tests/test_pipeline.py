from pathlib import Path

import ifcopenshell
import pytest

from ifcchef.pipeline import leftover_temp_files, output_path, process


def test_output_path():
    assert output_path(Path("map/model.ifc")) == Path("map/model_bewerkt.ifc")


def test_process_writes_bewerkt_file(ifc_path, otl_path):
    target, report = process(ifc_path, otl_path)

    assert target == ifc_path.with_name("voorbeeld_bewerkt.ifc")
    assert report.removed_properties == 4
    reopened = ifcopenshell.open(str(target))
    assert len(reopened.by_type("IfcWall")) == 5


def test_header_comment(ifc_path, otl_path):
    target, _ = process(ifc_path, otl_path)
    text = target.read_text(encoding="utf-8")

    header = text.split("ENDSEC;", 1)[0]
    assert "Deze IFC is bewerkt" in header
    assert str(otl_path) in header


def test_refuses_existing_output(ifc_path, otl_path):
    process(ifc_path, otl_path)
    with pytest.raises(FileExistsError):
        process(ifc_path, otl_path)
    process(ifc_path, otl_path, overwrite=True)


def test_refuses_overwriting_input(ifc_path, otl_path):
    with pytest.raises(ValueError):
        process(ifc_path, otl_path, output=ifc_path, overwrite=True)


def test_progress_and_no_temp_files_left(ifc_path, otl_path):
    phases = []
    target, _ = process(ifc_path, otl_path, progress=phases.append)

    assert len(phases) == 4
    assert leftover_temp_files(target) == []


def test_original_untouched(ifc_path, otl_path):
    before = ifc_path.read_bytes()
    process(ifc_path, otl_path)
    assert ifc_path.read_bytes() == before
