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

### QA-011 · 2026-11-08 16:21 · "2nd pass" keyword would have flagged rows the merge already fixed
**Rule(s):** R15, R16
**What looked off:** The approved R15 keyword list included `2nd pass`. `technician:44` ("logged again on 2nd pass") and `technician:92` (same note) both merge by serial with an earlier technician row (`technician:12`, `technician:56`).
**First theory:** These two merged rows would land in the review list for a duplicate that had already been resolved.
**Cause:** Confirmed by tracing the rules while writing the code. R15 runs on every row regardless of whether R16 merged it.
**How it was proven:** Within-technician serial matches from the inspection: `(ES, FBOU734596): [12, 44]` and `(MS, 71N74480): [56, 92]`. Both carry the "2nd pass" note.
**Fix:** R15 now splits the keywords into two lists. Repeat-entry keywords (`2nd pass`, `second pass`, `logged again`) only flag rows that didn't merge. `technician:143` (LP-2A, no serial) is still flagged.
**Verified by:** Full run at 16:25: `technician:44` and `technician:92` are merged and not in the review list; `technician:143` is flagged with "Technician note says this is a repeat entry, but no matching serial was found: 'Panel LP-2A, 2nd pass'". Test: `test_R15_repeat_note_only_flagged_when_not_merged`.

### QA-012 · 2026-11-08 16:26 · [AI error] Time log and QA log had invented timestamps
**Rule(s):** none (process)
**What looked off:** The first full run's summary was stamped 16:25, but TIME_LOG already had entries at 16:32 and 16:38 and QA-011 was dated 16:35. Those times were in the future.
**First theory:** Clock drift between the shell and the run.
**Cause:** The AI estimated elapsed time instead of reading the clock, and wrote the estimates as if they were real times.
**How it was proven:** `date` returned 16:26. `git log` shows the two doc commits at 16:19 and 16:22.
**Fix:** TIME_LOG rewritten from the system clock and git commit times. QA-011 re-dated to 16:21 (between the two commits). From here on, every timestamp comes from `date` or git.
**Verified by:** Every TIME_LOG entry now matches a commit time or a clock reading taken at that step. The slip happened once more: QA-016 was stamped 16:38 when the clock read 16:37. It was corrected to 16:36, the last clock reading before that entry.

### QA-013 · 2026-11-08 16:26 · [AI error] Inspection report undercounted the "Mitsubishi" rows
**Rule(s):** R6
**What looked off:** The inspection report said leaving plain "Mitsubishi" unmapped would affect 2 rows. The run summary shows 4 rows with "Manufacturer not recognized".
**First theory:** A mapping bug catching a correct spelling.
**Cause:** The report counted only the `Mitsubishi` spelling. The data also has `MITSUBISHI` (2 rows), which is the same word in a different case and is also unmapped. The tool was right; the report was wrong.
**How it was proven:** Review list: `technician:34` (MITSUBISHI), `technician:88` (Mitsubishi), `technician:93` (MITSUBISHI), `technician:148` (Mitsubishi). The distinct-value count from the inspection shows `'MITSUBISHI': 2, 'Mitsubishi': 2`.
**Fix:** No code change needed. The R6 decision affects 4 rows, not 2.
**Verified by:** Run summary: "Manufacturer not recognized | 4".

### QA-014 · 2026-11-08 16:26 · First full run matches the inspection counts
**Rule(s):** R3, R9–R19, R21
**What looked off:** Nothing; this is the check that the first run agrees with the hand counts from Step 1.
**First theory:** n/a
**Cause:** n/a
**How it was proven:**
- Rows: 146 technician + 55 partner = 201 in; 35 merged (33 cross-source + 2 within technician); 166 out (matches QA-003, QA-004).
- R19 condition conflicts: 5 (technician 100, 104, 108, 115, 126).
- R18 year conflicts: 2 (technician 105, 127).
- R5 asset types flagged: 13 (7 technician + 6 partner).
- R12 nameplate: 9. R9: 6 unreadable years + 1 future year.
- R10 condition: 4 missing (the 5th blank, `technician:113`, merged with `partner:14` "Poor", so R19 used the partner rating), 1 text, 1 out of range.
- R9 approximate years: 8. Partner years used: 23 (22 partner-only rows + `technician:112`/`partner:35`, where the technician year was blank).
- FMX's three example rows: all three are reproduced, including the exact review reason "Nameplate data missing; technician photo IMG_0527.jpg on file". The one difference is the row 1 location (`cafeteria roof` vs `Roof - Cafeteria`), which is the R8 decision.
**Fix:** No change needed.
**Verified by:** `output/run_summary.md` from the 16:25 run.

### QA-015 · 2026-11-08 16:30 · All 118 tests passed on the first run, so the tests were checked to confirm they can fail
**Rule(s):** R9, R10
**What looked off:** The first `pytest` run passed every test (118 of 118). A suite that has never failed hasn't shown it can catch anything.
**First theory:** Some tests might be too loose to catch a real mistake.
**Cause:** No problem found. Two deliberate bugs were each caught.
**How it was proven:**
- Changed R10's `math.ceil(score / 2)` to `round(score / 2)`: 3 R10 cases failed (Python rounds 0.5, 2.5 and 4.5 down to the even number, so scores 1, 5 and 9 converted wrong).
- Changed R9's cutoff from `current_year % 100` to a fixed `26`: `test_R9_two_digit_cutoff_follows_the_current_year` failed.
- Both files were restored with `git checkout -- reconcile.py`.
**Fix:** No change needed. A side lesson: `round()` would have been a quiet bug for scores 1, 5 and 9. `math.ceil` is the right call for "half, rounded up".
**Verified by:** `pytest`: 118 passed after the restore.

### QA-016 · 2026-11-08 16:36 · Blanket "blank serial is fine" exception replaced by an editable list
**Rule(s):** R12
**What looked off:** R12 never flagged a blank serial on its own. That was fine for the 21 electrical panels, but it also let `technician:29` (DX split, serial `N/A`) and `technician:91` (Fire Alarm Control Panel, serial `N/A`) go out as ready, even though that equipment normally has a serial and can't be matched as a duplicate without one.
**First theory:** The blanket exception was too broad; it was written from the panels alone.
**Cause:** A judgment call, not a bug. The original decision assumed every serial-less row was a panel.
**How it was proven:** Before the change, the 30 technician rows with a blank serial were 9 fully blank nameplates plus 21 Electrical Panels, and `N/A` serials weren't counted as blank. After adding `ASSET_TYPES_WITHOUT_SERIAL = ["Electrical Panel"]`, the new "Serial number missing" flag catches exactly 3 rows:
- `technician:29` and `technician:91` (newly flagged)
- `partner:54` (serial "see schedule"; already flagged by R14, now with a second reason)
**Fix:** The list lives in `mappings.py`, and the startup check confirms every entry is an accepted asset type. A fully blank nameplate gets only the R12 nameplate reason, not both.
**Verified by:** Run summary: 201 in = 115 ready + 51 needs_review + 35 merged (was 117 + 49 + 35). Tests `test_R12_blank_serial_flagged_unless_type_allowed` (6 cases) and `test_R12_fully_blank_nameplate_not_also_flagged_serial_missing`; 124 tests pass.

### QA-017 · 2026-11-08 16:38 · Room-number locations standardized; nothing else changed
**Rule(s):** R8
**What looked off:** Room locations appeared in five formats: `103` (stored as a number), `Room 102`, `rm110`, `Rm 101`, and FMX's own `Rm 205`.
**First theory:** A room number has one right answer, so it can be standardized without guessing. The risk was the pattern catching locations that only *contain* a number, like `Mech Rm 104`, `Kitchen 115` or `IT Closet 112`.
**Cause:** n/a (new rule). The pattern only accepts a whole value that is a room number: 1–4 digits, optionally after "Room" or "Rm".
**How it was proven:** The full run was compared before and after the change:
- 166 rows each time; 16 rows changed, and in every one only `location` changed.
- The 16 changes, all room numbers:
  - Bare numbers: `103`→`Rm 103`, plus `106`, `107`, `108`, `207`, `211`, `212`, `213` in the same way.
  - `Room 102`/`202`/`203`/`204` → `Rm …`
  - `rm110`/`206`/`208`/`210` → `Rm …`
- `Mech Rm 104`, `Kitchen 115`, `IT Closet 112` and `Classroom 208` were unchanged.
- Counts unchanged: 115 ready, 51 needs_review, 35 merged.
**Fix:** `normalize_location` added. The R8 decision is updated, and the broader location question is recorded in OPEN_QUESTIONS.md #5.
**Verified by:** `test_R8_room_numbers_standardized` (6 cases), `test_R8_other_locations_kept_as_captured` (5 cases), `test_R8_location_cleaned_inside_a_full_row`; 135 tests pass.

### QA-018 · 2026-11-08 16:47 · Accepted asset types were partly copied into code
**Rule(s):** R5
**What looked off:** While confirming that accepted asset types are read from `Asset_Types.xlsx` at run time, the code turned out to read the file only to *check* `mappings.py`. Recognition used the type names typed in `mappings.py` as keys.
**First theory:** Harmless, since all 17 accepted types were typed in correctly.
**Cause:** A real gap for unseen data. If FMX added a type to `Asset_Types.xlsx` (say "Cooling Tower"), a technician entry of exactly "Cooling Tower" would still be flagged "not in the accepted list" until someone also edited `mappings.py`.
**How it was proven:** `grep` showed `ASSET_TYPE_LOOKUP` built only from `mappings.ASSET_TYPES`. Before the fix, `normalize_asset_type("Switchgear")` only worked because of an empty `"Switchgear": []` entry in `mappings.py`.
**Fix:** `build_asset_type_lookup` adds every name from `Asset_Types.xlsx` to the lookup at run time. The empty `Switchgear` entry was removed from `mappings.py`, since the file now supplies it.
**Verified by:** `test_R5_accepted_types_are_read_from_the_file_at_run_time` ("Cooling Tower" in a temporary accepted-types file is recognized, and is not recognized without it). Second unseen file: `technician:4` "Switchgear" is ready. FMX output unchanged (166 rows, no cell differs).

### QA-019 · 2026-11-08 16:47 · False alarm: reconcile.py looked twice as long as expected
**Rule(s):** none (tooling)
**What looked off:** `grep` placed the summary code at line 1119. The file had been estimated at around 700 lines.
**First theory:** An earlier `git stash`/`git checkout` or a line-ending change had duplicated part of the file.
**Cause:** No duplication. The estimate was simply low; docstrings make up much of the file.
**How it was proven:** `wc -l` gives 1158 lines. `grep "^def " | sort | uniq -d` found no function defined twice. `cat -A` showed no doubled blank lines.
**Fix:** No change needed.
**Verified by:** Same commands; 51 unique functions.

### QA-020 · 2026-11-08 16:47 · Building keyword fallback, and its known limit
**Rule(s):** R4
**What looked off:** n/a (new rule). The concern was that a keyword fallback would accept names it shouldn't.
**First theory:** Whole-word matching would prevent false matches like "LMS" → MS, "Estates" → ES and "Highland" → High.
**Cause:** Confirmed for those three. One false match was found. On the second unseen file, "Westlake Middle", a made-up name for a school outside the district, was accepted as Lakeview Middle School and marked **ready**. The rule as specified can't tell a different school's name from a new spelling of this one.
**How it was proven:**
- Second unseen file: 4 names accepted by keyword: "Lakeview Elementary Bldg A", "Middle Sch.", "Lakeview HS Annex", "Westlake Middle".
- "Elem/Middle Shared Gym" was flagged as matching two buildings. "LMS" was flagged as not recognized.
- Real FMX file: 0 names fell through to keywords. Every one of the 16 spellings is in the alias list.
**Fix:** As specified. The limit is made visible rather than hidden: every keyword match is listed in the run summary under "Building names matched by keyword", and it's noted in R4 and the README. Two possible tightenings are left for a decision, not built: require "Lakeview" as well, or mark keyword matches needs_review.
**Verified by:** `test_R4_keyword_fallback_maps_names_not_in_the_list` (5), `test_R4_name_matching_two_buildings_is_flagged`, `test_R4_keywords_match_whole_words_only` (3), and `test_UNSEEN_second_file_new_spellings_are_flagged_or_listed`, which asserts the Westlake behavior so any change to it is deliberate.

### QA-021 · 2026-11-08 16:47 · New note keywords change nothing on the FMX files
**Rule(s):** R15
**What looked off:** 8 keywords were added (`out of service`, `disconnected`, `removed`, `decommissioned`, `inoperable`, `failed`, `leak`, `red tag`). The FMX counts didn't move.
**First theory:** The keywords weren't being read.
**Cause:** No bug. The only FMX note containing a new keyword is `technician:53` ("abandoned in place, disconnected from loop"). It was already flagged for "abandoned", and one note produces one reason. No other FMX note or comment contains a new keyword.
**How it was proven:** On the second unseen file, "red tag on burner", "water leak at coil", "decommissioned 2025" and "out of service" are each flagged with the note quoted. FMX `import_ready.csv` compared to the previous commit: 166 rows, 0 cells differ.
**Fix:** No change needed.
**Verified by:** `test_R15_note_keywords_are_flagged_and_quoted` (12 cases, including "leaking", "Out of Service" and "RED TAG" to confirm case and word-ending handling).

### QA-022 · 2026-11-08 16:47 · Run summary lists every unrecognized value
**Rule(s):** R22
**What looked off:** n/a (new output). The reason counts in the summary said *how many* rows had an unrecognized manufacturer, but not *which* spellings, so updating `mappings.py` meant reading the whole review list.
**First theory:** n/a
**Cause:** n/a
**How it was proven:** The FMX run lists 18 values:
- 10 asset types
- 2 manufacturer spellings: `MITSUBISHI` 2 and `Mitsubishi` 2, the same split as QA-013
- 2 condition values
- 4 year values

Values are counted per input row before merging, so a spelling covered by the other source in a merged row still shows up.
**Fix:** A new section, "Values the tool didn't recognize", with field, value as captured, file and rows, plus "Building names matched by keyword".
**Verified by:** `test_R22_summary_lists_every_unrecognized_value_by_field`. On the second unseen file the section listed 13 values, including `Johnson Controls`, `Trane Technologies`, `Cooling Tower` and `7/10`.

### QA-023 · 2026-11-08 16:59 · Keyword-matched buildings no longer go out as ready
**Rule(s):** R4
**What looked off:** QA-020 found that "Westlake Middle", a school outside the district, was accepted as Lakeview Middle School and marked ready.
**First theory:** Either tighten the keywords (require "Lakeview") or always ask a person.
**Cause:** A judgment call. Keywords can't tell a new spelling of a district building from a different school or a separate annex.
**How it was proven:** Second unseen file before the change: 3 ready, including `technician:9` "Westlake Middle". After the change: 1 ready (`partner:4`, which uses the alias "Lakeview HS"). All 4 keyword matches are needs_review with "Building '...' matched ... by keyword; confirm", and the building is still filled in. FMX files: no change (0 keyword matches; all 16 spellings are aliases).
**Fix:** A keyword match always adds that reason, so the alias list is the only path to ready. The decision and its why are recorded under R4.
**Verified by:** `test_R4_keyword_match_fills_building_but_needs_confirmation` (5 cases) and `test_UNSEEN_second_file_new_spellings_are_flagged_or_listed`, updated to expect 1 ready / 12 needs_review and Westlake = needs_review.

### QA-024 · 2026-11-08 16:59 · Failing gracefully: file checks, plain messages, safe outputs
**Rule(s):** R25, R26, R27, R28, R29
**What looked off:** Before this change, a missing column printed `ERROR: The technician file is missing these columns: ...` and stopped at the first problem. A row that hit an unexpected value would have crashed the whole run with a Python traceback. A failure while writing could leave `import_ready.csv` new and `review_list.csv` old. A typo in `mappings.py` crashed on import with a Python `SyntaxError`, before any message could be shown.
**First theory:** n/a. These were requested hardening items, checked one by one.
**Cause:** n/a
**How it was proven:** Each behavior has a test that runs the full command. Every one checks that the screen shows plain language with no Python error names or traceback, and where relevant, that previous outputs are byte-for-byte unchanged and no temporary files are left:
- Missing column (`Serial #` removed): stops, names the column, lists the columns found, says the previous outputs were not changed.
- Two problems at once (2 missing columns + missing partner file): all 3 reported in one run.
- Empty file, and a file with headings but no rows: plain stop messages.
- Files in the wrong order: one message saying so, not a list of missing columns.
- Damaged `.xlsx`: plain stop; the traceback goes to `error_log.txt`, or to the screen with `--debug`.
- Broken `mappings.py` (simulated `SyntaxError` at line 12): "mappings.py has a typing mistake near line 12".
- Deliberately broken row: `normalize_location` made to fail on `technician:8`. The run finishes (exit 0), the row is in the review list with "Could not process this row automatically: ...", and its former partner match `partner:5` is output on its own. Row check: 11 in, accounting holds. Details are in `error_log.txt`.
- Run failing partway: `write_review_list` made to fail after the import file was written to the temporary folder. Exit 1, "Your previous output files ... were not changed", and the outputs are byte-identical to before.
- Extra column `Inspector Notes` and a `.txt` extension: both listed as warnings in the run summary; the run continues.
**Fix:** Added `check_input_files` (all file checks before any processing), `report_stop`/`write_error_log`, the `--debug` flag, `StopRun`, per-row and per-group error handling (`fallback_row`), temp-folder writing with restore (`write_outputs`), and a guarded `mappings.py` import. Expected-but-unused columns (`Captured`, `Tech`, `System`) are listed in `mappings.py` so they don't warn.
**Verified by:** `tests/test_failures.py`, 12 tests for R25–R29; 176 tests pass in total.

### QA-025 · 2026-11-08 16:59 · Serial checks across rows, years stored as dates, leading zeros
**Rule(s):** R9, R16, R22, R23, R24
**What looked off:** Four gaps for unseen files:
- (a) Two different units with a mistyped shared serial would merge, and one unit would vanish.
- (b) A serial captured in two buildings went unnoticed.
- (c) A year stored as a date (`2004-01-01`) or a decimal string (`2004.0`) was flagged as unreadable, and `00644492` didn't match `644492`.
- (d) The summary should name its input files and run time.
**First theory:** n/a (requested).
**Cause:** n/a
**How it was proven:** Unit tests for each:
- R23: a different model blocks the merge and flags both rows; case and dash differences still merge.
- R24: both rows flagged, each naming the other building.
- R9: 5 date and decimal forms → 2004.
- R16: leading zeros ignored only for all-digit serials (`0A12` ≠ `A12`).
- R22: file names and "Run on" appear in the summary.

On the FMX files, `import_ready.csv` was compared with the previous commit: 166 rows, 0 cells differ. No FMX pair has conflicting details, no serial is in two buildings, and no leading-zero match is new.
**Fix:** Added `details_conflict`/`process_group` (R23), `flag_serials_in_several_buildings` (R24), date and decimal handling in `parse_install_year` (R9), leading-zero handling in `serial_key` (R16), and file names plus run date/time in the summary (R22). The summary already had a run time and two file names; it now lists all three input files.
**Verified by:** `test_R23_*` (2), `test_R24_*`, `test_R9_year_stored_as_date_or_decimal` (5), `test_R16_leading_zeros_ignored_only_for_all_digit_serials`, `test_R22_summary_names_input_files_and_run_time`.

### QA-026 · 2026-11-08 16:59 · [Decision, scoped out] Column names from other sources
**Rule(s):** R1, R2, R26
**What looked off:** Different sources will name columns differently. Another partner might write "Mfr." or "Serial No." instead of "Manufacturer" or "Serial Number", and a technician app might export "Condition" on an unknown scale.
**First theory:** Make the loader accept more heading names.
**Cause:** A design decision, not a bug. Two options were considered:
1. A growing list of accepted headings in `mappings.py`. Every new source means another code-adjacent edit, the list can quietly match the wrong column, and it can't tell which condition scale a "Condition" column uses.
2. A column-map file the tool writes out when it meets headings it doesn't recognize. A person fills it in once per new source format (matching each heading to a field and setting the condition scale), and the tool reuses it automatically.
**How it was proven:** n/a (decision). Today, a file with different headings stops before processing with every missing column named and the found columns listed (`test_R26_missing_column_stops_with_plain_message`).
**Fix:** Chose neither for now. Column handling is unchanged: the expected headings are fixed, missing ones stop the run with a clear message, and extra ones are warnings. Option 2 is recorded as the next thing to build (OPEN_QUESTIONS.md #8, NOTE_DRAFT.md). Why: the exercise says unseen files will be in the same format, and I chose a small tool that works over a bigger one that might not. Guessing a condition scale would corrupt every rating, so it shouldn't be guessed in any version.
**Verified by:** n/a (decision recorded in OPEN_QUESTIONS.md #8 and R29).

### QA-027 · 2026-11-08 17:11 · Independent review by a fresh AI subagent (report only, nothing fixed)
**Rule(s):** R2, R4, R9, R13, R14, R16, R18, R20, R23, R24, R26, R28
**What looked off:** Before writing the note, a separate AI subagent that took no part in writing the code reviewed it as a skeptical FMX data specialist. It looked for false "ready" rows, rule-vs-code mismatches, row accounting, merge edge cases and plain language. It traced 5 rows end to end and ran adversarial technician files (CSV, xlsx, and headings starting on row 3) built to break the tool. It changed nothing in the repo; its files are in the session scratch folder.
**First theory:** n/a (review).
**Cause:** Findings, ranked by the reviewer:
1. **Wrong data:** 4 ready rows are the same unit as a flagged row: `technician:95`/`partner:40` (RTU-4), `technician:109`/`partner:11` (B-3), `technician:119`/`partner:6` (AHU-2), `technician:141`/`technician:143` (Panel LP-2A). The flagged twin has no serial, so nothing links them, and once someone fills in the nameplate the unit would be imported twice. Suggested fix: tag/panel-name hint on the reason, ~45 min.
2. **Wrong data:** a year Excel stored as a date-formatted cell (2004 shown as a date = 1905-06-26) becomes 1905 and goes out ready. Suggested fix: flag date years before ~1950, ~15 min.
3. **Wrong data:** Excel-damaged serials can pass R13: scientific notation (`4.43E+09`), and all-digit serials over 15 digits (Excel keeps only 15 significant digits). Suggested fix: ~15 min.
4. **Wrong data:** a merge can pair one brand with another brand's model when one row's manufacturer is blank and the other row's model is blank. R23 skips blanks, so "Bell & Gossett / FI2507 (a Taco model)" went out ready. Suggested fix: flag when manufacturer and model come from different rows, ~20 min.
5. **Wrong data:** two ready rows in `import_ready.csv` are identical: `technician:33` (Panel LP-1B) and `technician:45` (Panel LP-1A). The panel name lives only in Notes, which the import format drops. Suggested fix: flag ready rows with identical output values and quote Notes, ~20 min.
6. **Minor:** a two-digit year of 27–99 becomes 1927–1999 and is ready; a real "30" would make a 1930 mini-split. Suggested fix: flag results before ~1970, ~10 min.
7. **Minor (rule mismatch):** R4's "confirm" flag is lost when a keyword-matched technician row merges with a partner row, because `choose_value` takes the partner's clean building. R4 says it always flags. Suggested fix: ~10 min.
8. **Unclear:** "; " is used both between reasons and inside some reasons ("...; used the lower rating", "Nameplate data missing; technician photo..."), so a reader can't tell where one reason ends. Suggested fix: ~10 min.
9. **Unclear:** a blank building gives "Serial number also appears at ; check the serial and building". Suggested fix: ~5 min.
10. **Unclear:** "differs between sources" is used when both rows are technician rows. Suggested fix: ~5 min.
11. **Unclear:** headings that start on row 3 give 10 "missing column" lines plus "Columns found: (none)" instead of one clear message. Suggested fix: ~10 min.
12. **Unclear:** "choose the correct type" is shown for Unit Heater, Expansion Tank and Plate Heat Exchanger, which aren't in FMX's list at all. Suggested fix: ~10 min.
13. **Minor:** a partner row with only Facility filled in is treated as a footer and dropped without a warning (as R2 says, but silently). Suggested fix: ~10 min.
14. **Minor (other):**
- "qty 4" without brackets isn't caught by R14 (that row was still flagged, through its asset type).
- A condition of `1e1` is read as 10.
- R18 says "captured first" but the code uses file order.
- On a first run with no previous outputs, a save that fails partway can leave one new file (R28).
- Lowercase models on technician-only rows are kept as captured (per R7).

**Checked and fine:**
- Leading zeros (`partner:15` `00644492` matches `644492`), and three-row merges.
- Year gaps of exactly 2 aren't flagged, gaps of 3 are. Condition gaps of exactly 2 are flagged.
- Blank or flagged values fall back to the other row.
- The repeated header row is skipped, and an empty row is dropped.
- A notes-only row is kept and flagged.
- R24 works across buildings.
- Every real merged pair picked the right values.
- No crash was found.
**How it was proven:**
- Row accounting, counted independently from the raw files: 201 IDs in, each appearing exactly once in the output. 166 output rows (115 ready + 51 needs_review) + 35 merged = 201. `review_list.csv` has 51 rows, matching the needs_review rows exactly, and every summary count matches the files.
- Five traces (`technician:106`+`partner:9`, `partner:40`, `technician:48` and `technician:102`+`partner:37`, `technician:78`, `technician:12`+`technician:44`): every value correct, apart from the duplicate noted in finding 1.
- Rule-vs-code mismatches: R4 (finding 7), R9 (finding 2), R18 (wording).
- 176 tests pass.
**Fix:** None yet; report only, as requested. Which findings to fix is a decision for me.
**Verified by:** Reviewer's report; adversarial inputs kept in `scratchpad/review/adv/` for re-running after any fix.

### QA-028 · 2026-11-08 17:14 · full_detail.csv: nothing captured is dropped
**Rule(s):** R28, R30
**What looked off:** `import_ready.csv` has to match FMX's target format exactly, so every column without a place in it was dropped: technician Notes, Photo, Captured, Tech; partner System, Tag, Comments; and details inside the partner description such as "12.5 ton" or "(qty 4)". The review list kept some raw values, but only for flagged rows. The independent review (QA-027, finding 5) also showed why this matters: `technician:33` (Panel LP-1B) and `technician:45` (Panel LP-1A) are identical in the import file, and the panel name exists only in Notes.
**First theory:** n/a (requested).
**Cause:** n/a
**How it was proven:**
- FMX run: `full_detail.csv` has 166 rows and 43 columns: source row IDs, 11 target columns with 8 raw columns interleaved, 12 `technician_` columns and 11 `partner_` columns.
- `technician:100; partner:42` keeps `partner_Equipment Description` "Rooftop Unit RTU-6, 12.5 ton", `partner_Tag` "RTU-6", and `technician_Notes` "RTU-6 heat exchanger cracked, locked out".
- `partner:54` keeps "(qty 4)". `technician:33` keeps "Panel LP-1B".
- The two-technician merge `technician:12; technician:44` shows both photos, each labelled with its row ID.
- An extra column (`Inspector Notes`) on a test file appears as `technician_Inspector Notes`.
- A deliberately broken detail file (last row dropped) stops the run with "The detail file didn't line up row for row with the import file...". Previous outputs are byte-for-byte unchanged and no temporary files are left.
**Fix:** Added `full_detail.csv` (`write_full_detail`), every original column kept on each record (`make_record`, with `unique_headings` so a repeated heading becomes "Notes (2)" instead of overwriting), and `check_full_detail_matches_import`, run in the temporary folder before any output is replaced. `OUTPUT_FILES` now lists 4 files, so the locked-file check and safe replace cover it. The why is recorded under R30.
**Verified by:** `test_R30_full_detail_has_same_rows_in_same_order_as_import`, `test_R30_full_detail_keeps_columns_the_import_drops`, `test_R30_raw_value_sits_next_to_each_cleaned_value`, `test_R30_extra_column_is_kept_in_full_detail`, `test_R30_repeated_heading_is_kept_not_overwritten`, `test_R30_detail_file_out_of_line_stops_and_keeps_previous_outputs`. FMX counts unchanged (115 / 51 / 35); 183 tests pass.

### QA-029 · 2026-11-08 17:14 · Coverage by building: two buildings have only one source
**Rule(s):** R22
**What looked off:** n/a (new summary table). Requested to show where each source contributed.
**First theory:** n/a
**Cause:** n/a. The table makes a data limit visible: the elementary and middle schools have technician data only, so the tool has nothing to cross-check them against.
**How it was proven:** FMX run, output rows by building:

| Building | Technician only | Partner only | Both | Total |
|---|---|---|---|---|
| Elementary | 45 | 0 | 0 | 45 |
| Middle | 46 | 0 | 0 | 46 |
| High | 20 | 22 | 33 | 75 |
| All | 111 | 22 | 33 | 166 |

The total matches `import_ready.csv`. The 2 technician-only merges (`technician:12+44`, `technician:56+92`) count as technician only.
**Fix:** `coverage_lines` added to the run summary. The limit is recorded in OPEN_QUESTIONS.md #9: finding missing equipment would need mechanical schedules, drawings, or a past assessment.
**Verified by:** `test_R22_coverage_table_counts_sources_per_building`.

### QA-030 · 2026-11-08 17:21 · Review findings 2–8 and 12 fixed
**Rule(s):** R4, R9, R13, R17, R20, R31, R5
**What looked off:** QA-027 findings chosen for fixing: #2 (date-cell year → 1905, ready), #3 (scientific-notation and >15-digit serials pass R13), #4 (brand from one row, model from another), #5 (identical ready rows), #6 (two-digit "27" → 1927, ready), #7 (R4 confirm flag lost on merge), #8 ("; " both inside and between reasons), #12 ("choose the correct type" when none exists).
**First theory:** n/a (fixing known findings).
**Cause:** As described in QA-027.
**How it was proven:** The reviewer's adversarial files were re-run, plus new unit tests:
- #2: `adv_tech.xlsx` technician:2 (2004 in a date cell, read as 1905-06-26) is now needs_review with "Year may have been misread; check nameplate (captured as '1905-06-26 00:00:00', which reads as 1905)". The CSV text form (`adv_tech.csv` technician:19) is flagged the same way.
- #3: `4.43E+09` (`adv_tech.csv` technician:2) and `12345678901234569216` (`adv_tech.xlsx` technician:3) are now flagged "may have been damaged by Excel".
- #4: `adv_tech.xlsx` technician:5 + technician:6 (MIX1) is now needs_review: "Manufacturer (technician:6) and model (technician:5) come from different rows". It flags only when no single row has both values; a normal merge where one row has both stays ready.
- #5: FMX `technician:33` / `technician:45` are now needs_review, quoting "Panel LP-1B" and "Panel LP-1A". No other ready rows in the FMX output are identical.
- #6: "27" is flagged. 98 → 1998 and 70 → 1970 are still ready.
- #7: `adv_tech.xlsx` technician:8 + partner:9 ("Lakeview High School Annex") keeps "matched Lakeview High School by keyword; confirm".
- #8: reasons are now joined with " | ". Semicolons appear only inside a single reason.
- #12: "Asset type 'X' is not in FMX's accepted list; choose an accepted type, or ask FMX whether to add it".
- FMX counts: 113 ready / 53 needs_review / 35 merged (was 115 / 51 / 35). The only change is the panel pair from #5.
**Fix:** `misread_year` and the cutoffs `DATE_YEAR_MISREAD_BEFORE = 1950` and `TWO_DIGIT_MISREAD_BEFORE = 1970` (R9); `check_serial_rounded` extended (R13); `check_brand_model_pairing` (R17); `flag_identical_ready_rows` (new R31); keyword building problems carried into `merge_duplicate` (R4); `flag_row` separator (R20); new asset-type wording (R5). Also the type-checker warnings: the guarded import now uses an empty placeholder module instead of `None`, so the ~15 "is not a known attribute of None" warnings are gone, with no change in behavior.
**Verified by:** `test_R9_probably_misread_years_are_flagged_and_left_blank` (4), `test_R9_real_date_year_after_1950_is_kept`, `test_R13_*` (8 cases), `test_R17_manufacturer_and_model_from_different_rows_is_flagged`, `test_R17_normal_merge_with_both_on_one_row_is_not_flagged`, `test_R31_*` (2), `test_R4_keyword_building_keeps_confirm_flag_after_merge`, `test_R20_every_reason_listed_separated_by_bars`; 198 tests pass.
**Not fixed, by decision:**
- #1 is the deferred tag matching. One row of each pair is already flagged, so nothing is imported twice without a person seeing it.
- #9, #10, #11, #13 and #14 are left as is. They're listed in NOTE_DRAFT.md.
- The `adv_tech.csv` run still shows #9 ("Serial number also appears at ; check..." on partner:8).

### QA-031 · 2026-11-08 17:21 · [AI error] Scientific-notation check flagged a real serial
**Rule(s):** R13
**What looked off:** After the #3 fix, FMX row `technician:125; partner:59` was newly flagged "Serial 7989E905548 may have been damaged by Excel".
**First theory:** The serial had genuinely been damaged.
**Cause:** The AI wrote the pattern with the sign optional (`e[+-]?\d+`), so "7989E905548", a normal A.O. Smith serial containing the letter E, matched. Excel's scientific notation always includes the sign (`4.43E+09`, `1E+15`). The reviewer's suggested pattern had the sign; the AI dropped it.
**How it was proven:** The partner list has the same serial typed independently (`partner:59` 7989E905548), and the other A.O. Smith serials have the same letter-in-the-middle shape (`4171M054224`, `3552Y379731`). Ready count after the bad pattern: 112; after the fix: 113.
**Fix:** The sign is now required (`e[+-]\d+`). Test cases were added for `7989E905548` (not flagged) and `1E+15` (flagged).
**Verified by:** `test_R13_all_digit_serial_ending_in_zeros_is_flagged[7989E905548-False]` and `[1E+15-True]`; FMX run: `technician:125; partner:59` is ready again.

### QA-032 · 2026-11-08 17:21 · Verification: adversarial re-run, mutated file, repeat runs
**Rule(s):** R3, R21, R16, R22
**What looked off:** n/a. These checks confirm the tool holds up on changed input and gives the same answer every time.
**First theory:** n/a
**Cause:** n/a
**How it was proven:** Script `scratchpad/verify_runs.py`, outside the repo.
1. **Reviewer's adversarial files** (`adv_tech.csv`, `adv_tech.xlsx`, `adv_tech_offset.xlsx`, each with `adv_partner.csv`): no crash and no traceback in any run.
   - `adv_tech.csv`: 21 + 10 rows in → 3 ready, 18 needs_review, 10 merged.
   - `adv_tech.xlsx`: 7 + 10 → 7 ready, 8 needs_review, 2 merged.
   - The offset file stops with a plain message (finding #11, not fixed).
2. **Mutated technician file**, built from the FMX technician file:
   - Rows shuffled; 29 of 146 deleted at random (seed 20261108), leaving 117.
   - Changes: 5 buildings `Lakeview HS` → `LV High`, 1 `Trane` → `Traine`, 1 `1998` → `'98`, 1 `2012` → `c. 2012`, 1 `UV` → `unit ventilator`.
   - Result: no crash. 117 + 55 = 172 in = 103 ready + 44 needs_review + 25 merged, and every row ID appears exactly once.
   - The counts change as expected:
     - An independent count found 24 technician high school rows with a partner serial; the output has 24 `both` rows.
     - Partner-only rose from 22 to 31 (55 − 24).
     - The 25 merged = 24 cross-source pairs + 1 surviving technician pair.
     - Coverage: elementary 35 (was 45), middle 38 (was 46), high 74.
     - "Traine" appears as a new unrecognized manufacturer. `LV High` and `'98` were handled silently, since both are known spellings.
3. **FMX files run twice** into separate folders: `import_ready.csv`, `review_list.csv`, `full_detail.csv` and `run_summary.md` are byte-identical. Caveat: `run_summary.md` includes the run time to the minute, so it matches only when both runs finish in the same minute. The three data files don't depend on time.
**Fix:** No change needed.
**Verified by:** The script output above, kept in `scratchpad/verify/`.

### QA-033 · 2026-11-08 17:41 · Manufacturer completed from the file's own evidence
**Rule(s):** R6
**What looked off:** The 4 "Mitsubishi"/"MITSUBISHI" rows stayed flagged (QA-013), but the same file has `technician:29` "Mitsubishi Electric" with model MSZ-GL12NA and `technician:146` "Mitsubishi Electric" with model PKA-A24KA7. Those are exactly the models on the 4 short-name rows.
**First theory:** The ambiguity (Mitsubishi Electric vs Heavy Industries) can be settled from the file itself, without a new lookup entry.
**Cause:** n/a (new rule step).
**How it was proven:**
- Before: 113 ready / 53 needs_review / 35 merged. After: 116 / 50 / 35.
- `technician:34`, `88` (MSZ-GL12NA) and `93` (PKA-A24KA7) are now "Mitsubishi Electric" and ready.
- `technician:148` is completed too, but stays needs_review for its unreadable year only.
- "Values the tool didn't recognize" no longer lists Mitsubishi. "Work done automatically": 105 manufacturer spellings, 4 of them completed from evidence.
**Fix:** `resolve_manufacturers_from_evidence` runs after cleaning. It completes the name only when the unrecognized value is the first word or words of exactly one known manufacturer, and the same model (case and spaces ignored) appears on another row under that full name. Otherwise the flag stays. The why is recorded under R6. REDUCING_REVIEW.md, NOTE_DRAFT.md, README and EXTENDING.md numbers were updated.
**Verified by:** `test_R6_short_name_completed_when_same_model_appears_under_full_name`, `test_R6_short_name_stays_flagged_when_model_not_seen_elsewhere`, `test_R6_evidence_under_a_different_brand_does_not_count`, `test_R6_real_file_completes_all_four_mitsubishi_rows`. Two tests updated for the new expected results: `test_R22_summary_lists_every_unrecognized_value_by_field` (Mitsubishi no longer listed) and `test_R31_real_file_panels_lp1a_and_lp1b_are_flagged` (116 ready). 203 tests pass.

### QA-034 · 2026-11-08 17:49 · Tag hint for possible twins (R32), tested in theory before building
**Rule(s):** R32, R21, R16
**What looked off:** Review finding #1 (QA-027): four "ready" rows were the same unit as a flagged row with no serial: `partner:40` RTU-4 / `technician:95`, `partner:11` B-3 / `technician:109`, `partner:6` AHU-2 / `technician:119`, and `technician:141` / `technician:143` (panel LP-2A). Advice received: merging on free-text tags is risky this late, so use a hint, not a merge.
**First theory:** A strict tag pattern plus a same-building rule would link exactly these pairs without false matches.
**Cause:** n/a (new rule).
**How it was proven:** Before any repo change, the logic ran in memory from `scratchpad/tag_hint_plugin.py` and `tag_hint_trial.py`, outside the repo:
- **FMX files:** exactly the 4 pairs above; 116 → 112 ready.
- **Shuffled, trimmed copy:** the same 4 pairs.
- **Reviewer's files and both made-up files:** 0 pairs.
- **Accounting and merges:** row accounting held in every run, and none of the 35 serial merges contradicts its own tags.
- **Real test suite with the hint on:** 202 pass; 1 failed only on the pinned ready count.
- **Tag-trap file:** one **false match**, "RTU-5 next to RTU-4" paired with the partner's RTU-4.
  - Misses: lowercase "rtu-4", and UV-215 against the range "UV-214 to UV-217".
  - Correct: KP-1 in three buildings not paired, EF-12 vs EF-12A kept apart, FI-2507 not taken for a tag.
- **One-tag rule:** with "a note naming two tags gives no tag", the false match disappeared and all 4 real pairs remained on both data sets.
**Fix:** Added `TAG_PATTERN`, `equipment_tags` and `flag_possible_same_unit`, which runs after flagging and never merges. FMX: 112 ready / 54 needs_review / 35 merged (unchanged). Docs updated: RULES R32, the README reasons table, REDUCING_REVIEW bucket 3 (now 7 rows), EXTENDING #7, and the numbers in NOTE_DRAFT.
- **Small [AI error] while adding tests:** two new R32 tests first failed because the AI changed the partner test row's tag to RTU-4 but left the helper's default description "Base-Mounted Pump P-1". The tool correctly flagged that description as an unknown asset type. The test data was fixed; no code change.
**Verified by:**
- `test_R32_rows_sharing_a_tag_in_one_building_are_both_flagged`
- `test_R32_note_naming_two_tags_gives_no_hint`
- `test_R32_same_tag_in_different_buildings_gives_no_hint`
- `test_R32_tag_pattern_is_strict` (3)
- `test_R32_real_file_links_the_four_twins_and_keeps_merges`
- `test_R31_real_file_panels_lp1a_and_lp1b_are_flagged`, updated to 112 ready

210 tests pass.
