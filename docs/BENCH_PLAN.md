# Plan for the first real-model run

Written 2026-10-27, before any real-model run, so the pass mark cannot be moved after seeing the results.

## Order

1. `examen calibrate --examiner <model>`. If the examiner fails (under 85% right, more than 10% of
   false claims passed, or more than 15% of true claims rejected), stop. Pick a different examiner.
   Do not run the bench with it. (Bar tightened 2026-10-27, before any real run: a wrongly rejected
   true claim makes the loop delete a true fact.)
2. `examen bench --writer <writer> --examiner <examiner> --budget 60000`, all ten questions, three
   scorings per first draft.
3. Commit the receipts folder for the run.

## Models

- Writers: `ollama:gemma3:4b` and `ollama:gemma3:12b`, temperature 0.2, seed 7.
- Examiner: `claude:claude-opus-5-5`, from a different model family than the writers.

## What counts as a result

- **The loop helps** if, for the same writer, `team+loop` gets at least 2 more of the 10 questions fully
  right than `team`, and is worse on none. The same rule applies to `single+loop` against `single`.
- **The team helps** if `team` gets at least 2 more fully right than `single`, and is worse on none.
- Anything smaller is reported as "no difference shown", not as a win. Ten questions cannot show small effects.
- Tokens spent are reported next to every result. A gain that costs three times the tokens is reported as exactly that.
- The held-back checklist score is reported. If it falls while the visible score rises, the writer
  is learning the test, and that result is reported as a failure.

## Added 2026-10-27, still before any real run

- Run the bench a second time with `--terse`, and a third time with `--cite-pass`. Each one is
  judged by the same rules against the plain run.
- Report every question where the loop lost an answer-key fact the no-loop arm had, with the
  sentence that was cut and the examiner's verdict on it.

## Added 2026-10-28, still before any real bench run

- No Claude key is available, so a local examiner may be used **if it passes calibration**,
  including the held-out kinds: plain, `guarded:` or `panel:`. The pass rules above do not change.
- If the examiner is the same family as the writer (gemma grading gemma), the result is reported
  with that warning next to it.
- Calibration showed these examiners give the same verdict when re-asked with a new seed (60 of 60,
  temperature 0.2). If that holds for the chosen examiner, scoring once instead of three times is
  allowed, and is reported.

## Added 2026-10-29, before the new test claims are made or run

The "reworded" true claims put "The … page records this:" in front of a page sentence. No writer
words a sentence that way, and the fact-by-fact examiner rejected 5 of 14 of them for it. They are
replaced, decided here before anything is run:

- **New reworded claims:** the page sentence with what a writer actually does to it. A leading
  "He", "She", "It" or "Its" is replaced by the page's subject ("He designed…" becomes "Thomas Varga
  designed…"), and common words are swapped for plain synonyms (about/around, residents/people,
  built/constructed, founded/set up, largest/biggest). If neither applies, the sentence starts
  "According to the … page," which is how writers do cite.
- **The examiner is shown the passage the scorer would choose for the reworded claim**, as in a
  real run, not the passage chosen for the original sentence.
- **Any change to an examiner is checked on two fresh sets of claims** (label seeds 11 and 13)
  that were not looked at while making the change. It is trusted only if it passes all three sets
  (7, 11, 13). The bars do not change.

## Added 2026-10-29 evening, after the five-set retest and before any further run

One false test claim was faulty: "Corrie also argued for the creation of the Brenna Council",
where the page says "campaigned for". The two mean nearly the same thing. Without it the examiner
would have passed all five sets; with it, it failed two. The result stands as **not trusted**,
because changing the test after seeing the result is the thing this plan exists to prevent.

- That verb swap is removed from the claim maker, and a test keeps it out.
- The next calibration is trusted only if it passes **all of** seeds 7, 11, 13, 17 and 19 (redrawn
  without the faulty swap) **and** two sets never drawn before (seeds 23 and 29). The bars do not change.
