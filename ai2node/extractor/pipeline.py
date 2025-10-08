from __future__ import annotations

"""Knowledge extraction pipeline.

Parses Java sources using `javalang` to extract a structured view:
- Classes and method signatures
- Lightweight complexity heuristics

"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import javalang

from ai2node.reader.java_reader import JavaFileInfo
from ai2node.llm.provider import build_provider, LLMProvider
from ai2node.utils.config import AppConfig
from ai2node.llm.chunker import batch_items


@dataclass
class MethodMetadata:
    name: str
    signature: str
    description: str = ""
    complexity: str = "Unknown"  # label: Low/Medium/High
    complexity_score: int = 1  # cyclomatic complexity score


@dataclass
class ClassMetadata:
    name: str
    description: str = ""
    methods: List[MethodMetadata] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # internal class names referenced


@dataclass
class ProjectKnowledge:
    project_overview: str
    modules: List[ClassMetadata]

    def to_dict(self) -> Dict[str, object]:
        """Serialize to the required JSON structure for output."""
        return {
            "projectOverview": self.project_overview,
            "modules": [
                {
                    "name": c.name,
                    "description": c.description,
                    "dependencies": c.dependencies,
                    "methods": [
                        {
                            "name": m.name,
                            "signature": m.signature,
                            "description": m.description,
                            "complexity": m.complexity,
                            "complexityScore": m.complexity_score,
                        }
                        for m in c.methods
                    ],
                }
                for c in self.modules
            ],
        }


def _method_signature(node: javalang.tree.MethodDeclaration) -> str:
    """Reconstruct a readable Java method signature.

    Note: This is a best-effort reconstruction focused on clarity, not exact
    fidelity (e.g., omits generics/annotations for brevity in reports).
    """
    params = ", ".join([f"{p.type.name} {p.name}" for p in node.parameters])
    ret = getattr(node, "return_type", None)
    ret_s = ret.name if ret else "void"
    return f"public {ret_s} {node.name}({params})"


def _cyclomatic_complexity(method: javalang.tree.MethodDeclaration) -> int:
    """Estimate cyclomatic complexity using AST control-flow constructs.

    Starts at 1 and increments for each decision point.
    """
    score = 1
    if not getattr(method, "body", None):
        return score

    def visit(node):
        nonlocal score
        if node is None:
            return
        # Decision structures
        # Use class name checks to avoid AttributeError on nodes that may not
        # exist in some javalang versions (e.g., Conditional/Ternary expr names).
        node_type = type(node).__name__
        if node_type in {"IfStatement", "ForStatement", "WhileStatement", "DoStatement"}:
            score += 1
        if node_type == "SwitchStatement":
            # each case is a branch
            score += len(getattr(node, "cases", []) or [])
        if node_type == "CatchClause":
            score += 1
        if node_type in {"TernaryExpression", "ConditionalExpression"}:
            score += 1
        if isinstance(node, javalang.tree.BinaryOperation):
            if node.operator in {"&&", "||"}:
                score += 1

        # Recurse into children
        for child_name, child in getattr(node, "__dict__", {}).items():
            if child_name.startswith("_"):
                continue
            if isinstance(child, list):
                for it in child:
                    visit(it)
            else:
                visit(child)

    for stmt in method.body:
        visit(stmt)
    return score


def _complexity_label(score: int) -> str:
    if score <= 5:
        return "Low"
    if score <= 10:
        return "Medium"
    return "High"


def _collect_type_names_from_class(type_decl) -> Set[str]:
    """Collect referenced type names from fields and method signatures."""
    refs: Set[str] = set()
    # Fields
    for field in getattr(type_decl, "fields", []) or []:
        ftype = getattr(field, "type", None)
        if getattr(ftype, "name", None):
            refs.add(ftype.name)
    # Method params and returns
    for m in getattr(type_decl, "methods", []) or []:
        for p in getattr(m, "parameters", []) or []:
            if getattr(p.type, "name", None):
                refs.add(p.type.name)
        rtype = getattr(m, "return_type", None)
        if getattr(rtype, "name", None):
            refs.add(rtype.name)
    return refs


def extract_metadata(java_files: List[JavaFileInfo], config: AppConfig | None = None, provider: LLMProvider | None = None) -> ProjectKnowledge:
    """Extract class and method metadata from Java files.

    Errors while parsing individual files are tolerated (skipped) to keep the
    pipeline robust across diverse real-world projects.
    """
    modules: List[ClassMetadata] = []
    class_names: Set[str] = set()

    for f in java_files:
        try:
            code = Path(f.path).read_text(encoding="utf-8", errors="ignore")
            tree = javalang.parse.parse(code)
        except Exception:
            continue
        for type_decl in getattr(tree, "types", []) or []:
            if not hasattr(type_decl, "name"):
                continue
            class_names.add(type_decl.name)
            
    # Second pass: build class metadata and dependencies with knowledge of all class names
    for f in java_files:
        try:
            code = Path(f.path).read_text(encoding="utf-8", errors="ignore")
            tree = javalang.parse.parse(code)
        except Exception:
            continue
        for type_decl in getattr(tree, "types", []) or []:
            if not hasattr(type_decl, "name"):
                continue
            cls = ClassMetadata(name=type_decl.name, description="")
            # Dependencies: intersect referenced types with internal class names
            refs = _collect_type_names_from_class(type_decl)
            cls.dependencies = sorted([r for r in refs if r in class_names and r != cls.name])
            for node in getattr(type_decl, "methods", []) or []:
                try:
                    sig = _method_signature(node)
                except Exception:
                    sig = node.name
                score = _cyclomatic_complexity(node)
                cls.methods.append(
                    MethodMetadata(
                        name=node.name,
                        signature=sig,
                        description="",
                        complexity=_complexity_label(score),
                        complexity_score=score,
                    )
                )
            modules.append(cls)

    overview = "Auto-generated overview. Use LLM provider to enrich."

    # Optional LLM enrichment (class-level summaries only for cost control)
    if config is not None and provider is not None:
        # Build prompts in small batches
        prompts: List[str] = []
        for c in modules:
            sigs = "\n".join([m.signature for m in c.methods][:20])
            prompts.append(
                (
                    f"You are summarizing a Java class for documentation.\n"
                    f"Class: {c.name}\n"
                    f"Dependencies: {', '.join(c.dependencies) if c.dependencies else 'None'}\n"
                    f"Method signatures:\n{sigs}\n"
                    f"Write a concise 1-2 sentence description of the class purpose."
                )
            )
        for idx, prompt in enumerate(prompts):
            resp = provider.complete(prompt)
            # Assign description back to class by index
            if idx < len(modules):
                modules[idx].description = (resp.text or "").strip()[:500]
        # Project overview from class names
        class_list = ", ".join([c.name for c in modules[:30]])
        ov_prompt = (
            "Summarize this Java project in 1-2 sentences based on class names: "
            + class_list
        )
        resp = provider.complete(ov_prompt)
        overview = (resp.text or overview).strip()[:600]

    knowledge = ProjectKnowledge(project_overview=overview, modules=modules)
    return knowledge


def save_knowledge(knowledge: ProjectKnowledge, path: Path) -> None:
    """Write knowledge JSON to disk using an explicit encoding."""
    path.write_text(json.dumps(knowledge.to_dict(), indent=2), encoding="utf-8")


