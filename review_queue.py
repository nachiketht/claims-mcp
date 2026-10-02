import json
import os
import tempfile
from pathlib import Path


class ReviewQueue:
    def append(self, record: dict) -> dict:
        raise NotImplementedError


class JsonFileQueue(ReviewQueue):
    def __init__(self, path: str | Path = "data/review_queue.json"):
        self.path = Path(path)

    def append(self, record: dict) -> dict:
        records = self._read()
        for existing in records:
            if (
                existing["employee_id"] == record["employee_id"]
                and existing["request"] == record["request"]
            ):
                return existing
        records.append(record)
        self._replace(records)
        return record

    def _read(self) -> list[dict]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _replace(self, records: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as outfile:
                json.dump(records, outfile)
                outfile.write("\n")
            os.replace(temporary, self.path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
