PY = PYTHONPATH=src python3 -m examen
OLLAMA_HOST ?= http://127.0.0.1:11434

test:
	PYTHONPATH=src python3 -m unittest discover -s tests

demo:
	$(PY) demo

bench:
	$(PY) bench --writer fake-flawed

# Real models through a running Ollama server. Test examiners first; the bench refuses an untested one.
calibrate-local:
	OLLAMA_HOST=$(OLLAMA_HOST) $(PY) calibrate --examiner ollama:gemma3:12b
	OLLAMA_HOST=$(OLLAMA_HOST) $(PY) calibrate --examiner ollama:gemma3:latest

# The same models with code checks in front, and both together as a panel.
calibrate-guarded:
	OLLAMA_HOST=$(OLLAMA_HOST) $(PY) calibrate --examiner guarded:ollama:gemma3:12b
	OLLAMA_HOST=$(OLLAMA_HOST) $(PY) calibrate --examiner "guarded:panel:ollama:gemma3:12b+ollama:gemma3:latest"

EXAMINER ?= claude:claude-opus-5-5
WRITER ?= ollama:gemma3:12b
bench-live:
	OLLAMA_HOST=$(OLLAMA_HOST) $(PY) bench --writer $(WRITER) --examiner $(EXAMINER) --require-trusted

.PHONY: test demo bench calibrate-local calibrate-guarded bench-live
