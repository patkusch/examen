# Why examen is built the way it is

Research done 2026-10-27. Four agents surveyed the field in parallel and a fifth argued against the
draft design. Figures marked *unverified* were seen only in secondary sources.

## 1. Deep-research agents

| System | Shape | Self-check | Published result |
|---|---|---|---|
| gpt-researcher | Planner, parallel executors, publisher | Context filtering only | No public end-to-end benchmark |
| STORM (Stanford) | Simulated expert conversations, then outline and write | None | FreshWiki: +25% organisation, +10% coverage vs retrieval baseline ([paper](https://arxiv.org/abs/2402.14207)) |
| open_deep_research (LangChain) | Supervisor + parallel researchers (legacy) | Reflection | RACE 0.434; 0.494 with ~3.5x the tokens. Archived 2026-08 |
| smolagents open_deep_research | One code-writing agent | None | GAIA val 55.15%; same set-up with JSON actions ~33% ([blog](https://huggingface.co/blog/open-deep-research)) |
| Anthropic Research | Lead + parallel subagents, separate citation agent | Rubric judge + humans | +90.2% over single agent on an internal eval; tokens explain 80% of BrowseComp variance ([post](https://www.anthropic.com/engineering/multi-agent-research-system)) |
| Tongyi DeepResearch | ReAct or "Heavy" parallel agents + synthesis; RL-trained | Synthesis agent | BrowseComp 43.4, HLE 32.9 ([blog](https://tongyi-agent.github.io/blog/introducing-tongyi-deep-research/)) |
| MiroThinker 1.7 | Single RL-trained agent, keeps last 5 tool results | None stated | BrowseComp 74.0, GAIA val 82.7 ([repo](https://github.com/MiroMindAI/MiroThinker)) |

What moves scores: spending more tokens; a model trained for research; managing what stays in the
context window (the leaders dropped multi-agent configs); checking work in a *separate* context.

## 2. Self-improving loops

| System | Evaluator | Result | What went wrong |
|---|---|---|---|
| Reflexion | Self-written unit tests | HumanEval 91% vs 80% | Weak self-written tests let wrong code pass ([paper](https://arxiv.org/abs/2303.11366)) |
| Self-Refine | Same model judges itself | ~20% avg gain *(unverified)* | Without outside feedback, self-correction does not help reasoning ([Huang et al.](https://arxiv.org/abs/2310.01798)) |
| AI Scientist v1/v2 (Sakana) | Code runs + LLM reviewer | 1 of 3 papers passed a workshop bar | Tried to extend its own timeout; audit found made-up numbers ([audit](https://arxiv.org/abs/2502.14297)) |
| Agent Laboratory | LLM self-review | 84% cheaper | Authors say it overrates its own work ([paper](https://arxiv.org/abs/2501.04227)) |
| Darwin Gödel Machine | SWE-bench tests | 20% → 50% | Faked tool logs; deleted the markers that detected faking, more so when the checker was visible ([paper](https://arxiv.org/abs/2505.22954)) |
| Huxley-Gödel Machine | SWE-bench | Beats DGM with less compute | A high score does not predict a good next step ([paper](https://arxiv.org/abs/2510.21614)) |
| AlphaEvolve / ShinkaEvolve | A program computes the score | New maths results | Needs a scoring program ([Shinka](https://arxiv.org/abs/2509.19349)) |
| AI co-scientist (Google) | Pairwise debate, Elo | Elo tracked GPQA accuracy | Elo "not based on ground truth" ([paper](https://arxiv.org/abs/2502.18864)) |
| autoresearch (Karpathy) | Fixed validation metric; keep or `git revert` | Many overnight experiments | Overfitting the validation set *(unverified)* |

Lesson: the loops that kept improving were scored by something the agent could not edit or see.

## 3. Swarm frameworks

crewAI, swarms, ruflo (claude-flow) and AutoGen publish speed or memory numbers, not accuracy. None
compares against one agent with the same tools and budget. OpenAI Swarm has been replaced, AutoGen is
archived, langgraph-supervisor is archived. MetaGPT (vs a weak 2023 baseline) and OWL (GAIA 69.7%,
no single-agent control) are the only ones with quality numbers.

- Google 2025 scaling study ([paper](https://arxiv.org/abs/2512.08296)): central coordination +80.9% on
  tasks that split cleanly; every multi-agent variant 39–70% worse on step-by-step reasoning; agents
  working independently amplified errors 17.2x vs 4.4x when coordinated; gains stop once one agent
  passes ~45%.
- MAST ([paper](https://arxiv.org/abs/2503.13657)): 41–87% failure rates across 7 frameworks, mostly
  from design and missing verification, not model weakness.
- Cognition 2026 ([post](https://cognition.com/blog/multi-agents-working)): what works is a writer
  plus a clean-context reviewer; keep writes single-threaded.
- Debate vs majority voting at equal compute: roughly equal ([Huang et al.](https://arxiv.org/abs/2310.01798)).

## 4. Grading without fooling yourself

Ranked by protection per unit of cost:

1. Check each (claim, cited page) pair against the saved page text. This is DeepResearch Bench's FACT
   step ([paper](https://arxiv.org/abs/2506.11763)). **Built.**
2. Citation recall, ALCE style ([paper](https://arxiv.org/abs/2305.14627)). **Built** as "share of
   sentences backed by their page".
3. Atomic, checkable claims only (FActScore, SAFE, VeriScore). **Partly**: sentences, not atomic facts.
4. A judge from a different model family ([PoLL](https://arxiv.org/abs/2404.18796)); models favour
   their own text ([Panickssery et al.](https://arxiv.org/abs/2404.13076)). **Advised** in the README; the
   examiner is a separate setting.
5. A checklist written before the report and frozen ([TICK](https://arxiv.org/abs/2410.03608)). **Built**,
   with some items held back.
6. Pairwise judging in both orders ([MT-Bench](https://arxiv.org/abs/2306.05685)). Cut for now.
7. Scoring against a reference report (RACE). Cut for now.

Stop rules: hard budget, plus patience on the outside numbers, never on the agent's own score. **Built.**

## 5. What the critic changed

| Critic's point | What examen does |
|---|---|
| A small local judge is weaker than the noise it measures | `examen calibrate`: 60 claims with known answers; must reach 85% right and pass no more than 10% of false ones. Runs warn when the examiner is unmeasured or fails |
| Keep-if-better on a noisy score keeps lucky noise | First draft scored 3 times; a rewrite must beat that spread. Final numbers come from a fresh scoring that took no part in choosing |
| Hidden checklist items leak through feedback | The writer is only ever told about visible items; a test checks this |
| "Share supported" rewards saying less | A rewrite is thrown away if the supported count drops; claims are pulled out by code |
| The control mixes up two changes | Bench is a 2x2: one agent vs team, crossed with loop vs no loop |
| Easy sources show nothing; matching the page is not truth | Invented island corpus with an answer key; questions need 2–3 pages; README says "backed by its page", never "accurate" |

Cut from version 1 on the critic's advice: parallel helpers, a population of versions, pairwise
tie-breaks, RACE, judge panels, arXiv, citation precision.

## 6. Second round: review, prior art and how others build it (2026-10-27)

Three more agents ran after version 0.1: one reviewed the code, one read how the leading projects
are built (source files and papers), one searched for work closest to examen.

### Closest prior art

| Work | What it checks | Loops | Tests its own judge |
|---|---|---|---|
| DeepVerifier ([paper](https://arxiv.org/abs/2601.15808)) | Deep-research answers against a rubric of 13 failure types | Yes | Yes |
| OpenScholar | Citation-worthy sentences, final grounding pass | Yes | Partly |
| PaperQA2 ([paper](https://arxiv.org/abs/2409.13740)) | Literature answers, contradictions | No revise loop | Expert sample |
| RARR ([paper](https://arxiv.org/abs/2210.08726)) | Each claim vs retrieved evidence; tracks how much text survives editing | One pass | Human study |
| DeepResearch Bench FACT | Statement and page pairs, scraped page | No | Some |
| Citation-verifier benchmark ([alphaXiv](https://www.alphaxiv.org/abs/2607.08700)) | 624 labelled pairs, ~60% adversarially edited | No | It is the judge test; best F1 about 0.75 |

Nothing found combines a frozen checklist with hidden items, a noise-aware keep rule, a tested
examiner and a 2x2 bench on an invented corpus. A 2026 study ([arXiv 2609.28614](https://arxiv.org/abs/2609.28614))
found agents given detailed failure feedback evaded checks in 40.5% of cases vs 20.3% with a
generic rejection, which is why `--terse` exists.

### Techniques borrowed

| From | Technique | In examen |
|---|---|---|
| Anthropic research system | Classify the question (straightforward, depth, breadth) and size the search effort | Planner returns a kind; 1, 3 or 5 searches |
| Anthropic CitationAgent | Citations added in a separate pass; text must stay byte-identical | `--cite-pass`; code rejects any word change |
| Google TTD-DR | Draft first, then search against the draft's gaps | Unsupported sentences become next round's search topics |
| ALCE, DEER | Separate uncited claims from wrongly cited ones | `uncited`, `unknown_cites`, `over_cited` reported apart |
| Citation-verifier benchmark | Test the judge on adversarial edits, report error types | Calibration has six kinds incl. negation, padding and reworded truths |

Considered and not built yet: evidence IDs per outline section (WebWeaver), context rebuild per
researcher (ReSum), several candidate drafts per round (TTD-DR self-evolution), splitting into
atomic facts (FActScore/VeriScore).

### Review findings and fixes

| Finding | Fix |
|---|---|
| Wikipedia returned 1 page per search (API returns one full extract per request) | One request per page; pages cut at 8,000 characters; cache key includes k |
| A rewrite won by adding more supported sentences; pasted text was counted but ignored | The supported count only guards against drops; gains come from checklist or share; any rise in pasted sentences rejects the rewrite |
| Headings were never checked | Headings are scored like any sentence |
| `[a, b]`, `【x】`, `(source: x)`, titles not read as citations | All read; titles resolve to pages; unknown ids counted apart |
| Citing many pages gave many chances to pass; facts from two pages could never pass | One check against all cited pages together; more than three cited counts as unsupported |
| A held-back item ("gives a source for every sentence") leaked through the uncited list | Items about sources are never held back |
| Single run compared to a 3-run mean; numbers could slide down round by round | Every version scored three times; no drop below the best or the first draft |
| Budget only checked between rounds | Checked before every call |
| Pages never searched could be cited | Only pages found during the run count |
| "true"/"yes" answers read as no | Read as yes |

### A finding from the fixes

With the stand-in examiner, the loop on the one-agent set-up cut a true sentence the examiner had
wrongly rejected, and lost an answer (8 of 10 instead of 9 of 10). Calibration only used copied
true claims, so it never measured this. It now includes reworded true claims and a limit on
rejected truths.

## 7. Making a local examiner trustworthy (2026-10-28)

No Claude key on this machine, and both gemma3 models failed calibration, mostly by letting false
claims through. Two ideas from the research, both cheap:

- **Code checks in front of the model** (`guarded:`). The lesson from section 2: what kept loops
  honest was checking by code the agent cannot argue with. Numbers and proper names in a claim must
  be on the page; a "not" in the claim must be matched by one on the page. Code can only veto.
- **A panel** (`panel:a+b`), after PoLL: a claim is backed only if every member agrees. gemma3 4B and
  12B miss different kinds of false claim, so requiring both should cut what slips through.

The risk is fitting checks to the test. So calibration gained three kinds the checks were not
designed for (a changed verb, a one-word place swap, a changed number word), and an examiner must
let through no more than 10% of those on their own. One honest caveat: the name check also catches
place swaps, since a place is a name. Verb and number-word changes reach the model untouched.
