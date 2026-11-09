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
| 16:31 | Tests written: 118 pass (one or more per rule, the accounting check, the unseen-file run, output columns). Two deliberate bugs confirmed caught. |
