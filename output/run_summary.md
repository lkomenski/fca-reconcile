# Run summary

Run on 2026-11-08 at 17:49.

- Technician file: `Technician_Capture.csv.xlsx`
- Partner file: `Partner_Equipment_List.xlsx`
- Accepted asset types: `Asset_Types.xlsx`
- Target format: `Target_Format.xlsx`

| Count | Rows |
|---|---|
| Technician rows in | 146 |
| Partner rows in | 55 |
| **Total rows in** | **201** |
| Rows ready | 112 |
| Rows flagged (needs_review) | 54 |
| Rows merged into a duplicate | 35 (in 35 merged rows) |
| Rows in import_ready.csv | 166 |

Row check (R21): 201 in = 112 ready + 54 needs_review + 35 merged. Passed.

## Coverage by building

Rows in import_ready.csv per building, by where they came from. Where only one source covered a building, there is nothing to compare against, so missing equipment can't be detected.

| Building | Technician only | Partner only | Both | Total |
|---|---|---|---|---|
| Lakeview Elementary School | 45 | 0 | 0 | 45 |
| Lakeview Middle School | 46 | 0 | 0 | 46 |
| Lakeview High School | 20 | 22 | 33 | 75 |
| **All buildings** | 111 | 22 | 33 | 166 |

## Work done automatically

Values the tool fixed without a person, counted per input row before duplicates were merged.

| Change | Rows |
|---|---|
| Manufacturer spellings standardized | 105 |
| ...of which completed from the same model elsewhere in the file (e.g. `Mitsubishi` to `Mitsubishi Electric`) | 4 |
| Asset types mapped to FMX's list | 167 |
| Building names standardized | 172 |
| Install years converted to four digits | 30 |
| Condition ratings converted to the 1-5 scale | 194 |
| Room numbers cleaned (e.g. `rm110` to `Rm 110`) | 17 |
| Duplicate rows merged | 35 (into 35 rows) |

## Accepted, but worth knowing

- Approximate years accepted (e.g. `~2004`, `2004?`): 8
- Partner year of manufacture used as install year: 23

## Review reasons

Number of flagged rows with each reason. A row with several problems is counted under each one.

| Reason | Rows |
|---|---|
| Asset type not in accepted list | 13 |
| Nameplate data missing | 9 |
| Possibly the same unit | 8 |
| Install year unreadable | 6 |
| Condition differs between sources | 5 |
| Condition missing | 4 |
| Note may affect row | 4 |
| Serial number missing | 3 |
| Identical to another row | 2 |
| Install year differs between sources | 2 |
| Install year in the future | 1 |
| Asset type missing | 1 |
| Condition not a number | 1 |
| Serial may be damaged by Excel | 1 |
| Repeat entry not matched | 1 |
| Condition out of range | 1 |
| One row describes several units | 1 |

## Values the tool didn't recognize

Each value below was kept as captured and flagged. Rows are input rows, counted before duplicates were merged. Add a value to `mappings.py` only if it has one clear meaning (README section 6).

| Field | Value as captured | File | Rows |
|---|---|---|---|
| Asset type | Unit Heater | partner | 3 |
| Asset type | Expansion Tank | partner | 2 |
| Asset type | fan | technician | 1 |
| Asset type | heater | technician | 1 |
| Asset type | HVAC unit | technician | 1 |
| Asset type | Kitchen hood | technician | 1 |
| Asset type | Plate Heat Exchanger | partner | 1 |
| Asset type | unit | technician | 1 |
| Asset type | unit heater | technician | 1 |
| Asset type | Unit Heater | technician | 1 |
| Condition | 11 | technician | 1 |
| Condition | Good | technician | 1 |
| Install year | unknown | technician | 4 |
| Install year | 19987 | technician | 1 |
| Install year | 2000s | technician | 1 |
| Install year | 2031 | technician | 1 |

### Building names matched by keyword

These were not in the building list but contained one building's keyword, so they were accepted. Add them to `BUILDINGS` in `mappings.py` to make the match exact.

| Value as captured | Matched to | Rows |
|---|---|---|
| (none) | | 0 |

## Warnings

- Sheet 'Legend' in the partner file was not read.
