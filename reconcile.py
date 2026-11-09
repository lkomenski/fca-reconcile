"""Reconcile FCA equipment data from a technician file and a partner file.

Run it like this:

    python reconcile.py data/Technician_Capture.csv.xlsx data/Partner_Equipment_List.xlsx --out output

The tool reads both files, cleans every value that has one clear right answer,
merges equipment that both sources logged, and flags everything else for a
person. It writes three files to the output folder: import_ready.csv,
review_list.csv and run_summary.md. Rule IDs (R1, R2, ...) refer to
docs/RULES.md.
"""

import argparse
import csv
import math
import re
import sys
from collections import Counter, namedtuple
from datetime import date, datetime
from pathlib import Path

import openpyxl

import mappings

HERE = Path(__file__).resolve().parent
DEFAULT_ASSET_TYPES = HERE / "data" / "Asset_Types.xlsx"
DEFAULT_TARGET_FORMAT = HERE / "data" / "Target_Format.xlsx"

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
Problem = namedtuple("Problem", ["field", "category", "reason"])


class RowAccountingError(Exception):
    """Raised when rows in do not equal rows out (R21)."""


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


BUILDING_LOOKUP = build_lookup(mappings.BUILDINGS, "BUILDINGS")
ASSET_TYPE_LOOKUP = build_lookup(mappings.ASSET_TYPES, "ASSET_TYPES")
MANUFACTURER_LOOKUP = build_lookup(mappings.MANUFACTURERS, "MANUFACTURERS")
PARTNER_CONDITION_LOOKUP = {lookup_key(word): score for word, score in mappings.PARTNER_CONDITION.items()}
SERIAL_PLACEHOLDER_KEYS = {lookup_key(value) for value in mappings.SERIAL_PLACEHOLDERS}


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


def read_rows(path, sheet_name=None):
    """Read every row of an .xlsx or .csv file as a list of cell values.

    For Excel files, the named sheet is used if it exists, otherwise the first
    sheet. The file is only read, never changed (requirement 1).
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        # Excel sometimes saves CSV files in the older Windows encoding.
        try:
            with open(path, newline="", encoding="utf-8-sig") as handle:
                return [list(row) for row in csv.reader(handle)]
        except UnicodeDecodeError:
            with open(path, newline="", encoding="cp1252") as handle:
                return [list(row) for row in csv.reader(handle)]
    if suffix in (".xlsx", ".xlsm"):
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
        else:
            sheet = workbook.worksheets[0]
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        workbook.close()
        return rows
    raise ValueError(f"{path.name}: the file must be .xlsx or .csv")


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


def make_record(source, row_number, row, columns):
    """Package one input row with its source row ID and its raw values.

    The row ID (e.g. "technician:42") is the spreadsheet row number, so any
    output row can be traced back to the row in Excel.
    """
    raw = {}
    for field, index in columns.items():
        raw[field] = row[index] if index < len(row) else None
    return {"row_id": f"{source}:{row_number}", "source": source, "raw": raw}


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
        records.append(make_record("technician", row_number, row, columns))
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
        records.append(make_record("partner", index + 1, row, columns))
    return records


# ---------------------------------------------------------------------------
# Cleaning one field at a time (R4 - R11)
# ---------------------------------------------------------------------------


def normalize_building(raw):
    """Map a building name to one of the three official names (R4).

    Only names listed in mappings.BUILDINGS are changed. An unknown name is
    kept as typed and flagged.
    """
    text = to_text(raw)
    if not text:
        return "", Problem("building", "Building missing", "Building is missing")
    building = BUILDING_LOOKUP.get(lookup_key(text))
    if building:
        return building, None
    return text, Problem(
        "building",
        "Building not recognized",
        f"Building '{text}' is not a recognized building name",
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


def normalize_asset_type(raw):
    """Map an asset type to a value from the accepted list (R5).

    Only spellings listed in mappings.ASSET_TYPES are changed. Anything else,
    including vague words like "fan", is kept as typed and flagged.
    """
    text = to_text(raw)
    if not text:
        return "", Problem("asset_type", "Asset type missing", "Asset type is missing")
    asset_type = ASSET_TYPE_LOOKUP.get(lookup_key(text))
    if asset_type:
        return asset_type, None
    return text, Problem(
        "asset_type",
        "Asset type not in accepted list",
        f"Asset type '{text}' is not in the accepted list; choose the correct type",
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
    )


def parse_install_year(raw, current_year):
    """Turn a captured install year into a four-digit year (R9).

    Returns (year, problem, approximate). Four-digit years, two-digit years
    ('04, 98), "Mfg 04/2011" dates and approximate years (~2004, 2004?) are
    read. Approximate years are kept and marked so the summary can count
    them. Blank stays blank with no flag. Future years and anything that is
    not one clear year are flagged and left blank.
    """
    text = to_text(raw)
    if not text:
        return None, None, False

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

    if year > current_year:
        return None, Problem(
            "install_year", "Install year in the future", f"Install year {year} is in the future"
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
        )
    if not 1 <= score <= 10:
        return None, Problem(
            "condition",
            "Condition out of range",
            f"Condition {text} is outside the technician's 1-10 scale",
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
    return re.sub(r"[\s\-]", "", text).upper()


# ---------------------------------------------------------------------------
# Cleaning a whole row
# ---------------------------------------------------------------------------


def clean_record(record, current_year):
    """Clean every field of one input row and collect its problems.

    Each value is cleaned by its own rule. Problems are collected, not acted
    on, so a row with three problems lists all three.
    """
    raw = record["raw"]
    source = record["source"]
    problems = []

    building, problem = normalize_building(raw["building"])
    problems.append(problem)

    if source == "partner":
        asset_text = partner_asset_type_text(raw["description"], raw["tag"])
    else:
        asset_text = raw["asset_type"]
    asset_type, problem = normalize_asset_type(asset_text)
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


def check_asset_type_mappings(path):
    """Stop if mappings.py uses an asset type FMX does not accept (R5, R12)."""
    accepted = read_accepted_asset_types(path)
    used = list(mappings.ASSET_TYPES) + list(mappings.ASSET_TYPES_WITHOUT_SERIAL)
    not_accepted = [value for value in used if value not in accepted]
    if not_accepted:
        raise ValueError(
            f"mappings.py uses asset types not in {Path(path).name}: {', '.join(not_accepted)}"
        )


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
    check_asset_type_mappings(asset_types_path)

    technician = load_technician(technician_path)
    partner = load_partner(partner_path)
    records = technician + partner
    cleaned = [clean_record(record, current_year) for record in records]

    output_rows = []
    for group in find_duplicates(cleaned):
        if len(group) == 1:
            output_rows.append(flag_row(single_row(group[0])))
        else:
            output_rows.append(flag_row(merge_duplicate(group)))

    counts = check_row_accounting([record["row_id"] for record in records], output_rows)
    counts["technician_in"] = len(technician)
    counts["partner_in"] = len(partner)
    counts["duplicate_groups"] = sum(1 for row in output_rows if len(row["members"]) > 1)
    counts["approximate_years"] = sum(1 for row in output_rows if row["approximate_year"])
    counts["partner_years"] = sum(1 for row in output_rows if row["year_from_partner"])
    return {"rows": output_rows, "counts": counts}


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


def write_outputs(result, out_dir, target_columns, technician_path, partner_path):
    """Write import_ready.csv, review_list.csv and run_summary.md (R22)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = result["rows"]

    with open(out_dir / "import_ready.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(target_columns)
        for row in rows:
            cells = dict(row["values"])
            cells.update(source=row["source"], status=row["status"], review_reason=row["review_reason"])
            writer.writerow([format_cell(cells[column]) for column in target_columns])

    review_columns = ["source_row_ids", "review_reason"]
    for field in FIELDS:
        review_columns += [field, f"raw_{field}"]
    review_columns += ["raw_notes", "raw_photo", "source"]
    with open(out_dir / "review_list.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(review_columns)
        for row in rows:
            if row["status"] != "needs_review":
                continue
            line = ["; ".join(row["row_ids"]), row["review_reason"]]
            for field in FIELDS:
                line += [format_cell(row["values"][field]), raw_value(row, field)]
            line += [raw_value(row, "notes"), raw_value(row, "photo"), row["source"]]
            writer.writerow(line)

    (out_dir / "run_summary.md").write_text(
        summary_text(result, technician_path, partner_path), encoding="utf-8"
    )


def summary_text(result, technician_path, partner_path):
    """Build the run summary: rows in, rows out, and a count per review reason."""
    counts = result["counts"]
    rows_in = counts["technician_in"] + counts["partner_in"]
    reason_counts = Counter(category for row in result["rows"] for category in row["categories"])
    lines = [
        "# Run summary",
        "",
        f"Run at {datetime.now():%Y-%m-%d %H:%M}.",
        f"Technician file: `{Path(technician_path).name}`. Partner file: `{Path(partner_path).name}`.",
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
    return "\n".join(lines) + "\n"


def main(argv=None):
    """Read the command line, run the tool, and write the outputs."""
    parser = argparse.ArgumentParser(description="Reconcile technician and partner FCA equipment data.")
    parser.add_argument("technician", help="technician capture file (.xlsx or .csv)")
    parser.add_argument("partner", help="partner equipment list (.xlsx or .csv)")
    parser.add_argument("--out", default="output", help="folder for the three output files (default: output)")
    parser.add_argument("--asset-types", default=DEFAULT_ASSET_TYPES, help="accepted asset types file")
    parser.add_argument("--target-format", default=DEFAULT_TARGET_FORMAT, help="target format file")
    args = parser.parse_args(argv)

    try:
        target_columns = read_target_columns(args.target_format)
        result = reconcile(args.technician, args.partner, asset_types_path=args.asset_types)
    except RowAccountingError as error:
        print(f"STOPPED: {error}. No output files were written.", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    write_outputs(result, args.out, target_columns, args.technician, args.partner)
    counts = result["counts"]
    print(
        f"Rows in: {counts['technician_in']} technician + {counts['partner_in']} partner. "
        f"Ready: {counts['ready']}. Needs review: {counts['needs_review']}. "
        f"Merged into duplicates: {counts['merged_away']}."
    )
    print(f"Wrote import_ready.csv, review_list.csv and run_summary.md to {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
