"""Controle op een echt projectmodel en de echte OTL (op de Z:-schijf).

Draait niet standaard mee; start met: pytest -m real
Ander model gebruiken: zet de omgevingsvariabele IFCCHEF_REAL_IFC.
"""

import os
from pathlib import Path

import ifcopenshell
import pytest

from ifcchef import config
from ifcchef.cleaner import _elements, clean_ils
from ifcchef.otl import load_otl
from ifcchef.pipeline import process

REAL_IFC = Path(
    os.environ.get(
        "IFCCHEF_REAL_IFC",
        r"Z:\91000 projecten\2025\25021 Skymark\01 werkmap\03 revit\06 exports\03 IFC"
        r"\origineel\SKY_TO_BWK_ROO_bouwkundig.ifc",
    )
)

pytestmark = [
    pytest.mark.real,
    pytest.mark.skipif(
        not (REAL_IFC.is_file() and config.DEFAULT_OTL_PATH.is_file()),
        reason="Echt model of OTL niet bereikbaar.",
    ),
]


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    output = tmp_path_factory.mktemp("real") / f"{REAL_IFC.stem}{config.OUTPUT_SUFFIX}.ifc"
    target, report = process(REAL_IFC, config.DEFAULT_OTL_PATH, output=output)
    return target, report


def test_properties_removed(result):
    _, report = result
    assert report.removed_properties > 0


def test_all_elements_accounted_for(result):
    _, report = result
    skipped = (
        len(report.skipped_no_pset)
        + len(report.skipped_no_objecttype)
        + len(report.skipped_unknown_objecttype)
    )
    assert report.elements_checked == report.elements_cleaned + skipped


def test_output_keeps_elements_and_is_clean(result):
    target, _ = result
    original = ifcopenshell.open(str(REAL_IFC))
    cleaned = ifcopenshell.open(str(target))

    assert len(cleaned.by_type("IfcProduct")) == len(original.by_type("IfcProduct"))
    assert len(_elements(cleaned)) == len(_elements(original))
    # Opnieuw opschonen mag niets meer verwijderen.
    assert clean_ils(cleaned, load_otl(config.DEFAULT_OTL_PATH)).removed_properties == 0
