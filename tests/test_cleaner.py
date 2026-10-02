import ifcopenshell.util.element
import pytest

from ifcchef.cleaner import clean_ils
from ifcchef.otl import load_otl


@pytest.fixture
def report(model, otl_path):
    return clean_ils(model, load_otl(otl_path))


def _element(model, name):
    return next(e for e in model.by_type("IfcRoot") if e.Name == name)


def _own_ils(model, name):
    """Properties van de ILS-pset die direct aan het element hangt (zonder type)."""
    for rel in _element(model, name).IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            pset = rel.RelatingPropertyDefinition
            if pset.Name == "ILS":
                return {p.Name for p in pset.HasProperties}
    return None


def test_occurrence_psets_cleaned(model, report):
    assert _own_ils(model, "beton") == {"Objecttype", "Materiaal"}
    assert _own_ils(model, "metsel") == {"Objecttype", "Kleur"}
    assert _own_ils(model, "ruimte") == {"Objecttype", "Ruimtenaam"}


def test_shared_type_keeps_union(model, report):
    wall_type = _element(model, "wandtype")
    psets = ifcopenshell.util.element.get_psets(wall_type)
    assert set(psets["ILS"]) - {"id"} == {"Materiaal", "Kleur"}
    assert report.removed_type_properties == 1


def test_skipped_elements_untouched(model, report):
    assert [s.name for s in report.skipped_no_pset] == ["zonder-ils"]
    assert [s.name for s in report.skipped_no_objecttype] == ["zonder-objecttype"]
    assert [(s.name, s.objecttype) for s in report.skipped_unknown_objecttype] == [
        ("onbekend", "glaswand")
    ]
    assert _own_ils(model, "zonder-objecttype") == {"Materiaal"}
    assert _own_ils(model, "onbekend") == {"Objecttype", "Kleur"}


def test_openings_ignored(model, report):
    assert _own_ils(model, "opening") == {"Objecttype", "Kleur"}


def test_report_counts(report):
    assert report.elements_checked == 6
    assert report.elements_cleaned == 3
    assert report.removed_occurrence_properties == 3
    assert report.removed_properties == 4
    assert "Properties verwijderd: 4" in report.summary()


def test_removed_properties_deleted_from_file(model, otl_path):
    before = len(model.by_type("IfcPropertySingleValue"))
    report = clean_ils(model, load_otl(otl_path))
    assert len(model.by_type("IfcPropertySingleValue")) == before - report.removed_properties
