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

When it finishes, it prints a one-line count like:

```
Rows in: 146 technician + 55 partner. Ready: 117. Needs review: 49. Merged into duplicates: 35.
```

If it prints `ERROR:`, the message says which file or column is the problem (for example, a missing column). If it prints `STOPPED:`, the row count didn't add up and no files were written. That should never happen, so report it.

## 3. What it writes

Three files appear in the `output` folder (it's created if needed, and files from an earlier run are replaced):

| File | What it's for |
|---|---|
| `import_ready.csv` | The file to import into FMX. Exactly the columns of `Target_Format.xlsx`. Every piece of equipment appears once, with `status` set to `ready` or `needs_review`. |
| `review_list.csv` | Only the `needs_review` rows, with the reason, the source row(s) the row came from, and the original captured value next to each cleaned value, so a fix takes one look. |
| `run_summary.md` | Counts for the run: rows in from each file, rows ready, rows flagged, duplicates merged, and how many rows have each review reason. It ends with **"Values the tool didn't recognize"**: every unrecognized building, asset type, manufacturer, condition and year, with counts, plus building names accepted by keyword. Use it to update `mappings.py` in one pass. Open it in any text editor. |

**Source row IDs** in the review list, like `technician:76` or `partner:42`, are the spreadsheet row numbers. Open the original file and go to row 76 to see exactly what was captured. A merged row lists every row it came from, e.g. `technician:100; partner:42`.

**Locations** are kept as captured, except a location that is only a room number, which is written as `Rm 103` (from `103`, `Room 103`, `rm103` and so on).

**Merged rows** (`source = both`) are equipment both the technician and the partner logged, matched by building and serial number. They take model and serial from the partner, location from the technician, and the worse of the two condition ratings.

## 4. Review reasons and what to do

| Reason (as it appears in `review_reason`) | What it means | What to do |
|---|---|---|
| Nameplate data missing; technician photo IMG_xxxx.jpg on file | Manufacturer, model and serial are all blank. | Open the photo and fill in the nameplate data. If it says "no photo on file", a site visit or the partner list is needed. |
| Asset type 'X' is not in the accepted list | The type is vague (e.g. "fan", "heater") or not one of FMX's accepted types (e.g. "Unit Heater", "Expansion Tank"). | Pick the correct type from `Asset_Types.xlsx`. If it's a common spelling, add it to `mappings.py` (section 6). |
| Asset type is missing | No equipment type was captured. | Check the notes and photo; the technician may not have reached it. |
| Manufacturer 'X' is not a recognized spelling | The name isn't in the known list. Plain "Mitsubishi" is left out on purpose because it could be Mitsubishi Electric or Mitsubishi Heavy Industries. | Confirm from the photo or model number. Add a new spelling to `mappings.py` if it's safe. |
| Manufacturer is missing | A model or serial was captured but no manufacturer. | Fill it in from the photo or model number. |
| Building 'X' is not a recognized building name / Building is missing | The building name doesn't match any known spelling or keyword. | Correct the building. Add the spelling to `mappings.py` if it's a real variant. |
| Building 'X' could mean more than one building | The name contains keywords for two buildings (e.g. "Elem/Middle Shared Gym"). | Pick the right building. |
| Install year 'X' could not be read as a year | E.g. "unknown", "2000s", or a typo like "19987". | Find the year on the nameplate or photo, or leave it blank. |
| Install year YYYY is in the future | Almost always a typo. | Correct it from the nameplate. |
| Install year differs between sources | Technician and partner years are more than 2 years apart. The technician's year was used. | Check which is right. The partner's year is the year of manufacture. |
| Condition is missing / not a number / outside the 1-10 scale / not one of Good, Fair, Poor, Critical | The condition couldn't be converted to FMX's 1-5 scale. | Ask the technician or partner for the rating, or rate it from the photo and notes. |
| Condition differs between sources | The two ratings are 2 or more points apart on the 1-5 scale. The lower (worse) rating was used. | Decide which rating is right; one person likely saw a problem the other didn't. |
| Serial number missing | The serial is blank or a placeholder like "N/A", and the asset type isn't one that usually has no serial. | Read the serial from the photo or nameplate. If this type of equipment normally has no serial, add the type to `ASSET_TYPES_WITHOUT_SERIAL` in `mappings.py`. |
| Serial NNNN may have been rounded by Excel | An all-number serial ending in 0000; Excel often damages long numbers. | Check the serial against the photo or nameplate. |
| One row describes N units | A single partner row covers several units (e.g. "qty 4"). | Split it into one row per unit with each serial (from the partner's mechanical schedule). |
| Technician note / Partner comment may affect this row | The note mentions something like "replaced", "abandoned" or "locked out". | Read the quoted note and update the year, condition, or row as needed. |
| Technician note says this is a repeat entry, but no matching serial was found | The note says "2nd pass", but there's no serial to match it to its first entry. | Find the first entry (often same building, tag and location) and delete one of the two. |

Rows marked `ready` need no action. The run summary also counts two things that are accepted but worth knowing: approximate years (e.g. "~2004") kept as is, and rows where the partner's year of manufacture is used as the install year.

## 5. Running it on a new technician file

The tool works on any technician file with the same column headings (`Bldg`, `Equip Type`, `Mfr`, `Model #`, `Serial #`, `Yr Installed`, `Cond (1-10)`, `Location`, `Notes`, `Photo`), and any partner file with the same headings as `Partner_Equipment_List.xlsx`. Extra columns are ignored. Title rows, blank rows, footers and repeated header rows are skipped automatically. If a required column is missing, the tool stops and names it.

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

## Folder layout

```
reconcile.py      the tool
mappings.py       lookup lists (safe to edit)
data/             input files, exactly as received from FMX
output/           what the tool writes
tests/            automated checks, with small made-up files in tests/fixtures/
docs/RULES.md     every rule in plain English, with the decisions behind it
docs/QA_LOG.md    what looked off during the build and how each issue was checked
docs/TIME_LOG.md  timestamps for the build
```
