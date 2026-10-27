# Plan for the first real-model run

Written 2026-10-27, before any real-model run, so the pass mark cannot be moved after seeing the results.

## Order

1. `examen calibrate --examiner <model>`. If the examiner fails (under 85% right, or more than 10% of
   false claims passed), stop. Pick a different examiner. Do not run the bench with it.
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
