# Run summary

Run at 2026-11-08 16:46.
Technician file: `Technician_Capture.csv.xlsx`. Partner file: `Partner_Equipment_List.xlsx`.

| Count | Rows |
|---|---|
| Technician rows in | 146 |
| Partner rows in | 55 |
| **Total rows in** | **201** |
| Rows ready | 115 |
| Rows flagged (needs_review) | 51 |
| Rows merged into a duplicate | 35 (in 35 merged rows) |
| Rows in import_ready.csv | 166 |

Row check (R21): 201 in = 115 ready + 51 needs_review + 35 merged. Passed.

## Accepted, but worth knowing

- Approximate years accepted (e.g. `~2004`, `2004?`): 8
- Partner year of manufacture used as install year: 23

## Review reasons

Number of flagged rows with each reason. A row with several problems is counted under each one.

| Reason | Rows |
|---|---|
| Asset type not in accepted list | 13 |
| Nameplate data missing | 9 |
| Install year unreadable | 6 |
| Condition differs between sources | 5 |
| Condition missing | 4 |
| Note may affect row | 4 |
| Manufacturer not recognized | 4 |
| Serial number missing | 3 |
| Install year differs between sources | 2 |
| Install year in the future | 1 |
| Asset type missing | 1 |
| Condition not a number | 1 |
| Serial may be rounded by Excel | 1 |
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
| Manufacturer | MITSUBISHI | technician | 2 |
| Manufacturer | Mitsubishi | technician | 2 |
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
