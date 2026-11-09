# QA log

A running log of anything that looked off, broke, or turned out to be a false alarm. Row IDs use the spreadsheet row number as shown in Excel: `technician:76` is row 76 of the technician sheet, so the row can be found by opening the file.

Entry format: **Rule(s)** · **What looked off** · **First theory** · **Cause** · **How it was proven** · **Fix** · **Verified by**. Entries marked **[AI error]** are mistakes made by the AI assistant and caught during review.

### QA-001 · 2026-11-08 16:00 · Input files are Excel, not CSV, and sit in a different folder
**Rule(s):** R1
**What looked off:** The build plan expected `data/technician_capture.csv`, `data/partner_equipment_list.xlsx`, `data/target_format.csv`, and `data/asset_types.csv`. The repo actually had four `.xlsx` files under `condition scales/data/`: `Technician_Capture.csv.xlsx`, `Partner_Equipment_List.xlsx`, `Target_Format.xlsx`, `Asset_Types.xlsx`.
**First theory:** The technician file had been converted to CSV and only kept `.csv` in its name.
**Cause:** All four are real Excel workbooks. The technician file is an Excel file whose name contains `.csv`.
**How it was proven:** Each file opened with openpyxl. Sheets found: `Technician Capture` (148 rows), `Equipment` + `Legend` (61 + 5 rows), `target_format` (4 rows), `asset_types` (18 rows).
**Fix:** All four files kept byte-for-byte, with original names, in `data/`. The loader accepts `.xlsx` or `.csv` (R1). The stray `condition scales/` folder, which also held an empty `requirements.txt`, was removed.
**Verified by:** SHA-256 of all four files before and after the move; `sha256sum -c` reported OK for each one.

### QA-002 · 2026-11-08 16:03 · [AI error] Inspection script named `inspect.py` broke openpyxl
**Rule(s):** none (tooling)
**What looked off:** The first inspection script crashed with `partially initialized module 'openpyxl' has no attribute 'load_workbook' (most likely due to a circular import)`.
**First theory:** A broken openpyxl install.
**Cause:** The AI named its scratch script `inspect.py`. Python puts the script's own folder first on the import path, so openpyxl's `import inspect` loaded the scratch script instead of the standard-library `inspect` module.
**How it was proven:** The traceback shows `openpyxl/compat/__init__.py` line 8, `import inspect`, landing in the scratch `inspect.py`. After renaming it to `fca_inspect.py` and deleting `__pycache__`, the same code ran cleanly.
**Fix:** Script renamed. Lesson: never give a script the same name as a standard-library module.
**Verified by:** The rerun produced the full report (146 technician rows, 55 partner rows).

### QA-003 · 2026-11-08 16:05 · Technician sheet has a repeated header row partway down
**Rule(s):** R1
**What looked off:** `technician:96` reads `Bldg, Equip Type, Mfr, ...`, an exact copy of the header row, sitting between the middle-school and high-school rows.
**First theory:** Two exports pasted together, one per day.
**Cause:** Confirmed. The row isn't data, so it must be skipped and not counted as an input row.
**How it was proven:** The row matches row 1 cell for cell. Without it there are 146 data rows (148 total − header − repeated header).
**Fix:** The loader drops any row that matches the header (R1).
**Verified by:** Pending implementation. Expected count: 146 technician rows in.

### QA-004 · 2026-11-08 16:05 · Partner sheet has title rows, a blank row, and a footer note
**Rule(s):** R2
**What looked off:** Rows 1–3 of `Equipment` are a title, a "Prepared by" line, and a blank row. The real header is row 4. Rows 60–61 are a blank row and a footer saying "Year is year of manufacture from the nameplate."
**First theory:** Standard report formatting around the table.
**Cause:** Confirmed. The footer also matters for the rules: the partner year is year of manufacture, not install year (R9, R18).
**How it was proven:** Data rows are 5–59, which is 55 rows. Every one has `Facility = Lakeview HS`.
**Fix:** The loader finds the header row by its column names, not a fixed row number, so a partner file with a different title block still loads (R2).
**Verified by:** Pending implementation. Expected count: 55 partner rows in.

### QA-005 · 2026-11-08 16:06 · Technician condition values outside the 1–10 scale
**Rule(s):** R10
**What looked off:** `technician:76` condition is `Good`, `technician:144` is `11`, and `technician:6, 40, 59, 113, 134` are blank. There are also two decimals: `technician:21` = 3.5 and `technician:57` = 5.5.
**First theory:** Typos and skipped fields.
**Cause:** Confirmed. R10 covers all of them: 7 flagged (1 text, 1 out of range, 5 blank), and the two decimals convert to 2 and 3.
**How it was proven:** Distinct-value count of `Cond (1-10)`: 13 distinct values, listed in the inspection report.
**Fix:** Covered by R10. Implementation pending.
**Verified by:** Pending.

### QA-006 · 2026-11-08 16:07 · Numeric serial `4430000000` looks rounded by Excel
**Rule(s):** R13
**What looked off:** `technician:85` (Generac SD150, middle school) has serial `4430000000`, stored as a number. The other Generac serials have no run of trailing zeros (`4586578415`, `4168275953`).
**First theory:** A long serial was typed or pasted, Excel displayed it as `4.43E+09`, and the digits were lost.
**Cause:** Can't be proven from the data alone.
**How it was proven:** Not proven. Compared against the other 10-digit Generac serials.
**Fix:** Flag any all-digit serial ending in four or more zeros (R13). Implementation pending.
**Verified by:** Pending.

### QA-007 · 2026-11-08 16:07 · FMX's example row has a cleaned-up location the requirements don't mention
**Rule(s):** R8
**What looked off:** Example row 1 in `Target_Format.xlsx` is clearly `technician:16` (same serial, `98C69138WD`), but the location `cafeteria roof` appears as `Roof - Cafeteria`.
**First theory:** Location cleanup might be an unstated requirement.
**Cause:** A judgment call, not a bug. The requirements only say model and serial are "as captured, trimmed" and say nothing about location. Rewriting free-text locations is guesswork.
**How it was proven:** Matched serial `98C69138WD` across both files. Example row 2 (`64W84118WM`, `Roof - Gym`) matches `technician:98` exactly, so there is only one example of a rewritten location.
**Fix:** Location kept as captured and trimmed. The decision is recorded under R8.
**Verified by:** Pending implementation.

### QA-008 · 2026-11-08 16:08 · Notes that contradict or invalidate a row
**Rule(s):** R15
**What looked off:** `technician:9` has year 1998 and the note "replaced 2016 per custodian". `technician:53` has the note "abandoned in place, disconnected from loop". `technician:143` has the note "Panel LP-2A, 2nd pass" and is the same panel as `technician:141` (high school, LP-2A, no serial), so serial matching can't merge them.
**First theory:** Rows that would go out as "ready" with wrong or misleading data.
**Cause:** A real risk. Without a notes check, `technician:9` goes out ready with install year 1998, and LP-2A appears twice in the import.
**How it was proven:** All non-blank notes were read (about 60). These three are the clear cases.
**Fix:** A short notes-keyword list in `mappings.py` flags the row and quotes the note (R15). Implementation pending.
**Verified by:** Pending.

### QA-009 · 2026-11-08 16:08 · One partner row covers four units
**Rule(s):** R14
**What looked off:** `partner:54` is "Unit Ventilators (qty 4)", serial `see schedule`, tag `UV-214 to UV-217`.
**First theory:** Four assets packed into one row.
**Cause:** Confirmed. The row can't be imported as one asset, and the tool shouldn't invent four rows, so it needs a person.
**How it was proven:** The Comments column says "Typical of 4, serials on mechanical schedule."
**Fix:** Flagged by R14. Implementation pending.
**Verified by:** Pending.

### QA-010 · 2026-11-08 16:24 · [AI error] Rule IDs in the first RULES.md draft were out of order
**Rule(s):** R9–R12
**What looked off:** In the first RULES.md draft, the nameplate rule was numbered R9 but appeared after R10–R12.
**First theory:** A cosmetic slip. But rule IDs are used in code, tests, and logs, so out-of-order IDs would make all three harder to follow.
**Cause:** The AI drafted the rules in one order, moved a section, and didn't renumber.
**How it was proven:** Listing every `**R#:` heading in order gave R1–R8, R10, R11, R12, R9, R13, and so on.
**Fix:** Renumbered (year → R9, technician condition → R10, partner condition → R11, nameplate → R12) and updated the two cross-references, in R6 and R17. Caught before any code used the IDs.
**Verified by:** The heading list now reads R1 to R22 in order, and both cross-references point to R12.

### QA-011 · 2026-11-08 16:35 · "2nd pass" keyword would have flagged rows the merge already fixed
**Rule(s):** R15, R16
**What looked off:** The approved R15 keyword list included `2nd pass`. `technician:44` ("logged again on 2nd pass") and `technician:92` (same note) both merge by serial with an earlier technician row (`technician:12`, `technician:56`).
**First theory:** These two merged rows would land in the review list for a duplicate that had already been resolved.
**Cause:** Confirmed by tracing the rules while writing the code. R15 runs on every row regardless of whether R16 merged it.
**How it was proven:** Within-technician serial matches from the inspection: `(ES, FBOU734596): [12, 44]` and `(MS, 71N74480): [56, 92]`. Both carry the "2nd pass" note.
**Fix:** R15 now splits the keywords into two lists. Repeat-entry keywords (`2nd pass`, `second pass`, `logged again`) only flag rows that didn't merge. `technician:143` (LP-2A, no serial) is still flagged.
**Verified by:** Pending (test `test_R15_repeat_note_only_flagged_when_not_merged`).
