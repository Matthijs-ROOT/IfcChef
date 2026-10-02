"""Opschonen van één IFC-bestand, van inlezen tot opslaan. Los van de GUI."""

import os
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import ifcopenshell

from ifcchef import __version__, config
from ifcchef.cleaner import CleanReport, clean_ils
from ifcchef.otl import load_otl

# "HEADER;" staat direct na de eerste regel van een IFC-bestand.
HEADER_SEARCH_BYTES = 4096
COPY_CHUNK_BYTES = 16 * 1024 * 1024


def output_path(input_path: Path) -> Path:
    """Standaard uitvoerpad: ``<stam>_bewerkt<ext>`` naast het origineel."""
    return input_path.with_name(f"{input_path.stem}{config.OUTPUT_SUFFIX}{input_path.suffix}")


def process(
    ifc_path: Path,
    otl_path: Path,
    output: Path | None = None,
    overwrite: bool = False,
    progress: Callable[[str], None] | None = None,
) -> tuple[Path, CleanReport]:
    """Schoon ``ifc_path`` op met de OTL in ``otl_path`` en sla het resultaat op.

    ``progress`` krijgt per fase een korte Nederlandse statustekst.
    Geeft het pad van het opgeslagen bestand en het rapport terug.
    """
    report_progress = progress or (lambda _text: None)
    target = output or output_path(ifc_path)
    if target.resolve() == ifc_path.resolve():
        raise ValueError("Het uitvoerbestand mag niet gelijk zijn aan het invoerbestand.")
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} bestaat al.")

    report_progress("OTL inlezen…")
    otl = load_otl(otl_path)
    report_progress("IFC-bestand openen…")
    model = ifcopenshell.open(str(ifc_path))
    report_progress("Properties opschonen…")
    report = clean_ils(model, otl)
    report_progress("Bewerkt bestand opslaan… (kan bij grote bestanden even duren)")
    model.write(str(target))
    _add_header_comment(target, otl_path)
    return target, report


def leftover_temp_files(target: Path) -> list[Path]:
    """Tijdelijke bestanden die ifcopenshell achterlaat als opslaan wordt afgebroken."""
    return list(target.parent.glob(f"{target.name}.*.tmp"))


def _add_header_comment(path: Path, otl_path: Path) -> None:
    comment = (
        "\n/***********************************************************************\n"
        "* Deze IFC is bewerkt, een geautomatiseerde opschoning heeft\n"
        "* plaatsgevonden op basis van de OTL op locatie:\n"
        f"* OTL locatie = {otl_path}\n"
        f"* Opgeschoond met IfcChef {__version__} op {datetime.now():%Y-%m-%d %H:%M}\n"
        "***********************************************************************/"
    )
    marker = b"HEADER;"
    temp = path.with_name(f"{path.name}.header.tmp")
    with path.open("rb") as source:
        start = source.read(HEADER_SEARCH_BYTES)
        head, found, rest = start.partition(marker)
        if not found:
            return
        with temp.open("wb") as destination:
            destination.write(head + marker + comment.encode("utf-8") + rest)
            shutil.copyfileobj(source, destination, COPY_CHUNK_BYTES)
    os.replace(temp, path)
