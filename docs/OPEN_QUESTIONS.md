# Open questions

These are things I decided without enough information, or would build differently with more time. Each one points to the rule it affects in [RULES.md](RULES.md).

Last updated 2026-11-08.

## 1. Whose data wins when the sources disagree (R17, R18, R19)

I decided whose data wins when the technician and partner disagree without knowing how FMX's field team and partner firms work, or which source data specialists already trust. Right now the technician's install year wins, the partner's model and serial win, and condition takes the worse of the two. Each choice has a reason, but none is based on how much FMX trusts each source in practice. That's one of the first things I'd check with Professional Services and the technicians.

## 2. How precise install years need to be (R9, R18)

I don't know how exact capital planning needs install years to be. I accept approximate years ("~2004", "2004?") as ready, I use the partner's year of manufacture as the install year when it's the only year available, and I don't flag a merged row unless the two years are more than 2 apart. If capital planning needs exact years, approximate years and partner years may need revisiting, either flagged or marked so they can be filtered. The run summary already counts both, so the size of the change is known: 8 approximate years and 23 partner years in this run.

## 3. Keeping the mappings up to date (R4, R5, R6, R12, R15)

Every spelling the tool fixes comes from a hand-maintained list in `mappings.py`. That works for one district, but it won't scale. I'd connect the mappings to a source like FMX's asset library, or learn from the fixes data specialists make in the review list (if "Kitchen hood" is corrected the same way three times, suggest adding it), so nobody maintains them by hand.

## 4. Partner asset types (R5)

Partners describe equipment in their own words ("Inline Circulator", "Plate Heat Exchanger"), and some of it doesn't fit FMX's accepted list at all. I'd fix this at the source by giving partners FMX's approved list as a template, so their file arrives already using accepted asset types instead of being mapped afterward.

## 5. Location cleanup beyond room numbers (R8)

The tool standardizes room numbers only (`103`, `Room 103`, `rm103` → `Rm 103`). Everything else is kept as captured, so the same place can still appear several ways: `cafeteria roof`, `Roof - Cafeteria`, `Roof (Cafeteria)`. FMX's own example row shows a cleaned-up location, so a consistent format would likely help. But rewriting free text means guessing, and I'd want an agreed location format first.

## 6. Where the lookups should come from (R5, R6)

Manufacturers and asset types should come from whatever FMX already uses as its source of truth, like its asset library. I didn't know what that was, so the lookups are kept in one file (`mappings.py`) that's easy to swap for a connection later, and each run reports what it didn't recognize. The accepted asset types are already read from FMX's `Asset_Types.xlsx` each run instead of being copied into the code. Only the extra spellings live in `mappings.py`.

## 7. Which equipment commonly has no serial (R12)

I'm not sure which equipment commonly has no serial. The list starts with Electrical Panel only, and anything not on it is flagged, which is the cautious direction: the worst case is a few extra review rows, not missing serials going out as ready. Technicians or Professional Services can tell me which types to add.
