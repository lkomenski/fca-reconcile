# Note draft (max 300 words)

# Note

**What it does.** One command reconciles both files into FMX's import format. On your files: 201 rows in, 112 ready, 54 flagged with plain reasons, 35 duplicates merged. 67% of rows need no one, so a specialist reviews 54 explained rows instead of reconciling two spreadsheets for two days (an estimate I'd measure with a specialist).

**What works.** Every input row is accounted for, or the run stops. Values are fixed only from editable lookups; anything else is flagged, never guessed. full_detail.csv keeps what the import format drops: notes, tags, photos. A bad row never stops the run; a bad file stops with a clear message. 210 tests pass, including a shuffled copy of your file.

**Independent review.** A separate AI reviewer that didn't write the code found five ways wrong data could go out as ready, like a year Excel turned into 1905. I fixed four and added a safeguard for the fifth.

**What doesn't work yet.**
- Three units with unreadable nameplates, and one panel logged twice, are flagged as possible twins by tag, not merged automatically.
- A few edge-case messages are unclear, and a partner row with only a building name is dropped silently.

**What I cut.** Automatic tag merging and flexible column names, to keep the tool small and working.

**Where AI got it wrong.** The AI's fix for Excel-damaged serials flagged 7989E905548, a real A.O. Smith serial, as scientific notation. I caught it because a rerun moved that row to review when nothing should have changed. It's fixed, with its own test.

**Open question.** Whose data should win when sources disagree. I'd ask Professional Services first.

**Next.** A column-map file per new source format; automatic tag merging; better capture, so 54 flags drop to about 10 real judgment calls ([REDUCING_REVIEW.md](REDUCING_REVIEW.md)); known limits in [EXTENDING.md](EXTENDING.md).