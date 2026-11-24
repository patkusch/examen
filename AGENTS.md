# Working in examen

A research agent that checks its own work against an answer sheet it cannot touch

## Run the tests

You need Python 3.11 or newer.

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

Every test should pass before you start and after you finish.

## Where things are

- `src/`: the code
- `tests/`: the tests
- `docs/`: written documentation
- `receipts/`: saved results of earlier runs

## Before you commit

- Make sure the tests pass.
- Put changes people will notice in `CHANGELOG.md`.
- Do not put real passwords, keys or private data in test files or examples. Use made-up ones.
