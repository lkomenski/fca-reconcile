# Reducing the review list

The FMX run flags 54 of 166 rows as needs_review. Some of those flags are the tool doing its job, and some are work that better data or better tooling could remove. I grouped every flagged row by its review reason into four buckets, based on what would remove the flag.

Counts are rows from the run on 2026-11-08 (112 ready, 54 needs_review). Each row falls into one bucket, so the bucket totals add up to 54.

## 1. Learnable: fixed by updating the lookups, or connecting them to FMX's source of truth (9 rows)

| Reason | Rows | Examples |
|---|---|---|
| Asset type not in FMX's accepted list (a real type, just not on the list) | 9 | Unit Heater ×5 (technician:90, 94; partner:45–47), Expansion Tank ×2 (partner:25, 26), Plate Heat Exchanger (partner:27), Kitchen hood (technician:46) |

**Future change:** connect the lookups to FMX's asset library instead of a hand-kept file. FMX decides once whether Unit Heater and Expansion Tank are asset types, and after that these rows would be ready every time.

This bucket already shrank once: four "Mitsubishi" rows (technician:34, 88, 93, 148) were here until the tool learned to complete the name when the same model appears elsewhere in the file under "Mitsubishi Electric" (R6). A connected model catalogue would do the same for models that appear only once.

## 2. Fix at capture: avoidable with required fields, validated inputs, or AI reading nameplate photos with a person confirming (29 rows)

| Reason | Rows | Examples |
|---|---|---|
| Nameplate data missing | 9 | technician:78 (photo IMG_0527.jpg), technician:40 (no photo, room locked) |
| Install year unreadable or in the future | 7 | "unknown" ×4, "19987", "2000s", 2031 |
| Condition missing, not a number, or out of range | 5 | blank ×3, "Good" (technician:76), 11 (technician:144) |
| Vague asset type | 4 | "fan", "heater", "HVAC unit", "unit" |
| Serial number missing | 3 | "N/A" ×2 (technician:29, 91), "see schedule" (partner:54) |
| Serial may be damaged by Excel | 1 | 4430000000 (technician:85) |

partner:54 also has "One row describes 4 units".

**Future change:**
- **Capture form:** required fields, a pick-list of FMX asset types instead of free text, a 1–10 condition picker, and a year field that only accepts four digits up to the current year.
- **Serials:** stored as text, so Excel can't damage them.
- **Nameplate photos:** AI reads the photo while the technician is still on site, and the technician confirms the result. 8 of the 9 nameplate rows already have a photo.
- **Partner template:** one row per unit, with FMX's approved list.

## 3. Better matching in the tool (7 rows, plus 3 already counted in bucket 2)

| Reason | Rows | Examples |
|---|---|---|
| Possibly the same unit (tag hint, R32), on the copy that has nameplate data | 4 | partner:40 RTU-4, partner:11 B-3, partner:6 AHU-2, technician:141 LP-2A |
| Repeat entry not matched | 1 | technician:143 "Panel LP-2A, 2nd pass", the same panel as technician:141 |
| Looks identical to another row | 2 | technician:33 / 45, panels LP-1B and LP-1A, told apart only by notes |
| (Nameplate missing, but the partner has the unit) | (3) | technician:95 RTU-4, 109 B-3, 119 AHU-2 |

**Future change:** automatic tag merging. The tool already links these twins with a hint (R32), which closes the double-import risk but adds 4 flags. Once the hint has been confirmed right on a few real assessments, it could merge them instead: the three nameplate rows into their partner copies, and the repeat panel into its first entry. The two identical panels, LP-1A and LP-1B, would need the panel name carried into the import, which FMX's format has no column for today.

## 4. Real judgment calls that should stay flagged (9 rows)

| Reason | Rows | Examples |
|---|---|---|
| Condition differs between sources by 2 or more | 5 | technician:100 + partner:42, RTU-6: technician 4/10 vs partner Good |
| Install year differs between sources by more than 2 | 2 | technician:105 + partner:43: 2019 vs 2004 |
| Note may affect the row | 4 | technician:9 "replaced 2016 per custodian", technician:53 "abandoned in place" (technician:100 and 108 also have a condition gap) |

**Future change:** none to the flagging. Better source trust rules (OPEN_QUESTIONS #1) could decide some year conflicts automatically, but a cracked heat exchanger or an abandoned boiler needs a person.

## Estimate

If buckets 1–3 were addressed, about **10 of the 54** flags would remain:
- the 9 judgment-call rows;
- technician:40, which no capture rule fixes, because the room was locked and nothing was captured.

That's a rough estimate. It assumes the capture form and photo reading work as intended, and that FMX's asset library covers the off-list types. Bucket 4 is the work a specialist should be doing: deciding between two people's observations, not retyping a year or fixing a spelling.
