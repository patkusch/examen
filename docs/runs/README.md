# Live runs

Every run with a real model, newest first. Each file has the numbers and what they mean.

| Date | What was tested | Outcome |
|---|---|---|
| 2026-10-29 | [Retest after fixing the code checks](2026-10-29-guard-fix-retest.md) | 94–98% right, passed 3 of 5 sets; each failure was one changed verb let through. Not trusted. |
| 2026-10-29 | [12B examiner on naturally reworded claims](2026-10-29-natural-rewording.md) | Looked like the model rejected most reworded truths; corrected: examen's own code checks did. |
| 2026-10-28 | [Code checks, panels and quoting first](2026-10-28-examiner-retest.md) | 12B quoting first passed two sets, then failed when the test gained shortened and natural claims. |
| 2026-10-27 | [gemma3 12B and 4B as examiners](2026-10-27-gemma3-calibration.md) | Both let about a third of false claims through. Not trusted. |

The four-way comparison (`examen bench`) runs only after an examiner passes every set of test
claims. It has not run yet. The rules for it, written before any run, are in
[../BENCH_PLAN.md](../BENCH_PLAN.md).
