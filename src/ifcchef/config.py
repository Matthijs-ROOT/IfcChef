"""Vaste instellingen."""

from pathlib import Path

DEFAULT_OTL_PATH = Path(r"Z:\96000 bim\11-BIM standaarden\ILS Root\ROOT-OTL.xlsx")

# Naam van de custom propertyset die wordt opgeschoond.
PSET_NAME = "ILS"
# Property in die pset die het OTL-objecttype bevat.
OBJECTTYPE_PROPERTY = "Objecttype"

OUTPUT_SUFFIX = "_bewerkt"

# Layout van het tabblad in de OTL-Excel (1-based).
OTL_SHEET = "OTL"
OTL_HEADER_ROW = 2
OTL_OBJECTTYPE_COLUMN = 3
# Celwaarden die betekenen dat een property bij een objecttype hoort.
OTL_ALLOWED_MARKS = frozenset({"x", "?"})
