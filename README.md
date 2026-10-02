# IfcChef

Schoont de propertyset `ILS` in IFC-bestanden op aan de hand van de OTL
(`ROOT-OTL.xlsx`). Per element wordt het `Objecttype` opgezocht in de OTL. Properties die
daar niet bij dat objecttype zijn aangevinkt (`x` of `?`), worden verwijderd.

Het resultaat wordt naast het origineel opgeslagen als `<naam>_bewerkt.ifc`. Het
originele bestand blijft ongewijzigd.

## Gebruik

Start IfcChef met een snelkoppeling naar `.venv\Scripts\ifcchef.exe`, of vanuit PowerShell:

```powershell
.venv\Scripts\ifcchef.exe
```

1. De OTL is al ingevuld (`Z:\96000 bim\11-BIM standaarden\ILS Root\ROOT-OTL.xlsx`).
   Met **OTL kiezen…** kies je een andere.
2. Kies met **IFC kiezen…** het IFC-bestand.
3. Klik op **Opschonen**. Na afloop zie je hoeveel properties zijn verwijderd en welke
   elementen zijn overgeslagen.

### Wat wordt overgeslagen

Deze elementen laat IfcChef ongemoeid; ze komen wel in het rapport:

- elementen zonder `ILS`-pset
- elementen zonder `Objecttype`
- elementen met een objecttype dat niet in de OTL staat

Een type-pset die door meerdere elementen wordt gebruikt, houdt alle properties die voor
minstens één van die elementen zijn toegestaan.

## Installatie (ontwikkelaars)

Vereist Python 3.11 (vanwege de beschikbaarheid van ifcopenshell).

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Ontwikkelen

```powershell
.venv\Scripts\python.exe -m pytest   # tests
.venv\Scripts\python.exe -m pytest -m real  # test op het originele Skymark-model (Z:, ca. 2,5 min)
.venv\Scripts\ruff check .           # linting
.venv\Scripts\ruff format .          # formatteren
```
