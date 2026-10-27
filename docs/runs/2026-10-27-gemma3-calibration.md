# gemma3 as examiner: calibration, 2026-10-27

Run on an Apple M5 with 16 GB, Ollama 0.33.3, temperature 0.2, `examen calibrate --examiner ollama:<model>`:
60 claims, half true, half false, each judged twice with different seeds.

| | gemma3 12B | gemma3 4B | Bar |
|---|---|---|---|
| Right | 87% | 83% | at least 85% |
| False claims passed | 27% (8 of 30) | 33% (10 of 30) | at most 10% |
| — number swapped | 1 of 8 | 0 of 8 | |
| — name swapped | 2 of 8 | 3 of 8 | |
| — "not" added | 3 of 7 | 1 of 7 | |
| — made-up detail added | 2 of 7 | 6 of 7 | |
| True claims rejected | 0 of 30 | 0 of 30 | at most 15% |
| Same verdict on both seeded passes | 60 of 60 | 60 of 60 | |
| Time | 2 min 16 s | 34 s | |
| **Trusted** | **no** | **no** | |

**What it means.** Both are too lenient, not too strict: they never rejected a true claim but let a
third of the false ones through. As the writer's grader, the loop would keep those sentences as
"backed by their page". So, as the bench plan requires, the bench was not run with either.

**Seeds.** The first run gave every repeat the same seed, so 100% agreement was guaranteed. After
the fix each pass has its own seed, and agreement is still 60 of 60. At temperature 0.2 these
models do not change their yes/no answers between seeds. Their scoring wobble is close to zero,
and that is now measured, not assumed.

**Next.** Test a stronger examiner from another family (Claude needs an API key on this machine).
