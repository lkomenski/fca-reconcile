# Note draft (max 300 words)

**What works.** One command reconciles both files into FMX's import format: 201 rows in, 113 ready, 53 flagged with plain reasons, 35 merged as duplicates. Every input row is accounted for or the run stops. Values are fixed only from an editable lookup file; anything else is flagged, never guessed. full_detail.csv keeps everything the import format drops: notes, tags, photos. Bad files stop with a clear message; a bad row never stops the run. 198 tests pass, including made-up files and a shuffled, trimmed copy of the real one.

**Independent review.** A separate AI reviewer that didn't write the code found five ways wrong data could go out as ready, like a year Excel turned into 1905. I fixed those, plus two unclear messages.

**What doesn't work yet.**
- Three high school units with unreadable nameplates, and one panel logged twice, aren't linked to their twin. One of each is flagged, so nothing imports twice unseen.
- A blank building gives an incomplete message.
- Two merged technician rows are described as "sources".
- Headings that don't start on row 1 give a long list of missing columns.
- A partner row with only a building name is silently dropped.

**What I cut and why.** Tag matching and flexible column names. I chose a small tool that works over a bigger one that might not.

**Where AI got it wrong.** The AI's inspection said unmapped "Mitsubishi" affected 2 rows; the tool reported 4. The tool was right: the AI had missed "MITSUBISHI" in capitals. I trust the code's counts over anyone's summary.

**What I'd build next.**
1. A column-map file a person fills in once per new source format, including its condition scale.
2. Tag matching for units with missing nameplates.
3. Shrinking the review list: [REDUCING_REVIEW.md](REDUCING_REVIEW.md).
