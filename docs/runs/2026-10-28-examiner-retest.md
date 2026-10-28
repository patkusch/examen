# Examiner retest with code checks and a panel, 2026-10-28

84 claims (42 true, 42 false in seven kinds, six each), each judged twice with different seeds.
Apple M5, 16 GB, Ollama 0.33.3, temperature 0.2.

| Examiner | Right | False let through | Held-out kinds let through | True rejected | Time | Trusted |
|---|---|---|---|---|---|---|
| gemma3 12B | 88% | 24% | 33% | 0% | 3 min 11 s | no |
| gemma3 4B | 88% | 24% | 22% | 0% | 49 s | no |
| 12B + code checks | 94% | 12% | 28% | 0% | 2 min 4 s | no |
| 4B + code checks | 90% | 19% | 22% | 0% | 36 s | no |
| **12B and 4B panel + code checks** | **95%** | **9.5%** | **22%** | **0%** | 10 min 17 s | **no** |
| Bar | at least 85% | at most 10% | at most 10% | at most 15% | | |

False claims let through, by kind:

| Kind | 12B | 4B | 12B + checks | 4B + checks | Panel + checks |
|---|---|---|---|---|---|
| Number swapped | 1 | 0 | 0 | 0 | 0 |
| Name swapped | 1 | 2 | 0 | 0 | 0 |
| "Not" added | 2 | 0 | 0 | 0 | 0 |
| Made-up detail added | 0 | 4 | 0 | 4 | 0 |
| Verb changed (held out) | **5** | **4** | **5** | **4** | **4** |
| Place swapped (held out) | 1 | 0 | 0 | 0 | 0 |
| Number word changed (held out) | 0 | 0 | 0 | 0 | 0 |
| (out of) | 6 each | | | | |

**What it means.**
- The code checks did what they were built for: every swapped number, swapped name and added
  "not" was caught. With the panel, the overall false-pass rate fell from 24% to 9.5%, inside the bar.
- They did nothing for changed verbs, which they were never designed to catch. Both models accept
  "The Halvey Ferry Company **sold** boats between…" when the page says **runs**. The panel did not
  help either: every verb change 4B missed, 12B missed too.
- The held-out rule is what stopped this from looking like a pass. Without it, the panel would
  have been trusted on overall numbers while still reading "sold" as "runs".
- No examiner rejected a true claim, so none of them would make the loop delete true facts.
- Every examiner gave the same verdict on both seeded passes for all 84 claims.

**Decision.** Nothing passed, so, as the plan requires, the bench was not run.

**Next idea (not fitted to the test).** Ask the examiner to quote the words on the page that state
the claim before it answers, and check by code that the quote is really on the page. Judges that
show their evidence first are reported to be more reliable, and it targets reading, not a claim kind.
