# Changelog

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
