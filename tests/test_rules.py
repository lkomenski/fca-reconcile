"""One small test per rule in docs/RULES.md. Each test name starts with its
rule ID so the results can be read rule by rule."""

import csv
from pathlib import Path

import pytest

import mappings
import reconcile as rc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = HERE / "fixtures"
REAL_TECHNICIAN = ROOT / "data" / "Technician_Capture.csv.xlsx"
REAL_PARTNER = ROOT / "data" / "Partner_Equipment_List.xlsx"
YEAR = 2026  # fixed so the tests give the same answer in any year


def tech_record(row_number=2, **fields):
    """A made-up technician row. Any field can be overridden."""
    raw = {field: None for field in mappings.TECHNICIAN_COLUMNS.values()}
    raw.update(
        building="Lakeview High School",
        asset_type="Pump",
        manufacturer="Taco",
        model="1600",
        serial_number="S1",
        install_year=2010,
        condition=6,
        location="Boiler Rm",
    )
    raw.update(fields)
    return {"row_id": f"technician:{row_number}", "source": "technician", "raw": raw}


def partner_record(row_number=5, **fields):
    """A made-up partner row. Any field can be overridden."""
    raw = {field: None for field in mappings.PARTNER_COLUMNS.values()}
    raw.update(
        building="Lakeview HS",
        description="Base-Mounted Pump P-1",
        tag="P-1",
        manufacturer="Taco",
        model="1600",
        serial_number="S1",
        install_year=2010,
        condition="Fair",
        location="Boiler Room 108",
    )
    raw.update(fields)
    return {"row_id": f"partner:{row_number}", "source": "partner", "raw": raw}


def clean(record):
    return rc.clean_record(record, YEAR)


def reasons(output_row):
    return output_row["review_reason"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


TECH_HEADER = list(mappings.TECHNICIAN_COLUMNS) + ["Captured", "Tech"]


# --- R1 / R2 / R3: loading -------------------------------------------------


def test_R1_skips_blank_rows_and_repeated_header(tmp_path):
    path = tmp_path / "tech.csv"
    row = ["LVHS", "RTU", "Trane", "M", "S1", "2004", "6", "Roof", "", "", "", ""]
    write_csv(path, [TECH_HEADER, row, [""] * 12, TECH_HEADER, row])
    records = rc.load_technician(path)
    assert [r["row_id"] for r in records] == ["technician:2", "technician:5"]


def test_R1_keeps_mostly_blank_rows(tmp_path):
    path = tmp_path / "tech.csv"
    mostly_blank = ["Lakeview Elem", "", "", "", "", "", "", "Rm 118", "locked, come back", "", "", ""]
    write_csv(path, [TECH_HEADER, mostly_blank])
    assert len(rc.load_technician(path)) == 1


def test_R1_reads_xlsx_with_csv_in_its_name():
    records = rc.load_technician(REAL_TECHNICIAN)
    assert records[0]["row_id"] == "technician:2"
    assert "technician:96" not in [r["row_id"] for r in records]  # the repeated header


def test_R1_missing_column_stops_with_clear_error(tmp_path):
    path = tmp_path / "tech.csv"
    write_csv(path, [TECH_HEADER[:-3]])  # drops Photo, Captured, Tech
    with pytest.raises(ValueError, match="Photo"):
        rc.load_technician(path)


def test_R2_finds_header_below_title_and_skips_footer():
    records = rc.load_partner(FIXTURES / "unseen_partner.csv")
    assert [r["row_id"] for r in records] == ["partner:4", "partner:5", "partner:6"]


def test_R2_real_partner_file_rows_5_to_59():
    records = rc.load_partner(REAL_PARTNER)
    assert records[0]["row_id"] == "partner:5"
    assert records[-1]["row_id"] == "partner:59"


def test_R3_rows_in_counts_every_data_row():
    assert len(rc.load_technician(REAL_TECHNICIAN)) == 146
    assert len(rc.load_partner(REAL_PARTNER)) == 55


# --- R4 - R8: field mapping -------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("LVHS ", "Lakeview High School"),
        ("lakeview middle", "Lakeview Middle School"),
        ("Lakeview Elem", "Lakeview Elementary School"),
        ("LAKEVIEW  ES", "Lakeview Elementary School"),
    ],
)
def test_R4_known_building_names_are_mapped(raw, expected):
    assert rc.normalize_building(raw) == (expected, None)


@pytest.mark.parametrize(
    "raw, reason",
    [
        ("Lakeview Annex", "Building 'Lakeview Annex' is not a recognized building name"),
        (None, "Building is missing"),
    ],
)
def test_R4_unknown_or_blank_building_is_flagged(raw, reason):
    assert rc.normalize_building(raw)[1].reason == reason


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("RTU", "Rooftop Unit"),
        ("roof top AC", "Rooftop Unit"),
        ("Rooftop unit", "Rooftop Unit"),
        ("RTU (gas/elec)", "Rooftop Unit"),
        ("HWH", "Water Heater"),
        ("AHU ", "Air Handling Unit"),
    ],
)
def test_R5_known_asset_types_are_mapped(raw, expected):
    assert rc.normalize_asset_type(raw) == (expected, None)


@pytest.mark.parametrize("raw", ["fan", "heater", "Unit Heater", "Kitchen hood"])
def test_R5_vague_or_unlisted_asset_type_is_flagged_with_its_value(raw):
    value, problem = rc.normalize_asset_type(raw)
    assert value == raw
    assert problem.reason == f"Asset type '{raw}' is not in the accepted list; choose the correct type"


@pytest.mark.parametrize(
    "description, tag, expected",
    [
        ("Hot Water Boiler B-1, 1,500 MBH", "B-1", "Hot Water Boiler"),
        ("Exhaust Fan EF-10", "EF-10", "Exhaust Fan"),
        ("Unit Ventilators (qty 4)", "UV-214 to UV-217", "Unit Ventilators"),
    ],
)
def test_R5_partner_type_taken_from_description(description, tag, expected):
    assert rc.partner_asset_type_text(description, tag) == expected


def test_R5_every_mapped_asset_type_is_in_accepted_list():
    accepted = rc.read_accepted_asset_types(ROOT / "data" / "Asset_Types.xlsx")
    assert set(mappings.ASSET_TYPES) <= accepted


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("TRANE", "Trane"),
        ("Trane Inc.", "Trane"),
        ("Green Heck", "Greenheck"),
        ("B&G", "Bell & Gossett"),
        ("SquareD", "Square D"),
        ("Cutler-Hammer", "Cutler-Hammer"),
        ("EATON", "Eaton"),
    ],
)
def test_R6_spelling_variants_are_combined_but_brands_are_not(raw, expected):
    assert rc.normalize_manufacturer(raw, "M", "S") == (expected, None)


def test_R6_unknown_manufacturer_is_flagged_with_its_value():
    problem = rc.normalize_manufacturer("Mitsubishi", "M", "S")[1]
    assert problem.reason == "Manufacturer 'Mitsubishi' is not a recognized spelling; confirm the manufacturer"


def test_R6_blank_manufacturer_flagged_only_when_model_or_serial_present():
    assert rc.normalize_manufacturer(None, "PRL1A", "")[1].reason == "Manufacturer is missing"
    assert rc.normalize_manufacturer(None, "", "") == ("", None)


@pytest.mark.parametrize(
    "raw, expected",
    [(684796, "684796"), (11, "11"), (2004.0, "2004"), (" LGB-12 ", "LGB-12"), ("67W-465 53NA", "67W-465 53NA")],
)
def test_R7_model_and_serial_as_captured_trimmed(raw, expected):
    assert rc.to_text(raw) == expected


def test_R8_location_kept_as_captured():
    row = clean(tech_record(location="cafeteria roof"))
    assert row["values"]["location"] == "cafeteria roof"
    assert clean(tech_record(location=103))["values"]["location"] == "103"


# --- R9: install year ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw, year, approximate",
    [
        (1998, 1998, False),
        ("'04", 2004, False),
        (98, 1998, False),
        (21, 2021, False),
        (26, 2026, False),
        (27, 1927, False),
        ("Mfg 04/2011", 2011, False),
        ("approx. 2004", 2004, True),
        ("~2004", 2004, True),
        ("2016?", 2016, True),
        ("c. 2012", 2012, True),
        (None, None, False),
    ],
)
def test_R9_years_with_one_clear_reading(raw, year, approximate):
    assert rc.parse_install_year(raw, YEAR) == (year, None, approximate)


@pytest.mark.parametrize(
    "raw, reason",
    [
        (2031, "Install year 2031 is in the future"),
        (19987, "Install year '19987' could not be read as a year"),
        ("2000s", "Install year '2000s' could not be read as a year"),
        ("unknown", "Install year 'unknown' could not be read as a year"),
    ],
)
def test_R9_unclear_years_are_flagged_and_left_blank(raw, reason):
    year, problem, _ = rc.parse_install_year(raw, YEAR)
    assert year is None
    assert problem.reason == reason


def test_R9_two_digit_cutoff_follows_the_current_year():
    assert rc.parse_install_year(28, 2026)[0] == 1928
    assert rc.parse_install_year(28, 2030)[0] == 2028


# --- R10 / R11: condition ------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4), (8, 4), (9, 5), (10, 5), (3.5, 2), (5.5, 3), ("7", 4)],
)
def test_R10_half_the_score_rounded_up(raw, expected):
    assert rc.convert_condition_10pt(raw) == (expected, None)


@pytest.mark.parametrize(
    "raw, reason",
    [
        (None, "Condition is missing"),
        (11, "Condition 11 is outside the technician's 1-10 scale"),
        (0, "Condition 0 is outside the technician's 1-10 scale"),
        ("Good", "Condition 'Good' is not a number on the technician's 1-10 scale"),
    ],
)
def test_R10_blank_out_of_range_or_text_is_flagged(raw, reason):
    assert rc.convert_condition_10pt(raw)[1].reason == reason


@pytest.mark.parametrize("raw, expected", [("Good", 4), ("fair", 3), ("POOR", 2), ("Critical", 1)])
def test_R11_partner_words_map_to_scale(raw, expected):
    assert rc.convert_condition_text(raw) == (expected, None)


@pytest.mark.parametrize(
    "raw, reason",
    [
        ("Excellent", "Condition 'Excellent' is not one of Good, Fair, Poor, Critical"),
        (None, "Condition is missing"),
    ],
)
def test_R11_other_words_are_flagged(raw, reason):
    assert rc.convert_condition_text(raw)[1].reason == reason


# --- R12 - R15: problems that need a person -----------------------------------


def test_R12_blank_nameplate_with_photo():
    problem = rc.check_nameplate("", "", "", "IMG_0527.jpg")
    assert problem.reason == "Nameplate data missing; technician photo IMG_0527.jpg on file"


def test_R12_blank_nameplate_without_photo():
    assert rc.check_nameplate("", "", "", None).reason == "Nameplate data missing; no photo on file"


@pytest.mark.parametrize(
    "asset_type, serial, flagged",
    [
        ("Panel", None, False),  # Electrical Panel is on the allowed-no-serial list
        ("Panel", "N/A", False),
        ("DX split", "N/A", True),
        ("Fire Alarm Control Panel", None, True),
        ("fan", None, True),  # unknown type: not on the list, so flagged
        ("DX split", "3039513", False),
    ],
)
def test_R12_blank_serial_flagged_unless_type_allowed(asset_type, serial, flagged):
    row = rc.flag_row(rc.single_row(clean(tech_record(asset_type=asset_type, serial_number=serial))))
    assert ("Serial number missing" in row["review_reason"]) == flagged


def test_R12_fully_blank_nameplate_not_also_flagged_serial_missing():
    row = rc.flag_row(rc.single_row(clean(tech_record(manufacturer=None, model=None, serial_number=None, photo="IMG_1.jpg"))))
    assert row["review_reason"] == "Nameplate data missing; technician photo IMG_1.jpg on file"


@pytest.mark.parametrize("serial, flagged", [("4430000000", True), ("4586578415", False), ("FBOU0000", False)])
def test_R13_all_digit_serial_ending_in_zeros_is_flagged(serial, flagged):
    assert (rc.check_serial_rounded(serial) is not None) == flagged


def test_R14_row_with_several_units_is_flagged():
    problem = rc.check_multi_unit("Unit Ventilators (qty 4)", "UV-214 to UV-217")
    assert problem.reason == "One row describes 4 units (tag UV-214 to UV-217); each unit needs its own row and serial"
    assert rc.check_multi_unit("Exhaust Fan EF-1", "EF-1") is None


@pytest.mark.parametrize(
    "notes, flagged",
    [("replaced 2016 per custodian", True), ("abandoned in place", True), ("filters dirty", False), (None, False)],
)
def test_R15_note_keywords_are_flagged_and_quoted(notes, flagged):
    problem = rc.check_notes(notes, "technician")
    assert (problem is not None) == flagged
    if flagged:
        assert problem.reason == f"Technician note may affect this row: '{notes}'"


def test_R15_repeat_note_only_flagged_when_not_merged():
    first = clean(tech_record(2, serial_number="A1"))
    repeat = clean(tech_record(3, serial_number="A-1", notes="logged again on 2nd pass"))
    lonely = clean(tech_record(4, serial_number=None, notes="Panel LP-2A, 2nd pass"))
    merged = rc.flag_row(rc.merge_duplicate([first, repeat]))
    single = rc.flag_row(rc.single_row(lonely))
    assert merged["status"] == "ready"
    assert "repeat entry" in single["review_reason"]


# --- R16 - R19: duplicates -----------------------------------------------------


@pytest.mark.parametrize(
    "a, b, same",
    [("67W-465 53NA", "67W46553NA", True), ("fbou810423", "FBOU810423", True), ("A1", "A2", False)],
)
def test_R16_serials_compared_without_spaces_dashes_or_case(a, b, same):
    assert (rc.serial_key(a) == rc.serial_key(b)) == same


@pytest.mark.parametrize("serial", [None, "", "N/A", "see schedule"])
def test_R16_blank_and_placeholder_serials_never_match(serial):
    assert rc.serial_key(serial) is None


def test_R16_same_serial_in_different_buildings_is_not_merged():
    a = clean(tech_record(2, building="LVHS", serial_number="X1"))
    b = clean(tech_record(3, building="LVMS", serial_number="X1"))
    assert len(rc.find_duplicates([a, b])) == 2


def test_R16_source_is_both_or_technician():
    tech = clean(tech_record(2))
    partner = clean(partner_record(5))
    repeat = clean(tech_record(3))
    assert rc.merge_duplicate([tech, partner])["source"] == "both"
    assert rc.merge_duplicate([tech, repeat])["source"] == "technician"


def test_R17_partner_model_and_serial_technician_location():
    tech = clean(tech_record(2, model="ycd150f3", serial_number="67W-465 53NA", location="cafeteria roof"))
    partner = clean(partner_record(5, model="YCD150F3", serial_number="67W46553NA", location="Roof, Cafeteria"))
    values = rc.merge_duplicate([tech, partner])["values"]
    assert values["model"] == "YCD150F3"
    assert values["serial_number"] == "67W46553NA"
    assert values["location"] == "cafeteria roof"


def test_R17_problem_dropped_when_other_source_supplies_clean_value():
    tech = clean(tech_record(2, asset_type="Pump"))
    partner = clean(partner_record(5, description="Inline Pump P-1"))  # "Inline Pump" is not mapped
    merged = rc.flag_row(rc.merge_duplicate([tech, partner]))
    assert merged["values"]["asset_type"] == "Pump"
    assert merged["status"] == "ready"


def test_R18_year_gap_over_two_is_flagged_technician_year_kept():
    tech = clean(tech_record(105, install_year=2019))
    partner = clean(partner_record(43, install_year=2004))
    merged = rc.flag_row(rc.merge_duplicate([tech, partner]))
    assert merged["values"]["install_year"] == 2019
    assert merged["review_reason"] == (
        "Install year differs between sources: technician:105 2019, partner:43 2004 (year of manufacture)"
    )


def test_R18_one_year_gap_is_not_flagged():
    merged = rc.flag_row(rc.merge_duplicate([clean(tech_record(install_year=2012)), clean(partner_record(install_year=2011))]))
    assert merged["status"] == "ready"
    assert merged["values"]["install_year"] == 2012


def test_R18_blank_technician_year_uses_partner_year():
    merged = rc.merge_duplicate([clean(tech_record(install_year=None)), clean(partner_record(install_year=2011))])
    assert merged["values"]["install_year"] == 2011
    assert merged["year_from_partner"]


def test_R19_gap_of_two_uses_lower_rating_and_flags():
    tech = clean(tech_record(100, condition=4))
    partner = clean(partner_record(42, condition="Good"))
    merged = rc.flag_row(rc.merge_duplicate([tech, partner]))
    assert merged["values"]["condition"] == 2
    assert merged["review_reason"] == (
        "Condition differs between sources: technician:100 4/10 (2 of 5), partner:42 Good (4 of 5); used the lower rating"
    )


def test_R19_gap_of_one_uses_lower_rating_and_stays_ready():
    merged = rc.flag_row(rc.merge_duplicate([clean(tech_record(condition=6)), clean(partner_record(condition="Poor"))]))
    assert merged["values"]["condition"] == 2
    assert merged["status"] == "ready"


def test_R19_blank_technician_condition_uses_partner_rating():
    merged = rc.flag_row(rc.merge_duplicate([clean(tech_record(condition=None)), clean(partner_record(condition="Poor"))]))
    assert merged["values"]["condition"] == 2
    assert merged["status"] == "ready"


# --- R20 - R22: status, accounting, outputs ----------------------------------


def test_R20_every_reason_listed_separated_by_semicolons():
    row = rc.flag_row(rc.single_row(clean(tech_record(asset_type=None, condition=None, manufacturer=None, model=None, serial_number=None))))
    assert row["status"] == "needs_review"
    assert row["review_reason"] == "Asset type is missing; Condition is missing; Nameplate data missing; no photo on file"


def test_R20_clean_row_is_ready_with_blank_reason():
    row = rc.flag_row(rc.single_row(clean(tech_record())))
    assert (row["status"], row["review_reason"]) == ("ready", "")


def test_R21_real_files_rows_in_equal_ready_plus_review_plus_merged():
    counts = rc.reconcile(REAL_TECHNICIAN, REAL_PARTNER, current_year=YEAR)["counts"]
    assert counts["technician_in"] + counts["partner_in"] == 201
    assert counts["ready"] + counts["needs_review"] + counts["merged_away"] == 201
    assert counts["merged_away"] == 35


def test_R21_lost_row_stops_the_run():
    rows = rc.reconcile(REAL_TECHNICIAN, REAL_PARTNER, current_year=YEAR)["rows"]
    input_ids = [row_id for row in rows for row_id in row["row_ids"]]
    with pytest.raises(rc.RowAccountingError):
        rc.check_row_accounting(input_ids, rows[:-1])


def test_R22_import_columns_match_target_and_ready_values_are_valid(tmp_path):
    exit_code = rc.main([str(REAL_TECHNICIAN), str(REAL_PARTNER), "--out", str(tmp_path)])
    assert exit_code == 0
    with open(tmp_path / "import_ready.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0].keys()) == rc.read_target_columns(ROOT / "data" / "Target_Format.xlsx")
    accepted = rc.read_accepted_asset_types(ROOT / "data" / "Asset_Types.xlsx")
    for row in rows:
        if row["status"] == "ready":
            assert row["asset_type"] in accepted
            assert row["building"] in mappings.BUILDINGS
            assert row["install_year"] == "" or len(row["install_year"]) == 4
            assert row["condition"] in {"1", "2", "3", "4", "5"}


def test_R22_three_outputs_written(tmp_path):
    rc.main([str(REAL_TECHNICIAN), str(REAL_PARTNER), "--out", str(tmp_path)])
    review = list(csv.DictReader(open(tmp_path / "review_list.csv", encoding="utf-8")))
    assert all(row["review_reason"] for row in review)
    assert "Row check (R21)" in (tmp_path / "run_summary.md").read_text(encoding="utf-8")


# --- The unseen file: proves no rule depends on the real rows ----------------


def test_UNSEEN_made_up_files_reconcile_with_expected_counts():
    result = rc.reconcile(FIXTURES / "unseen_technician.csv", FIXTURES / "unseen_partner.csv", current_year=YEAR)
    counts = result["counts"]
    assert (counts["technician_in"], counts["partner_in"]) == (8, 3)
    assert (counts["ready"], counts["needs_review"], counts["merged_away"]) == (3, 5, 3)

    by_ids = {"; ".join(row["row_ids"]): row for row in result["rows"]}
    boiler = by_ids["technician:2; partner:4"]
    assert (boiler["source"], boiler["status"]) == ("both", "ready")
    assert boiler["values"]["model"] == "CGA-5"  # R17: partner model
    assert by_ids["technician:3; technician:10"]["status"] == "ready"  # R15: merged repeat not flagged
    assert "Install year differs" in by_ids["technician:8; partner:5"]["review_reason"]
    assert "Building 'Lakeview Annex'" in by_ids["technician:11"]["review_reason"]
    assert "Install year 2030 is in the future" in by_ids["technician:11"]["review_reason"]
    assert by_ids["technician:7"]["approximate_year"]
