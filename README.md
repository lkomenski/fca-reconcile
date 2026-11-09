# fca-reconcile

This tool combines a technician's FCA equipment capture and a partner's equipment list into one clean list in FMX's import format. It fixes values that have one clear right answer (spellings, building names, years, condition scales), merges equipment that both sources logged, and sends only the rows that need a person to a review list.

## 1. One-time setup

1. **Install Python 3.10 or newer.** On Windows, download it from [python.org/downloads](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** on the first screen of the installer. On a Mac, use the same site.
2. **Open a terminal in this folder.** On Windows, open the `fca-reconcile` folder in File Explorer, click the address bar, type `cmd`, and press Enter. On a Mac, right-click the folder and choose **New Terminal at Folder**.
3. **Install the packages** (only needed once):

   ```
   python -m pip install -r requirements.txt
   ```

   If `python` isn't found on a Mac, use `python3` in this command and the ones below.

## 2. Run it

Put the technician file and the partner file in the `data` folder, then run:

```
python reconcile.py data/Technician_Capture.csv.xlsx data/Partner_Equipment_List.xlsx --out output
```

Change the two file names if yours are different. Both files can be `.xlsx` or `.csv`. The input files are only read, never changed.

When it finishes, it prints any warnings and a one-line count like:

```
Warning: Sheet 'Legend' in the partner file was not read.
Rows in: 146 technician + 55 partner. Ready: 116. Needs review: 50. Merged into duplicates: 35.
```

The `Legend` warning is expected for FMX's partner file (see section 8).

If it prints `STOPPED:`, nothing was changed. The message says what went wrong and what to do; see section 8, "If something goes wrong".

## 3. What it writes

Four files appear in the `output` folder (it's created if needed, and files from an earlier run are replaced):

| File | What it's for |
|---|---|
| `import_ready.csv` | The file to import into FMX. Exactly the columns of `Target_Format.xlsx`. Every piece of equipment appears once, with `status` set to `ready` or `needs_review`. |
| `review_list.csv` | Only the `needs_review` rows, with the reason, the source row(s) the row came from, and the original captured value next to each cleaned value, so a fix takes one look. |
| `full_detail.csv` | Everything that was captured, including what the import format has no column for (tags, notes, photos, who captured it, the partner's full description). Same rows in the same order as `import_ready.csv`, so you can look up any row's full background. |
| `run_summary.md` | Counts for the run: rows in from each file, rows ready, rows flagged, duplicates merged, a coverage table showing which buildings each source covered, and how many rows have each review reason. It ends with **"Values the tool didn't recognize"**: every unrecognized building, asset type, manufacturer, condition and year, with counts, plus building names accepted by keyword. Use it to update `mappings.py` in one pass. Open it in any text editor. |

**Source row IDs** in the review list, like `technician:76` or `partner:42`, are the spreadsheet row numbers. Open the original file and go to row 76 to see exactly what was captured. A merged row lists every row it came from, e.g. `technician:100; partner:42`.

**Locations** are kept as captured, except a location that is only a room number, which is written as `Rm 103` (from `103`, `Room 103`, `rm103` and so on).

**Merged rows** (`source = both`) are equipment both the technician and the partner logged, matched by building and serial number. They take model and serial from the partner, location from the technician, and the worse of the two condition ratings.

## 4. Review reasons and what to do

A row with several problems lists them all, separated by ` | `.

| Reason (as it appears in `review_reason`) | What it means | What to do |
|---|---|---|
| Nameplate data missing; technician photo IMG_xxxx.jpg on file | Manufacturer, model and serial are all blank. | Open the photo and fill in the nameplate data. If it says "no photo on file", a site visit or the partner list is needed. |
| Asset type 'X' is not in FMX's accepted list | The type is vague (e.g. "fan", "heater") or not one of FMX's accepted types (e.g. "Unit Heater", "Expansion Tank"). | Pick the correct type from `Asset_Types.xlsx`. If it's a common spelling, add it to `mappings.py` (section 6). |
| Asset type is missing | No equipment type was captured. | Check the notes and photo; the technician may not have reached it. |
| Manufacturer 'X' is not a recognized spelling | The name isn't in the known list. Plain "Mitsubishi" is left out on purpose because it could be Mitsubishi Electric or Mitsubishi Heavy Industries; it is completed automatically only when the same model appears elsewhere in the file under the full name. | Confirm from the photo or model number. Add a new spelling to `mappings.py` if it's safe. |
| Manufacturer is missing | A model or serial was captured but no manufacturer. | Fill it in from the photo or model number. |
| Building 'X' is not a recognized building name / Building is missing | The building name doesn't match any known spelling or keyword. | Correct the building. Add the spelling to `mappings.py` if it's a real variant. |
| Building 'X' matched [building] by keyword; confirm | The name isn't in the building list, but contains one building's keyword (e.g. "Middle Sch."). The building was filled in. | Check it really is that building, and not another school or a separate annex. If it is, add the spelling to `BUILDINGS` in `mappings.py` so it's ready next time. |
| Building 'X' could mean more than one building | The name contains keywords for two buildings (e.g. "Elem/Middle Shared Gym"). | Pick the right building. |
| Install year 'X' could not be read as a year | E.g. "unknown", "2000s", or a typo like "19987". | Find the year on the nameplate or photo, or leave it blank. |
| Install year YYYY is in the future | Almost always a typo. | Correct it from the nameplate. |
| Install year differs between sources | Technician and partner years are more than 2 years apart. The technician's year was used. | Check which is right. The partner's year is the year of manufacture. |
| Condition is missing / not a number / outside the 1-10 scale / not one of Good, Fair, Poor, Critical | The condition couldn't be converted to FMX's 1-5 scale. | Ask the technician or partner for the rating, or rate it from the photo and notes. |
| Condition differs between sources | The two ratings are 2 or more points apart on the 1-5 scale. The lower (worse) rating was used. | Decide which rating is right; one person likely saw a problem the other didn't. |
| Serial number missing | The serial is blank or a placeholder like "N/A", and the asset type isn't one that usually has no serial. | Read the serial from the photo or nameplate. If this type of equipment normally has no serial, add the type to `ASSET_TYPES_WITHOUT_SERIAL` in `mappings.py`. |
| Serial NNNN may have been damaged by Excel | The serial ends in 0000, is in scientific notation (4.43E+09), or is longer than 15 digits. Excel often damages long numbers. | Check the serial against the photo or nameplate. |
| Year may have been misread; check nameplate | The year reads as very old (before 1950 from a date cell, or before 1970 from a two-digit year like '27'), which usually means Excel or a typo changed it. | Check the nameplate or photo and type the real year. |
| Manufacturer (...) and model (...) come from different rows | A merged row got its manufacturer from one row and its model from another, and no single row had both. | Check the photo or nameplate to confirm the model belongs to that manufacturer. |
| Looks identical to another row in the import file | Two rows have exactly the same values in every import column. | Use the quoted notes (e.g. panel names) to tell them apart, or delete one if it's a true duplicate. |
| One row describes N units | A single partner row covers several units (e.g. "qty 4"). | Split it into one row per unit with each serial (from the partner's mechanical schedule). |
| Technician note / Partner comment may affect this row | The note mentions something like "replaced", "abandoned" or "locked out". | Read the quoted note and update the year, condition, or row as needed. |
| Same serial but different equipment details; possible serial typo | Two rows share a serial, but their manufacturer or model differ, so they weren't merged. | Check both serials against the photos or nameplates; one is probably mistyped. If they really are the same unit, delete one row. |
| Serial number also appears at [building] | The same serial was captured in two buildings. One unit can't be in both. | Check the serial and the building on both rows. |
| Could not process this row automatically: ... | Something in the row was in a format the tool didn't expect. The row is kept with its values as captured. | Fix the row by hand from the raw values. If it keeps happening, send `output/error_log.txt` to a developer. |
| Technician note says this is a repeat entry, but no matching serial was found | The note says "2nd pass", but there's no serial to match it to its first entry. | Find the first entry (often same building, tag and location) and delete one of the two. |

Rows marked `ready` need no action. The run summary also counts two things that are accepted but worth knowing: approximate years (e.g. "~2004") kept as is, and rows where the partner's year of manufacture is used as the install year.

## 5. Running it on a new technician file

The tool works on any technician file with the same column headings (`Bldg`, `Equip Type`, `Mfr`, `Model #`, `Serial #`, `Yr Installed`, `Cond (1-10)`, `Location`, `Notes`, `Photo`), and any partner file with the same headings as `Partner_Equipment_List.xlsx`. Extra columns are ignored and listed as a warning in the run summary. Title rows, blank rows, footers and repeated header rows are skipped automatically.

A file with different column names will stop with a clear message listing the columns it expected and the columns it found.

## 6. Teaching it a new spelling

All lookup lists live in `mappings.py`, which holds only lists, no logic. Open it in any text editor (Notepad works).

To add a new spelling, find the correct value and add the spelling to its list, in quotes, followed by a comma. For example, to teach it that "Roof Unit" means Rooftop Unit:

```python
    "Rooftop Unit": [
        "RTU",
        "Roof Top Unit",
        "Roof Unit",        # new
```

The same pattern works for `BUILDINGS`, `MANUFACTURERS`, `ASSET_TYPES`, `ASSET_TYPES_WITHOUT_SERIAL` and the notes keyword lists. Case and extra spaces don't matter, so there's no need to add "ROOF UNIT" separately.

Two things are handled without editing:
- **Accepted asset types** are read from `Asset_Types.xlsx` every run. If FMX adds a type to that file, an exact match is recognized automatically. `mappings.py` only needs other spellings of it.
- **Building names** that aren't in `BUILDINGS` fall back to keywords (`BUILDING_KEYWORDS`): "elem…"/"ES", "middle"/"MS", "high"/"HS", as whole words. The run summary lists every name accepted this way. Check that list, because a name from outside the district, like "Westlake Middle", would also match. Add correct names to `BUILDINGS` to make the match exact.

Rules for safe edits:
- Only add a spelling that can mean one thing. If it could mean two (like "fan"), leave it out and let the tool flag it.
- Only combine spellings of the same name. Different brands stay separate, even if one owns the other (e.g. Cutler-Hammer and Eaton).
- An asset type on the left must be one of the values in `Asset_Types.xlsx`. The tool checks this and stops with a clear message if not.
- If the same spelling is listed under two values, the tool stops and names it.

After editing, run the tool again. To check nothing broke, run the tests (section 7).

## 7. Checking the tool (optional)

```
python -m pytest
```

At the end it prints one line per rule, e.g. `R10 technician condition 1-10 to 1-5: 17 cases passed`. The rules themselves are written out in plain English in [docs/RULES.md](docs/RULES.md).

## 8. If something goes wrong

The tool only stops for problems with a whole file. A problem with a single row never stops it; that row goes to the review list instead. When it stops, it lists **every** problem it found at once, and says whether your previous output files are still there. It never leaves half-written outputs: either all four files are replaced, or none are.

| Message starts with | What it means | What to do |
|---|---|---|
| The technician file / partner file '...' was not found | The file name or folder in the command doesn't match a real file. | Check the spelling, the folder, and the extension (`.xlsx`). Dragging the file into the terminal window types its full path for you. |
| ... could not be opened. It may be damaged or not a spreadsheet | The file isn't a readable spreadsheet. | Open it in Excel, choose **Save As** → `.xlsx`, and run again with the new file. |
| ... could not be opened because another program is using it | The input file is locked, usually because it's open in Excel. | Close it in Excel and run again. |
| ... is empty / has column headings but no equipment rows | The file has no data. | Check that you selected the right file. |
| The technician file is missing the column '...' (followed by "Columns found in ...") | A required column is missing or was renamed. | Check you selected the right file. If a column was renamed, rename it back to the name shown. |
| The partner file '...' has no header row with the columns 'Facility' and 'Serial Number' | The partner file isn't in the expected layout. | Check you selected the partner equipment list. |
| The two files seem to be in the wrong order | The partner file came first in the command. | Put the technician file first and the partner file second. |
| The technician file '...' looks like a partner equipment list (or the reverse) | The same kind of file was given twice. | Check both file names in the command. |
| mappings.py has a typing mistake near line N | A recent edit to `mappings.py` broke it. | Undo the last change, or check that every spelling is in quotes and followed by a comma (section 6). |
| mappings.py: '...' is listed under both ... | The same spelling is under two different values. | Remove it from one of them. |
| mappings.py uses asset types that aren't in 'Asset_Types.xlsx' | A value on the left of `ASSET_TYPES` or in `ASSET_TYPES_WITHOUT_SERIAL` isn't an accepted type. | Fix its spelling to match `Asset_Types.xlsx` exactly. |
| The target format file ... has columns the tool doesn't know how to fill | The target format file isn't FMX's. | Use `data/Target_Format.xlsx`. |
| The output file '...' is open in another program | An output file is open in Excel, so it can't be replaced. | Close it and run again. |
| An output file could not be saved | Saving failed partway; the previous files were put back. | Close the files in the output folder and run again. |
| The detail file didn't line up row for row with the import file / The row count didn't add up / The tool hit an unexpected problem | Something went wrong inside the tool. | Send `output/error_log.txt` (and the input files, if you can) to a developer. |

**Warnings** (the run continues): an extra column the tool doesn't use, a file whose extension isn't `.xlsx` or `.csv` but still opened, or a workbook sheet that wasn't read. The tool reads one sheet per file (the partner file's `Equipment` sheet, or otherwise the first), so the FMX partner file always warns that its `Legend` sheet wasn't read; that's expected. If a technician workbook has one tab per building, only the first tab is used. They're printed on screen and listed at the end of `run_summary.md`. Check that you used the right file.

**For a developer:** the full technical error is in `output/error_log.txt`. Add `--debug` to the command to show it on screen as well.

## Folder layout

| Path | What it is |
|---|---|
| [reconcile.py](reconcile.py) | The tool |
| [mappings.py](mappings.py) | Lookup lists (safe to edit; see section 6) |
| [data/](data/) | Input files, exactly as received from FMX |
| [output/](output/) | What the tool writes (section 3) |
| [tests/](tests/) | Automated checks, with small made-up files in [tests/fixtures/](tests/fixtures/) |
| [docs/RULES.md](docs/RULES.md) | Every rule in plain English, with the decisions behind it |
| [docs/QA_LOG.md](docs/QA_LOG.md) | What looked off during the build and how each issue was checked |
| [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) | Decisions made without enough information, and what to build next |
| [docs/REDUCING_REVIEW.md](docs/REDUCING_REVIEW.md) | The flagged rows grouped by what would remove each flag |
| [docs/EXTENDING.md](docs/EXTENDING.md) | For the team taking the tool over: how to extend it, and its built-in limits |
| [docs/TIME_LOG.md](docs/TIME_LOG.md) | Timestamps for the build |
| [docs/NOTE_DRAFT.md](docs/NOTE_DRAFT.md) | Draft of the submission note |
