from __future__ import annotations

"""Java → Node.js conversion helpers.

This module renders minimal Express scaffolds for Controller/Service/DAO using
Jinja2 templates. The focus is on structure preservation and traceability rather
than perfect behavioral translation, which would require deeper semantic
analysis beyond POC scope.
"""

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ai2node.reader.java_reader import JavaFileInfo
import javalang


@dataclass
class ConversionResult:
    source: str
    target: str
    category: str
    bytes_in: int
    bytes_out: int
    elapsed_ms: float


def _select_targets(files: List[JavaFileInfo]) -> Dict[str, List[JavaFileInfo]]:
    """Group files by category for bulk conversion."""
    picks: Dict[str, List[JavaFileInfo]] = {"Controller": [], "Service": [], "DAO": []}
    for f in files:
        if f.category in picks:
            picks[f.category].append(f)
    return picks


def _camel_to_kebab(name: str) -> str:
    out = []
    for ch in name:
        if ch.isupper() and out:
            out.append('-')
        out.append(ch.lower())
    return ''.join(out)


def _infer_http_method(method_name: str) -> str:
    n = method_name.lower()
    if n.startswith(("get", "find", "list", "fetch")):
        return "get"
    if n.startswith(("create", "add", "post")):
        return "post"
    if n.startswith(("update", "put")):
        return "put"
    if n.startswith(("delete", "remove", "del")):
        return "delete"
    return "post"


def _infer_route_path(class_name: str, method_name: str) -> str:
    # Basic heuristic: /{class-kebab}/{method-kebab}
    return f"/{_camel_to_kebab(class_name)}/{_camel_to_kebab(method_name)}"


def _extract_controller_model(java_source: str) -> Dict[str, Any]:
    """Parse Java and build a controller model with routes.

    Attempts to read Spring-style annotations; falls back to method-name heuristics.
    """
    try:
        tree = javalang.parse.parse(java_source)
    except Exception:
        return {"className": "Controller", "routes": []}
    routes: List[Dict[str, Any]] = []
    class_name = "Controller"
    service_name = None
    for type_decl in getattr(tree, "types", []) or []:
        if not hasattr(type_decl, "name"):
            continue
        class_name = type_decl.name
        # Heuristic mapping: FooController -> FooService
        base = class_name
        if base.lower().endswith("controller"):
            base = base[: -len("controller")]
        candidate = base + "Service"
        service_name = candidate
        base_path = ""
        # Class-level @RequestMapping("/x")
        for ann in getattr(type_decl, "annotations", []) or []:
            if getattr(ann, "name", "").endswith("RequestMapping"):
                # support value/path attributes
                path_val = None
                for attr in getattr(ann, "element", []) or []:
                    pass
                # best-effort parse of annotation values
                val = getattr(ann, "element", None)
                if hasattr(val, "value"):
                    path_val = getattr(val, "value", None)
                if isinstance(path_val, str):
                    base_path = path_val
        for m in getattr(type_decl, "methods", []) or []:
            http = None
            path = None
            # Try method annotations
            for ann in getattr(m, "annotations", []) or []:
                an = getattr(ann, "name", "")
                if an.endswith("GetMapping"):
                    http = "get"
                elif an.endswith("PostMapping"):
                    http = "post"
                elif an.endswith("PutMapping"):
                    http = "put"
                elif an.endswith("DeleteMapping"):
                    http = "delete"
                elif an.endswith("RequestMapping"):
                    # Might specify method via attributes; default to GET
                    http = http or "get"
                # Path extraction best-effort
                val = getattr(ann, "element", None)
                if hasattr(val, "value") and isinstance(val.value, str):
                    path = val.value
            if http is None:
                http = _infer_http_method(m.name)
            if path is None:
                path = _infer_route_path(class_name, m.name)
            full_path = (base_path.rstrip("/") + path) if base_path else path
            params = []
            for p in getattr(m, "parameters", []) or []:
                ptype = getattr(getattr(p, "type", None), "name", "Object")
                source = "body"
                for pann in getattr(p, "annotations", []) or []:
                    an = getattr(pann, "name", "")
                    if an.endswith("PathVariable"):
                        source = "path"
                        break
                    if an.endswith("RequestParam"):
                        source = "query"
                        break
                    if an.endswith("RequestBody"):
                        source = "body"
                        break
                params.append({"name": p.name, "type": ptype, "source": source})
            routes.append({
                "http": http,
                "path": full_path,
                "methodName": m.name,
                "params": params,
            })
        break
    return {"className": class_name, "serviceName": service_name, "routes": routes}


def _extract_methods_model(java_source: str) -> Dict[str, Any]:
    try:
        tree = javalang.parse.parse(java_source)
    except Exception:
        return {"className": "Class", "methods": []}
    for type_decl in getattr(tree, "types", []) or []:
        if not hasattr(type_decl, "name"):
            continue
        methods = []
        for m in getattr(type_decl, "methods", []) or []:
            methods.append({
                "name": m.name,
                "params": [
                    {"name": p.name, "type": getattr(getattr(p, "type", None), "name", "Object")}
                    for p in getattr(m, "parameters", []) or []
                ]
            })
        return {"className": type_decl.name, "methods": methods}
    return {"className": "Class", "methods": []}


def _write_app_scaffold(out_dir: Path, controller_files: List[Path]) -> None:
    """Create a minimal Express app that mounts all generated controllers.

    This provides a runnable server for quick validation. Users can integrate
    the generated routes into their projects as needed.
    """
    lines = [
        "const express = require('express');",
        "const app = express();",
        "app.use(express.json());",
    ]
    for p in controller_files:
        rel = "./" + p.name  # same folder
        var_name = p.stem.replace('-', '_')
        lines.append(f"const {var_name} = require('{rel}');")
        lines.append(f"app.use('{ '/' + p.stem.replace('controller', '').replace('_', '-').lower() }', {var_name});")
    lines.append("app.get('/health', (req, res) => res.json({status:'ok'}));")
    lines.append("const port = process.env.PORT || 3000;")
    lines.append("app.listen(port, () => console.log(`Server listening on ${port}`));")
    (out_dir / "app.js").write_text("\n".join(lines), encoding="utf-8")


def convert_to_express(files: List[JavaFileInfo], templates_dir: Path, out_dir: Path) -> List[ConversionResult]:
    """Render Express artifacts from selected Java files.

    We embed the original Java file path in the generated output for auditability
    and easier manual follow-up.
    """
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape([]))
    controller_t = env.get_template("controller.js.j2")
    service_t = env.get_template("service.js.j2")
    dao_t = env.get_template("dao.js.j2")

    out_dir.mkdir(parents=True, exist_ok=True)
    picks = _select_targets(files)
    results: List[ConversionResult] = []
    generated_controllers: List[Path] = []

    mapping = {
        "Controller": (controller_t, "Controller.js"),
        "Service": (service_t, "Service.js"),
        "DAO": (dao_t, "DAO.js"),
    }

    for cat, finfos in picks.items():
        for finfo in finfos:
            tmpl, default_name = mapping[cat]
            start = perf_counter()
            code = Path(finfo.path).read_text(encoding="utf-8", errors="ignore")
            if cat == "Controller":
                model = _extract_controller_model(code)
                fname = f"{model['className']}Controller.js"
                rendered = tmpl.render(java_path=finfo.path, **model)
            else:
                model = _extract_methods_model(code)
                suffix = "Service.js" if cat == "Service" else "DAO.js"
                fname = f"{model['className']}{suffix}"
                rendered = tmpl.render(java_path=finfo.path, **model)
            target_path = out_dir / fname
            target_path.write_text(rendered, encoding="utf-8")
            if cat == "Controller":
                generated_controllers.append(target_path)
            elapsed = (perf_counter() - start) * 1000.0
            results.append(
                ConversionResult(
                    source=finfo.path,
                    target=str(target_path.resolve()),
                    category=cat,
                    bytes_in=finfo.size_bytes,
                    bytes_out=len(rendered.encode("utf-8")),
                    elapsed_ms=elapsed,
                )
            )
    if generated_controllers:
        _write_app_scaffold(out_dir, generated_controllers)
    return results

# Extensibility Notes:
# - To add NestJS support, create templates under
#   `ai2node/converter/templates/nest/` and a `convert_to_nest` function that
#   mirrors this one. Consider generating controllers, providers, and modules.
# - To translate methods more faithfully, parse Java AST (see extractor) and
#   pass structured data into templates instead of raw source.


