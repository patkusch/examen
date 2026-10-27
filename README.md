<div align="center">

# examen

**A research agent that marks its own homework, using an answer sheet it is not allowed to touch.**

*examen* is Latin for both "a swarm of bees" and "an examination".

![tests](https://img.shields.io/github/actions/workflow/status/patkusch/examen/ci.yml?branch=main&style=for-the-badge&label=tests)
![python](https://img.shields.io/badge/python-3.11%E2%80%933.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![dependencies](https://img.shields.io/badge/dependencies-none-2ea44f?style=for-the-badge)
![license](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)

</div>

**Most "agent swarm" projects show how fast they run, not whether their answers are right.
examen researches a question, checks every sentence against the page it came from, and only keeps a rewrite if it is genuinely better.**

## The thirty-second version

Ask it: *"Who designed the lighthouse in the main town of Halvey, and in what year was that lighthouse automated?"*

On the first draft, the writer (a stand-in built to make mistakes) slipped in two bad sentences:

> Experts widely agree this is the single most important fact about the subject [port-seld].
> Many people find this topic fascinating and keep coming back to it.

The examiner checked each sentence against the page it named. The first was not on that page. The second named no page at all. The writer was told exactly which two sentences failed, and rewrote the report. The rewrite was kept because more of it was backed by its sources and nothing had got worse:

| | First draft | Kept version |
|---|---|---|
| Sentences backed by the page they name | 6 of 8 | 6 of 6 |
| Sentences with no source | 1 | 0 |
| Checklist questions passed | 1 of 2 | 2 of 2 |
| Facts from the answer key found | 2 of 2 | 2 of 2 |

Every number above is in the run's receipts. Run `examen demo` to see it yourself, with no internet and no AI model needed.

## Why it is built this way

Before writing any code, four research agents went through the well-known projects: deep-research agents, self-improving loops and "swarm" frameworks, plus the research on how to grade AI answers. A fifth agent then argued against the draft design. Full notes and sources are in [docs/DESIGN.md](docs/DESIGN.md). What they found:

1. **More agents is not the same as better answers.** The popular swarm frameworks publish speed numbers, not accuracy. A Google study found extra agents help only when the work splits into independent parts, and make step-by-step reasoning 39–70% worse.
2. **An AI grading its own work fools itself.** Models prefer their own writing. Loops that kept improving were scored by something the agent could not edit or see.
3. **Checking sentences against the page they cite is the cheapest honest check there is.** It needs no opinion, only the page.

So examen uses **one writer**, a few **read-only helpers** that each research one part, and a **separate examiner** that:

- writes a checklist from the question **before** any research starts, then freezes it, so the writer cannot move the goalposts;
- **holds back** some checklist questions. The writer is never told about them, so they show whether the report really got better or just learned the test;
- checks every sentence against the **saved text of the page** it cites;
- scores the first draft three times to see how much the score wobbles on its own, and keeps a rewrite only if it **beats that wobble** and **nothing got worse**. A shorter, safer report does not count as better;
- stops when the outside numbers stop improving or the budget runs out, **never on the writer's own opinion**.

## Is the examiner any good? Measure it first

A weak examiner makes every number meaningless, so examen tests it before trusting it. `examen calibrate` gives the examiner 60 claims with known answers. Half are copied from a page; half have one number or one name swapped. It must get 85% right **and** let no more than 10% of the false claims through.

The built-in stand-in examiner gets 85% right but lets 30% of the false claims through, so examen labels it **not to be trusted**, and every run that uses it carries a warning. That is the check working as intended.

## The fair test

Does the loop help? Do the helpers help? Changing both at once proves nothing, so `examen bench` runs four set-ups on the same ten questions with the same token cap:

| | no loop | loop |
|---|---|---|
| **one agent** | writes once | writes, is checked, rewrites |
| **team** | helpers research, one writer writes once | same, plus rewrites |

The questions are about an **invented island group**, so no model can answer from memory: it has to read the pages. Each question needs facts from two or three pages, and right answers are checked against an answer key, not against what the report happened to cite.

Offline, with the mistake-making stand-in writer:

| Set-up | Answers fully right | Sentences backed by their page | Held-back checklist passed | Tokens spent |
|---|---|---|---|---|
| one agent | 9 of 10 | 72% | 80% | 596 |
| one agent + loop | 9 of 10 | 100% | 100% | 1,066 |
| team | 8 of 10 | 74% | 80% | 1,566 |
| team + loop | 8 of 10 | 100% | 100% | 2,507 |

**This only shows the machinery works.** The stand-in is a few rules, not a model: the loop cleans out the planted mistakes, but nothing here says which set-up gives better answers. That needs real models, and the plan for that run, with the pass mark written down in advance, is in [docs/BENCH_PLAN.md](docs/BENCH_PLAN.md).

## Use it

```bash
pip install git+https://github.com/patkusch/examen   # no dependencies
examen demo                                          # offline, about a second
examen bench --writer fake-flawed                    # the four set-ups, offline
examen calibrate --examiner fake                     # measure an examiner
```

With real models (a local one through [Ollama](https://ollama.com), or Claude):

```bash
examen calibrate --examiner claude:claude-opus-5-5
examen run "Who built the first Eddystone lighthouse?" --source wikipedia \
    --writer ollama:gemma3:12b --examiner claude:claude-opus-5-5
examen bench --writer ollama:gemma3:12b --examiner claude:claude-opus-5-5
```

The Claude path needs `pip install 'examen[claude]'` and an API key. **Neither real-model path has been run yet**: they are built and the Ollama one is tested against a local stand-in server, but no live numbers exist. Use a different family of model for the examiner than for the writer, since models favour their own writing.

Every run writes its receipts to `receipts/`: the frozen checklist, every round's scores and verdicts, why each rewrite was kept or thrown away, and the final report.

## What "backed by its source" does not mean

It means the page says it. It does not mean it is true. A wrong page gets full marks. That is why the bench checks answers against an answer key as well.

## How it works inside

| File | Job |
|---|---|
| `loop.py` | Draft, score, rewrite, keep or throw away, stop |
| `score.py` | Checklist, sentence checks, wobble, the keep-or-throw-away rule |
| `calibrate.py` | Claims with known answers; measures the examiner |
| `bench.py` | The four set-ups at the same budget |
| `sources.py` | The invented islands (offline) and Wikipedia (live, cached on disk) |
| `models.py` | The stand-in, Ollama and Claude |
| `prompts.py` | What each role is asked; every answer is JSON |

Researcher notes must quote their page word for word; a note whose quote is not on the page is dropped by code before the writer sees it.

## Not done yet

- A live run with real models. This is the main gap.
- Parallel helpers. They run one after another until the bench shows they help.
- A larger question set; ten questions can show a big difference, not a small one.

MIT licence.
