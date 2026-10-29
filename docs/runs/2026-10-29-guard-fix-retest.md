# Retest after fixing the code checks, 2026-10-29

Examiner: gemma3 12B with code checks, quoting the page sentence, then marking each fact as in the
quote or not (`guarded:quote:ollama:gemma3:12b`). Same claims as the morning run, plus two fresh sets
(seeds 17 and 19) never seen before. About 13 minutes per set on an Apple M5.

| Claim set (label seed) | 7 | 11 | 13 | 17 | 19 | Bar |
|---|---|---|---|---|---|---|
| Right | 94% | 94% | 94% | 98% | 95% | at least 85% |
| False claims let through | 7% | 2% | 5% | 0% | 5% | at most 10% |
| Held-out kinds let through | **11%** | 6% | 0% | 0% | **12%** | at most 10% |
| True claims rejected | 5% | 10% | 7% | 5% | 5% | at most 15% |
| — reworded | 2 of 14 | 1 of 14 | 1 of 14 | 1 of 14 | 1 of 13 | |
| — shortened | 0 of 6 | 3 of 8 | 2 of 9 | 1 of 5 | 1 of 6 | |
| Trusted | no | yes | yes | yes | no | |

Seed 19 drew 80 claims, not 84: the generator found only four sentences with a number word to change.

**What it means.**
- The fix worked. Reworded true claims rejected fell from 8–9 of 14 to 1–2 of 14. The morning's
  failure was examen's own bug, not the model.
- The examiner passed three sets and failed two, each time by one claim: a changed verb let through
  ("Corrie also argued for the creation of the Brenna Council"). The bar for held-out kinds is 10%,
  and one wrong verdict in 18 or 16 is 11–12%.
- **That test claim was faulty.** The page says Corrie "campaigned for" the council, so "argued for"
  barely changes the meaning, and passing it was a fair call. The other two verbs let through were
  real mistakes ("taught under" for "trained under", "abandoned" for "automated"). Without the faulty
  claim, seeds 7 and 19 would have passed.
- The rule written before any run says an examiner is trusted only if it passes every set. It did
  not, so **the bench was not run**. The result was not rescored after the faulty claim was found;
  the claim maker is fixed, and the next run must pass seven sets, two of them new
  ([BENCH_PLAN.md](../BENCH_PLAN.md)).
- The same true claim is rejected in all five sets: "Kessick is the mainland terminal for the Halvey
  Ferry Company", where the page says "It is…". The model will not link "It" to the page's subject.
- Padding (a made-up clause stuck on a true sentence) slipped through 3 times in 30.

**Where this leaves examen.** This is the closest a local model has come: it grades well on most
sets, but a changed verb can still fool it. Nothing in examen can fix that without fitting the test.
The next step is still a stronger examiner from another family.
