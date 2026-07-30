from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Generic, Iterable, TypeVar


T = TypeVar("T")


class JsonConfigStore(Generic[T]):
    """Validated JSON-list storage with atomic replacement and one backup."""

    def __init__(
        self,
        path: Path,
        loader: Callable[[dict[str, object]], T],
        dumper: Callable[[T], dict[str, object]],
    ) -> None:
        self.path = path
        self.loader = loader
        self.dumper = dumper

    @property
    def backup_path(self) -> Path:
        return self.path.with_suffix(f"{self.path.suffix}.bak")

    def load(self) -> list[T]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, list):
            raise ValueError(f"{self.path.name} must contain a JSON list")
        return [self.loader(item) for item in raw]

    def save(self, items: Iterable[T]) -> None:
        materialized = list(items)
        payload = [self.dumper(item) for item in materialized]
        self.path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            if self.path.exists():
                shutil.copy2(self.path, self.backup_path)
            os.replace(temporary_path, self.path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

