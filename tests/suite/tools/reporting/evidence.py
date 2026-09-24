from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import urllib.parse

from ..execution.process import write_json


class Evidence:
    def __init__(self, root: Path, secrets: list[str] | None = None):
        self.root = root
        self.secrets: list[str] = []
        self.add_secrets(secrets or [])
        self.root.mkdir(parents=True, exist_ok=True)

    def add_secrets(self, values: Any) -> None:
        variants = set(self.secrets)
        for value in values:
            raw = str(value)
            if not raw:
                continue
            variants.add(raw)
            variants.add(urllib.parse.quote(raw, safe=""))
            variants.add(urllib.parse.quote_plus(raw, safe=""))
        # Replace longer values first so one secret cannot expose the suffix of
        # another when their values overlap.
        self.secrets = sorted((value for value in variants if value), key=len, reverse=True)

    def _safe(self, value: Any) -> Any:
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "<redacted>")
            return value
        if isinstance(value, dict):
            return {str(key): self._safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._safe(item) for item in value]
        return value

    def json(self, relative: str, value: Any) -> str:
        path = self.root / relative
        write_json(path, self._safe(value))
        return str(path)

    def text(self, relative: str, value: str) -> str:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(self._safe(value)), encoding="utf-8")
        return str(path)

    @staticmethod
    def tree_digest(root: Path) -> str:
        digest = hashlib.sha256()
        if not root.exists():
            return "missing"
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode())
            if path.is_symlink():
                digest.update(b"SYMLINK")
                digest.update(str(path.readlink()).encode())
            elif path.is_file():
                digest.update(path.read_bytes())
        return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"manifest is missing or invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value
