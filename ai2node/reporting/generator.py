from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ai2node.converter.convert import ConversionResult
from ai2node.extractor.pipeline import ProjectKnowledge

"""Reporting generator.

Renders human-readable TXT and HTML reports from conversion results along with
aggregate performance and token usage. Uses Jinja2 templates to keep
presentation concerns separate from logic.
"""


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int


def generate_reports(
    results: List[ConversionResult],
    total_ms: float,
    token_usage: TokenUsage,
    template_dir: Path,
    out_dir: Path,
    knowledge: ProjectKnowledge | None = None,
) -> None:
    """Renders TXT/HTML reports to `out_dir`.

    This function accepts explicit paths to avoid relying on implicit CWD.
    """
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=select_autoescape(["html"]))
    txt_t = env.get_template("report.txt.j2")
    html_t = env.get_template("report.html.j2")

    out_dir.mkdir(parents=True, exist_ok=True)
    def tree(root: Path) -> List[str]:
        lines: List[str] = []
        base_len = len(str(root))
        for p in sorted(root.rglob('*')):
            rel = str(p)[base_len+1:]
            depth = rel.count(os.sep)
            indent = '  ' * depth
            entry = f"{indent}{p.name}{'/' if p.is_dir() else ''}"
            lines.append(entry)
        return lines

    # Attempt to include source/output trees if under conventional dirs
    src_root = None
    out_root = None
    for r in results:
        try:
            src_root = Path(r.source).parents[2]
            out_root = Path(r.target).parent
            break
        except Exception:
            continue

    model = {
        "results": results,
        "totalMs": total_ms,
        "totalInputTokens": token_usage.input_tokens,
        "totalOutputTokens": token_usage.output_tokens,
        "knowledge": knowledge.to_dict() if knowledge else None,
        "srcTree": tree(src_root) if src_root and src_root.exists() else None,
        "outTree": tree(out_root) if out_root and out_root.exists() else None,
    }

    (out_dir / "conversion_report.txt").write_text(txt_t.render(**model), encoding="utf-8")
    (out_dir / "conversion_report.html").write_text(html_t.render(**model), encoding="utf-8")


