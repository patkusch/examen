# The 12B examiner on naturally reworded claims, 2026-10-29

> **Correction, later the same day.** The conclusion below is wrong. Almost all of the rejected
> reworded true claims (8 of the 8–9 in each set) were rejected by examen's own code checks, not by
> the model: the name check treated "According" at the start of a sentence as a name, and missed
> possessives ("Port Seld's" vs "Port Seld"). Those checks are fixed and a test now makes sure they
> reject no true test claim. The examiner is being retested. The table is kept as it was measured.

Examiner: gemma3 12B with code checks, quoting the page sentence, then marking each fact as in the
quote or not. Writers' rewording was made the way decided in BENCH_PLAN.md that morning (name the
subject instead of "He/It", plain synonyms, "According to the … page," otherwise). Three sets of
claims, about 12 minutes each.

| Claim set (label seed) | 7 | 11 | 13 | Bar |
|---|---|---|---|---|
| Right | 86% | 83% | 83% | at least 85% |
| False claims let through | 7% | 5% | 10% | at most 10% |
| Held-out kinds let through | 11% | 6% | 0% | at most 10% |
| True claims rejected | **21%** | **29%** | **24%** | at most 15% |
| — copied word for word | 0 of 22 | 0 of 20 | 0 of 18 | |
| — reworded | **9 of 14** | **9 of 14** | **8 of 14** | |
| — shortened | 0 of 6 | 3 of 8 | 2 of 10 | |
| Trusted | no | no | no | |

**What it means.**
- The examiner is good at catching false claims and bad at accepting true ones that are not
  copied. It rejected about 6 in 10 reworded true claims, including plain ones: "Kessick is the
  mainland terminal for the Halvey Ferry Company" fails because the page says "It is the mainland
  terminal…", and the model will not connect "It" with Kessick.
- Yesterday's pass (98%, then 100% on a fresh set) was flattered by the old reworded claims, which
  kept the page sentence word for word behind a lead-in. With claims that read like writing, it fails.
- As the grader of a loop, this examiner would make the writer delete true facts or paste pages
  word for word. Neither is acceptable, so, as the plan requires, **the bench was not run**.
- Two false claims in the test were malformed ("has not no airport", "the MV The Seld"); the code
  that makes them is fixed. Neither changes the result, which fails on rejected true claims.

**Where this leaves examen.** Three local set-ups were tried: plain models, code checks and panels,
and quoting first. Each fixed one kind of mistake and showed another. A gemma3 model on this
machine is not a trustworthy grader of reworded writing. The plan's first choice, a stronger model
from another family (Claude, which needs an API key here), is the next step.
