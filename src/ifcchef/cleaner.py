"""Opschonen van de ILS-propertyset op basis van de OTL."""

from collections import Counter
from dataclasses import asdict, dataclass, field

import ifcopenshell
import ifcopenshell.util.element

from ifcchef import config
from ifcchef.otl import Otl, normalize


@dataclass(frozen=True)
class SkippedElement:
    global_id: str
    ifc_class: str
    name: str | None
    objecttype: str | None = None


@dataclass
class CleanReport:
    elements_checked: int = 0
    elements_cleaned: int = 0
    removed_occurrence_properties: int = 0
    removed_type_properties: int = 0
    removed_psets: int = 0
    protected_psets: int = 0
    skipped_no_pset: list[SkippedElement] = field(default_factory=list)
    skipped_no_objecttype: list[SkippedElement] = field(default_factory=list)
    skipped_unknown_objecttype: list[SkippedElement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CleanReport":
        lists = ("skipped_no_pset", "skipped_no_objecttype", "skipped_unknown_objecttype")
        values = {k: v for k, v in data.items() if k not in lists}
        return cls(**values, **{k: [SkippedElement(**i) for i in data.get(k, [])] for k in lists})

    @property
    def removed_properties(self) -> int:
        return self.removed_occurrence_properties + self.removed_type_properties

    def summary(self) -> str:
        pset = config.PSET_NAME
        lines = [
            f"Elementen gecontroleerd: {self.elements_checked}",
            f"Elementen opgeschoond: {self.elements_cleaned}",
            f"Properties verwijderd: {self.removed_properties} "
            f"(element: {self.removed_occurrence_properties}, "
            f"type: {self.removed_type_properties})",
        ]
        if self.removed_psets:
            lines.append(f"Lege {pset}-psets verwijderd: {self.removed_psets}")
        if self.protected_psets:
            lines.append(
                f"{pset}-psets ongemoeid gelaten omdat ze gedeeld worden met een "
                f"overgeslagen element: {self.protected_psets}"
            )
        for title, items, key in (
            (f"Overgeslagen, geen {pset}-pset", self.skipped_no_pset, "ifc_class"),
            (
                f"Overgeslagen, geen {config.OBJECTTYPE_PROPERTY}",
                self.skipped_no_objecttype,
                "ifc_class",
            ),
            (
                "Overgeslagen, objecttype niet in OTL",
                self.skipped_unknown_objecttype,
                "objecttype",
            ),
        ):
            if items:
                lines.append("")
                lines.append(f"{title}: {len(items)}")
                counts = Counter(getattr(item, key) for item in items)
                lines.extend(f"  - {value}: {count}x" for value, count in counts.most_common())
        return "\n".join(lines)


def clean_ils(model: ifcopenshell.file, otl: Otl) -> CleanReport:
    """Verwijder uit de ILS-psets de properties die volgens de OTL niet bij het objecttype horen.

    Een pset die door meerdere elementen wordt gebruikt (bijv. een type-pset) behoudt alle
    properties die voor minstens één van die elementen zijn toegestaan. Een pset die gekoppeld
    is aan een overgeslagen element wordt niet aangepast.
    """
    report = CleanReport()
    allowed_per_pset: dict[int, set[str]] = {}
    is_type_pset: dict[int, bool] = {}
    protected: set[int] = set()

    for element in _elements(model):
        report.elements_checked += 1
        own = _occurrence_psets(element)
        of_type = _type_psets(element)
        if not own and not of_type:
            report.skipped_no_pset.append(_describe(element))
            continue

        objecttype = _objecttype(own) or _objecttype(of_type)
        if not objecttype:
            report.skipped_no_objecttype.append(_describe(element))
            protected.update(p.id() for p in own + of_type)
            continue

        allowed = otl.get(normalize(objecttype))
        if allowed is None:
            report.skipped_unknown_objecttype.append(_describe(element, objecttype))
            protected.update(p.id() for p in own + of_type)
            continue

        for pset_list, type_level in ((own, False), (of_type, True)):
            for pset in pset_list:
                allowed_per_pset.setdefault(pset.id(), set()).update(allowed)
                is_type_pset[pset.id()] = type_level
        report.elements_cleaned += 1

    for pset_id, allowed in allowed_per_pset.items():
        if pset_id in protected:
            report.protected_psets += 1
            continue
        removed = _remove_properties(model, model.by_id(pset_id), allowed, report)
        if is_type_pset[pset_id]:
            report.removed_type_properties += removed
        else:
            report.removed_occurrence_properties += removed
    return report


def _elements(model: ifcopenshell.file) -> list[ifcopenshell.entity_instance]:
    elements = [e for e in model.by_type("IfcElement") if not e.is_a("IfcOpeningElement")]
    return elements + list(model.by_type("IfcSpace"))


def _is_ils(definition: ifcopenshell.entity_instance) -> bool:
    return definition.is_a("IfcPropertySet") and definition.Name == config.PSET_NAME


def _occurrence_psets(element: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
    psets = []
    for rel in getattr(element, "IsDefinedBy", None) or ():
        if rel.is_a("IfcRelDefinesByProperties") and _is_ils(rel.RelatingPropertyDefinition):
            psets.append(rel.RelatingPropertyDefinition)
    return psets


def _type_psets(element: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
    element_type = ifcopenshell.util.element.get_type(element)
    if element_type is None:
        return []
    return [p for p in element_type.HasPropertySets or () if _is_ils(p)]


def _objecttype(psets: list[ifcopenshell.entity_instance]) -> str | None:
    for pset in psets:
        for prop in pset.HasProperties or ():
            if prop.Name == config.OBJECTTYPE_PROPERTY and prop.is_a("IfcPropertySingleValue"):
                value = prop.NominalValue.wrappedValue if prop.NominalValue else None
                if value is not None and str(value).strip():
                    return str(value).strip()
    return None


def _remove_properties(
    model: ifcopenshell.file,
    pset: ifcopenshell.entity_instance,
    allowed: set[str],
    report: CleanReport,
) -> int:
    keep, remove = [], []
    for prop in pset.HasProperties or ():
        (keep if normalize(prop.Name) in allowed else remove).append(prop)
    if not remove:
        return 0

    if keep:
        pset.HasProperties = keep
    else:
        # Een propertyset zonder properties is ongeldig: verwijder de hele pset.
        for rel in model.get_inverse(pset):
            if rel.is_a("IfcRelDefinesByProperties"):
                model.remove(rel)
        model.remove(pset)
        report.removed_psets += 1

    for prop in remove:
        if model.get_total_inverses(prop) == 0:
            model.remove(prop)
    return len(remove)


def _describe(
    element: ifcopenshell.entity_instance, objecttype: str | None = None
) -> SkippedElement:
    return SkippedElement(
        global_id=element.GlobalId,
        ifc_class=element.is_a(),
        name=element.Name,
        objecttype=objecttype,
    )
