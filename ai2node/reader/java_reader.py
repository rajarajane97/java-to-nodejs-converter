from __future__ import annotations

"""Java source code reader and categorizer.

Responsibilities:
- Recursively walk a codebase starting at a root directory
- Apply exclude glob patterns to skip irrelevant/large content
- Enforce per-file size limits to avoid heavy IO and token blow-ups
- Categorize Java files using simple heuristics (names and path segments)

Why these heuristics?
- They are fast, easy to reason about, and avoid coupling to specific
  frameworks (e.g., Spring annotations) at this stage. They provide enough
  signal for downstream selection of representative classes.
"""

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, Iterable, List, Optional, Tuple


JAVA_EXTENSIONS = {".java"}


@dataclass
class JavaFileInfo:
    path: str
    size_bytes: int
    category: str

    def to_dict(self) -> Dict[str, object]:
        """Convert to JSON-serializable dictionary for reporting/storage."""
        return {
            "path": self.path,
            "sizeBytes": self.size_bytes,
            "category": self.category,
        }


class JavaCodebaseReader:
    def __init__(
        self,
        root_dir: Path,
        exclude_globs: Iterable[str],
        max_file_size_kb: int,
        categorization_rules: Iterable[str],
    ) -> None:
        self.root_dir = root_dir
        self.exclude_globs = list(exclude_globs)
        self.max_file_size_kb = max_file_size_kb
        self.categorization_rules = list(categorization_rules)

    def _is_excluded(self, path: Path) -> bool:
        """Check if a path matches any exclude pattern.

        Note: We use fnmatch over the POSIX path string for consistent pattern
        matching across platforms (Windows vs UNIX separators).
        """
        rel = str(path.as_posix())
        for pattern in self.exclude_globs:
            if fnmatch.fnmatch(rel, pattern):
                return True
        return False

    def _categorize(self, file_path: Path) -> str:
        """Guess a file category based on filename and path segments.

        This is intentionally simple. If the project follows common conventions,
        it produces sufficiently accurate labels without parsing source.
        """
        name = file_path.name
        for rule in self.categorization_rules:
            if rule.lower() in name.lower():
                return rule
        # Heuristic: packages
        parts = [p.lower() for p in file_path.parts]
        if "controller" in parts:
            return "Controller"
        if "service" in parts:
            return "Service"
        if "repository" in parts or "repo" in parts:
            return "Repository"
        if "dao" in parts or "mapper" in parts:
            return "DAO"
        if "model" in parts or "entity" in parts:
            return "Model"
        return "Unknown"

    def scan(self) -> List[JavaFileInfo]:
        """Return a list of discovered Java files after filters.

        Performance considerations:
        - Prune directories early to avoid descending into excluded trees
        - Use stat() once per candidate file to avoid re-reading
        - Avoid reading file contents here; defer to later stages as needed
        """
        start = perf_counter()
        results: List[JavaFileInfo] = []
        max_bytes = self.max_file_size_kb * 1024

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # Apply exclude on directories to prune traversal
            pruned_dirnames = []
            for d in dirnames:
                full = Path(dirpath) / d
                if self._is_excluded(full):
                    continue
                pruned_dirnames.append(d)
            dirnames[:] = pruned_dirnames

            for fname in filenames:
                path = Path(dirpath) / fname
                if path.suffix.lower() not in JAVA_EXTENSIONS:
                    continue
                if self._is_excluded(path):
                    continue
                try:
                    size = path.stat().st_size
                except FileNotFoundError:
                    continue
                if size > max_bytes:
                    continue
                results.append(
                    JavaFileInfo(
                        path=str(path.resolve()),
                        size_bytes=size,
                        category=self._categorize(path),
                    )
                )

        _ = perf_counter() - start  # reserved for reporting
        return results


