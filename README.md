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

The examiner checked each sentence against the page it named. The first was not on that page. The second named no page at all. Before cutting anything, examen searched again for sources for the sentences that failed. Then the writer rewrote the report. The rewrite was kept because more of it was backed by its sources and nothing had got worse. Two more rewrites were tried and thrown away, because they were no better.

| | First draft | Kept version |
|---|---|---|
| Sentences backed by the page they name | 5 of 8 | 9 of 10 |
| Sentences with no source | 1 | 0 |
| Checklist questions passed | 1 of 2 | 2 of 2 |
| Facts from the answer key found | 2 of 2 | 2 of 2 |

Every number above is in the run's receipts. Run `examen demo` to see it yourself, with no internet and no AI model needed.

## How others approached it

Before writing any code, four research agents went through the well-known projects, and a fifth argued against the draft design. After the first version, three more agents reviewed the code, studied how the leading projects are built, and searched for anything already doing the same thing. Full notes and sources are in [docs/DESIGN.md](docs/DESIGN.md).

| Project | How it works | How it checks itself | What examen took from it |
|---|---|---|---|
| Anthropic's research system | A lead agent sends out helpers; a separate step adds citations | An AI grader plus people | Effort sized to the question; a citation step that may not change any words |
| Google TTD-DR | Writes a draft first, then searches to fix its gaps | Draft compared against rivals | Sentences that fail their check become the next searches |
| DeepResearch Bench (FACT) | Scoring only | Each sentence checked against the page it cites | The core check |
| Karpathy's autoresearch | Change, measure, keep or undo | A fixed number the agent cannot edit | Keep or undo, but only past the score's own wobble |
| Darwin Gödel Machine | Agents rewrite their own code | Coding tests | A warning: it cheated more when it could see the checker |
| OpenScholar, DeepVerifier | Answer, check, revise | Citation checks; DeepVerifier also tests its checker | Measure the examiner before trusting it |
| crewAI, swarms, claude-flow | Many agents with roles | Speed and memory numbers, not accuracy | Little: more agents is not the same as better answers |

No project we found combines all of examen's parts. Each part exists somewhere. The combination examen adds is a frozen checklist with hidden questions, a keep rule that allows for the score's wobble, a tested examiner, and a fair four-way test on an invented corpus.

## Why it is built this way

1. **More agents is not the same as better answers.** A Google study found extra agents help only when the work splits into independent parts, and make step-by-step reasoning 39–70% worse.
2. **An AI grading its own work fools itself.** Models prefer their own writing. The loops that kept improving were scored by something the agent could not edit or see.
3. **Checking sentences against the page they cite is the cheapest honest check.** It needs no opinion, only the page.

So examen uses **one writer**, a few **read-only helpers** that each research one part, and a **separate examiner** that:

- writes a checklist from the question **before** any research starts, then freezes it, so the writer cannot move the goalposts;
- **holds back** some checklist questions. The writer is never told about them, so they show whether the report really got better or the writer just learned the test;
- checks every sentence, headings included, against the **saved text of the pages** it cites. Only pages actually found during the run count;
- treats a sentence citing more than three pages as unsupported, so piling on citations buys no extra chances;
- scores every version three times and keeps a rewrite only if it **beats the score's wobble**, nothing dropped below the best version or the first draft, and **no more sentences were pasted** from the pages;
- stops when the outside numbers stop improving or the budget runs out, **never on the writer's own opinion**. The budget is checked before every call.

## The examiner has to pass a test first

A weak examiner makes every number meaningless, so `examen calibrate` tests it on 84 claims with known answers. Half are true: some copied from a page, some reworded. Half are false, each with one small change of one of seven kinds:

- a number swapped, a name swapped, a "not" added, a made-up detail tacked on;
- held out from examen's own code checks: a verb changed ("built" becomes "demolished"), a one-word place swapped, a number written as a word changed ("three" becomes "four").

To be trusted, it must get 85% right, let through no more than 10% of the false claims, reject no more than 15% of the true ones, and let through no more than 10% of the held-out kinds on their own. That last rule stops anyone fitting checks to the test.

Any examiner can be strengthened two ways:

- `guarded:<examiner>` puts code checks in front of it. A claim whose numbers or names are not on the page, or that adds a "not" the page lacks, is rejected without asking the model. The checks can only say no.
- `panel:<a>+<b>` asks several examiners and backs a claim only if all of them do. Different models miss different things.

The built-in stand-in examiner fails, which is the point of the test:

| False claims it let through | plain | with code checks |
|---|---|---|
| A number swapped | 0 of 6 | 0 of 6 |
| A name swapped | 1 of 6 | 0 of 6 |
| A "not" added | 6 of 6 | 0 of 6 |
| A made-up detail tacked on | 0 of 6 | 0 of 6 |
| A verb changed (held out) | 6 of 6 | 6 of 6 |
| A place swapped (held out) | 6 of 6 | 0 of 6 |
| A number word changed (held out) | 6 of 6 | 6 of 6 |
| **True claims it wrongly rejected** | **6 of 42** | **6 of 42** |

The name check also catches swapped places, because a place is a name. Changed verbs and number words get past every code check, so they test the model alone.

Real local models: the closest so far is gemma3 12B with code checks that must quote the page sentence before answering. It catches false claims well (5–10% let through), but once the true test claims were reworded the way writers really write, it rejected about 6 in 10 of them. That would make the loop delete true facts, so it is not trusted and the four-way comparison has not run. Details in [docs/runs](docs/runs/2026-10-29-natural-rewording.md). Before quoting, the best was a panel of gemma3 12B and 4B with code checks. It got 95% right, let through 9.5% of false claims and rejected no true ones, but still let through 4 of 6 changed verbs, so it is not trusted. Details in [docs/runs](docs/runs/2026-10-28-examiner-retest.md).

On the earlier 60-claim test, real local models failed too. gemma3 12B got 87% right but passed 27% of false claims; gemma3 4B passed 33%, including 6 of 7 claims with a made-up detail added. Neither rejected a true claim. Details in [docs/runs](docs/runs/2026-10-27-gemma3-calibration.md).

**Wrongly rejecting a true sentence is not harmless.** The loop removes sentences the examiner rejects, so a true fact gets deleted. The fair test below caught exactly that.

## The fair test

Does the loop help? Do the helpers help? Changing both at once proves nothing, so `examen bench` runs four set-ups on the same ten questions with the same token cap:

| | no loop | loop |
|---|---|---|
| **one agent** | writes once | writes, is checked, rewrites |
| **team** | helpers research, one writer writes once | same, plus rewrites |

The questions are about an **invented island group**, so no model can answer from memory: it has to read the pages. Each question needs facts from two or three pages. Right answers are checked against an answer key, not against what the report happened to cite.

Offline, with the mistake-making stand-in writer and stand-in examiner:

| Set-up | Answers fully right | Sentences backed by their page | Tokens spent |
|---|---|---|---|
| one agent | 9 of 10 | 66% | 644 |
| one agent + loop | **8 of 10** | 100% | 1,610 |
| team | 9 of 10 | 65% | 1,721 |
| team + loop | 9 of 10 | 93% | 6,600 |

The loop raised the share of backed sentences every time. But in one case it lost an answer. The examiner wrongly rejected *"She was born in Kessick"*, the loop cut the sentence, and the answer went with it. More checking is only as good as the checker. Test the examiner before you trust the loop.

These are a few rules standing in for models, so they show the machinery works, not which set-up is best. The plan for the real-model run, with the pass mark written down in advance, is in [docs/BENCH_PLAN.md](docs/BENCH_PLAN.md).

## Use it

```bash
pip install git+https://github.com/patkusch/examen   # no dependencies
examen demo                                          # offline, about a second
examen bench --writer fake-flawed                    # the four set-ups, offline
examen calibrate --examiner fake                     # test an examiner
examen show receipts                                 # what the newest run decided, round by round
```

With real models (a local one through [Ollama](https://ollama.com), or Claude):

```bash
examen calibrate --examiner claude:claude-opus-5-5
examen run "Who built the first Eddystone lighthouse?" --source wikipedia \
    --writer ollama:gemma3:12b --examiner claude:claude-opus-5-5
examen bench --writer ollama:gemma3:12b --examiner claude:claude-opus-5-5 --require-trusted
```

Two options borrowed from other projects:

- `--cite-pass` writes the report first, then adds citations in a separate step. Code checks that the citation step changed nothing but the citations (Anthropic's approach).
- `--terse` tells the writer that parts of the question are missing, but not which ones. A 2026 study found writers given detailed failure lists learned to dodge the checks about twice as often.

The Claude path needs `pip install 'examen[claude]'` and an API key. **Neither real-model path has been run yet.** Both are built and tested against stand-ins, but no live numbers exist. Use a different family of model for the examiner than for the writer, since models favour their own writing.

Every run writes its receipts to `receipts/`: the frozen checklist, every round's scores and verdicts, why each rewrite was kept or thrown away, and the final report.

## What "backed by its page" does not mean

It means the page says it. It does not mean it is true. A wrong page gets full marks. That is why the fair test checks answers against an answer key as well.

## How it works inside

| File | Job |
|---|---|
| `loop.py` | Size the question, research, draft, score, rewrite, keep or throw away, stop |
| `score.py` | Checklist, sentence checks, wobble, the keep-or-throw-away rule |
| `calibrate.py` | Claims with known answers, six kinds; tests the examiner |
| `bench.py` | The four set-ups at the same budget |
| `sources.py` | The invented islands (offline) and Wikipedia (live, saved to disk) |
| `models.py` | The stand-in, Ollama and Claude |
| `prompts.py` | What each role is asked; every answer is JSON |
| `text.py` | Sentences and citations in the styles real models write: `[id]`, `[a, b]`, `【id】`, `(source: id)`, page titles |

Researcher notes must quote their page word for word. A note whose quote is not on the page is dropped by code before the writer sees it.

## Not done yet

- A live run with real models. This is the main gap.
- Swapping which checklist questions are held back between runs, so a writer cannot learn them.
- Splitting sentences into single facts before checking. Right now a true clause can carry a false one, if the examiner misses it.
- Parallel helpers. They run one after another until the fair test shows they help.

MIT licence.
