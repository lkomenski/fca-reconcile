# Reconciliation rules

Each behavior of the tool has a rule ID. The same ID is used in code comments, test names, and the QA log. Each rule states what the tool does and what it flags. Where a rule reflects a real choice, the choice is recorded under it as **Decision:** (what was chosen and what wasn't) followed by **Why:**.

Last updated 2026-11-08.

Principles that apply to every rule:
- A value is auto-fixed only when it matches a known entry in `mappings.py` exactly, ignoring case and extra spaces. Anything new or ambiguous is flagged, never guessed.
- A flagged row still appears in the import file, with `status = needs_review` and a plain-English `review_reason`. A row with more than one problem lists every reason, separated by "; ".
- Every row keeps its source row ID (`technician:42`, `partner:7`): the spreadsheet row number as shown in Excel.

---

## Loading

**R1: Load the technician file.** The tool reads the first sheet of the file (`.xlsx` or `.csv`). Row 1 is the header. Any later row identical to the header (a pasted-in second export) and any completely empty row are skipped. Every other row is an input row, even if most of its fields are blank. Nothing else is dropped.
- **Decision:** The files are kept byte-for-byte, with their original names, in `data/`. The loader accepts `.xlsx` or `.csv` based on the real file extension. The files are not renamed or converted.
- **Why:** FMX sent all four files as `.xlsx`, and the technician file is named `Technician_Capture.csv.xlsx`. Requirement 1 says to use the inputs as provided, and I want the tool to handle a future technician file in either format.

**R2: Load the partner file.** The tool reads the `Equipment` sheet, or the first sheet if no sheet has that name. The header row is found by looking for a row containing `Facility` and `Serial Number`, not by a fixed row number. Below the header, empty rows, note rows with text only in the first column (the footer), and repeated copies of the header are skipped. Every other row is an input row.

**R3: Count rows in.** Rows in, per source, is the number of rows left after R1 and R2. R21 checks this number.

## Mapping each field

**R4: Building.** The building name is looked up in the building table in `mappings.py` (e.g. `LVMS`, `lakeview middle`, `Lakeview MS` → `Lakeview Middle School`). The three target names match `Target_Format.xlsx`.
- If the name isn't in the table, a keyword fallback (`BUILDING_KEYWORDS` in `mappings.py`) is tried:
  - A word starting with "elem", or the word "ES" → Lakeview Elementary School.
  - "middle" or "MS" → Lakeview Middle School.
  - "high" or "HS" → Lakeview High School.
  - Matching is case-insensitive and on whole words, so "LMS", "Estates" and "Highland" don't match.
  - Names accepted this way are listed in the run summary so they can be added to the table.
- Flag: no keyword match → "Building 'X' is not a recognized building name". More than one match → "Building 'X' could mean more than one building (...)". Blank → "Building is missing".
- **Decision:** The alias list stays and is checked first. Keywords are a fallback for spellings it doesn't cover, so a new building spelling on an unseen file doesn't have to be added by hand before the tool can use it.
- **Why:** The district has three buildings, so a name containing "middle" can only mean one of them. Matching more than one building, or none, is still a guess, so it's flagged. One known limit: a name from outside the district, like "Westlake Middle", would be accepted as Lakeview Middle School. It shows up in the run summary's keyword list, but the row isn't flagged (QA-020).

**R5: Asset type.** The accepted asset types are read from `Asset_Types.xlsx` every run, not copied into the code, so an exact accepted name (any case or spacing) is always recognized. Other spellings come from the asset type table in `mappings.py` (e.g. `RTU`, `roof top AC`, `RTU (gas/elec)` → `Rooftop Unit`). At startup the tool checks that every value the table maps to appears in `Asset_Types.xlsx`, and stops if one doesn't.
- For partner rows, the type comes from the Equipment Description. The tool takes the text before the first comma, removes the Tag value and any "(qty N)" note, and looks up what's left. For example, "Hot Water Boiler B-1, 1,500 MBH" with tag `B-1` becomes "Hot Water Boiler".
- Flag: a value not in the table → "Asset type 'X' is not in the accepted list; choose the correct type". Blank → "Asset type is missing".
- **Decision:** These values are deliberately left out of the table, so they get flagged: `fan`, `heater`, `HVAC unit`, `unit`, `Kitchen hood`, `Unit Heater`, plus the partner's `Expansion Tank` and `Plate Heat Exchanger`.
- **Why:** "Fan" could be a supply fan or an exhaust fan, and "heater" could be a water heater or a unit heater. Unit Heater, Expansion Tank, and Plate Heat Exchanger aren't in FMX's accepted list at all. Picking one would be a guess.

**R6: Manufacturer.** The manufacturer is looked up in the manufacturer table in `mappings.py`. The table only combines spelling variants of the same name: `TRANE`, `trane`, `Trane Inc.` → `Trane`; `Green Heck` → `Greenheck`; `Square-D`, `SquareD` → `Square D`.
- Flag: a value not in the table → "Manufacturer 'X' is not a recognized spelling; confirm the manufacturer". Blank while the model or serial is filled in → "Manufacturer is missing". When the manufacturer, model, and serial are all blank, R12 applies instead.
- **Decision:** Only spellings of one name are combined, so Cutler-Hammer and Eaton stay separate. `B&G` and `Bell and Gossett` are treated as spellings of `Bell & Gossett`, and `Daikin Applied` as `Daikin`. Plain `Mitsubishi` is not mapped and gets flagged.
- **Why:** Fixing a spelling is safe, but deciding two brands are the same is a guess, even when one company owns the other. To me, B&G is the same name abbreviated, and "Applied" is a division suffix like "Inc.". Mitsubishi Electric and Mitsubishi Heavy Industries both make mini-splits, so I can't tell which one "Mitsubishi" means.

**R7: Model and serial number.** Kept exactly as captured, with leading and trailing spaces trimmed. Values Excel stored as numbers (e.g. serial `684796`, model `11`) are written as plain text with no decimal point.

**R8: Location.** A location that is only a room number is standardized to `Rm <number>`: `103`, `Room 103`, `rm103`, `Rm. 103` and `RM 103` all become `Rm 103`. The whole value must be a room number (1–4 digits, optionally after "Room" or "Rm"). Anything else is kept as captured and trimmed, including locations that merely contain a room number, like `Mech Rm 104` or `Kitchen 115`. Nothing is flagged.
- **Decision:** Only room-number formats are standardized. All other locations are kept as captured.
- **Why:** A bare room number has one right answer, and `Rm 205` is the format FMX's own example row uses. Other free text, like FMX's example rewriting `cafeteria roof` as `Roof - Cafeteria`, means guessing what the technician meant, and I'd want an agreed location format first. See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) #5.

## Install year

**R9: Install year.** The captured year becomes a four-digit year:
- A four-digit year is kept as is (e.g. `1998`).
- A two-digit year, with or without an apostrophe (`'04`, `98`, `21`): up to the last two digits of the current year becomes 20xx, and anything higher becomes 19xx. Run in 2026, that means 00–26 → 2000s and 27–99 → 1900s.
- A manufacture date like `Mfg 04/2011` becomes `2011`.
- An approximate year (`approx. 2004`, `~2004`, `2004?`, `c. 2012`) keeps the year, stays ready, and is counted in the run summary as "approximate years accepted".
- Blank stays blank and is not flagged on its own.
- Flag: a year after the current year (e.g. `2031`) → "Install year 2031 is in the future". Anything else that isn't a clear single year from 1900 on (e.g. `19987`, `2000s`, `unknown`) → "Install year 'X' could not be read as a year".
- "Current year" means the year the tool is run, from the computer's clock, so nothing is hard-coded to 2026. Both the future-year check and the two-digit cutoff use it.
- **Decision (approximate years):** Approximate years are kept, marked ready, and counted in the summary.
- **Why:** Capital plans are estimates, and a reviewer can't improve on the technician's estimate without a site visit. Flagging these would add review rows nobody can fix from a desk.
- **Decision (two-digit years):** A two-digit year that would land in the future reads as the 1900s, and anything else reads as the 2000s. The cutoff follows the current year, not a fixed 26.
- **Why:** A two-digit year has one sensible reading. Tying the cutoff to the current year keeps the rule correct in later years and matches the future-year check exactly. Decades, typos, and "unknown" have no single reading, so a person should decide.
- **Decision (partner year):** Whenever the output install year comes from the partner file, the year of manufacture is used as the install year. That covers a partner-only row, and a merged row where the technician's year was blank or flagged. The run summary counts these as "partner year of manufacture used as install year".
- **Why:** The partner's footer says its year is the year of manufacture. That's the best estimate available and is usually within a year of install.

## Condition

**R10: Technician condition, 1–10 → 1–5.** Half the score, rounded up: 1–2→1, 3–4→2, 5–6→3, 7–8→4, 9–10→5. Decimals use the same formula (3.5→2, 5.5→3).
- Flag: blank → "Condition is missing". Outside 1–10 (e.g. `11`) → "Condition 11 is outside the technician's 1-10 scale". Not a number (e.g. `Good`) → "Condition 'Good' is not a number on the technician's 1-10 scale".
- **Decision:** Half the score, rounded up.
- **Why:** It matches FMX's own example rows (technician 3 → 2, 7 → 4).

**R11: Partner condition, text → 1–5.** Good→4, Fair→3, Poor→2, Critical→1. Nothing maps to 5.
- Flag: blank → "Condition is missing". Anything else → "Condition 'X' is not one of Good, Fair, Poor, Critical".
- **Decision:** Good maps to 4, not 5.
- **Why:** FMX's example row maps Good to 4, and the partner's legend defines Good as "operating as intended," not new.

## Problems that need a person

**R12: Nameplate or serial missing.** A row whose manufacturer, model, and serial are all blank is flagged: "Nameplate data missing; technician photo IMG_0527.jpg on file", with the file name taken from the Photo column. With no photo: "Nameplate data missing; no photo on file".
- A row with a blank or placeholder serial (`N/A`, `see schedule`, and the other entries in the serial placeholder list) is flagged "Serial number missing", unless its asset type is on the list of asset types allowed to have no serial in `mappings.py` (currently Electrical Panel only). An unrecognized asset type isn't on the list, so it's flagged too. When the whole nameplate is blank, only the nameplate reason is given, not both.
- **Decision:** An editable list of asset types allowed to have no serial, starting with Electrical Panel. It replaces a blanket rule that a blank serial on its own is never flagged.
- **Why:** I didn't know which equipment commonly lacks a serial, so it's an editable list rather than a blanket exception. In this data every row with only the serial missing is an electrical panel (21 rows), which is why the list starts there. Anyone who learns that another type usually has no serial can add it in `mappings.py` without touching the code. See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) #7.

**R13: Serial that Excel may have rounded.** A serial made only of digits that ends in four or more zeros (e.g. `4430000000`) is flagged: "Serial 4430000000 may have been rounded by Excel; check the photo or nameplate".
- **Decision:** The check is "all digits", not "stored as a number in Excel".
- **Why:** A CSV file has no number type, and the same damage shows up there. A real serial that happens to end in 0000 gets flagged too, but I'd rather someone spend one quick check than have a wrong serial in the import.

**R14: One row describing several units.** A partner Equipment Description with a quantity like "(qty 4)" is flagged: "One row describes 4 units (tag UV-214 to UV-217); each unit needs its own row and serial".

**R15: Notes that affect the row.** A technician note or partner comment containing a keyword from the notes keyword list in `mappings.py` (`replaced`, `abandoned`, `locked out`, `out of service`, `disconnected`, `removed`, `decommissioned`, `inoperable`, `failed`, `leak`, `red tag`) is flagged, with the note quoted: "Technician note may affect this row: 'replaced 2016 per custodian'" (or "Partner comment ..."). A second list holds repeat-entry keywords (`2nd pass`, `second pass`, `logged again`). These flag a row only if it was **not** merged into a duplicate by R16: "Technician note says this is a repeat entry, but no matching serial was found: '...'".
- **Decision:** Notes are checked against a short keyword list, not ignored. Repeat-entry notes are only flagged on rows that didn't merge.
- **Why:** Without the check, a row noting the unit was replaced in 2016 would go out as ready with install year 1998. It's a lookup in `mappings.py`, not interpretation: the tool puts the note in front of a person and doesn't act on it. A "2nd pass" note is exactly the problem R16 solves. When the serial matched and the rows merged, the note is already handled. When nothing matched (e.g. a panel with no serial), the note is the only clue that the row is a repeat.

## Duplicates

**R16: Finding duplicates.** Two or more rows are the same equipment if they have the same building (after R4) and the same serial number, compared with spaces, dashes, and case ignored. This applies across both files and within the technician file.
- Blank serials and placeholder values (`N/A`, `see schedule`, and the other entries in the serial placeholder list in `mappings.py`) are never matched.
- All rows sharing a building and serial become one output row.
- `source` is `both` if the group has rows from both files, and otherwise the name of the one file.
- **Decision:** Matching uses building plus serial only. Rows with no usable serial are never merged in this version.
- **Why:** Serial is the one field that identifies a specific unit. Matching on tag, model, or location could merge two different units.

**R17: Filling in a merged row.** Each field comes from the preferred source, falling back to the other source when the preferred value is blank or was flagged:
- `model`, `serial_number`: partner first.
- `building`, `asset_type`, `manufacturer`, `location`: technician first.
- `install_year`: R18. `condition`: R19.

A problem stays on the merged row only if it belongs to a value actually used, or isn't about a single field (R14, R15). The review list shows every source row ID in the group.
- **Decision:** Model and serial come from the partner when present. Location comes from the technician. The other fields default to the technician.
- **Why:** I take the partner's model and serial because it's the cleaner nameplate copy, typed at a desk from the nameplate. For example, the technician entered `67W-465 53NA` where the partner has `67W46553NA`. I keep the technician's location because the technician was on site at every building, and FMX's example row 2 uses the technician's location (`Roof - Gym`, not the partner's `Roof, Gymnasium`). The other fields default to the technician because it's the primary source and covers all three buildings.

**R18: Install year in a merged row.** The technician's install year is used. If it is blank or flagged, the other row's year is used. If both years are present and valid but more than 2 years apart, the technician's year is still used, and the row is flagged: "Install year differs between sources: technician:105 2019, partner:43 2004 (year of manufacture)".
- **Decision:** A gap of 2 years or less is not flagged. When two technician rows merge, the row captured first counts as the technician side.
- **Why:** The partner records year of manufacture, so a 1-year gap is expected, not a conflict. Whose year wins is an open question; see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) #1 and #2.

**R19: Condition in a merged row.** After both ratings are converted to 1–5, the worse (lower) one is filled in. If they differ by 0 or 1, the row is ready. If they differ by 2 or more, the worse rating is still filled in and the row is flagged: "Condition differs between sources: technician:100 4/10 (2 of 5), partner:42 Good (4 of 5); used the lower rating". If one side is blank or flagged, the other side is used.
- **Decision:** Always the worse rating. A gap of 2 or more is flagged.
- **Why:** The worse rating is the cautious choice for capital planning. A gap of 2 or more means one person saw something the other didn't, so a person should look. Whose rating to trust is an open question; see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) #1.

## Accounting and outputs

**R20: Status and reasons.** A row with any reason from the rules above gets `status = needs_review`, with every reason joined by "; ". A row with no reasons gets `status = ready` and a blank `review_reason`.

**R21: Row accounting.** Rows in (R3) must equal rows ready + rows needs_review + rows merged away. "Merged away" counts the extra rows folded into a duplicate, so a group of 2 counts as 1. Every input row ID must also appear in exactly one output row. If either check fails, the tool stops with an error and writes nothing, so a lost row can't go unnoticed.

**R22: Outputs.** Written to the output folder:
- `import_ready.csv`: exactly the columns of `Target_Format.xlsx`, in order, with every output row (ready and needs_review).
- `review_list.csv`: only needs_review rows, with the reason, the source row IDs, and the raw captured values next to the cleaned ones.
- `run_summary.md`: rows in per source, rows ready, rows flagged, duplicates merged, approximate years accepted, partner years of manufacture used, and a count for each type of review reason. It also lists every value the tool didn't recognize, by field (building, asset type, manufacturer, condition, install year), with the file it came from and the number of input rows, plus every building name accepted by keyword. A specialist can then update `mappings.py` in one pass.
