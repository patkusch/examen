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

## Update: quote first, then compare

`quote:<examiner>` makes the examiner copy the page sentence closest to the claim (code checks the
quote is really there), then compare the claim with that one sentence part by part: who, what was
done, to what, when, where, how many. Same 84 claims, code checks in front.

| Examiner | Right | False let through | Held-out kinds | True rejected | Time | Trusted |
|---|---|---|---|---|---|---|
| 4B, code checks + quote first | 89% | 0% | 0% | 21% (9 of 42) | 2 min 49 s | no |
| **12B, code checks + quote first** | **98%** | **0%** | **0%** | **5% (2 of 42)** | 7 min 10 s | **yes** |

Changed verbs went from 5 of 6 let through to 0 of 6 for the 12B. The 4B now lets nothing false
through but rejects too many true claims; with it as grader the loop would delete true facts.

**Caveat.** The comparison prompt was written after seeing the verb failures, on this same set of
claims. Its wording is general (it never mentions verbs), but to check it was not fitted to these
84 claims, the 12B is being retested on a fresh draw (`--label-seed 11`; 32 of its 42 false claims
are new).

**Earlier idea, now tried.** Ask the examiner to quote the words on the page that state
the claim before it answers, and check by code that the quote is really on the page. Judges that
show their evidence first are reported to be more reliable, and it targets reading, not a claim kind.

## Update 2026-10-29: the fresh set passed, then the bench found a gap the test missed

- **Fresh claims (`--label-seed 11`):** the 12B with code checks and quote first got all 84 right,
  let nothing false through and rejected nothing true. The pass was not fitted to the first set.
- **The bench was started**, and 12 of its 40 runs finished before the session ended. They were
  thrown away, because they showed the examiner was wrong in a way the test never measured. It
  rejected true sentences that said *less* than the page: "The Seld Lighthouse was built in 1871"
  failed because the page also says who built it. The 4B writer's one-agent reports scored 0 of 3
  sentences backed, even when every answer was right. Asked to check "who, what was done…", the
  12B treated a missing "who" as a difference.
- **Fixes, made before any new bench run:**
  1. The examiner test now has *shortened* true claims, cut at a safe point ("…in 1871." from
     "…in 1871 by the engineer Thomas Varga.").
  2. The comparison asks the model to split the claim into facts and mark each as in the quote or
     not; code backs the claim only if every fact is there. Loosening the wording instead made it
     worse (changed verbs got through), so that version was dropped.
  3. The planner prompt now says a question asking for two things is never "straightforward"; the
     4B had given every two-part question a single search.
- The examiner is being retested on both sets with these fixes; the bench runs again only if it
  passes both.

## Update 2026-10-29: the fact-by-fact examiner fails narrowly; bench not run

Same examiner (12B, code checks, quote first) with the fact-by-fact comparison, on the first set of
claims (`--label-seed 7`, now including shortened true claims). 13 min 19 s.

| | Result | Bar |
|---|---|---|
| Right | 90% | at least 85% |
| False claims let through | 7% (3 of 42) | at most 10% |
| Held-out kinds let through | **11% (2 of 18)** | at most 10% |
| True claims rejected | 12% (5 of 42) | at most 15% |
| — shortened true claims | 0 of 6 | |
| — reworded true claims | 5 of 14 | |

What slipped through: 2 changed verbs and 1 made-up detail. Splitting the claim into facts fixed
the shortened claims but made the model a little less strict about wording. That is a real weakness.

The 5 rejected true claims are all of the "reworded" kind, which is a page sentence with "The …
page records this:" put in front. The model lists "the page records this" as a fact, cannot find
it in the quote, and rejects the claim. No real writer words a sentence that way, so this is
partly a flaw in the test. It is recorded here, not fixed: changing the test after failing it would
be moving the goalposts. A better rewording kind can be added later, decided before it is run.

**Decision.** Not trusted, so, as the plan requires, the bench was not run.

**Where this leaves the examiner.** The previous version (one "same or not" question) passed both
sets of claims but rejected true claims that say less than the page, which real writers produce all
the time. The fact-by-fact version handles those but lets a few changed verbs through. Neither is
good enough to grade the bench. A stronger model from another family (Claude, needs an API key)
remains the plan's first choice.
