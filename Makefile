test:
	PYTHONPATH=src python3 -m unittest discover -s tests

demo:
	PYTHONPATH=src python3 -m examen demo

bench:
	PYTHONPATH=src python3 -m examen bench --writer fake-flawed

.PHONY: test demo bench
