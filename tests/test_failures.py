"""Tests for failing gracefully and for the cross-row serial checks (R9, R16,
R22 - R29). Tests that run the full command check that every message is
plain language, that no Python error appears, and that previous outputs are
left untouched when a run stops."""

import csv
import re
from datetime import datetime

import reconcile as rc
from test_rules import (
    FIXTURES,
    REAL_PARTNER,
    REAL_TECHNICIAN,
    TECH_HEADER,
    YEAR,
    clean,
    partner_record,
    tech_record,
    write_csv,
)

import pytest

UNSEEN_T = FIXTURES / "unseen_technician.csv"
UNSEEN_P = FIXTURES / "unseen_partner.csv"


def run_main(capsys, *args):
    """Run the tool like the command line and return (exit code, everything printed)."""
    code = rc.main([str(arg) for arg in args])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def assert_plain(text):
    """No Python error names or tracebacks on screen."""
    assert "Traceback" not in text
    assert not re.search(r"\b[A-Z]\w*(Error|Exception)\b", text), text


def seed_outputs(capsys, out_dir):
    """Make a successful run first, and return the bytes of its outputs."""
    assert run_main(capsys, UNSEEN_T, UNSEEN_P, "--out", out_dir)[0] == 0
    return {name: (out_dir / name).read_bytes() for name in rc.OUTPUT_FILES}


def assert_outputs_unchanged(out_dir, before):
    assert {name: (out_dir / name).read_bytes() for name in rc.OUTPUT_FILES} == before
    assert not list(out_dir.glob(".reconcile_tmp_*"))  # no temporary files left behind


# --- R23 / R24: serial checks across rows -------------------------------------


def test_R23_same_serial_different_model_is_flagged_not_merged():
    tech = clean(tech_record(2, model="YCD150F3", serial_number="X1"))
    partner = clean(partner_record(5, model="CGAM110", serial_number="X1"))
    rows = rc.process_group([tech, partner])
    assert len(rows) == 2
    for row in rows:
        assert row["status"] == "needs_review"
        assert "Same serial but different equipment details; possible serial typo" in row["review_reason"]


def test_R23_case_and_dash_differences_still_merge():
    tech = clean(tech_record(2, model="ycd 150-f3", manufacturer="TRANE", serial_number="X1"))
    partner = clean(partner_record(5, model="YCD150F3", manufacturer="Trane", serial_number="X1"))
    assert len(rc.process_group([tech, partner])) == 1


def test_R24_serial_in_two_buildings_flags_both_rows():
    a = clean(tech_record(2, building="LVHS", serial_number="X1"))
    b = clean(tech_record(3, building="LVMS", serial_number="X-1"))
    rc.flag_serials_in_several_buildings([a, b])
    assert "Serial number also appears at Lakeview Middle School" in a["problems"][-1].reason
    assert "Serial number also appears at Lakeview High School" in b["problems"][-1].reason


# --- R9 / R16 / R22: dates, decimals, leading zeros, summary header ---------


@pytest.mark.parametrize("raw", [datetime(2004, 1, 1), "2004-01-01", "2004-01-01 00:00:00", "2004.0", 2004.0])
def test_R9_year_stored_as_date_or_decimal(raw):
    assert rc.parse_install_year(raw, YEAR) == (2004, None, False)


def test_R16_leading_zeros_ignored_only_for_all_digit_serials():
    assert rc.serial_key("00644492") == rc.serial_key(644492)
    assert rc.serial_key("0A12") != rc.serial_key("A12")


def test_R22_summary_names_input_files_and_run_time():
    result = rc.reconcile(UNSEEN_T, UNSEEN_P, current_year=YEAR)
    text = rc.summary_text(result, "x", "y")
    assert "Technician file: `unseen_technician.csv`" in text
    assert "Partner file: `unseen_partner.csv`" in text
    assert "Run on " in text


# --- R25 - R29: failing gracefully --------------------------------------------


def test_R26_missing_column_stops_with_plain_message(tmp_path, capsys):
    before = seed_outputs(capsys, tmp_path)
    broken = tmp_path / "tech.csv"
    rows = list(csv.reader(open(UNSEEN_T, encoding="utf-8")))
    write_csv(broken, [[cell for i, cell in enumerate(row) if i != 4] for row in rows])  # drop Serial #
    code, text = run_main(capsys, broken, UNSEEN_P, "--out", tmp_path)
    assert code == 1
    assert "The technician file is missing the column 'Serial #'. Check that you selected the right file" in text
    assert "Columns found in the technician file: 'Bldg'" in text
    assert "previous output files" in text
    assert_plain(text)
    assert_outputs_unchanged(tmp_path, before)


def test_R26_every_file_problem_reported_at_once(tmp_path, capsys):
    broken = tmp_path / "tech.csv"
    write_csv(broken, [[c for c in TECH_HEADER if c not in ("Serial #", "Photo")], ["LVHS"] * 10])
    code, text = run_main(capsys, broken, tmp_path / "no_such_partner.xlsx", "--out", tmp_path / "out")
    assert code == 1
    assert "missing the column 'Serial #'" in text
    assert "missing the column 'Photo'" in text
    assert "The partner file" in text and "was not found" in text
    assert "No output files were written." in text
    assert_plain(text)


def test_R26_empty_file_stops_with_plain_message(tmp_path, capsys):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    code, text = run_main(capsys, empty, UNSEEN_P, "--out", tmp_path / "out")
    assert code == 1
    assert "The technician file 'empty.csv' is empty. Check that you selected the right file." in text
    assert_plain(text)


def test_R26_headings_but_no_rows_stops(tmp_path, capsys):
    header_only = tmp_path / "header_only.csv"
    write_csv(header_only, [TECH_HEADER])
    code, text = run_main(capsys, header_only, UNSEEN_P, "--out", tmp_path / "out")
    assert code == 1
    assert "has column headings but no equipment rows" in text
    assert_plain(text)


def test_R26_files_in_wrong_order_stop_with_plain_message(tmp_path, capsys):
    before = seed_outputs(capsys, tmp_path)
    code, text = run_main(capsys, UNSEEN_P, UNSEEN_T, "--out", tmp_path)
    assert code == 1
    assert "The two files seem to be in the wrong order" in text
    assert "Put the technician file first and the partner file second" in text
    assert_plain(text)
    assert_outputs_unchanged(tmp_path, before)


def test_R26_damaged_file_stops_and_details_go_to_error_log(tmp_path, capsys):
    damaged = tmp_path / "damaged.xlsx"
    damaged.write_bytes(b"this is not a spreadsheet")
    code, text = run_main(capsys, damaged, UNSEEN_P, "--out", tmp_path / "out")
    assert code == 1
    assert "could not be opened. It may be damaged or not a spreadsheet" in text
    assert_plain(text)
    assert "Traceback" in (tmp_path / "out" / "error_log.txt").read_text(encoding="utf-8")


def test_R27_debug_flag_shows_technical_details(tmp_path, capsys):
    damaged = tmp_path / "damaged.xlsx"
    damaged.write_bytes(b"this is not a spreadsheet")
    code, text = run_main(capsys, damaged, UNSEEN_P, "--out", tmp_path / "out", "--debug")
    assert code == 1
    assert "--- debug details ---" in text and "Traceback" in text


def test_R27_broken_mappings_file_gives_plain_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rc, "MAPPINGS_ERROR", SyntaxError("invalid syntax", ("mappings.py", 12, 5, "x")))
    code, text = run_main(capsys, UNSEEN_T, UNSEEN_P, "--out", tmp_path / "out")
    assert code == 1
    assert "mappings.py has a typing mistake near line 12" in text
    assert_plain(text)


def test_R25_broken_row_is_flagged_and_run_continues(monkeypatch, tmp_path, capsys):
    real_normalize_location = rc.normalize_location

    def breaks_on_one_row(raw):
        if raw == "Pump Rm":  # technician:8 in the unseen file
            raise ValueError("simulated unexpected value")
        return real_normalize_location(raw)

    monkeypatch.setattr(rc, "normalize_location", breaks_on_one_row)
    code, text = run_main(capsys, UNSEEN_T, UNSEEN_P, "--out", tmp_path)
    assert code == 0
    assert "1 row(s) could not be processed automatically" in text
    assert_plain(text)
    with open(tmp_path / "review_list.csv", encoding="utf-8") as handle:
        review = {row["source_row_ids"]: row for row in csv.DictReader(handle)}
    assert review["technician:8"]["review_reason"].startswith("Could not process this row automatically: ")
    assert "partner:5" in review  # its partner match is no longer merged, but is still there
    summary = (tmp_path / "run_summary.md").read_text(encoding="utf-8")
    assert "Row check (R21): 11 in" in summary  # accounting still holds
    assert "simulated unexpected value" in (tmp_path / "error_log.txt").read_text(encoding="utf-8")


def test_R28_run_failing_partway_leaves_previous_outputs(monkeypatch, tmp_path, capsys):
    before = seed_outputs(capsys, tmp_path)

    def fails(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr(rc, "write_review_list", fails)
    code, text = run_main(capsys, REAL_TECHNICIAN, REAL_PARTNER, "--out", tmp_path)
    assert code == 1
    assert "The tool hit an unexpected problem and stopped" in text
    assert f"Your previous output files in '{tmp_path}' were not changed." in text
    assert_plain(text)
    assert_outputs_unchanged(tmp_path, before)


def test_R29_extra_column_and_odd_extension_are_warnings(tmp_path, capsys):
    odd = tmp_path / "tech.txt"
    rows = list(csv.reader(open(UNSEEN_T, encoding="utf-8")))
    write_csv(odd, [row + (["Inspector Notes"] if i in (0, 5) else ["x"]) for i, row in enumerate(rows)])
    code, text = run_main(capsys, odd, UNSEEN_P, "--out", tmp_path / "out")
    assert code == 0
    summary = (tmp_path / "out" / "run_summary.md").read_text(encoding="utf-8")
    assert "has the extension '.txt', not .xlsx or .csv" in summary
    assert "has a column the tool doesn't use, 'Inspector Notes'" in summary
    assert_plain(text)


# --- R30: full_detail.csv keeps everything captured --------------------------


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_R30_full_detail_has_same_rows_in_same_order_as_import(tmp_path, capsys):
    assert run_main(capsys, REAL_TECHNICIAN, REAL_PARTNER, "--out", tmp_path)[0] == 0
    target = rc.read_target_columns(rc.DEFAULT_TARGET_FORMAT)
    import_rows = [[row[c] for c in target] for row in read_csv_rows(tmp_path / "import_ready.csv")]
    detail_rows = [[row[c] for c in target] for row in read_csv_rows(tmp_path / "full_detail.csv")]
    assert len(detail_rows) == 166
    assert detail_rows == import_rows


def test_R30_full_detail_keeps_columns_the_import_drops(tmp_path, capsys):
    run_main(capsys, REAL_TECHNICIAN, REAL_PARTNER, "--out", tmp_path)
    rows = {row["source_row_ids"]: row for row in read_csv_rows(tmp_path / "full_detail.csv")}
    merged = rows["technician:100; partner:42"]
    assert merged["partner_Equipment Description"] == "Rooftop Unit RTU-6, 12.5 ton"  # tonnage kept
    assert merged["partner_Tag"] == "RTU-6"
    assert merged["technician_Notes"] == "RTU-6 heat exchanger cracked, locked out"
    assert merged["technician_Tech"] == "JR"
    assert merged["partner_System"] == "HVAC"
    assert rows["partner:54"]["partner_Equipment Description"] == "Unit Ventilators (qty 4)"
    assert rows["technician:33"]["technician_Notes"] == "Panel LP-1B"
    # Two technician rows merged: both sides kept, each labelled with its row ID.
    assert rows["technician:12; technician:44"]["technician_Photo"] == (
        "technician:12: IMG_0416.jpg | technician:44: IMG_0540.jpg"
    )


def test_R30_raw_value_sits_next_to_each_cleaned_value(tmp_path, capsys):
    run_main(capsys, REAL_TECHNICIAN, REAL_PARTNER, "--out", tmp_path)
    with open(tmp_path / "full_detail.csv", newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    for field in rc.FIELDS:
        assert header[header.index(field) + 1] == f"raw_{field}"
    row = {r["source_row_ids"]: r for r in read_csv_rows(tmp_path / "full_detail.csv")}["technician:12; technician:44"]
    assert (row["location"], row["raw_location"]) == ("Rm 103", "technician:12: 103 | technician:44: 103")


def test_R30_extra_column_is_kept_in_full_detail(tmp_path, capsys):
    extra = tmp_path / "tech.csv"
    rows = list(csv.reader(open(UNSEEN_T, encoding="utf-8")))
    write_csv(extra, [row + (["Inspector Notes"] if i in (0, 5) else [f"note {i}"]) for i, row in enumerate(rows)])
    assert run_main(capsys, extra, UNSEEN_P, "--out", tmp_path / "out")[0] == 0
    detail = read_csv_rows(tmp_path / "out" / "full_detail.csv")
    assert "note 1" in [row["technician_Inspector Notes"] for row in detail]


def test_R30_repeated_heading_is_kept_not_overwritten():
    assert rc.unique_headings(["Notes", "", "Notes", "Tag"]) == [("Notes", 0), ("Notes (2)", 2), ("Tag", 3)]


def test_R30_detail_file_out_of_line_stops_and_keeps_previous_outputs(monkeypatch, tmp_path, capsys):
    before = seed_outputs(capsys, tmp_path)
    real_write_full_detail = rc.write_full_detail

    def drops_last_row(result, folder, target_columns):
        real_write_full_detail(result, folder, target_columns)
        path = folder / "full_detail.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    monkeypatch.setattr(rc, "write_full_detail", drops_last_row)
    code, text = run_main(capsys, UNSEEN_T, UNSEEN_P, "--out", tmp_path)
    assert code == 1
    assert "The detail file didn't line up row for row with the import file" in text
    assert "were not changed" in text
    assert_plain(text)
    assert_outputs_unchanged(tmp_path, before)


# --- R22: coverage by building -------------------------------------------------


def test_R22_coverage_table_counts_sources_per_building():
    result = rc.reconcile(REAL_TECHNICIAN, REAL_PARTNER, current_year=YEAR)
    text = rc.summary_text(result, REAL_TECHNICIAN, REAL_PARTNER)
    assert "| Lakeview Elementary School | 45 | 0 | 0 | 45 |" in text
    assert "| Lakeview Middle School | 46 | 0 | 0 | 46 |" in text
    assert "| Lakeview High School | 20 | 22 | 33 | 75 |" in text
    assert "| **All buildings** | 111 | 22 | 33 | 166 |" in text
