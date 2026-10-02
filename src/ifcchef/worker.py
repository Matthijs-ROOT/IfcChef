"""Voert het opschonen uit in een apart proces, zodat de GUI blijft reageren.

ifcopenshell houdt tijdens het opslaan van grote bestanden de GIL vast (bij het
Skymark-model bijna een minuut). In een thread zou het venster dan bevriezen.

Protocol via stdout (UTF-8), één bericht per regel:
  STATUS <tekst>   voortgang
  RESULT <json>    laatste regel: {"ok": true, "output": ..., "report": {...}}
                   of {"ok": false, "message": ...}
"""

import argparse
import json
import sys
from pathlib import Path

from ifcchef import pipeline

STATUS = "STATUS "
RESULT = "RESULT "


def error_message(exc: Exception) -> str:
    """Een fout in begrijpelijk Nederlands voor de gebruiker."""
    if isinstance(exc, FileNotFoundError):
        return f"Bestand niet gevonden:\n{exc.filename or exc}"
    if isinstance(exc, PermissionError):
        return (
            "Geen toegang tot het bestand. "
            f"Is het misschien geopend in een ander programma?\n\n{exc}"
        )
    return str(exc) or exc.__class__.__name__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ifcchef.worker")
    parser.add_argument("ifc", type=Path)
    parser.add_argument("otl", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    def status(text: str) -> None:
        print(STATUS + text, flush=True)

    try:
        target, report = pipeline.process(
            args.ifc, args.otl, overwrite=args.overwrite, progress=status
        )
        result = {"ok": True, "output": str(target), "report": report.to_dict()}
    except Exception as exc:  # elke fout teruggeven aan de GUI
        result = {"ok": False, "message": error_message(exc)}
    print(RESULT + json.dumps(result), flush=True)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
