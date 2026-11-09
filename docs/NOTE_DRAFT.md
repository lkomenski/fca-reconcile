# Note draft (max 300 words)

**What works.** One command reconciles the technician and partner files into FMX's import format: 201 rows in, 115 ready, 51 flagged with plain-language reasons, 35 merged into duplicates. Every input row is accounted for, and the run stops if one isn't. Spellings, buildings, years, and both condition scales are fixed only from an editable lookup file; anything else is flagged, never guessed. Each run lists every value it didn't recognize, so the lookups can be updated in one pass. Bad files stop with a clear message; a bad row is flagged and the run continues. 176 tests, including two made-up unseen files.

**What doesn't.** Three high school units with unreadable nameplates aren't matched to their partner rows, because matching on anything but serial number risked merging different units. Locations beyond room numbers are kept as captured.

**What I cut and why.** Tag matching, fuzzy suggestions, and flexible column names. I chose a small tool that works over a bigger one that might not. The rules I'm least sure of, like whose data wins when the sources disagree, are in OPEN_QUESTIONS.md for Professional Services.

**Where AI got it wrong.** The AI's inspection report said leaving "Mitsubishi" unmapped affected 2 rows. The tool's run summary said 4. Checking the raw data showed the tool was right: the report had missed "MITSUBISHI" in capitals. That's why I trust counts the code produces over summaries anyone writes, including the AI.

**What I'd build next.**
1. A column-map file: when a new source uses headings the tool doesn't recognize, it writes a map that a person fills in once (including the condition scale), and every later file from that source just works.
2. Tag matching for units with missing nameplates.
3. Lookups connected to FMX's asset library instead of a hand-kept file.
