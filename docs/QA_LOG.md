# QA log

A running log of everything that looked off, broke, or turned out to be a false alarm. Row IDs use the spreadsheet row number as it appears in Excel (for example `technician:76` is row 76 of the technician sheet), so anyone can find the row by opening the file.

### QA-001 · 2026-11-08 16:00 · Input files are Excel, not CSV, and sit in a different folder
**Rule(s):** R1
**What looked off:** My plan expected `data/technician_capture.csv`, `data/partner_equipment_list.xlsx`, `data/target_format.csv` and `data/asset_types.csv`. The repo actually has four `.xlsx` files under `condition scales/data/`: `Technician_Capture.csv.xlsx`, `Partner_Equipment_List.xlsx`, `Target_Format.xlsx`, `Asset_Types.xlsx`.
**What I suspected:** The technician file had been converted to CSV and only kept the `.csv` in its name.
**What it actually was:** All four are real Excel workbooks (openpyxl opens each one). The technician file is an Excel file whose name includes `.csv`.
**How I proved it:** I opened each file with openpyxl and listed its sheets: `Technician Capture` (148 rows), `Equipment` + `Legend` (61 + 5 rows), `target_format` (4 rows), `asset_types` (18 rows).
**Fix:** I decided to keep all four files byte-for-byte, with original names, in `data/`, and to make the loader accept `.xlsx` or `.csv` (R1). I moved them out of the stray `condition scales/` folder, which also held an empty `requirements.txt`, and removed that folder.
**Verified by:** SHA-256 of all four files before and after the move: `sha256sum -c` reported OK for each.

### QA-002 · 2026-11-08 16:03 · [AI error] Inspection script named `inspect.py` broke openpyxl
**Rule(s):** none (tooling)
**What looked off:** The first inspection script crashed with `partially initialized module 'openpyxl' has no attribute 'load_workbook' (most likely due to a circular import)`.
**What I suspected:** A broken openpyxl install.
**What it actually was:** The AI named its scratch script `inspect.py`. Python puts the script's own folder first on the import path, so when openpyxl ran `import inspect` it loaded the AI's script instead of Python's built-in `inspect` module.
**How I proved it:** The traceback shows `openpyxl/compat/__init__.py` line 8 `import inspect` landing in the scratch `inspect.py`. After renaming the file to `fca_inspect.py` and deleting `__pycache__`, the same code ran cleanly.
**Fix:** Renamed the script. Lesson: never give a script the same name as a standard-library module.
**Verified by:** Rerun produced the full report (146 technician rows, 55 partner rows).

### QA-003 · 2026-11-08 16:05 · Technician sheet has a repeated header row partway down
**Rule(s):** R1
**What looked off:** `technician:96` is `Bldg, Equip Type, Mfr, ...`, an exact copy of the header row, between the middle-school and high-school rows.
**What I suspected:** Two exports pasted together, one per day.
**What it actually was:** Same thing. It isn't data, so it must be skipped and not counted as an input row.
**How I proved it:** The row equals row 1 cell for cell. Without it there are 146 data rows (148 total − header − repeated header).
**Fix:** Pending. The loader drops any row that matches the header.
**Verified by:** Pending. Expected count: 146 technician rows in.

### QA-004 · 2026-11-08 16:05 · Partner sheet has title rows, a blank row, and a footer note
**Rule(s):** R1
**What looked off:** Rows 1–3 of `Equipment` are a title, a "Prepared by" line, and a blank row. The real header is row 4. Rows 60–61 are blank plus a footer saying "Year is year of manufacture from the nameplate."
**What I suspected:** Standard report formatting around the table.
**What it actually was:** Same. The footer also matters for the rules: the partner year is year of manufacture, not install year (decision 6).
**How I proved it:** Data rows are 5–59, which gives 55 rows. Each one has `Facility = Lakeview HS`.
**Fix:** Pending. The loader finds the header row by its column names, not by a fixed row number, so a partner file with a different title block still loads.
**Verified by:** Pending. Expected count: 55 partner rows in.

### QA-005 · 2026-11-08 16:06 · Technician condition values outside the 1–10 scale
**Rule(s):** R10
**What looked off:** `technician:76` condition is `Good`, `technician:144` is `11`, and `technician:6, 40, 59, 113, 134` are blank. There are also two decimals, `technician:21` = 3.5 and `technician:57` = 5.5.
**What I suspected:** Typos and skipped fields.
**What it actually was:** As expected. Decision 1 covers all of them: 7 flagged (1 text, 1 out of range, 5 blank), and the decimals convert to 2 and 3.
**How I proved it:** Distinct-value count of `Cond (1-10)`: 13 distinct values, listed in the inspection report.
**Fix:** Covered by R10. Implementation pending.
**Verified by:** Pending.

### QA-006 · 2026-11-08 16:07 · Numeric serial `4430000000` looks rounded by Excel
**Rule(s):** R13
**What looked off:** `technician:85` (Generac SD150, middle school) has serial `4430000000` stored as a number. The other Generac serials have no trailing zero run (`4586578415`, `4168275953`).
**What I suspected:** Someone typed or pasted a long serial, Excel showed it as `4.43E+09`, and the digits were lost.
**What it actually was:** I can't prove it from the data alone. Open question.
**How I proved it:** Not yet proven. Compared against the other 10-digit Generac serials.
**Fix:** I decided to flag numeric serials ending in four or more zeros (R13). Implementation pending.
**Verified by:** Pending.

### QA-007 · 2026-11-08 16:07 · FMX's example row has a cleaned-up location the requirements don't mention
**Rule(s):** R8
**What looked off:** Example row 1 in `Target_Format.xlsx` is clearly `technician:16` (same serial `98C69138WD`), but the location `cafeteria roof` appears as `Roof - Cafeteria`.
**What I suspected:** Location normalization might be an unstated requirement.
**What it actually was:** Judgment call. The requirements only say model and serial are "as captured, trimmed" and say nothing about location. Rewriting free-text locations is guesswork.
**How I proved it:** Matched serial `98C69138WD` across both files. Example row 2 (`64W84118WM`, `Roof - Gym`) matches `technician:98` exactly, so I only have one example of a rewritten location.
**Fix:** Judgment call: I keep location as captured and trimmed (R8, decision recorded there). No code needed beyond trimming.
**Verified by:** Pending.

### QA-008 · 2026-11-08 16:08 · Notes that contradict or invalidate a row
**Rule(s):** R15
**What looked off:** `technician:9` year 1998, note "replaced 2016 per custodian". `technician:53` note "abandoned in place, disconnected from loop". `technician:143` note "Panel LP-2A, 2nd pass", which is the same panel as `technician:141` (high school, LP-2A, no serial), so the serial rule can't merge them.
**What I suspected:** Rows that would come out "ready" with wrong or misleading data.
**What it actually was:** Real risk. Without some handling of notes, `technician:9` gets install year 1998 and status ready, and LP-2A appears twice in the import.
**How I proved it:** Read every non-blank note (about 60). These three are the clear cases.
**Fix:** I decided on a short notes-keyword list in `mappings.py` (R15) that flags the row and quotes the note. Implementation pending.
**Verified by:** Pending.

### QA-009 · 2026-11-08 16:08 · One partner row covers four units
**Rule(s):** R14
**What looked off:** `partner:54` is "Unit Ventilators (qty 4)", serial `see schedule`, tag `UV-214 to UV-217`.
**What I suspected:** Four assets packed into one row.
**What it actually was:** Same. It can't be imported as one asset and the tool shouldn't invent four rows, so it needs a person.
**How I proved it:** Comments column: "Typical of 4, serials on mechanical schedule."
**Fix:** Flagged by R14. Implementation pending.
**Verified by:** Pending.

### QA-010 · 2026-11-08 16:24 · [AI error] Rule IDs in the first RULES.md draft were out of order
**Rule(s):** R9–R12
**What looked off:** In the first draft of RULES.md the nameplate rule was numbered R9 but appeared after R10–R12, because it was moved to the "problems" section without being renumbered.
**What I suspected:** Just a cosmetic slip, but rule IDs are used in code, tests, and logs, so out-of-order IDs would make all of them harder to follow.
**What it actually was:** The AI drafted the rules in one order and then moved a section.
**How I proved it:** Listed every `**R#:` heading in order: R1–R8, R10, R11, R12, R9, R13...
**Fix:** Renumbered (year → R9, technician condition → R10, partner condition → R11, nameplate → R12) and updated the two cross-references (in R6 and R17). Caught before any code used the IDs.
**Verified by:** The heading list now reads R1 to R22 in order, and both cross-references point to R12.
