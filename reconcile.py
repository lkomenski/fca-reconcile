"""Reconcile FCA equipment data from a technician file and a partner file.

Run it like this:

    python reconcile.py data/Technician_Capture.csv.xlsx data/Partner_Equipment_List.xlsx --out output

The tool reads both files, cleans every value that has one clear right answer,
merges equipment that both sources logged, and flags everything else for a
person. It writes four files to the output folder: import_ready.csv,
review_list.csv, run_summary.md and full_detail.csv. Rule IDs (R1, R2, ...) refer to
docs/RULES.md.
"""

import argparse
import csv
import math
import os
import re
import shutil
import sys
import tempfile
import traceback
from collections import Counter, namedtuple
from datetime import date, datetime
from pathlib import Path

import openpyxl

# R27: a typing mistake while editing mappings.py must give a plain message,
# not a Python error, so the import is guarded and reported by main().
try:
    import mappings

    MAPPINGS_ERROR = None
except Exception as import_error:
    mappings = None
    MAPPINGS_ERROR = import_error

HERE = Path(__file__).resolve().parent
DEFAULT_ASSET_TYPES = HERE / "data" / "Asset_Types.xlsx"
DEFAULT_TARGET_FORMAT = HERE / "data" / "Target_Format.xlsx"
OUTPUT_FILES = ["import_ready.csv", "review_list.csv", "run_summary.md", "full_detail.csv"]
ERROR_LOG = "error_log.txt"
KNOWN_EXTENSIONS = (".xlsx", ".xlsm", ".csv")

# Lists every part of the tool needs from mappings.py.
REQUIRED_MAPPINGS = [
    "BUILDINGS",
    "BUILDING_KEYWORDS",
    "ASSET_TYPES",
    "ASSET_TYPES_WITHOUT_SERIAL",
    "MANUFACTURERS",
    "PARTNER_CONDITION",
    "SERIAL_PLACEHOLDERS",
    "NOTE_KEYWORDS",
    "REPEAT_NOTE_KEYWORDS",
    "TECHNICIAN_COLUMNS",
    "TECHNICIAN_IGNORED_COLUMNS",
    "PARTNER_COLUMNS",
    "PARTNER_IGNORED_COLUMNS",
]

# The eight equipment fields every source row is cleaned into.
FIELDS = [
    "building",
    "asset_type",
    "manufacturer",
    "model",
    "serial_number",
    "install_year",
    "condition",
    "location",
]

# One problem found on a row. "field" says which value it belongs to (None
# means it is about the whole row), "category" is the short label counted in
# the run summary, and "reason" is the sentence a data specialist reads.
# "value" is set only when the problem is an unrecognized captured value, so
# the run summary can list every one of them (R22).
Problem = namedtuple("Problem", ["field", "category", "reason", "value"], defaults=[None])

# Field names as shown in the run summary's unrecognized-values list.
FIELD_LABELS = {
    "building": "Building",
    "asset_type": "Asset type",
    "manufacturer": "Manufacturer",
    "condition": "Condition",
    "install_year": "Install year",
}


class RowAccountingError(Exception):
    """Raised when rows in do not equal rows out (R21)."""


class OutputMismatchError(Exception):
    """Raised when full_detail.csv and import_ready.csv don't line up row for row (R30)."""


class StopRun(Exception):
    """A file-level problem that stops the run before anything is written (R26).

    Carries every plain-language problem found, so they are all reported at
    once, plus technical details for error_log.txt.
    """

    def __init__(self, problems, details=""):
        super().__init__("; ".join(problems))
        self.problems = problems
        self.details = details


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def lookup_key(text):
    """Turn a value into the form used for table lookups.

    Upper/lower case and extra spaces are ignored, so "LVHS ", "lvhs" and
    "LVHS" all match the same entry in mappings.py.
    """
    return " ".join(str(text).split()).lower()


def build_lookup(table, table_name):
    """Turn a mappings.py table into a quick "spelling -> correct value" lookup.

    Each correct value also matches itself. If the same spelling is listed
    under two different correct values, the tool stops, because that would
    make the mapping a guess.
    """
    lookup = {}
    for correct_value, spellings in table.items():
        for spelling in [correct_value] + list(spellings):
            key = lookup_key(spelling)
            if key in lookup and lookup[key] != correct_value:
                raise ValueError(
                    f"mappings.py {table_name}: '{spelling}' is listed under both "
                    f"'{lookup[key]}' and '{correct_value}'. Remove one."
                )
            lookup[key] = correct_value
    return lookup


BUILDING_LOOKUP = {}
# Spellings from mappings.py only. The accepted names themselves are added at
# run time from Asset_Types.xlsx by build_asset_type_lookup (R5).
ASSET_TYPE_LOOKUP = {}
MANUFACTURER_LOOKUP = {}
PARTNER_CONDITION_LOOKUP = {}
SERIAL_PLACEHOLDER_KEYS = set()
if MAPPINGS_ERROR is None:
    try:
        missing_lists = [name for name in REQUIRED_MAPPINGS if not hasattr(mappings, name)]
        if missing_lists:
            raise ValueError(f"mappings.py is missing the list {', '.join(missing_lists)}")
        BUILDING_LOOKUP = build_lookup(mappings.BUILDINGS, "BUILDINGS")
        ASSET_TYPE_LOOKUP = build_lookup(mappings.ASSET_TYPES, "ASSET_TYPES")
        MANUFACTURER_LOOKUP = build_lookup(mappings.MANUFACTURERS, "MANUFACTURERS")
        PARTNER_CONDITION_LOOKUP = {lookup_key(word): score for word, score in mappings.PARTNER_CONDITION.items()}
        SERIAL_PLACEHOLDER_KEYS = {lookup_key(value) for value in mappings.SERIAL_PLACEHOLDERS}
    except Exception as lookup_error:
        MAPPINGS_ERROR = lookup_error


def mappings_problem():
    """A plain-language message for a broken mappings.py, or None if it loaded (R27)."""
    if MAPPINGS_ERROR is None:
        return None
    if isinstance(MAPPINGS_ERROR, SyntaxError):
        return (
            f"mappings.py has a typing mistake near line {MAPPINGS_ERROR.lineno}. Undo your last change to "
            "mappings.py, or check that each spelling is in quotes and followed by a comma (README section 6)."
        )
    if isinstance(MAPPINGS_ERROR, ValueError):
        return f"{MAPPINGS_ERROR}. Fix mappings.py and run the tool again (README section 6)."
    return "mappings.py could not be loaded. Undo your last change to mappings.py and run the tool again."


def to_text(value):
    """Turn a spreadsheet cell into trimmed text.

    Empty cells become "". Whole numbers that Excel stored as decimals
    (2004.0) are written without the ".0" (R7).
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def has_value(value):
    """True if a cleaned value is filled in (not blank and not None)."""
    return value is not None and value != ""


# ---------------------------------------------------------------------------
# Loading (R1, R2, R3)
# ---------------------------------------------------------------------------


def read_csv_rows(path):
    """Read every row of a CSV file."""
    # Excel sometimes saves CSV files in the older Windows encoding.
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            return [list(row) for row in csv.reader(handle)]
    except UnicodeDecodeError:
        with open(path, newline="", encoding="cp1252") as handle:
            return [list(row) for row in csv.reader(handle)]


def read_excel_rows(path, sheet_name=None):
    """Read every row of an Excel sheet: the named sheet if it exists, otherwise the first."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
        else:
            sheet = workbook.worksheets[0]
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def read_rows(path, sheet_name=None):
    """Read every row of an .xlsx or .csv file as a list of cell values.

    The file is only read, never changed (requirement 1). A file with an
    unfamiliar extension is tried as Excel, then as CSV; the file check
    (R29) warns about it.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv_rows(path)
    if suffix in (".xlsx", ".xlsm"):
        return read_excel_rows(path, sheet_name)
    try:
        return read_excel_rows(path, sheet_name)
    except Exception:
        return read_csv_rows(path)


def padded_texts(row, width):
    """Return the row's cells as trimmed text, padded with "" to a fixed width."""
    texts = [to_text(cell) for cell in row]
    return texts + [""] * (width - len(texts))


def map_columns(header, column_map, file_label):
    """Find the position of each expected column in the header row.

    Column names are matched ignoring case and spaces. If an expected column
    is missing, the tool stops and names it, because the file is not in the
    expected format.
    """
    positions = {lookup_key(name): index for index, name in enumerate(header) if name}
    columns = {}
    missing = []
    for column_name, field in column_map.items():
        key = lookup_key(column_name)
        if key in positions:
            columns[field] = positions[key]
        else:
            missing.append(column_name)
    if missing:
        raise ValueError(f"{file_label} is missing these columns: {', '.join(missing)}")
    return columns


def unique_headings(header):
    """Give every non-blank heading a unique name, so no column is lost (R30).

    A heading used twice becomes "Notes", "Notes (2)".
    """
    names = []
    for position, name in enumerate(header):
        if not name:
            continue
        unique = name
        count = 2
        while unique in [existing for existing, _ in names]:
            unique = f"{name} ({count})"
            count += 1
        names.append((unique, position))
    return names


def make_record(source, row_number, row, columns, header):
    """Package one input row with its source row ID, its raw values, and every original column.

    The row ID (e.g. "technician:42") is the spreadsheet row number, so any
    output row can be traced back to the row in Excel. "original" keeps
    every column as captured, including ones the import format has no place
    for, so full_detail.csv can show them (R30).
    """
    raw = {}
    for field, index in columns.items():
        raw[field] = row[index] if index < len(row) else None
    original = {}
    for name, index in unique_headings(header):
        original[name] = row[index] if index < len(row) else None
    return {"row_id": f"{source}:{row_number}", "source": source, "raw": raw, "original": original}


def load_technician(path):
    """Load the technician file (R1).

    Row 1 is the header. Completely empty rows and repeated copies of the
    header row are skipped. Every other row is kept, even if most of it is
    blank, so no equipment record is lost.
    """
    rows = read_rows(path)
    if not rows:
        raise ValueError(f"{Path(path).name} is empty")
    width = max(len(row) for row in rows)
    header = padded_texts(rows[0], width)
    columns = map_columns(header, mappings.TECHNICIAN_COLUMNS, "The technician file")
    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        texts = padded_texts(row, width)
        if not any(texts):
            continue  # R1: empty row
        if texts == header:
            continue  # R1: header pasted in again (second export)
        records.append(make_record("technician", row_number, row, columns, header))
    return records


def load_partner(path):
    """Load the partner file (R2).

    The header is the first row containing "Facility" and "Serial Number",
    so title rows above it are skipped wherever the table starts. Below it,
    empty rows, footer notes (text only in the first column) and repeated
    header rows are skipped. Every other row is kept.
    """
    rows = read_rows(path, sheet_name="Equipment")
    width = max((len(row) for row in rows), default=0)
    header_index = None
    for index, row in enumerate(rows):
        keys = {lookup_key(text) for text in padded_texts(row, width)}
        if "facility" in keys and "serial number" in keys:
            header_index = index
            break
    if header_index is None:
        raise ValueError(
            "The partner file has no header row with 'Facility' and 'Serial Number' columns"
        )
    header = padded_texts(rows[header_index], width)
    columns = map_columns(header, mappings.PARTNER_COLUMNS, "The partner file")
    records = []
    for index, row in enumerate(rows[header_index + 1 :], start=header_index + 1):
        texts = padded_texts(row, width)
        if not any(texts):
            continue  # R2: empty row
        if not any(texts[1:]):
            continue  # R2: footer note, text in the first column only
        if texts == header:
            continue  # R2: repeated header
        records.append(make_record("partner", index + 1, row, columns, header))
    return records


# ---------------------------------------------------------------------------
# Cleaning one field at a time (R4 - R11)
# ---------------------------------------------------------------------------


def match_building_keywords(text):
    """List the buildings whose keywords appear in a building name (R4).

    Keywords come from mappings.BUILDING_KEYWORDS and match whole words only,
    so "ES" matches "Lakeview ES" but not "Estates". A keyword ending in "*"
    matches any word starting with it ("elem*" matches "Elementary").
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    matches = []
    for building, keywords in mappings.BUILDING_KEYWORDS.items():
        for keyword in keywords:
            keyword = keyword.lower()
            if keyword.endswith("*"):
                found = any(word.startswith(keyword[:-1]) for word in words)
            else:
                found = keyword in words
            if found and building not in matches:
                matches.append(building)
    return matches


def normalize_building(raw):
    """Map a building name to one of the three official names (R4).

    Names in mappings.BUILDINGS are matched first; only these can be ready.
    Anything else falls back to keywords ("middle", "MS", ...): one match
    fills in the building but flags the row for confirmation. A name
    matching no building, or more than one, is kept as typed and flagged.
    """
    text = to_text(raw)
    if not text:
        return "", Problem("building", "Building missing", "Building is missing")
    building = BUILDING_LOOKUP.get(lookup_key(text))
    if building:
        return building, None
    matches = match_building_keywords(text)
    if len(matches) == 1:
        # R4: filled in, but only the alias list can make a row ready.
        return matches[0], Problem(
            "building",
            "Building matched by keyword",
            f"Building '{text}' matched {matches[0]} by keyword; confirm",
        )
    if len(matches) > 1:
        return text, Problem(
            "building",
            "Building matches more than one building",
            f"Building '{text}' could mean more than one building ({', '.join(matches)})",
            text,
        )
    return text, Problem(
        "building",
        "Building not recognized",
        f"Building '{text}' is not a recognized building name",
        text,
    )


def partner_asset_type_text(description, tag):
    """Pull the equipment type out of a partner description (R5).

    "Hot Water Boiler B-1, 1,500 MBH" with tag "B-1" becomes
    "Hot Water Boiler": keep the text before the first comma, then remove the
    tag and any "(qty N)" note.
    """
    text = to_text(description).split(",")[0]
    text = re.sub(r"\(\s*qty\.?\s*\d+\s*\)", "", text, flags=re.IGNORECASE)
    tag = to_text(tag)
    if tag:
        # Only remove the tag as a whole word, so tag "EF-1" can't eat part of "EF-10".
        text = re.sub(r"(?<!\w)" + re.escape(tag) + r"(?!\w)", "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def build_asset_type_lookup(accepted_types):
    """Combine FMX's accepted asset types with the spellings in mappings.py (R5).

    The accepted names are read from Asset_Types.xlsx at run time, so a type
    FMX adds to that file is recognized without editing the code.
    """
    lookup = dict(ASSET_TYPE_LOOKUP)
    for name in accepted_types:
        lookup[lookup_key(name)] = name
    return lookup


def normalize_asset_type(raw, lookup=ASSET_TYPE_LOOKUP):
    """Map an asset type to a value from the accepted list (R5).

    Only accepted names and spellings listed in mappings.ASSET_TYPES are
    changed. Anything else, including vague words like "fan", is kept as
    typed and flagged.
    """
    text = to_text(raw)
    if not text:
        return "", Problem("asset_type", "Asset type missing", "Asset type is missing")
    asset_type = lookup.get(lookup_key(text))
    if asset_type:
        return asset_type, None
    return text, Problem(
        "asset_type",
        "Asset type not in accepted list",
        f"Asset type '{text}' is not in the accepted list; choose the correct type",
        text,
    )


def normalize_manufacturer(raw, model, serial):
    """Fix the spelling of a manufacturer name (R6).

    Only spellings listed in mappings.MANUFACTURERS are changed; different
    brands are never combined. A blank manufacturer is flagged only when the
    model or serial is filled in. A fully blank nameplate is handled by R12.
    """
    text = to_text(raw)
    if not text:
        if model or serial:
            return "", Problem("manufacturer", "Manufacturer missing", "Manufacturer is missing")
        return "", None
    manufacturer = MANUFACTURER_LOOKUP.get(lookup_key(text))
    if manufacturer:
        return manufacturer, None
    return text, Problem(
        "manufacturer",
        "Manufacturer not recognized",
        f"Manufacturer '{text}' is not a recognized spelling; confirm the manufacturer",
        text,
    )


def parse_install_year(raw, current_year):
    """Turn a captured install year into a four-digit year (R9).

    Returns (year, problem, approximate). Four-digit years, two-digit years
    ('04, 98), "Mfg 04/2011" dates and approximate years (~2004, 2004?) are
    read. Approximate years are kept and marked so the summary can count
    them. Blank stays blank with no flag. Future years and anything that is
    not one clear year are flagged and left blank. A year stored as a date
    (2004-01-01) or a decimal (2004.0) is read as that year.
    """
    if isinstance(raw, date):
        # R9: Excel turned the year into a date; the year part is what was meant.
        return check_year_range(raw.year, to_text(raw), current_year, False)
    text = to_text(raw)
    if not text:
        return None, None, False

    date_text_match = re.fullmatch(r"(\d{4})-\d{1,2}-\d{1,2}(?:[ T][\d:.]*)?", text)
    decimal_match = re.fullmatch(r"(\d{4})\.0+", text)
    if date_text_match:
        return check_year_range(int(date_text_match.group(1)), text, current_year, False)
    if decimal_match:
        return check_year_range(int(decimal_match.group(1)), text, current_year, False)

    approximate = False
    approximate_match = re.fullmatch(
        r"(?:approx\.?|approximately|circa|ca\.|c\.|~)\s*(\d{4})|(\d{4})\s*\?",
        text,
        flags=re.IGNORECASE,
    )
    two_digit_match = re.fullmatch(r"'?(\d{2})", text)
    manufacture_date_match = re.fullmatch(r"mfg\.?\s*\d{1,2}/(\d{4})", text, flags=re.IGNORECASE)

    if approximate_match:
        year = int(approximate_match.group(1) or approximate_match.group(2))
        approximate = True
    elif re.fullmatch(r"\d{4}", text):
        year = int(text)
    elif two_digit_match:
        # R9: up to the current year's last two digits is the 2000s, higher is the 1900s.
        two_digits = int(two_digit_match.group(1))
        if two_digits <= current_year % 100:
            year = 2000 + two_digits
        else:
            year = 1900 + two_digits
    elif manufacture_date_match:
        year = int(manufacture_date_match.group(1))
    else:
        return None, unreadable_year(text), False
    return check_year_range(year, text, current_year, approximate)


def check_year_range(year, text, current_year, approximate):
    """Accept a year from 1900 up to the current year; flag anything else (R9)."""
    if year > current_year:
        return None, Problem(
            "install_year", "Install year in the future", f"Install year {year} is in the future", text
        ), False
    if year < 1900:
        return None, unreadable_year(text), False
    return year, None, approximate


def unreadable_year(text):
    """The R9 problem for a year that is not one clear year."""
    return Problem(
        "install_year",
        "Install year unreadable",
        f"Install year '{text}' could not be read as a year",
        text,
    )


def normalize_location(raw):
    """Standardize a location that is only a room number (R8).

    "103", "Room 103", "rm103" and "Rm. 103" all become "Rm 103". Anything
    else, like "Mech Rm 104" or "cafeteria roof", is kept as captured,
    because rewriting free text would be a guess.
    """
    text = to_text(raw)
    match = re.fullmatch(r"(?:(?:room|rm)\.?\s*)?(\d{1,4})", text, flags=re.IGNORECASE)
    if match:
        return f"Rm {match.group(1)}"
    return text


def convert_condition_10pt(raw):
    """Convert a technician 1-10 condition score to the 1-5 scale (R10).

    Half the score, rounded up: 1-2 -> 1, 3-4 -> 2, 5-6 -> 3, 7-8 -> 4,
    9-10 -> 5. Decimals use the same formula (3.5 -> 2). Blank, text, and
    numbers outside 1-10 are flagged.
    """
    text = to_text(raw)
    if not text:
        return None, Problem("condition", "Condition missing", "Condition is missing")
    try:
        score = float(text)
    except ValueError:
        return None, Problem(
            "condition",
            "Condition not a number",
            f"Condition '{text}' is not a number on the technician's 1-10 scale",
            text,
        )
    if not 1 <= score <= 10:
        return None, Problem(
            "condition",
            "Condition out of range",
            f"Condition {text} is outside the technician's 1-10 scale",
            text,
        )
    return math.ceil(score / 2), None


def convert_condition_text(raw):
    """Convert a partner condition word to the 1-5 scale (R11).

    Good -> 4, Fair -> 3, Poor -> 2, Critical -> 1 (from mappings.py).
    Nothing maps to 5. Blank or any other word is flagged.
    """
    text = to_text(raw)
    if not text:
        return None, Problem("condition", "Condition missing", "Condition is missing")
    score = PARTNER_CONDITION_LOOKUP.get(lookup_key(text))
    if score is not None:
        return score, None
    words = ", ".join(mappings.PARTNER_CONDITION)
    return None, Problem(
        "condition",
        "Condition word not recognized",
        f"Condition '{text}' is not one of {words}",
        text,
    )


# ---------------------------------------------------------------------------
# Checks that need a person (R12 - R15)
# ---------------------------------------------------------------------------


def check_nameplate(manufacturer, model, serial, photo):
    """Flag a row whose nameplate fields are all blank (R12).

    The reason names the technician's photo file so the specialist can read
    the nameplate from it. A blank serial alone is handled by
    check_serial_missing.
    """
    if manufacturer or model or serial:
        return None
    photo = to_text(photo)
    if photo:
        reason = f"Nameplate data missing; technician photo {photo} on file"
    else:
        reason = "Nameplate data missing; no photo on file"
    return Problem("nameplate", "Nameplate data missing", reason)


def check_serial_missing(asset_type, serial, nameplate_problem):
    """Flag a blank or placeholder serial, unless the asset type usually has none (R12).

    Asset types allowed to have no serial are listed in
    mappings.ASSET_TYPES_WITHOUT_SERIAL (e.g. Electrical Panel). If the whole
    nameplate is blank, the nameplate reason already covers it, so no second
    reason is added.
    """
    if nameplate_problem or serial_key(serial) is not None:
        return None
    if asset_type in mappings.ASSET_TYPES_WITHOUT_SERIAL:
        return None
    return Problem("serial_number", "Serial number missing", "Serial number missing")


def check_serial_rounded(serial):
    """Flag an all-digit serial ending in 0000, which Excel may have rounded (R13)."""
    if serial.isdigit() and serial.endswith("0000"):
        return Problem(
            "serial_number",
            "Serial may be rounded by Excel",
            f"Serial {serial} may have been rounded by Excel; check the photo or nameplate",
        )
    return None


def check_multi_unit(description, tag):
    """Flag a partner row that describes several units, e.g. "(qty 4)" (R14)."""
    match = re.search(r"\(\s*qty\.?\s*(\d+)\s*\)", to_text(description), flags=re.IGNORECASE)
    if not match or int(match.group(1)) < 2:
        return None
    tag = to_text(tag)
    tag_part = f" (tag {tag})" if tag else ""
    return Problem(
        None,
        "One row describes several units",
        f"One row describes {match.group(1)} units{tag_part}; each unit needs its own row and serial",
    )


def note_contains(notes, keywords):
    """True if the note contains any of the keywords (case ignored)."""
    note = lookup_key(notes)
    return any(lookup_key(keyword) in note for keyword in keywords)


def check_notes(notes, source):
    """Flag a row whose note contains a keyword from mappings.NOTE_KEYWORDS (R15).

    The note is quoted so the specialist sees it without opening the file.
    The tool does not try to act on the note.
    """
    notes = to_text(notes)
    if not notes or not note_contains(notes, mappings.NOTE_KEYWORDS):
        return None
    label = "Technician note" if source == "technician" else "Partner comment"
    return Problem(None, "Note may affect row", f"{label} may affect this row: '{notes}'")


def repeat_note_problem(notes):
    """The R15 problem for a "2nd pass" note on a row that did not merge."""
    return Problem(
        None,
        "Repeat entry not matched",
        f"Technician note says this is a repeat entry, but no matching serial was found: '{notes}'",
    )


def serial_key(serial):
    """The form of a serial used to find duplicates (R16).

    Spaces and dashes are removed and case is ignored, so "67W-465 53NA"
    matches "67W46553NA". Blank and placeholder serials ("N/A") return None
    and are never matched. The original serial is kept for the output.
    """
    text = to_text(serial)
    if not text or lookup_key(text) in SERIAL_PLACEHOLDER_KEYS:
        return None
    key = re.sub(r"[\s\-]", "", text).upper()
    # R16: an all-digit serial may have lost its leading zeros in Excel, so
    # "00644492" and "644492" match. Serials with letters keep their zeros.
    if key.isdigit():
        key = key.lstrip("0") or "0"
    return key


# ---------------------------------------------------------------------------
# Cleaning a whole row
# ---------------------------------------------------------------------------


def clean_record(record, current_year, asset_type_lookup=ASSET_TYPE_LOOKUP):
    """Clean every field of one input row and collect its problems.

    Each value is cleaned by its own rule. Problems are collected, not acted
    on, so a row with three problems lists all three.
    """
    raw = record["raw"]
    source = record["source"]
    problems = []

    building, problem = normalize_building(raw["building"])
    problems.append(problem)
    # Remember names matched by keyword rather than the alias list, so the
    # run summary can suggest adding them to mappings.BUILDINGS (R4, R22).
    building_by_keyword = ""
    if problem and problem.category == "Building matched by keyword":
        building_by_keyword = to_text(raw["building"])

    if source == "partner":
        asset_text = partner_asset_type_text(raw["description"], raw["tag"])
    else:
        asset_text = raw["asset_type"]
    asset_type, problem = normalize_asset_type(asset_text, asset_type_lookup)
    problems.append(problem)

    model = to_text(raw["model"])  # R7: as captured, trimmed
    serial = to_text(raw["serial_number"])
    manufacturer, problem = normalize_manufacturer(raw["manufacturer"], model, serial)
    problems.append(problem)

    year, problem, approximate = parse_install_year(raw["install_year"], current_year)
    problems.append(problem)

    if source == "technician":
        condition, problem = convert_condition_10pt(raw["condition"])
        condition_display = f"{to_text(raw['condition'])}/10"
    else:
        condition, problem = convert_condition_text(raw["condition"])
        condition_display = to_text(raw["condition"])
    problems.append(problem)

    nameplate_problem = check_nameplate(to_text(raw["manufacturer"]), model, serial, raw.get("photo"))
    problems.append(nameplate_problem)
    problems.append(check_serial_missing(asset_type, serial, nameplate_problem))
    problems.append(check_serial_rounded(serial))
    if source == "partner":
        problems.append(check_multi_unit(raw["description"], raw["tag"]))
    problems.append(check_notes(raw["notes"], source))

    repeat_note = ""
    if source == "technician" and note_contains(to_text(raw["notes"]), mappings.REPEAT_NOTE_KEYWORDS):
        repeat_note = to_text(raw["notes"])

    return {
        "row_id": record["row_id"],
        "source": source,
        "raw": raw,
        "values": {
            "building": building,
            "asset_type": asset_type,
            "manufacturer": manufacturer,
            "model": model,
            "serial_number": serial,
            "install_year": year,
            "condition": condition,
            "location": normalize_location(raw["location"]),
        },
        "problems": [problem for problem in problems if problem],
        "approximate_year": approximate,
        "condition_display": condition_display,
        "serial_key": serial_key(serial),
        "repeat_note": repeat_note,
        "building_by_keyword": building_by_keyword,
        "original": record.get("original", {}),
    }


# ---------------------------------------------------------------------------
# Duplicates (R16 - R19)
# ---------------------------------------------------------------------------


def find_duplicates(cleaned_rows):
    """Group rows that are the same equipment (R16).

    Rows match when building and serial are the same (serial compared with
    spaces, dashes and case ignored). Rows with no usable serial each stay
    in their own group. Groups keep the order rows were read in.
    """
    groups = []
    group_for_key = {}
    for row in cleaned_rows:
        if row["serial_key"] is None:
            groups.append([row])
            continue
        key = (row["values"]["building"], row["serial_key"])
        if key in group_for_key:
            group_for_key[key].append(row)
        else:
            group_for_key[key] = [row]
            groups.append(group_for_key[key])
    return groups


def problems_for_field(row, field):
    """The problems on a row that belong to one field."""
    return [problem for problem in row["problems"] if problem.field == field]


def choose_value(field, ordered_rows):
    """Pick one value for a field in a merged row (R17).

    The first row in preference order with a filled-in, unflagged value wins.
    If none is clean, the first filled-in value is used with its problems,
    so nothing is silently dropped.
    """
    for row in ordered_rows:
        if has_value(row["values"][field]) and not problems_for_field(row, field):
            return row["values"][field], []
    filled = [row for row in ordered_rows if has_value(row["values"][field])]
    chosen = filled[0] if filled else ordered_rows[0]
    return chosen["values"][field], problems_for_field(chosen, field)


def describe_year(row):
    """A row's install year for a conflict reason, e.g. "partner:43 2004 (year of manufacture)"."""
    text = f"{row['row_id']} {row['values']['install_year']}"
    if row["source"] == "partner":
        text += " (year of manufacture)"
    return text


def merge_install_year(ordered_rows):
    """Pick the install year for a merged row (R18).

    The technician's year is used. If it is blank or flagged, the next row's
    year is used. If two valid years are more than 2 apart, the technician's
    year is still used and the row is flagged, because the partner's year of
    manufacture is normally within a year of install.
    """
    valid = [row for row in ordered_rows if row["values"]["install_year"] is not None]
    if not valid:
        for row in ordered_rows:
            if problems_for_field(row, "install_year"):
                return None, problems_for_field(row, "install_year"), row
        return None, [], None
    chosen = valid[0]
    problems = []
    for other in valid[1:]:
        if abs(chosen["values"]["install_year"] - other["values"]["install_year"]) > 2:
            problems.append(
                Problem(
                    "install_year",
                    "Install year differs between sources",
                    f"Install year differs between sources: {describe_year(chosen)}, {describe_year(other)}",
                )
            )
    return chosen["values"]["install_year"], problems, chosen


def merge_condition(ordered_rows):
    """Pick the condition for a merged row (R19).

    The worse (lower) 1-5 rating is always used, the cautious choice for
    capital planning. If the ratings differ by 2 or more, the row is also
    flagged with every original rating. A blank or flagged rating is skipped.
    """
    valid = [row for row in ordered_rows if row["values"]["condition"] is not None]
    if not valid:
        for row in ordered_rows:
            if problems_for_field(row, "condition"):
                return None, problems_for_field(row, "condition")
        return None, []
    ratings = [row["values"]["condition"] for row in valid]
    worst = min(ratings)
    problems = []
    if max(ratings) - worst >= 2:
        details = ", ".join(
            f"{row['row_id']} {row['condition_display']} ({row['values']['condition']} of 5)"
            for row in valid
        )
        problems.append(
            Problem(
                "condition",
                "Condition differs between sources",
                f"Condition differs between sources: {details}; used the lower rating",
            )
        )
    return worst, problems


def source_label(rows):
    """"both" if the rows come from both files, otherwise the one file's name (R16)."""
    sources = {row["source"] for row in rows}
    if len(sources) > 1:
        return "both"
    return sources.pop()


def merge_duplicate(group):
    """Combine the rows of one duplicate group into a single output row (R17).

    Model and serial come from the partner first (the cleaner nameplate copy).
    Building, asset type, manufacturer and location come from the technician
    first. Year and condition follow R18 and R19. Problems are kept only when
    they belong to a value that was actually used, or are about the whole row.
    """
    technician_rows = [row for row in group if row["source"] == "technician"]
    partner_rows = [row for row in group if row["source"] == "partner"]
    technician_first = technician_rows + partner_rows
    partner_first = partner_rows + technician_rows

    values = {}
    problems = []
    for field in ["building", "asset_type", "manufacturer", "location"]:
        values[field], field_problems = choose_value(field, technician_first)
        problems += field_problems
    for field in ["model", "serial_number"]:
        values[field], field_problems = choose_value(field, partner_first)
        problems += field_problems

    values["install_year"], year_problems, year_row = merge_install_year(technician_first)
    problems += year_problems
    values["condition"], condition_problems = merge_condition(technician_first)
    problems += condition_problems

    # R12 is checked again on the merged values: a nameplate one source
    # missed may have been filled in by the other.
    photo = technician_first[0]["raw"].get("photo")
    problems.append(check_nameplate(values["manufacturer"], values["model"], values["serial_number"], photo))

    # R14, R15: whole-row problems from any member row are always kept.
    # Repeat-entry notes are not flagged here because the merge resolved them.
    for row in group:
        problems += [problem for problem in row["problems"] if problem.field is None]

    return {
        "values": values,
        "source": source_label(group),
        "members": group,
        "problems": [problem for problem in problems if problem],
        "approximate_year": bool(year_row and year_row["approximate_year"]),
        "year_from_partner": bool(year_row and year_row["source"] == "partner"),
    }


def single_row(row):
    """Turn a row with no duplicate into an output row.

    A "2nd pass" note on a row that did not merge is flagged here (R15),
    because no matching serial was found to confirm the repeat.
    """
    problems = list(row["problems"])
    if row["repeat_note"]:
        problems.append(repeat_note_problem(row["repeat_note"]))
    return {
        "values": dict(row["values"]),
        "source": row["source"],
        "members": [row],
        "problems": problems,
        "approximate_year": row["approximate_year"],
        "year_from_partner": row["source"] == "partner" and row["values"]["install_year"] is not None,
    }


def flag_row(output_row):
    """Set status and review reason from the row's problems (R20).

    Any problem means needs_review, with every reason listed and separated
    by "; ". No problems means ready with a blank reason.
    """
    reasons = []
    categories = []
    for problem in output_row["problems"]:
        if problem.reason not in reasons:
            reasons.append(problem.reason)
            categories.append(problem.category)
    output_row["status"] = "needs_review" if reasons else "ready"
    output_row["review_reason"] = "; ".join(reasons)
    output_row["categories"] = categories
    output_row["row_ids"] = [row["row_id"] for row in output_row["members"]]
    return output_row


def details_key(value):
    """A model or manufacturer in the form used to compare two sources (R23)."""
    return re.sub(r"[\s\-]", "", lookup_key(value))


def details_conflict(group):
    """True if rows sharing a serial disagree on manufacturer or model (R23).

    Blank values are skipped, and case, spaces and dashes are ignored, so
    "ycd150f3" and "YCD150F3" agree.
    """
    for field in ["manufacturer", "model"]:
        values = {details_key(row["values"][field]) for row in group if has_value(row["values"][field])}
        if len(values) > 1:
            return True
    return False


def process_group(group):
    """Turn one group of matching rows into output rows (R16, R23).

    A single row is output as is. Rows that share a serial are merged,
    unless their manufacturer or model disagree: then each is output on its
    own and flagged as a possible serial typo, because merging two different
    units would lose one of them.
    """
    if len(group) == 1:
        return [flag_row(single_row(group[0]))]
    if not details_conflict(group):
        return [flag_row(merge_duplicate(group))]
    output_rows = []
    for row in group:
        others = ", ".join(other["row_id"] for other in group if other is not row)
        output_row = single_row(row)
        output_row["problems"].append(
            Problem(
                None,
                "Same serial, different equipment details",
                f"Same serial but different equipment details; possible serial typo (same serial as {others})",
            )
        )
        output_rows.append(flag_row(output_row))
    return output_rows


def flag_serials_in_several_buildings(cleaned_rows):
    """Flag every row whose serial also appears at another building (R24).

    One unit can't be in two buildings, so either a serial or a building is
    wrong. The rows are not merged.
    """
    buildings_for_serial = {}
    for row in cleaned_rows:
        if row["serial_key"] is not None:
            buildings_for_serial.setdefault(row["serial_key"], set()).add(row["values"]["building"])
    for row in cleaned_rows:
        buildings = buildings_for_serial.get(row["serial_key"], set())
        if len(buildings) > 1:
            others = ", ".join(sorted(b for b in buildings if b != row["values"]["building"]))
            row["problems"].append(
                Problem(
                    None,
                    "Serial in more than one building",
                    f"Serial number also appears at {others}; check the serial and building",
                )
            )


def plain_cause(error):
    """A short plain-language description of an unexpected row error (R25)."""
    if isinstance(error, (ValueError, TypeError)):
        return "a value in this row is in a format the tool doesn't handle (details in error_log.txt)"
    return "an unexpected problem (details in error_log.txt)"


def unprocessed_problem(error):
    """The R25 problem for a row the tool could not process."""
    return Problem(
        None,
        "Could not process row",
        f"Could not process this row automatically: {plain_cause(error)}",
    )


def fallback_row(record, error):
    """A cleaned row for an input row that could not be processed (R25).

    Every value is kept as captured text where possible, year and condition
    are left blank, and the row is never merged, so a person sees the raw
    data and the accounting still holds.
    """
    raw = record["raw"]
    values = {}
    for field in FIELDS:
        try:
            values[field] = to_text(raw.get(field))
        except Exception:
            values[field] = ""
    values["install_year"] = None
    values["condition"] = None
    return {
        "row_id": record["row_id"],
        "source": record["source"],
        "raw": raw,
        "values": values,
        "problems": [unprocessed_problem(error)],
        "approximate_year": False,
        "condition_display": "",
        "serial_key": None,
        "repeat_note": "",
        "building_by_keyword": "",
        "original": record.get("original", {}),
    }


# ---------------------------------------------------------------------------
# Accounting and the full run (R3, R21)
# ---------------------------------------------------------------------------


def check_row_accounting(input_ids, output_rows):
    """Stop the run if any input row is missing or counted twice (R21).

    Rows in must equal rows ready + rows needs_review + rows merged away,
    and every input row ID must appear in exactly one output row.
    """
    ready = sum(1 for row in output_rows if row["status"] == "ready")
    needs_review = sum(1 for row in output_rows if row["status"] == "needs_review")
    merged_away = sum(len(row["row_ids"]) - 1 for row in output_rows)
    if len(input_ids) != ready + needs_review + merged_away:
        raise RowAccountingError(
            f"Row count does not add up: {len(input_ids)} rows in, but {ready} ready + "
            f"{needs_review} needs_review + {merged_away} merged = {ready + needs_review + merged_away}"
        )
    seen = Counter(row_id for row in output_rows for row_id in row["row_ids"])
    missing = [row_id for row_id in input_ids if row_id not in seen]
    repeated = [row_id for row_id, count in seen.items() if count > 1]
    unknown = [row_id for row_id in seen if row_id not in set(input_ids)]
    if missing or repeated or unknown:
        raise RowAccountingError(
            f"Row IDs do not line up. Missing: {missing}. In more than one row: {repeated}. "
            f"Not in the input: {unknown}"
        )
    return {"ready": ready, "needs_review": needs_review, "merged_away": merged_away}


def read_accepted_asset_types(path):
    """Read the accepted asset types from Asset_Types.xlsx (or .csv)."""
    rows = read_rows(path)
    header = [lookup_key(to_text(cell)) for cell in rows[0]]
    column = header.index("asset_type") if "asset_type" in header else 0
    return {to_text(row[column]) for row in rows[1:] if column < len(row) and to_text(row[column])}


def check_asset_type_mappings(accepted):
    """Stop if mappings.py uses an asset type FMX does not accept (R5, R12)."""
    used = list(mappings.ASSET_TYPES) + list(mappings.ASSET_TYPES_WITHOUT_SERIAL)
    not_accepted = [value for value in used if value not in accepted]
    if not_accepted:
        raise ValueError(
            f"mappings.py uses asset types not in the accepted asset types file: {', '.join(not_accepted)}"
        )


def unrecognized_values(cleaned_rows):
    """Count every captured value the tool did not recognize, by field (R22).

    Counted per input row, before merging, so the list shows every spelling
    that needs a lookup entry, even ones the other source happened to cover.
    """
    counts = Counter()
    for row in cleaned_rows:
        for problem in row["problems"]:
            if problem.value is not None:
                counts[(problem.field, problem.value, row["source"])] += 1
    return counts


def read_target_columns(path):
    """Read the column names, in order, from Target_Format.xlsx (or .csv) (R22)."""
    header = [to_text(cell) for cell in read_rows(path)[0]]
    columns = [name for name in header if name]
    known = FIELDS + ["source", "status", "review_reason"]
    unknown = [name for name in columns if name not in known]
    if unknown:
        raise ValueError(f"{Path(path).name} has columns the tool does not produce: {', '.join(unknown)}")
    return columns


def reconcile(technician_path, partner_path, current_year=None, asset_types_path=DEFAULT_ASSET_TYPES):
    """Run every step except writing files, and return the results.

    Load both files, clean each row, merge duplicates, flag problems, and
    check that every input row is accounted for. Kept separate from writing
    so the tests can check results directly.
    """
    if current_year is None:
        current_year = date.today().year
    # R5: accepted asset types come from the file at run time, not from code.
    accepted_types = read_accepted_asset_types(asset_types_path)
    check_asset_type_mappings(accepted_types)
    asset_type_lookup = build_asset_type_lookup(accepted_types)

    technician = load_technician(technician_path)
    partner = load_partner(partner_path)
    records = technician + partner

    # R25: a row that can't be processed, for any reason, is kept and
    # flagged instead of stopping the run. Details go to error_log.txt.
    row_errors = []
    cleaned = []
    for record in records:
        try:
            cleaned.append(clean_record(record, current_year, asset_type_lookup))
        except Exception as error:
            row_errors.append(f"{record['row_id']}\n{traceback.format_exc()}")
            cleaned.append(fallback_row(record, error))

    flag_serials_in_several_buildings(cleaned)

    output_rows = []
    for group in find_duplicates(cleaned):
        try:
            output_rows += process_group(group)
        except Exception as error:
            # R25: if merging fails, output each row on its own, flagged.
            row_errors.append(f"{', '.join(row['row_id'] for row in group)}\n{traceback.format_exc()}")
            for row in group:
                output_row = single_row(row)
                output_row["problems"].append(unprocessed_problem(error))
                output_rows.append(flag_row(output_row))

    counts = check_row_accounting([record["row_id"] for record in records], output_rows)
    counts["technician_in"] = len(technician)
    counts["partner_in"] = len(partner)
    counts["duplicate_groups"] = sum(1 for row in output_rows if len(row["members"]) > 1)
    counts["approximate_years"] = sum(1 for row in output_rows if row["approximate_year"])
    counts["partner_years"] = sum(1 for row in output_rows if row["year_from_partner"])
    keyword_buildings = Counter(
        (row["building_by_keyword"], row["values"]["building"]) for row in cleaned if row["building_by_keyword"]
    )
    return {
        "rows": output_rows,
        "counts": counts,
        "unrecognized": unrecognized_values(cleaned),
        "keyword_buildings": keyword_buildings,
        "row_errors": row_errors,
        "warnings": [],
        # R30: every original column, in file order, for full_detail.csv.
        "original_columns": {
            "technician": list(technician[0]["original"]) if technician else [],
            "partner": list(partner[0]["original"]) if partner else [],
        },
        "run_at": datetime.now(),
        "files": {
            "Technician file": Path(technician_path).name,
            "Partner file": Path(partner_path).name,
            "Accepted asset types": Path(asset_types_path).name,
        },
    }


# ---------------------------------------------------------------------------
# Writing the three outputs (R22)
# ---------------------------------------------------------------------------


def format_cell(value):
    """Write blanks as empty cells and everything else as text."""
    return "" if value is None else value


def raw_value(output_row, field):
    """The original captured value(s) for one field, for the review list.

    For a merged row, each source's value is shown with its row ID so the
    specialist can see where each one came from.
    """
    members = output_row["members"]
    parts = []
    for member in members:
        raw = member["raw"]
        if field == "asset_type" and member["source"] == "partner":
            value = raw.get("description")
        else:
            value = raw.get(field)
        text = to_text(value)
        if len(members) == 1:
            return text
        if text:
            parts.append(f"{member['row_id']}: {text}")
    return " | ".join(parts)


def write_import_file(result, folder, target_columns):
    """Write import_ready.csv in exactly the target columns (R22)."""
    with open(Path(folder) / "import_ready.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(target_columns)
        for row in result["rows"]:
            cells = dict(row["values"])
            cells.update(source=row["source"], status=row["status"], review_reason=row["review_reason"])
            writer.writerow([format_cell(cells[column]) for column in target_columns])


def write_review_list(result, folder):
    """Write review_list.csv: needs_review rows with raw values next to cleaned ones (R22)."""
    review_columns = ["source_row_ids", "review_reason"]
    for field in FIELDS:
        review_columns += [field, f"raw_{field}"]
    review_columns += ["raw_notes", "raw_photo", "source"]
    with open(Path(folder) / "review_list.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(review_columns)
        for row in result["rows"]:
            if row["status"] != "needs_review":
                continue
            line = ["; ".join(row["row_ids"]), row["review_reason"]]
            for field in FIELDS:
                line += [format_cell(row["values"][field]), raw_value(row, field)]
            line += [raw_value(row, "notes"), raw_value(row, "photo"), row["source"]]
            writer.writerow(line)


def original_value(output_row, source, column):
    """One original column from one source, for full_detail.csv (R30).

    If several rows from the same source were merged, each value is shown
    with its row ID, so nothing from either row is lost.
    """
    members = [member for member in output_row["members"] if member["source"] == source]
    if len(members) == 1:
        return to_text(members[0]["original"].get(column))
    parts = []
    for member in members:
        text = to_text(member["original"].get(column))
        if text:
            parts.append(f"{member['row_id']}: {text}")
    return " | ".join(parts)


def write_full_detail(result, folder, target_columns):
    """Write full_detail.csv: every output row with every original column from both sources (R30).

    Same rows, in the same order, as import_ready.csv. The target columns
    come first, each cleaned value followed by its raw value, then every
    original column, prefixed technician_ or partner_.
    """
    original_columns = result["original_columns"]
    header = ["source_row_ids"]
    for column in target_columns:
        header.append(column)
        if column in FIELDS:
            header.append(f"raw_{column}")
    header += [f"technician_{name}" for name in original_columns["technician"]]
    header += [f"partner_{name}" for name in original_columns["partner"]]
    with open(Path(folder) / "full_detail.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in result["rows"]:
            cells = dict(row["values"])
            cells.update(source=row["source"], status=row["status"], review_reason=row["review_reason"])
            line = ["; ".join(row["row_ids"])]
            for column in target_columns:
                line.append(format_cell(cells[column]))
                if column in FIELDS:
                    line.append(raw_value(row, column))
            line += [original_value(row, "technician", name) for name in original_columns["technician"]]
            line += [original_value(row, "partner", name) for name in original_columns["partner"]]
            writer.writerow(line)


def check_full_detail_matches_import(folder, target_columns):
    """Stop if full_detail.csv and import_ready.csv don't have the same rows in the same order (R30)."""
    with open(Path(folder) / "import_ready.csv", newline="", encoding="utf-8") as handle:
        import_rows = [[row[column] for column in target_columns] for row in csv.DictReader(handle)]
    with open(Path(folder) / "full_detail.csv", newline="", encoding="utf-8") as handle:
        detail_rows = [[row[column] for column in target_columns] for row in csv.DictReader(handle)]
    if import_rows != detail_rows:
        raise OutputMismatchError(
            f"full_detail.csv has {len(detail_rows)} rows and import_ready.csv has {len(import_rows)}, "
            "or their rows differ"
        )


def write_outputs(result, out_dir, target_columns, technician_path, partner_path):
    """Write the three outputs without ever leaving a half-written set (R22, R28).

    The files are written to a temporary folder first. Only when all three
    are complete are the old files moved aside and replaced. If anything
    fails, the old files are put back.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".reconcile_tmp_", dir=out_dir))
    try:
        write_import_file(result, temp_dir, target_columns)
        write_review_list(result, temp_dir)
        write_full_detail(result, temp_dir, target_columns)
        check_full_detail_matches_import(temp_dir, target_columns)
        (temp_dir / "run_summary.md").write_text(
            summary_text(result, technician_path, partner_path), encoding="utf-8"
        )
        replaced = []
        try:
            for name in OUTPUT_FILES:
                target = out_dir / name
                if target.exists():
                    backup = temp_dir / f"{name}.previous"
                    os.replace(target, backup)
                    replaced.append((backup, target))
                os.replace(temp_dir / name, target)
        except Exception:
            # R28: put the previous files back so the folder is never half old, half new.
            for backup, target in replaced:
                os.replace(backup, target)
            raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def summary_text(result, technician_path, partner_path):
    """Build the run summary: rows in, rows out, and a count per review reason."""
    counts = result["counts"]
    rows_in = counts["technician_in"] + counts["partner_in"]
    reason_counts = Counter(category for row in result["rows"] for category in row["categories"])
    run_at = result.get("run_at") or datetime.now()
    files = result.get("files") or {
        "Technician file": Path(technician_path).name,
        "Partner file": Path(partner_path).name,
    }
    lines = [
        "# Run summary",
        "",
        f"Run on {run_at:%Y-%m-%d} at {run_at:%H:%M}.",
        "",
    ]
    for label, name in files.items():
        lines.append(f"- {label}: `{name}`")
    lines += [
        "",
        "| Count | Rows |",
        "|---|---|",
        f"| Technician rows in | {counts['technician_in']} |",
        f"| Partner rows in | {counts['partner_in']} |",
        f"| **Total rows in** | **{rows_in}** |",
        f"| Rows ready | {counts['ready']} |",
        f"| Rows flagged (needs_review) | {counts['needs_review']} |",
        f"| Rows merged into a duplicate | {counts['merged_away']} (in {counts['duplicate_groups']} merged rows) |",
        f"| Rows in import_ready.csv | {counts['ready'] + counts['needs_review']} |",
        "",
        f"Row check (R21): {rows_in} in = {counts['ready']} ready + {counts['needs_review']} "
        f"needs_review + {counts['merged_away']} merged. Passed.",
    ]
    lines += coverage_lines(result)
    lines += [
        "",
        "## Accepted, but worth knowing",
        "",
        f"- Approximate years accepted (e.g. `~2004`, `2004?`): {counts['approximate_years']}",
        f"- Partner year of manufacture used as install year: {counts['partner_years']}",
        "",
        "## Review reasons",
        "",
        "Number of flagged rows with each reason. A row with several problems is counted under each one.",
        "",
        "| Reason | Rows |",
        "|---|---|",
    ]
    for category, count in reason_counts.most_common():
        lines.append(f"| {category} | {count} |")
    if not reason_counts:
        lines.append("| (none) | 0 |")
    lines += unrecognized_section(result)

    # R29: warnings never stop the run, but they are written down.
    lines += ["", "## Warnings", ""]
    warnings = result.get("warnings") or []
    lines += [f"- {warning}" for warning in warnings] or ["None."]
    if result.get("row_errors"):
        lines.append(
            f"- {len(result['row_errors'])} row(s) could not be processed automatically and were flagged. "
            "Technical details are in error_log.txt."
        )
    return "\n".join(lines) + "\n"


def coverage_lines(result):
    """A table of output rows per building: technician only, partner only, and both (R22).

    It shows where only one source covered a building. In that case the tool
    has nothing to compare against, so it can't tell what equipment is missing.
    """
    buildings = list(mappings.BUILDINGS)
    for row in result["rows"]:
        building = row["values"]["building"] or "(no building)"
        if building not in buildings:
            buildings.append(building)
    counts = {building: Counter() for building in buildings}
    for row in result["rows"]:
        counts[row["values"]["building"] or "(no building)"][row["source"]] += 1
    lines = [
        "",
        "## Coverage by building",
        "",
        "Rows in import_ready.csv per building, by where they came from. Where only one source covered a "
        "building, there is nothing to compare against, so missing equipment can't be detected.",
        "",
        "| Building | Technician only | Partner only | Both | Total |",
        "|---|---|---|---|---|",
    ]
    totals = Counter()
    for building in buildings:
        row_counts = counts[building]
        total = sum(row_counts.values())
        totals.update(row_counts)
        lines.append(
            f"| {building} | {row_counts['technician']} | {row_counts['partner']} | {row_counts['both']} | {total} |"
        )
    lines.append(
        f"| **All buildings** | {totals['technician']} | {totals['partner']} | {totals['both']} | {sum(totals.values())} |"
    )
    return lines


def unrecognized_section(result):
    """List every unrecognized value by field, so the lookups can be updated in one pass (R22)."""
    lines = [
        "",
        "## Values the tool didn't recognize",
        "",
        "Each value below was kept as captured and flagged. Rows are input rows, counted before "
        "duplicates were merged. Add a value to `mappings.py` only if it has one clear meaning "
        "(README section 6).",
        "",
        "| Field | Value as captured | File | Rows |",
        "|---|---|---|---|",
    ]
    unrecognized = result["unrecognized"]
    field_order = list(FIELD_LABELS)
    ordered = sorted(
        unrecognized.items(),
        key=lambda item: (field_order.index(item[0][0]), -item[1], str(item[0][1]).lower()),
    )
    for (field, value, source), count in ordered:
        lines.append(f"| {FIELD_LABELS[field]} | {value} | {source} | {count} |")
    if not unrecognized:
        lines.append("| (none) | | | 0 |")

    lines += [
        "",
        "### Building names matched by keyword",
        "",
        "These were not in the building list but contained one building's keyword, so they were "
        "accepted. Add them to `BUILDINGS` in `mappings.py` to make the match exact.",
        "",
        "| Value as captured | Matched to | Rows |",
        "|---|---|---|",
    ]
    for (value, building), count in result["keyword_buildings"].most_common():
        lines.append(f"| {value} | {building} | {count} |")
    if not result["keyword_buildings"]:
        lines.append("| (none) | | 0 |")
    return lines


# ---------------------------------------------------------------------------
# File checks before processing (R26, R29)
# ---------------------------------------------------------------------------


def find_partner_header(rows):
    """The index of the first row containing "Facility" and "Serial Number", or None (R2)."""
    for index, row in enumerate(rows):
        keys = {lookup_key(to_text(cell)) for cell in row}
        if "facility" in keys and "serial number" in keys:
            return index
    return None


def looks_like_technician(rows):
    """True if the first row has the technician headings "Bldg" and "Serial #"."""
    keys = {lookup_key(to_text(cell)) for cell in rows[0]}
    return "bldg" in keys and "serial #" in keys


def open_input_file(path, label, problems, warnings, details, sheet_name=None):
    """Open one input file, recording plain-language problems instead of crashing (R26).

    Returns the file's rows, or None if it can't be used.
    """
    path = Path(path)
    if not path.exists():
        problems.append(
            f"The {label} '{path}' was not found. Check the file name and folder in the command, "
            "including the extension (for example .xlsx)."
        )
        return None
    if path.is_dir():
        problems.append(f"The {label} '{path}' is a folder, not a file. Give the full file name, including the extension.")
        return None
    try:
        rows = read_rows(path, sheet_name)
    except PermissionError:
        details.append(f"{label} {path}:\n{traceback.format_exc()}")
        problems.append(
            f"The {label} '{path.name}' could not be opened because another program is using it. "
            "Close it in Excel and run the tool again."
        )
        return None
    except Exception:
        details.append(f"{label} {path}:\n{traceback.format_exc()}")
        problems.append(
            f"The {label} '{path.name}' could not be opened. It may be damaged or not a spreadsheet. "
            "Open it in Excel, save a fresh copy as .xlsx, and run the tool again."
        )
        return None
    if path.suffix.lower() not in KNOWN_EXTENSIONS:
        warnings.append(
            f"The {label} '{path.name}' has the extension '{path.suffix or '(none)'}', not .xlsx or .csv. "
            "It opened, so the run continued; check that it is the right file."
        )
    if not any(to_text(cell) for row in rows for cell in row):
        problems.append(f"The {label} '{path.name}' is empty. Check that you selected the right file.")
        return None
    return rows


def check_columns(header, column_map, ignored, label, problems, warnings):
    """Report missing required columns (problems) and unknown extra columns (warnings)."""
    present = {lookup_key(name) for name in header if name}
    missing = [column for column in column_map if lookup_key(column) not in present]
    for column in missing:
        problems.append(
            f"The {label} is missing the column '{column}'. Check that you selected the right file, "
            "or that the column wasn't renamed."
        )
    if missing:
        found = ", ".join(f"'{name}'" for name in header if name) or "(none)"
        problems.append(f"Columns found in the {label}: {found}.")
    known = {lookup_key(name) for name in list(column_map) + list(ignored)}
    for name in header:
        if name and lookup_key(name) not in known:
            warnings.append(f"The {label} has a column the tool doesn't use, '{name}'. It was ignored.")


def has_data_rows(rows, header_index):
    """True if any row below the header has a value and isn't a copy of the header."""
    header = [to_text(cell) for cell in rows[header_index]]
    for row in rows[header_index + 1 :]:
        texts = [to_text(cell) for cell in row]
        if any(texts) and texts[: len(header)] != header:
            return True
    return False


def check_input_files(technician_path, partner_path, asset_types_path, target_format_path, out_dir):
    """Check every file before processing anything, and collect every problem (R26).

    Returns (problems, warnings, details). Problems stop the run; all of them
    are reported together so they can be fixed in one go. Warnings are
    noted in the run summary and the run continues (R29). Details are the
    technical errors for error_log.txt.
    """
    problems, warnings, details = [], [], []
    mapping_problem = mappings_problem()
    if mapping_problem:
        problems.append(mapping_problem)
        details.append("".join(traceback.format_exception(MAPPINGS_ERROR)))
        return problems, warnings, details

    technician = open_input_file(technician_path, "technician file", problems, warnings, details)
    partner = open_input_file(partner_path, "partner file", problems, warnings, details, sheet_name="Equipment")

    technician_is_partner = technician is not None and find_partner_header(technician) is not None
    partner_is_technician = partner is not None and looks_like_technician(partner)
    if technician_is_partner and partner_is_technician:
        problems.append(
            f"The two files seem to be in the wrong order: '{Path(technician_path).name}' looks like a partner "
            f"equipment list and '{Path(partner_path).name}' looks like a technician capture. Put the technician "
            "file first and the partner file second, then run the tool again."
        )
    else:
        if technician_is_partner:
            problems.append(
                f"The technician file '{Path(technician_path).name}' looks like a partner equipment list. "
                "The first file in the command must be the technician capture."
            )
        elif technician is not None:
            header = padded_texts(technician[0], max(len(row) for row in technician))
            check_columns(
                header, mappings.TECHNICIAN_COLUMNS, mappings.TECHNICIAN_IGNORED_COLUMNS,
                "technician file", problems, warnings,
            )
            if not has_data_rows(technician, 0):
                problems.append(
                    f"The technician file '{Path(technician_path).name}' has column headings but no equipment rows. "
                    "Check that you selected the right file."
                )
        if partner_is_technician:
            problems.append(
                f"The partner file '{Path(partner_path).name}' looks like a technician capture. "
                "The second file in the command must be the partner equipment list."
            )
        elif partner is not None:
            header_index = find_partner_header(partner)
            if header_index is None:
                problems.append(
                    f"The partner file '{Path(partner_path).name}' has no header row with the columns 'Facility' "
                    "and 'Serial Number'. Check that you selected the right file, or that the columns weren't renamed."
                )
            else:
                header = padded_texts(partner[header_index], max(len(row) for row in partner))
                check_columns(
                    header, mappings.PARTNER_COLUMNS, mappings.PARTNER_IGNORED_COLUMNS,
                    "partner file", problems, warnings,
                )
                if not has_data_rows(partner, header_index):
                    problems.append(
                        f"The partner file '{Path(partner_path).name}' has column headings but no equipment rows. "
                        "Check that you selected the right file."
                    )

    asset_rows = open_input_file(asset_types_path, "accepted asset types file", problems, warnings, details)
    if asset_rows is not None:
        accepted = read_accepted_asset_types(asset_types_path)
        used = list(mappings.ASSET_TYPES) + list(mappings.ASSET_TYPES_WITHOUT_SERIAL)
        not_accepted = [value for value in used if value not in accepted]
        if not_accepted:
            problems.append(
                f"mappings.py uses asset types that aren't in '{Path(asset_types_path).name}': "
                f"{', '.join(not_accepted)}. Fix the spelling in mappings.py, or check that you're using "
                "FMX's asset types file."
            )

    target_rows = open_input_file(target_format_path, "target format file", problems, warnings, details)
    if target_rows is not None:
        known = FIELDS + ["source", "status", "review_reason"]
        unknown = [to_text(cell) for cell in target_rows[0] if to_text(cell) and to_text(cell) not in known]
        if unknown:
            problems.append(
                f"The target format file '{Path(target_format_path).name}' has columns the tool doesn't know how "
                f"to fill: {', '.join(unknown)}. Check that you're using FMX's Target_Format file."
            )

    out_dir = Path(out_dir)
    if out_dir.exists() and not out_dir.is_dir():
        problems.append(f"The output folder '{out_dir}' is a file, not a folder. Choose a different --out folder.")
    elif out_dir.exists():
        for name in OUTPUT_FILES:
            target = out_dir / name
            if target.exists():
                try:
                    with open(target, "a"):
                        pass
                except PermissionError:
                    problems.append(
                        f"The output file '{name}' is open in another program (probably Excel), so it can't be "
                        "replaced. Close it and run the tool again."
                    )
    return problems, warnings, details


# ---------------------------------------------------------------------------
# Running from the command line (R27, R28)
# ---------------------------------------------------------------------------


def previous_outputs_note(out_dir):
    """Tell the user whether the previous output files are still there (R28)."""
    existing = [name for name in OUTPUT_FILES if (Path(out_dir) / name).exists()]
    if existing:
        return f"Your previous output files in '{out_dir}' were not changed."
    return "No output files were written."


def write_error_log(out_dir, problems, details):
    """Save the technical details for a developer to error_log.txt. Returns its path, or None."""
    try:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path = Path(out_dir) / ERROR_LOG
        lines = [f"reconcile.py error log, {datetime.now():%Y-%m-%d %H:%M:%S}", f"Command: {' '.join(sys.argv)}", ""]
        lines += ["Messages shown:"] + [f"- {problem}" for problem in problems] + ["", "Technical details:", details or "(none)"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    except Exception:
        return None


def report_stop(problems, details, out_dir, debug):
    """Print a plain-language stop message and save the technical details (R27)."""
    print("STOPPED: the run did not finish.", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    print(previous_outputs_note(out_dir), file=sys.stderr)
    log_path = write_error_log(out_dir, problems, details)
    if log_path:
        print(f"Technical details for a developer were saved to {log_path}.", file=sys.stderr)
    else:
        print("Technical details could not be saved; run again with --debug to see them.", file=sys.stderr)
    if debug and details:
        print("\n--- debug details ---\n" + details, file=sys.stderr)
    return 1


def main(argv=None):
    """Read the command line, check the files, run the tool, and write the outputs.

    Only file-level problems stop the run (R26). Every stop message is plain
    language; technical details go to error_log.txt, or to the screen with
    --debug (R27). Outputs are only replaced when the whole run succeeds (R28).
    """
    parser = argparse.ArgumentParser(description="Reconcile technician and partner FCA equipment data.")
    parser.add_argument("technician", help="technician capture file (.xlsx or .csv)")
    parser.add_argument("partner", help="partner equipment list (.xlsx or .csv)")
    parser.add_argument("--out", default="output", help="folder for the three output files (default: output)")
    parser.add_argument("--asset-types", default=DEFAULT_ASSET_TYPES, help="accepted asset types file")
    parser.add_argument("--target-format", default=DEFAULT_TARGET_FORMAT, help="target format file")
    parser.add_argument("--debug", action="store_true", help="show technical error details on screen")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)

    try:
        problems, warnings, details = check_input_files(
            args.technician, args.partner, args.asset_types, args.target_format, out_dir
        )
        if problems:
            raise StopRun(problems, "\n\n".join(details))
        target_columns = read_target_columns(args.target_format)
        result = reconcile(args.technician, args.partner, asset_types_path=args.asset_types)
        result["warnings"] = warnings
        result["files"]["Target format"] = Path(args.target_format).name
        write_outputs(result, out_dir, target_columns, args.technician, args.partner)
    except StopRun as stop:
        return report_stop(stop.problems, stop.details, out_dir, args.debug)
    except OutputMismatchError:
        message = (
            "The detail file didn't line up row for row with the import file, so no output files were replaced. "
            "This is a problem in the tool, not in your files. Send error_log.txt to a developer."
        )
        return report_stop([message], traceback.format_exc(), out_dir, args.debug)
    except RowAccountingError:
        message = (
            "The row count didn't add up, so the run was stopped to avoid losing equipment rows. "
            "This is a problem in the tool, not in your files. Send error_log.txt to a developer."
        )
        return report_stop([message], traceback.format_exc(), out_dir, args.debug)
    except PermissionError:
        message = (
            "An output file could not be saved, probably because it is open in Excel. "
            "Close the files in the output folder and run the tool again."
        )
        return report_stop([message], traceback.format_exc(), out_dir, args.debug)
    except Exception:
        message = (
            "The tool hit an unexpected problem and stopped. "
            "Send error_log.txt to a developer, and include the two input files if you can."
        )
        return report_stop([message], traceback.format_exc(), out_dir, args.debug)

    # R27: row-level errors don't stop the run, but their details are kept.
    if result["row_errors"]:
        write_error_log(out_dir, ["Some rows could not be processed automatically."], "\n\n".join(result["row_errors"]))
    elif (out_dir / ERROR_LOG).exists():
        (out_dir / ERROR_LOG).unlink()  # an old log from a failed run would be misleading

    for warning in warnings:
        print(f"Warning: {warning}")
    counts = result["counts"]
    print(
        f"Rows in: {counts['technician_in']} technician + {counts['partner_in']} partner. "
        f"Ready: {counts['ready']}. Needs review: {counts['needs_review']}. "
        f"Merged into duplicates: {counts['merged_away']}."
    )
    print(f"Wrote import_ready.csv, review_list.csv, run_summary.md and full_detail.csv to {out_dir.resolve()}")
    if result["row_errors"]:
        print(
            f"{len(result['row_errors'])} row(s) could not be processed automatically; they are in the review list. "
            f"Details for a developer are in {out_dir / ERROR_LOG}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
