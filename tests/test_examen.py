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
        self.assertEqual(out, ["First one.", "Second one.", "Third"])

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
        self.src = FixtureSource()
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
        self.assertLess(rounds[0]["metrics"]["supported_share"], 1.0)
        self.assertTrue(rounds[1]["kept"])
        self.assertNotIn("Experts widely agree", r["report"])
        self.assertNotIn(UNCITED, r["report"])
        self.assertEqual(r["final"]["supported_share"], 1.0)
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
                return Reply({"supported": payload["claim"] in payload["source"]}, 1)

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

    def test_bench_prints_a_table(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self._run("bench", "--limit", "1", "--repeats", "1", "--writer", "fake-flawed", "--receipts", d)
        self.assertEqual(code, 0)
        self.assertIn("team+loop", out)
        self.assertIn("same on", out)


if __name__ == "__main__":
    unittest.main()
