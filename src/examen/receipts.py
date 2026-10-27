"""Everything a run decided, written to disk as it happens, so any result can be checked later."""
from __future__ import annotations

import json
from pathlib import Path


class Receipts:
    def __init__(self, folder: str | Path | None) -> None:
        self.dir = Path(folder) if folder else None
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def append(self, name: str, row: dict) -> None:
        if self.dir:
            with open(self.dir / name, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def write_json(self, name: str, data) -> None:
        if self.dir:
            (self.dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    def write_text(self, name: str, text: str) -> None:
        if self.dir:
            (self.dir / name).write_text(text)

    def sub(self, name: str) -> "Receipts":
        return Receipts(self.dir / name if self.dir else None)
