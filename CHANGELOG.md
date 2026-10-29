# Changelog

## Unreleased
- Calibration has 84 claims and three held-out kinds of false claim (changed verb, swapped place, changed number word); an examiner must pass those on their own.
- `guarded:<examiner>`: code checks reject claims whose numbers, names or "not" do not match the page, before the model is asked.
- `panel:<a>+<b>`: a claim is backed only if every examiner agrees.
- `calibrate` prints a readable summary (`--json` for the full result) and how many verdicts the code checks made.
- `make calibrate-guarded`.
- `quote:<examiner>`: the examiner copies the page sentence closest to the claim (checked by code), then marks each fact in the claim as in that sentence or not; code backs the claim only if every fact is there.
- Calibration has shortened true claims, and `--label-seed` draws a fresh set of claims.
- `bench --resume` carries on a stopped bench.
- Planner: a question that asks for two things gets one search per thing.
- Reworded true test claims now read like a writer's (subject named instead of "He/It", plain synonyms), decided before running; `calibrate --misses` lists every wrong verdict; two malformed false claims fixed.
- Code checks no longer reject true claims: "According" is not a name, and possessives match ("Seld's" is "Seld"). A test makes sure they reject no true claim in six sets.
- `labels --seed`; an index of live runs in docs/runs.
- Live (docs/runs/2026-10-29-natural-rewording.md): first read as the model rejecting most reworded true claims; corrected, the code checks did. Retest under way; the bench has not run.
- Live retest (docs/runs/2026-10-28-examiner-retest.md): the gemma3 panel with code checks reaches 95% right and 9.5% false let through, but misses 4 of 6 changed verbs, so it is not trusted and the bench was not run.

## 0.3.0 (2026-10-27)
- `--require-trusted` refuses to run with an examiner that has not passed `examen calibrate`.
- Warns when the writer and examiner come from the same model family.
- `examen show` prints what a past run decided, round by round.
- `make calibrate-local` and `make bench-live` for real models; the live bench is guarded.
- SECURITY.md (pages are untrusted) and CITATION.cff.
- Each repeated scoring uses its own seed, so the measured wobble and self-agreement are real for local models (before, every repeat gave the identical answer).
- `calibrate --runs` sets how many seeded passes judge each claim.
- First real-model results: gemma3 12B and 4B tested as examiners; neither passes (27% and 33% of false claims let through). See docs/runs.
- `--split-seed` changes which checklist questions are held back, so a writer run many times cannot learn them.

## 0.2.0 (2026-10-27)
- Fixed ten holes from a code review: Wikipedia returned one page per search; pasted or extra sentences could win a rewrite; headings were unchecked; common citation styles were unread; piling on citations bought extra chances; a held-back item leaked; numbers could slide down round by round; the budget was not a hard cap; unsearched pages could be cited; "yes" answers read as no.
- Borrowed from other research agents: question kinds size the search, a citation pass that may not change words, failed sentences become searches, terse feedback.
- Examiner test now covers added "not", made-up details and reworded true claims, with a limit on rejected truths.

## 0.1.0 (2026-10-27)
- First version: one writer, read-only helpers, a separate examiner with a frozen checklist, a noise-aware keep rule, examiner calibration and a four-way bench on an invented island corpus.
