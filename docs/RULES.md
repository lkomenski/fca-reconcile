# Reconciliation rules

Every behavior of the tool is listed here with an ID. The same ID appears in the code comments, the test names, and the QA log. Each rule says what the tool does and what it flags. Where I made a real decision, it's recorded under the rule as **Decision:** (what I chose, what I didn't, and why).

Last updated 2026-11-08.

General principles behind every rule:
- I only auto-fix a value when it matches a known entry in `mappings.py` exactly, ignoring case and extra spaces. Anything new or ambiguous is flagged, never guessed.
- A flagged row still appears in the import file, with `status = needs_review` and a plain-English `review_reason`. If a row has more than one problem, every reason is listed, separated by "; ".
- Every row keeps its source row ID (`technician:42`, `partner:7`), using the spreadsheet row number as seen in Excel.

---

## Loading

**R1: Load the technician file.** I read the first sheet of the file (`.xlsx` or `.csv`). Row 1 is the header. I skip any later row identical to the header (a pasted-in second export) and any completely empty row. Every other row is an input row, even if most of its fields are blank. Nothing else is dropped.
- **Decision:** FMX sent all four files as `.xlsx`, and the technician file is named `Technician_Capture.csv.xlsx`. I keep them byte-for-byte with their original names in `data/`, and the loader accepts either `.xlsx` or `.csv` based on the real file extension. I didn't rename or convert them, because requirement 1 says to use the inputs as provided, and a future technician file could arrive in either format.

**R2: Load the partner file.** I read the `Equipment` sheet (or the first sheet if there's no sheet by that name). I find the header row by looking for the row containing `Facility` and `Serial Number`, not by a fixed row number. Below the header, I skip empty rows and note rows that have text only in the first column (the footer). Every other row is an input row.

**R3: Count rows in.** The number of input rows per source is the number of rows that survive R1 and R2. This is the "rows in" figure that R19 checks against.

## Mapping each field

**R4: Building.** I look up the building name in the building table in `mappings.py` (e.g. `LVMS`, `lakeview middle`, `Lakeview MS` → `Lakeview Middle School`). The three target names come from `Target_Format.xlsx`.
- Flag: unknown name → "Building 'X' is not a recognized building name". Blank → "Building is missing".

**R5: Asset type.** I look up the asset type in the asset type table in `mappings.py` (e.g. `RTU`, `roof top AC`, `RTU (gas/elec)` → `Rooftop Unit`). Every target value in the table must appear in `Asset_Types.xlsx`; the tool checks this at startup and stops if one doesn't.
- For partner rows, the type comes from the Equipment Description: I take the text before the first comma and remove the Tag value (e.g. "Hot Water Boiler B-1, 1,500 MBH" with tag `B-1` becomes "Hot Water Boiler"). Then I look it up the same way.
- Flag: not in the table → "Asset type 'X' is not in the accepted list; choose the correct type". Blank → "Asset type is missing".
- **Decision:** I deliberately left vague or off-list technician values out of the table: `fan`, `heater`, `HVAC unit`, `unit`, `Kitchen hood`, `Unit Heater`, and from the partner `Expansion Tank` and `Plate Heat Exchanger`. "Fan" could be a supply fan or an exhaust fan, and "heater" could be a water heater or a unit heater. Unit Heater, Expansion Tank, and Plate Heat Exchanger aren't in FMX's accepted list at all. Picking one would be a guess.

**R6: Manufacturer.** I look up the manufacturer in the manufacturer table in `mappings.py`, which only combines spelling variants of the same name (e.g. `TRANE`, `trane`, `Trane Inc.` → `Trane`; `Green Heck` → `Greenheck`; `Square-D`, `SquareD` → `Square D`).
- Flag: not in the table → "Manufacturer 'X' is not a recognized spelling; confirm the manufacturer". Blank while model or serial is filled in → "Manufacturer is missing". If manufacturer, model and serial are all blank, R12 covers it instead.
- **Decision:** I only combine spellings of one name. Cutler-Hammer and Eaton stay separate even though Eaton owns Cutler-Hammer, because deciding two brands are the same is a guess. I treated `B&G` and `Bell and Gossett` as spellings of `Bell & Gossett` (same name, abbreviated), and `Daikin Applied` as `Daikin` (same name with a division suffix, like `Trane Inc.`). I don't map plain `Mitsubishi`: Mitsubishi Electric and Mitsubishi Heavy Industries both make mini-splits, so it gets flagged.

**R7: Model and serial number.** Kept exactly as captured, with leading and trailing spaces trimmed. Numbers that Excel stored as numbers (e.g. serial `684796`, model `11`) are written as plain text without a decimal point.

**R8: Location.** Kept as captured, trimmed. Room numbers stored as numbers (e.g. `103`) are written as text.
- **Decision:** FMX's first example row shows `cafeteria roof` rewritten as `Roof - Cafeteria`, but the requirements never ask for location cleanup, and rewriting free text means guessing at the technician's meaning. I keep what was captured.

## Install year

**R9: Install year.** I turn the captured year into a four-digit year:
- A four-digit year is kept as is (e.g. `1998`).
- Two digits, with or without an apostrophe (`'04`, `98`, `21`): 00–26 becomes 20xx and 27–99 becomes 19xx.
- A manufacture date like `Mfg 04/2011` becomes `2011`.
- An approximate year (`approx. 2004`, `~2004`, `2004?`, `c. 2012`) keeps the year, stays ready, and is counted in the run summary as "approximate years accepted".
- Blank stays blank and isn't flagged by itself.
- Flag: a year after the current year (e.g. `2031`) → "Install year 2031 is in the future". Anything else that isn't a clear single year (e.g. `19987`, `2000s`, `unknown`) → "Install year 'X' could not be read as a year".
- **Decision (approximate years):** I keep approximate years and mark them ready. Capital plans are estimates, and a reviewer can't improve on the technician's estimate without a site visit, so flagging them would add review rows nobody can fix from a desk. I count them in the summary so they stay visible.
- **Decision (two-digit years):** 00–26 → 2000s and 27–99 → 1900s, because a two-digit year has one sensible reading. Decades, typos, and "unknown" have no single reading, so a person decides.
- **Decision (partner year):** The partner's year is the year of manufacture (their footer says so). For partner-only rows I use it as the install year and mark the row ready, and the run summary counts these rows as "partner year of manufacture used as install year". It's the best estimate available and is usually within a year of install.

## Condition

**R10: Technician condition, 1–10 → 1–5.** Half the score, rounded up: 1–2→1, 3–4→2, 5–6→3, 7–8→4, 9–10→5. Decimals use the same formula (3.5→2, 5.5→3).
- Flag: blank → "Condition is missing". Outside 1–10 (e.g. `11`) → "Condition 11 is outside the technician's 1-10 scale". Not a number (e.g. `Good`) → "Condition 'Good' is not a number on the technician's 1-10 scale".
- **Decision:** I chose half the score rounded up because it matches FMX's own example rows (technician 3 → 2, 7 → 4).

**R11: Partner condition, text → 1–5.** Good→4, Fair→3, Poor→2, Critical→1. Nothing maps to 5.
- Flag: anything else, including blank → "Condition 'X' is not one of Good, Fair, Poor, Critical".
- **Decision:** Good maps to 4, not 5, because FMX's example row maps Good to 4 and the partner's legend defines Good as "operating as intended," not new.

## Problems that need a person

**R12: Nameplate missing.** If manufacturer, model, and serial are all blank, the row is flagged: "Nameplate data missing; technician photo IMG_0527.jpg on file", using the Photo column. If there's no photo: "Nameplate data missing; no photo on file".
- **Decision:** A blank serial on its own isn't flagged. Every row with only the serial missing is an electrical panel (21 rows), and panels usually don't carry a serial. Flagging them would fill the review list with rows nobody can fix.

**R13: Serial that Excel may have rounded.** If the serial was stored as a number in Excel and ends in four or more zeros (e.g. `4430000000`), flag: "Serial 4430000000 may have been rounded by Excel; check the photo or nameplate".

**R14: One row describing several units.** If a partner Equipment Description contains a quantity like "(qty 4)", flag: "One row describes 4 units (tag UV-214 to UV-217); each unit needs its own row and serial".

**R15: Notes that affect the row.** If a technician note or partner comment contains a keyword from the notes keyword list in `mappings.py` (`replaced`, `abandoned`, `2nd pass`, `locked out`), flag the row and quote the note: "Technician note may affect this row: 'replaced 2016 per custodian'".
- **Decision:** I added a short keyword list instead of ignoring notes. Without it, a row noting the unit was replaced in 2016 would go out as ready with install year 1998. It's still a lookup in `mappings.py`, not interpretation: the tool doesn't try to act on the note, it just puts it in front of a person.

## Duplicates

**R16: Finding duplicates.** Two or more rows are the same equipment if they have the same building (after R4) and the same serial number, comparing with spaces, dashes, and case ignored. This applies across both files and within the technician file. Blank serials and placeholder values (`N/A`, `see schedule`, and the other entries in the serial placeholder list in `mappings.py`) are never matched. All rows sharing a building and serial become one output row. `source` is `both` if the group has rows from both files, otherwise the name of the one file.
- **Decision:** Serial is the only field that identifies a specific unit, so it's the only thing I match on. Matching on tag, model, or location could merge two different units. Rows with no usable serial are never merged in this version.

**R17: Filling in a merged row.** For each field I use the preferred source, falling back to the other source when the preferred value is blank or was flagged:
- `model`, `serial_number`: partner first.
- `building`, `asset_type`, `manufacturer`, `location`: technician first.
- `install_year`: R18. `condition`: R19.
A problem stays on the merged row only if it belongs to the value actually used, or isn't about a single field (R14, R15). For example, a technician's missing nameplate (R12) is resolved when the partner supplies one. The review list shows every source row ID in the group.
- **Decision:** I take model and serial from the partner when present because it's the cleaner nameplate copy, typed at a desk from the nameplate. For example the technician entered `67W-465 53NA` where the partner has `67W46553NA`. I keep the technician's location because the technician was on site at every building and FMX's example row 2 uses the technician's location (`Roof - Gym`, not the partner's `Roof, Gymnasium`). The other fields default to the technician, the primary source covering all three buildings.

**R18: Install year in a merged row.** I use the technician's install year. If it's blank or flagged, I use the other row's year. If both years are present, valid, and more than 2 years apart, I still use the technician's year and flag: "Install year differs between sources: technician 2019, partner 2004 (year of manufacture)".
- **Decision:** A gap of 2 years or less isn't flagged, because the partner records year of manufacture, so a 1-year gap is expected, not a conflict. When two technician rows are merged, the same rule applies, with the first-captured row treated as the technician side.

**R19: Condition in a merged row.** After both are converted to 1–5, I fill in the worse (lower) rating. If they differ by 1 or not at all, the row is ready. If they differ by 2 or more, I still fill in the worse rating and flag it: "Condition differs between sources: technician 4/10 (2 of 5), partner Good (4 of 5); used the lower rating". If one side is blank or flagged, I use the other side.
- **Decision:** The worse rating is the cautious choice for capital planning, and a gap of 2 or more means one person saw something the other didn't, so a person should look.

## Accounting and outputs

**R20: Status and reasons.** A row with any reason from the rules above gets `status = needs_review` and every reason joined with "; ". A row with no reasons gets `status = ready` and a blank `review_reason`.

**R21: Row accounting.** Rows in (R3) must equal rows ready + rows needs_review + rows merged away, where "merged away" means the extra rows folded into a duplicate (a group of 2 counts as 1 merged). If the numbers don't add up, the tool stops with an error and writes nothing, so a lost row can never go unnoticed.

**R22: Outputs.** Written to the output folder:
- `import_ready.csv`: exactly the columns of `Target_Format.xlsx`, in order, with every output row (ready and needs_review).
- `review_list.csv`: only needs_review rows, with the reason, the source row IDs, and the raw captured values next to the cleaned ones.
- `run_summary.md`: rows in per source, rows ready, rows flagged, duplicates merged, approximate years accepted, partner years of manufacture used, and a count per type of review reason.
