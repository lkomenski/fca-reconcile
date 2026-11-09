"""Lookup tables used by reconcile.py.

This file holds data only, no logic, so it can be edited without touching the
tool. To teach the tool a new spelling, add it to the list under the correct
value and save. Matching ignores upper/lower case and extra spaces, so
"Rooftop unit", "ROOFTOP UNIT" and "rooftop  unit" are all the same entry.

Never add a value that is a guess. If a spelling could mean two different
things (for example "fan" or "heater"), leave it out and the tool will flag it
for a person.
"""

# R4: Building names. The three keys must match the building names in
# Target_Format.xlsx exactly.
BUILDINGS = {
    "Lakeview Elementary School": [
        "Lakeview Elementary",
        "Lakeview Elem",
        "Lakeview ES",
        "LV Elementary",
        "LVES",
    ],
    "Lakeview Middle School": [
        "Lakeview Middle",
        "Lakeview MS",
        "LV Middle",
        "LVMS",
    ],
    "Lakeview High School": [
        "Lakeview High",
        "Lakeview HS",
        "LV High",
        "LVHS",
    ],
}

# R5: Asset types. Every key must appear in Asset_Types.xlsx; the tool checks
# this when it starts. Partner descriptions are looked up here too, after the
# tag and any "(qty N)" are removed (e.g. "Hot Water Boiler").
# Deliberately NOT listed (see RULES.md R5): fan, heater, HVAC unit, unit,
# Kitchen hood, Unit Heater, Expansion Tank, Plate Heat Exchanger.
ASSET_TYPES = {
    "Rooftop Unit": [
        "RTU",
        "Roof Top Unit",
        "Roof Top AC",
        "Rooftop AC",
        "RTU (gas/elec)",
    ],
    "Air Handling Unit": ["AHU", "Air Handler"],
    "Boiler": ["Blr", "HW Boiler", "Boiler - Hot Water", "Hot Water Boiler"],
    "Chiller": ["Air-Cooled Chiller"],
    "Pump": ["CHW Pump", "HW Pump", "Circ Pump", "Inline Circulator", "Base-Mounted Pump"],
    "Exhaust Fan": ["EF", "Exh Fan", "Roof Exhaust"],
    "Unit Ventilator": ["UV", "Unit Vent", "Classroom UV", "Unit Ventilators"],
    "Make-Up Air Unit": ["MAU"],
    "Split System": ["DX Split", "Mini Split", "Ductless Split"],
    "Water Heater": ["WH", "HWH", "Gas Water Heater"],
    "Backflow Preventer": ["Backflow", "BFP", "RPZ Backflow Preventer"],
    "Electrical Panel": ["Panel", "Panelboard", "Elec Panel"],
    "Switchgear": [],
    "Transformer": ["XFMR"],
    "Emergency Generator": ["Genset", "Emergency Gen"],
    "Fire Alarm Control Panel": ["Fire Alarm Panel", "FACP"],
    "Elevator": ["Hydraulic Elevator"],
}

# R6: Manufacturers. Only spelling variants of the SAME name go together.
# Different brands stay separate even if one company owns the other
# (Cutler-Hammer and Eaton are separate entries). Plain "Mitsubishi" is
# deliberately not listed: it could be Mitsubishi Electric or Mitsubishi
# Heavy Industries.
MANUFACTURERS = {
    "Trane": ["Trane Inc."],
    "Carrier": [],
    "Lennox": [],
    "York": [],
    "Daikin": ["Daikin Applied"],
    "Weil-McLain": ["WeilMcLain", "Weil McLain"],
    "Lochinvar": [],
    "Bell & Gossett": ["Bell and Gossett", "B&G"],
    "Taco": [],
    "Greenheck": ["Green Heck"],
    "CaptiveAire": ["Captive-Aire", "Captive Aire"],
    "Mitsubishi Electric": [],
    "A.O. Smith": ["AO Smith", "A O Smith", "A. O. Smith"],
    "Watts": [],
    "Zurn Wilkins": [],
    "Square D": ["Square-D", "SquareD"],
    "Cutler-Hammer": [],
    "Eaton": [],
    "Generac": [],
    "Notifier": [],
    "Otis": [],
}

# R11: Partner condition words to the 1-5 scale (1 = failed, 5 = new).
# Nothing maps to 5: the partner's "Good" means "operating as intended".
PARTNER_CONDITION = {
    "Good": 4,
    "Fair": 3,
    "Poor": 2,
    "Critical": 1,
}

# R16: Serial values that mean "no serial". Rows with these are never matched
# as duplicates.
SERIAL_PLACEHOLDERS = [
    "N/A",
    "NA",
    "None",
    "Unknown",
    "See schedule",
    "See photo",
    "TBD",
    "-",
]

# R15: Words in a technician note or partner comment that mean a person
# should look at the row. Matching is "the note contains this text".
NOTE_KEYWORDS = [
    "replaced",
    "abandoned",
    "locked out",
]

# R15: Words that mean the row is a repeat entry. Only flagged when the tool
# could NOT merge the row with a matching serial (if it merged, the repeat is
# already handled).
REPEAT_NOTE_KEYWORDS = [
    "2nd pass",
    "second pass",
    "logged again",
]

# R1: Technician column headers -> internal field names.
TECHNICIAN_COLUMNS = {
    "Bldg": "building",
    "Equip Type": "asset_type",
    "Mfr": "manufacturer",
    "Model #": "model",
    "Serial #": "serial_number",
    "Yr Installed": "install_year",
    "Cond (1-10)": "condition",
    "Location": "location",
    "Notes": "notes",
    "Photo": "photo",
}

# R2: Partner column headers -> internal field names.
PARTNER_COLUMNS = {
    "Facility": "building",
    "Equipment Description": "description",
    "Manufacturer": "manufacturer",
    "Model Number": "model",
    "Serial Number": "serial_number",
    "Year of Manufacture": "install_year",
    "Condition Rating": "condition",
    "Room/Area": "location",
    "Tag": "tag",
    "Comments": "notes",
}
