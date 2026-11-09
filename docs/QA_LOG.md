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
