# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Platform: Windows. Python 3.11 virtual environment in `.venv/` (git-ignored). Python 3.11 is used because ifcopenshell wheels lag behind newer Python releases.
- Setup: `py -3.11 -m venv .venv` then `.venv/Scripts/python.exe -m pip install -e ".[dev]"`.
- Without activating, call tools directly: `.venv/Scripts/python.exe`, `.venv/Scripts/ruff`.

## Commands

- Tests: `.venv/Scripts/python.exe -m pytest` (single test: `... -m pytest tests/test_cleaner.py::test_shared_type_keeps_union`)
- Lint/format: `.venv/Scripts/ruff check .` / `.venv/Scripts/ruff format .`
- Run GUI: `.venv/Scripts/ifcchef.exe` (gui-script, no console) or `.venv/Scripts/python.exe -m ifcchef`

## Architecture

src-layout package `ifcchef`; user-facing text is Dutch. Purpose: remove properties from the `ILS` property set that the OTL Excel does not allow for the element's `Objecttype`. Replaces a former single-file script that edited the STEP text with regex.

- `config.py`: constants: default OTL path on `Z:`, pset/property names, OTL sheet layout, `_bewerkt` suffix.
- `otl.py`: `load_otl()` reads sheet `OTL` (headers in row 2, objecttype in column C, `x`/`?` marks allowed) into `{objecttype: frozenset(property names)}`, all normalized via `normalize()` (strip + lower).
- `cleaner.py`: `clean_ils(model, otl) -> CleanReport`. Pure logic on an `ifcopenshell.file`. Elements = `IfcElement` minus openings, plus `IfcSpace`. Allowed sets are unioned per pset, so a type pset shared by several objecttypes keeps everything any of them needs. Psets linked to a skipped element (no objecttype / unknown objecttype) are left untouched. Removal edits `HasProperties` directly (not `pset.edit_pset`, which only supports single/enumerated values).
- `pipeline.py`: `process(ifc_path, otl_path, output=None, overwrite=False)`: load → clean → `model.write` → insert a comment block after `HEADER;`. Never overwrites the input; refuses an existing output unless `overwrite`.
- `gui.py`: tkinter window (OTL prefilled, IFC chooser, "Opschonen", phase + elapsed time). Does **not** run the pipeline in-process: it starts `python -m ifcchef.worker` as a subprocess, because ifcopenshell holds the GIL during `model.write` (~50 s on the Skymark model), which would freeze a thread-based GUI. A reader thread parses the worker's stdout into a queue polled with `after()`. Closing the window while busy kills the worker and deletes leftover `<output>.*.tmp` files (`pipeline.leftover_temp_files`).
- `worker.py`: stdout protocol, one message per line: `STATUS <text>` (from the pipeline's `progress` callback) and finally `RESULT <json>` (`CleanReport.to_dict()` or a user-facing Dutch error message).
- Keep the core independent of the GUI so a CLI can be added later.
- Tests build a small OTL xlsx and IFC4 model in `tests/conftest.py`.
- `tests/test_real_model.py` (marker `real`, deselected by default, ~2.5 min) runs on the original (uncleaned) Skymark model `Z:\91000 projecten\2025\25021 Skymark\01 werkmap\03 revit\06 exports\03 IFC\origineel\SKY_TO_BWK_ROO_bouwkundig.ifc` with the real OTL (~179k properties removed); run with `pytest -m real`, override the model with env var `IFCCHEF_REAL_IFC`. It is skipped when `Z:` is unreachable. This is the reference model for manual checks too; never write output to `Z:` when testing.
