# Time log

Budget: 3 hours, started 2026-11-08 15:34. Checkpoint at about 17:19. Hard stop at 18:34.

Times are from the system clock or git commit times. See QA-012 for why earlier estimated times were replaced.

| Time  | Step |
|-------|------|
| 15:34 | Start. Exercise read; prompt and decisions prepared. |
| 15:55 | Initial commit of the repo (README, LICENSE). |
| 16:00 | Step 1: all four input files inspected; distinct values and duplicate pairs counted. |
| 16:09 | Inspection report delivered; QA log started. Rules waiting on confirmation. |
| 16:19 | Decisions confirmed, inputs moved into data/ (checksums verified), RULES.md R1–R22 approved. Commit `0741f42`. |
| 16:22 | R9 cutoff tied to the current year; docs switched to a neutral voice. Commit `1d48d91`. |
| 16:25 | Step 3: mappings.py and reconcile.py written. First full run: 201 in, 117 ready, 49 needs_review, 35 merged. |
| 16:26 | Output checked against the inspection counts and FMX's three example rows. Commit `953363f`. |
| 16:31 | Tests written: 118 pass (one or more per rule, the accounting check, the unseen-file run, output columns). Two deliberate bugs confirmed caught. Commit `f7d871e`. |
| 16:32 | README written. All must-haves done, about 47 minutes before the checkpoint. Commit `2a1c31b`. |
| 16:36 | R12 changed to an editable list of asset types allowed to have no serial. 115 ready / 51 needs_review / 35 merged. Commit `34419f6`. |
| 16:37 | OPEN_QUESTIONS.md added and referenced from R18/R19. Commit `03b2fe5`. |
| 16:38 | R8 room-number cleanup: 16 locations standardized, counts unchanged, 135 tests pass. Commit `c8beb6b`. |
| 16:47 | Unseen-file hardening: unrecognized-values summary, building keyword fallback, accepted asset types read at run time, 8 note keywords, second unseen file. FMX counts unchanged; 155 tests pass. Commit `e5d6b7d`. |
| 16:59 | Keyword buildings → needs_review; graceful failure (file checks, plain messages, error log, safe outputs, row errors, warnings); serial checks across rows; years as dates; column-map idea scoped out; NOTE_DRAFT started. FMX counts unchanged; 176 tests pass. |
| 17:00 | Commit `2f63c45`. Independent review subagent launched (report only). |
| 17:11 | Review back: row accounting passes, no crashes, 5 wrong-data findings. Logged as QA-027 (commit `3fc631a`); nothing fixed, pending decision. |
| 17:14 | full_detail.csv (R30) and coverage-by-building table added. FMX counts unchanged; 183 tests pass. |
