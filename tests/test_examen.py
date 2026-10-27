import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from examen.bench import bench
from examen.calibrate import calibrate, make_labels
from examen.cli import main
from examen.loop import Config, Run, run
from examen.models import PLANTED, UNCITED, FakeModel, Model, OllamaModel, Reply, clauses, load_model
from examen.prompts import parse_json, render
from examen.receipts import Receipts
from examen.score import accept, copied, key_recall, make_checklist, noise, score_report
from examen.sources import FixtureSource, WikipediaSource, load_corpus
from examen.text import claims, overlap, sentences

CORPUS = load_corpus()
Q1 = CORPUS["questions"][0]


class TextTests(unittest.TestCase):
    def test_sentences_skip_headings_and_bullets(self):
        out = sentences("# Title\n- First one. Second one.\n1. Third")
        self.assertEqual(out, ["Title", "First one.", "Second one.", "Third"])

    def test_claims_strip_citations(self):
        c = claims("The tower is 31 metres tall [seld-lighthouse]. Hi.")
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0].cites, ["seld-lighthouse"])
        self.assertEqual(c[0].text, "The tower is 31 metres tall.")

    def test_overlap_ignores_filler(self):
        self.assertEqual(overlap("the lighthouse of Seld", "Seld lighthouse"), 1.0)


class CorpusTests(unittest.TestCase):
    def test_every_answer_key_is_in_the_corpus(self):
        text = " ".join(d["text"].lower() for d in CORPUS["docs"])
        for q in CORPUS["questions"]:
            for k in q["keys"]:
                self.assertIn(k, text, q["id"])

    def test_most_questions_need_more_than_one_page(self):
        self.assertGreaterEqual(sum(len(q["needs"]) >= 2 for q in CORPUS["questions"]), 9)
        ids = {d["id"] for d in CORPUS["docs"]}
        for q in CORPUS["questions"]:
            self.assertTrue(set(q["needs"]) <= ids)

    def test_search_finds_the_right_page(self):
        top = FixtureSource().search("puffin colony breeding pairs", 2)
        self.assertEqual(top[0].id, "little-mar")


class PromptTests(unittest.TestCase):
    def test_parse_json_from_chatter(self):
        self.assertEqual(parse_json('Sure! ```json\n{"a": "x}"}\n``` done'), {"a": "x}"})
        self.assertEqual(parse_json('{"q": "she said \\"hi\\" {"}'), {"q": 'she said "hi" {'})
        self.assertEqual(parse_json("no json here"), {})
        self.assertEqual(parse_json("[1, 2]"), {})

    def test_every_role_has_a_prompt(self):
        for role in ["checklist", "plan", "notes", "write", "write_from_docs", "support", "check"]:
            system, user = render(role, {"x": 1})
            self.assertIn("JSON", system)
        with self.assertRaises(KeyError):
            render("nope", {})

    def test_clauses(self):
        self.assertEqual(len(clauses(Q1["question"])), 2)


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.src = FixtureSource(preload=True)
        self.ex = FakeModel()

    def test_made_up_and_unsourced_sentences_are_caught(self):
        report = (PLANTED.format(src="seld-lighthouse") + " " + UNCITED + " "
                  "The Seld Lighthouse was built in 1871 by the engineer Thomas Varga [seld-lighthouse].")
        s = score_report(report, Q1["question"], [], self.ex, self.src)
        self.assertEqual(s.metrics["claims"], 3)
        self.assertEqual(s.metrics["supported"], 1)
        self.assertEqual(s.metrics["uncited"], 1)
        fb = s.feedback()
        self.assertEqual(len(fb["unsupported"]), 1)
        self.assertEqual(fb["uncited"], [UNCITED])

    def test_unknown_source_id_is_not_support(self):
        s = score_report("The light was automated in 1979 [no-such-page].", "q", [], self.ex, self.src)
        self.assertEqual(s.metrics["supported"], 0)

    def test_changed_number_is_not_support(self):
        s = score_report("The light was automated in 1982 [seld-lighthouse].", "q", [], self.ex, self.src)
        self.assertEqual(s.metrics["supported"], 0)

    def test_copy_flag(self):
        src = "The Seld Lighthouse was built in 1871 by the engineer Thomas Varga."
        self.assertTrue(copied(src, src))
        self.assertFalse(copied("Thomas Varga, an engineer, put up the tower at Seld in the year 1871.", src))

    def test_checklist_is_frozen_and_split(self):
        a, _ = make_checklist(self.ex, Q1["question"])
        b, _ = make_checklist(self.ex, Q1["question"])
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertTrue(a.hidden)
        self.assertTrue(a.visible)
        self.assertFalse(set(a.hidden) & set(a.visible))

    def test_accept_refuses_a_shrunk_report(self):
        best = {"supported": 6, "visible_pass": 0.5, "supported_share": 0.75}
        smaller = {"supported": 3, "visible_pass": 0.5, "supported_share": 1.0}
        ok, why = accept(best, smaller, {"supported": 0, "visible_pass": 0, "supported_share": 0})
        self.assertFalse(ok)
        self.assertIn("supported fell", why)

    def test_accept_ignores_gains_inside_the_noise(self):
        best = {"supported": 6, "visible_pass": 0.5, "supported_share": 0.75}
        cand = {"supported": 7, "visible_pass": 0.5, "supported_share": 0.78}
        margin = {"supported": 2, "visible_pass": 0.25, "supported_share": 0.1}
        self.assertFalse(accept(best, cand, margin)[0])
        self.assertTrue(accept(best, cand, {k: 0 for k in margin})[0])

    def test_noise_is_the_spread(self):
        class Flaky(Model):
            name = "flaky"
            n = 0

            def ask(self, role, payload):
                self.n += 1
                return Reply({"supported": self.n % 2 == 0, "pass": True}, 1)

        judge = Flaky()
        s = [score_report("The light was automated in 1979 [seld-lighthouse].", "q", [], judge, self.src)
             for _ in range(2)]
        self.assertEqual(noise(s)["supported"], 1)

    def test_key_recall(self):
        self.assertEqual(key_recall("Thomas  Varga built it", ["thomas varga", "1979"]), 0.5)


class LoopTests(unittest.TestCase):
    def test_loop_removes_the_planted_mistakes(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config(),
                    Receipts(d), Q1["keys"])
            rounds = [json.loads(x) for x in (Path(d) / "rounds.jsonl").read_text().splitlines()]
            self.assertTrue((Path(d) / "report.md").exists())
            self.assertTrue((Path(d) / "checklist.json").exists())
        self.assertTrue(rounds[1]["kept"])
        self.assertNotIn("Experts widely agree", r["report"])
        self.assertNotIn(UNCITED, r["report"])
        self.assertGreater(r["final"]["supported_share"], rounds[0]["metrics"]["supported_share"])
        self.assertEqual(r["final"]["uncited"], 0)
        self.assertTrue(r["final"]["correct"])

    def test_writer_never_sees_held_back_items(self):
        ex = FakeModel()
        checklist, _ = make_checklist(ex, Q1["question"])
        self.assertTrue(checklist.hidden)
        runner = Run(Q1["question"], FakeModel(flawed=True), ex, FixtureSource(), Config())
        runner.go()
        seen = json.dumps(runner.seen_by_writer)
        told = [x["payload"].get("feedback", {}) for x in runner.seen_by_writer]
        told = json.dumps([t.get("open_points", []) for t in told if t])
        self.assertIn("open_points", json.dumps(runner.seen_by_writer))  # feedback really was given
        for item in checklist.hidden:
            self.assertNotIn(item, seen)
            # The question's own words are fine to see; being told the held-back item failed is not.
            self.assertNotIn(item.split(":", 1)[-1].strip(" ?"), told)

    def test_invented_quotes_are_dropped(self):
        class Liar(FakeModel):
            def _notes(self, p):
                return {"notes": [{"source": "seld-lighthouse", "quote": "It was painted pink in 1990.", "point": "pink"},
                                  {"source": "nowhere", "quote": "x", "point": "x"}]}

        runner = Run(Q1["question"], Liar(), FakeModel(), FixtureSource(), Config(loop=False))
        runner.go()
        self.assertEqual(runner.notes, [])
        self.assertGreaterEqual(runner.dropped_quotes, 2)

    def test_budget_stops_the_loop(self):
        r = run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config(budget=10))
        self.assertEqual(r["rounds"], 1)
        self.assertEqual(r["stopped"], "budget spent")

    def test_patience_stops_a_stuck_loop(self):
        class Stuck(FakeModel):
            def _write(self, p):
                return {"report": UNCITED}

        r = run(Q1["question"], Stuck(), FakeModel(), FixtureSource(), Config(max_rounds=10, patience=2))
        self.assertEqual(r["stopped"], "no kept gain in 2 rounds")
        self.assertEqual(r["rounds"], 3)

    def test_single_mode_runs(self):
        r = run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config(mode="single"),
                keys=Q1["keys"])
        self.assertEqual(r["mode"], "single")
        self.assertEqual(r["final"]["supported_share"], 1.0)


class BenchAndCalibrationTests(unittest.TestCase):
    def test_bench_has_four_arms(self):
        out = bench(FakeModel(flawed=True), FakeModel(), limit=2, repeats=1)
        self.assertEqual(set(out["summary"]), {"single", "single+loop", "team", "team+loop"})
        self.assertEqual(len(out["rows"]), 8)
        self.assertGreater(out["summary"]["team+loop"]["supported_share"], out["summary"]["team"]["supported_share"])

    def test_labels_are_balanced_and_known(self):
        labels = make_labels(40)
        self.assertEqual(sum(x["label"] for x in labels), 20)
        kinds = {x["kind"] for x in labels}
        self.assertEqual(kinds, {"verbatim", "reworded", "number", "name", "negation", "padding"})
        for x in labels:
            if not x["label"]:
                self.assertNotIn(x["claim"], x["source"])

    def test_fake_examiner_is_not_trusted(self):
        res = calibrate(FakeModel(), make_labels(60))
        self.assertEqual(res["pairs"], 60)
        self.assertEqual(res["self_agreement"], 1.0)
        self.assertGreater(res["false_pass_rate"], 0.10)
        self.assertFalse(res["trusted"])

    def test_perfect_examiner_is_trusted(self):
        class Oracle(Model):
            name = "oracle"

            def ask(self, role, payload):
                claim = payload["claim"].split(": ", 1)[-1] if payload["claim"].startswith("The ") and \
                    " page records this: " in payload["claim"] else payload["claim"]
                return Reply({"supported": claim in payload["source"]}, 1)

        self.assertTrue(calibrate(Oracle(), make_labels(60))["trusted"])


class BackendTests(unittest.TestCase):
    def test_load_model(self):
        self.assertEqual(load_model("fake").name, "fake")
        self.assertEqual(load_model("ollama:gemma3:4b").name, "ollama:gemma3:4b")
        with self.assertRaises(SystemExit):
            load_model("gpt")

    def test_ollama_backend_against_a_local_stand_in(self):
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                H.got = body
                out = json.dumps({"message": {"content": '{"supported": true}'},
                                  "prompt_eval_count": 10, "eval_count": 3}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            m = OllamaModel("gemma3:4b", host=f"http://127.0.0.1:{srv.server_port}")
            r = m.ask("support", {"claim": "a", "source": "a"})
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(r.data, {"supported": True})
        self.assertEqual(r.tokens, 13)
        self.assertEqual(H.got["format"], "json")
        self.assertEqual(H.got["messages"][0]["role"], "system")

    def test_repeats_use_different_seeds_so_wobble_is_real(self):
        seeds = []

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seed = body["options"]["seed"]
                seeds.append(seed)
                # A judge whose answer depends on its seed, like a real sampled model.
                out = json.dumps({"message": {"content": json.dumps({"supported": seed == 7, "pass": True})},
                                  "prompt_eval_count": 1, "eval_count": 1}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            judge = OllamaModel("gemma3", host=f"http://127.0.0.1:{srv.server_port}", seed=7)
            res = calibrate(judge, make_labels(4), runs=2)
            self.assertEqual(len(set(seeds)), 2)
            self.assertLess(res["self_agreement"], 1.0)
            seeds.clear()
            runner = Run(Q1["question"], FakeModel(), judge, FixtureSource(preload=True), Config(loop=False))
            scores = runner._score("The light was automated in 1979 [seld-lighthouse].", [], repeats=3)
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(len(set(seeds)), 3)
        self.assertEqual(noise(scores)["supported"], 1)
        self.assertEqual(judge.seed, 7)  # the original is untouched; repeats use copies

    def test_wikipedia_source_caches(self):
        calls = []

        def opener(params):
            calls.append(params)
            if params.get("list") == "search":
                return {"query": {"search": [{"pageid": 42}]}}
            return {"query": {"pages": {"42": {"title": "Lighthouse", "extract": "A lighthouse is a tower."}}}}

        with tempfile.TemporaryDirectory() as d:
            w = WikipediaSource(d, opener=opener)
            docs = w.search("lighthouse")
            w2 = WikipediaSource(d, opener=opener)
            w2.search("lighthouse")
        self.assertEqual(docs[0].id, "w42")
        self.assertEqual(w.get("w42").title, "Lighthouse")
        self.assertEqual(len(calls), 2)


class CliTests(unittest.TestCase):
    def _run(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_run_warns_about_an_unmeasured_examiner(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = self._run("run", "Who founded the Halvey Ferry Company?", "--receipts", d)
        self.assertEqual(code, 0)
        self.assertIn("has not been measured", err)
        self.assertIn("halvey-ferry", out)

    def test_calibrate_then_warn_about_a_weak_examiner(self):
        with tempfile.TemporaryDirectory() as d:
            self._run("calibrate", "--receipts", d)
            _, _, err = self._run("run", "Who founded the Halvey Ferry Company?", "--receipts", d, "--no-loop")
        self.assertIn("Treat its verdicts as rough", err)

    def test_calibrate_runs_option(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self._run("calibrate", "--receipts", d, "--pairs", "8", "--runs", "3")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["pairs"], 8)

    def test_bench_prints_a_table(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self._run("bench", "--limit", "1", "--repeats", "1", "--writer", "fake-flawed", "--receipts", d)
        self.assertEqual(code, 0)
        self.assertIn("team+loop", out)
        self.assertIn("same on", out)


class ReviewFixTests(unittest.TestCase):
    """One test per hole the code review found, plus the ideas borrowed from other projects."""

    def setUp(self):
        self.src = FixtureSource(preload=True)
        self.ex = FakeModel()

    def score(self, report, items=()):
        return score_report(report, "q", list(items), self.ex, self.src)

    def test_citation_styles_real_models_use(self):
        from examen.text import find_cites
        self.assertEqual(find_cites("x [a, b] y [c; d]"), ["a", "b", "c", "d"])
        self.assertEqual(find_cites("x 【ostra】 y (source: kessick)"), ["ostra", "kessick"])
        s = self.score("The light was automated in 1979 [Seld Lighthouse].")
        self.assertEqual(s.metrics["supported"], 1)
        s = self.score("The light was automated in 1979 [1].")
        self.assertEqual((s.metrics["supported"], s.metrics["unknown_cites"]), (0, 1))

    def test_made_up_heading_is_checked(self):
        s = self.score("# The lighthouse was designed by Ada Lovelace in 1802 [seld-lighthouse]")
        self.assertEqual((s.metrics["claims"], s.metrics["supported"]), (1, 0))

    def test_abbreviations_do_not_split_and_cited_sentences_do(self):
        self.assertEqual(len(sentences("Dr. Varga built it in 1871. It is tall.")), 2)
        c = claims("The light was automated in 1979 [seld-lighthouse]. it was also painted pink by pirates.")
        self.assertEqual([x.cites for x in c], [["seld-lighthouse"], []])

    def test_too_many_citations_count_as_unsupported(self):
        s = self.score("The light was automated in 1979 [seld-lighthouse, ostra, kessick, wool-fair].")
        self.assertEqual((s.metrics["supported"], s.metrics["over_cited"]), (0, 1))

    def test_a_claim_from_two_pages_passes_when_both_are_cited(self):
        claim = "Thomas Varga built the Seld Lighthouse and trained under Helen Ashdown"
        self.assertEqual(self.score(claim + " [thomas-varga].").metrics["supported"], 1)
        two = self.score(claim + " and it was automated in 1979 [thomas-varga, seld-lighthouse].")
        self.assertEqual(two.metrics["supported"], 1)
        self.assertEqual(self.score(claim + " and it was automated in 1979 [thomas-varga].").metrics["supported"], 0)

    def test_pages_not_found_this_run_cannot_be_cited(self):
        fresh = FixtureSource()
        s = score_report("The light was automated in 1979 [seld-lighthouse].", "q", [], self.ex, fresh)
        self.assertEqual(s.metrics["supported"], 0)
        fresh.search("lighthouse automated", 4)
        s = score_report("The light was automated in 1979 [seld-lighthouse].", "q", [], self.ex, fresh)
        self.assertEqual(s.metrics["supported"], 1)

    def test_yes_and_true_strings_count(self):
        from examen.text import truthy
        self.assertTrue(truthy("Yes") and truthy("true") and truthy(True))
        self.assertFalse(truthy("no") or truthy(None) or truthy(1))

    def test_more_pasting_is_not_kept(self):
        best = {"supported": 6, "visible_pass": 0.5, "supported_share": 0.75, "copied": 0}
        cand = {"supported": 8, "visible_pass": 1.0, "supported_share": 1.0, "copied": 3}
        ok, why = accept(best, cand, {"supported": 0, "visible_pass": 0, "supported_share": 0})
        self.assertFalse(ok)
        self.assertIn("pasted", why)

    def test_a_bigger_count_alone_is_not_a_gain(self):
        best = {"supported": 6, "visible_pass": 0.5, "supported_share": 1.0}
        cand = {"supported": 9, "visible_pass": 0.5, "supported_share": 1.0}
        self.assertFalse(accept(best, cand, {"supported": 0, "visible_pass": 0, "supported_share": 0})[0])

    def test_slow_slide_below_the_first_draft_is_refused(self):
        first = {"supported": 6, "visible_pass": 0.5, "supported_share": 0.8}
        best = {"supported": 5, "visible_pass": 0.75, "supported_share": 0.8}
        cand = {"supported": 4, "visible_pass": 1.0, "supported_share": 0.8}
        margin = {"supported": 1, "visible_pass": 0, "supported_share": 0}
        ok, why = accept(best, cand, margin, first)
        self.assertFalse(ok)
        self.assertIn("first draft", why)

    def test_split_seed_rotates_held_back_items(self):
        q = "Which charity runs the Seld Lighthouse, who has been its director since 2015, and what did it restore?"
        splits = {tuple(make_checklist(self.ex, q, salt=str(i))[0].hidden) for i in range(10)}
        self.assertGreater(len(splits), 1)
        r = run(q, FakeModel(), FakeModel(), FixtureSource(), Config(loop=False, split_seed="a"))
        self.assertEqual(r["held_back"], 1)

    def test_items_about_sources_are_never_held_back(self):
        for q in CORPUS["questions"]:
            cl, _ = make_checklist(self.ex, q["question"])
            self.assertFalse(any("source" in h for h in cl.hidden), q["id"])
            self.assertTrue(cl.hidden, q["id"])

    def test_budget_is_checked_before_every_call(self):
        r = run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config(budget=100))
        self.assertEqual(r["stopped"], "budget spent")
        self.assertLess(r["agent_tokens"], 1000)
        r = run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config(budget=3000))
        self.assertLessEqual(r["agent_tokens"], 3000 + 2500)  # at most one call past the cap

    def test_citation_pass_adds_tags_only(self):
        r = run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config(cite_pass=True),
                keys=Q1["keys"])
        self.assertIn("[seld-lighthouse]", r["report"])
        self.assertEqual(r["cite_pass_rejected"], 0)

        class Sneaky(FakeModel):
            def _cite(self, p):
                return {"report": p["report"] + " The lighthouse is haunted [seld-lighthouse]."}

        r = run(Q1["question"], Sneaky(), FakeModel(), FixtureSource(), Config(cite_pass=True, loop=False))
        self.assertEqual(r["cite_pass_rejected"], 1)
        self.assertNotIn("haunted", r["report"])

    def test_terse_feedback_names_no_checklist_item(self):
        runner = Run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config(terse=True))
        runner.go()
        told = [x["payload"]["feedback"] for x in runner.seen_by_writer if x["payload"].get("feedback")]
        self.assertTrue(told)
        for fb in told:
            self.assertTrue(all(p == "Some parts of the question are not answered yet." for p in fb["open_points"]))

    def test_failed_sentences_become_search_topics(self):
        runner = Run(Q1["question"], FakeModel(flawed=True), FakeModel(), FixtureSource(), Config())
        runner.go()
        gaps = [x["payload"]["gaps"] for x in runner.seen_by_writer if x["role"] == "plan"]
        self.assertTrue(any("Experts widely agree" in g for gs in gaps for g in gs))

    def test_effort_follows_the_kind_of_question(self):
        runner = Run("Who founded the Halvey Ferry Company?", FakeModel(), FakeModel(), FixtureSource(),
                     Config(loop=False))
        r = runner.go()
        self.assertEqual(r["kind"], "straightforward")
        self.assertEqual(sum(x["role"] == "notes" for x in runner.seen_by_writer), 1)

    def test_wikipedia_fetches_each_page_and_cuts_long_ones(self):
        calls = []

        def opener(params):
            calls.append(params)
            if params.get("list") == "search":
                return {"query": {"search": [{"pageid": 1}, {"pageid": 2}][: params["srlimit"]]}}
            pid = params["pageids"]
            return {"query": {"pages": {pid: {"title": f"P{pid}", "extract": "x. " * 9000}}}}

        with tempfile.TemporaryDirectory() as d:
            w = WikipediaSource(d, opener=opener)
            docs = w.search("q", 2)
            one = WikipediaSource(d, opener=opener).search("q", 1)
        self.assertEqual([x.id for x in docs], ["w1", "w2"])
        self.assertTrue(all("|" not in c.get("pageids", "") for c in calls))
        self.assertEqual(len(docs[0].text), WikipediaSource.MAX_CHARS)
        self.assertEqual(len(one), 1)  # a different k is a different search, not the cached one

    def test_claude_sends_effort_only_where_supported(self):
        from examen.models import ClaudeModel

        class Msg:
            stop_reason, model = "end_turn", "claude-opus-5-5"
            content = [type("B", (), {"type": "text", "text": '{"pass": true}'})()]
            usage = type("U", (), {"input_tokens": 5, "output_tokens": 2})()

        sent = []
        client = type("C", (), {})()
        client.beta = type("B", (), {})()
        client.beta.messages = type("M", (), {"create": lambda self, **kw: sent.append(kw) or Msg()})()
        for model in ("claude-opus-5-5", "claude-3-haiku"):
            m = object.__new__(ClaudeModel)
            m.client, m.model, m.effort, m.name, m.served = client, model, "low", "claude:" + model, set()
            self.assertEqual(m.ask("check", {"x": 1}).data, {"pass": True})
        self.assertEqual(sent[0]["fallbacks"], "default")
        self.assertIn("output_config", sent[0])
        self.assertNotIn("output_config", sent[1])
        self.assertNotIn("fallbacks", sent[1])

    def test_demo_writes_where_it_is_told(self):
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(io.StringIO()):
                main(["demo", "--receipts", d])
            self.assertTrue(any(Path(d).iterdir()))


if __name__ == "__main__":
    unittest.main()
