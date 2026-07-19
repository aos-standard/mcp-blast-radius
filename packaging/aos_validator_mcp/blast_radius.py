"""
MCP Blast-Radius Auditor — static extraction engine (layers a/b/c inputs).

Layer (a): dependency scan (requirements / pyproject / package.json).
Layer (b): Python AST scan (imports, file I/O, network, env, subprocess).
Layer (c): divergence detection is performed in validate_pure against manifest.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Confidence = Literal["declared", "observed-static", "cannot-determine"]

_ALWAYS_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".egg-info",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "test-results",
}

_PERIPHERAL_SKIP_DIRS = {
    "tests",
    "test",
    "docs",
    "doc",
    "examples",
    "example",
    "scripts",
    "benchmarks",
    ".github",
}

_SKIP_DIRS = _ALWAYS_SKIP_DIRS | _PERIPHERAL_SKIP_DIRS

_SCAN_SCOPE_PRODUCTION = (
    "production package (tests/docs/examples/scripts/benchmarks/.github excluded)"
)
_SCAN_SCOPE_FULL = "full repository (peripheral included)"

_TEST_FILE_EXACT = frozenset({"conftest.py"})

_PATTERNS_PATH = Path(__file__).with_name("blast_radius_patterns.json")

_FILE_WRITE_MODES = frozenset({"w", "a", "x", "w+", "a+", "x+", "wb", "ab", "xb"})
_NETWORK_MODULES = frozenset({"socket", "urllib", "urllib3", "http", "requests", "httpx", "aiohttp"})
_SUBPROCESS_NAMES = frozenset({"system", "popen", "exec", "execv", "execve", "spawn", "call", "run", "Popen"})
_ENV_NAMES = frozenset({"environ", "getenv", "putenv", "unsetenv"})
_PATH_IO_METHODS = frozenset(
    {
        "write_text",
        "write_bytes",
        "read_text",
        "read_bytes",
        "open",
        "unlink",
        "rename",
        "replace",
        "mkdir",
        "rmdir",
    }
)
_MCP_TOOL_DECORATORS = frozenset(
    {
        "tool",
        "list_tools",
        "call_tool",
        "resource",
        "list_resources",
    }
)


@dataclass
class Finding:
    capability: str
    detail: str
    confidence: Confidence
    source_file: str | None = None
    line: int | None = None
    tool_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "detail": self.detail,
            "confidence": self.confidence,
            "source_file": self.source_file,
            "line": self.line,
            "tool_name": self.tool_name,
        }


@dataclass
class BlastRadiusReport:
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    tools: dict[str, list[str]] = field(default_factory=dict)
    scanned_files: int = 0
    python_files: int = 0
    scan_scope: str = _SCAN_SCOPE_PRODUCTION
    excluded_file_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        by_cap: dict[str, list[dict[str, Any]]] = {}
        for f in self.findings:
            by_cap.setdefault(f.capability, []).append(f.to_dict())
        return {
            "dependencies": self.dependencies,
            "capabilities": by_cap,
            "findings": [f.to_dict() for f in self.findings],
            "tools": self.tools,
            "scanned_files": self.scanned_files,
            "python_files": self.python_files,
            "scan_scope": self.scan_scope,
            "excluded_file_count": self.excluded_file_count,
            "limitations": (
                "Static analysis only. Dynamic imports, getattr/eval, obfuscation, "
                "and native extensions may hide capabilities (confidence=cannot-determine)."
            ),
        }


def _load_patterns() -> dict[str, list[str]]:
    if _PATTERNS_PATH.is_file():
        return json.loads(_PATTERNS_PATH.read_text(encoding="utf-8"))
    return {}


def _is_test_pattern_file(name: str) -> bool:
    if name in _TEST_FILE_EXACT:
        return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    return name.endswith("_test.py")


def _active_skip_dirs(*, include_peripheral: bool) -> set[str]:
    if include_peripheral:
        return set(_ALWAYS_SKIP_DIRS)
    return set(_SKIP_DIRS)


def _should_exclude_file(path: Path, root: Path, *, include_peripheral: bool) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    skip_dirs = _active_skip_dirs(include_peripheral=include_peripheral)
    if any(part in skip_dirs for part in rel_parts):
        return True
    if not include_peripheral and _is_test_pattern_file(path.name):
        return True
    return False


def _iter_project_files(root: Path, *, include_peripheral: bool = False) -> tuple[list[Path], int]:
    files: list[Path] = []
    excluded_count = 0
    root = root.expanduser().resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _should_exclude_file(path, root, include_peripheral=include_peripheral):
            excluded_count += 1
            continue
        files.append(path)
    return files, excluded_count


def _parse_requirements_text(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        token = re.split(r"[>=<!~\[]", line, maxsplit=1)[0].strip()
        if token:
            names.append(token.lower().replace("_", "-"))
    return names


def _parse_pyproject_deps(text: str) -> list[str]:
    names: list[str] = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^dependencies\s*=\s*\[", stripped):
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("]"):
                in_deps = False
                continue
            m = re.match(r'^["\']([^"\']+)["\']', stripped)
            if m:
                token = re.split(r"[>=<!~\[]", m.group(1), maxsplit=1)[0].strip()
                if token:
                    names.append(token.lower().replace("_", "-"))
    for match in re.finditer(r"^([a-zA-Z0-9_.-]+)\s*=", text, re.MULTILINE):
        key = match.group(1).lower().replace("_", "-")
        if key not in names:
            pass  # poetry keys handled below
    for match in re.finditer(
        r"^\s{2,}([a-zA-Z0-9_.-]+)\s*=\s*", text, re.MULTILINE
    ):
        key = match.group(1).lower().replace("_", "-")
        if key and key not in ("name", "version", "description"):
            if re.search(r"\[tool\.poetry\.(dev-)?dependencies\]", text):
                names.append(key)
    return list(dict.fromkeys(names))


def _parse_package_json_deps(text: str) -> list[str]:
    names: list[str] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return names
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        block = data.get(section) or {}
        if isinstance(block, dict):
            names.extend(k.lower() for k in block)
    return names


def _categorize_dependency(name: str, patterns: dict[str, list[str]]) -> list[str]:
    normalized = name.lower().replace("_", "-")
    cats: list[str] = []
    for category, entries in patterns.items():
        for entry in entries:
            entry_n = entry.lower().replace("_", "-")
            if normalized == entry_n or normalized.startswith(entry_n + "-") or entry_n in normalized:
                cats.append(category)
                break
    return cats


def scan_dependencies(root: Path) -> list[dict[str, Any]]:
    """Layer (a): enumerate risky dependencies from lockfiles / manifests."""
    patterns = _load_patterns()
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    candidates: list[tuple[str, Path]] = [
        ("requirements.txt", root / "requirements.txt"),
        ("pyproject.toml", root / "pyproject.toml"),
        ("package.json", root / "package.json"),
    ]
    for extra in sorted(root.glob("requirements*.txt")):
        candidates.append((extra.name, extra))

    for source_file, path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.name == "pyproject.toml":
            dep_names = _parse_pyproject_deps(text)
        elif path.name == "package.json":
            dep_names = _parse_package_json_deps(text)
        else:
            dep_names = _parse_requirements_text(text)
        for dep in dep_names:
            key = f"{source_file}:{dep}"
            if key in seen:
                continue
            seen.add(key)
            categories = _categorize_dependency(dep, patterns)
            results.append(
                {
                    "name": dep,
                    "source_file": source_file,
                    "categories": categories,
                    "confidence": "declared",
                }
            )
    return results


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return None


def _collect_mcp_tools(tree: ast.AST) -> set[str]:
    tools: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            name = _decorator_name(dec)
            if name in _MCP_TOOL_DECORATORS:
                tools.add(node.name)
    return tools


class _PythonScanner(ast.NodeVisitor):
    def __init__(self, rel_path: str, mcp_tools: set[str]) -> None:
        self.rel_path = rel_path
        self.mcp_tools = mcp_tools
        self.current_tool: str | None = None
        self.findings: list[Finding] = []
        self.imports: set[str] = set()

    def _add(
        self,
        capability: str,
        detail: str,
        *,
        line: int | None = None,
        confidence: Confidence = "observed-static",
    ) -> None:
        self.findings.append(
            Finding(
                capability=capability,
                detail=detail,
                confidence=confidence,
                source_file=self.rel_path,
                line=line,
                tool_name=self.current_tool,
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod = alias.name.split(".")[0]
            self.imports.add(mod)
            self._classify_import(mod, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            mod = node.module.split(".")[0]
            self.imports.add(mod)
            self._classify_import(mod, node.lineno)
        self.generic_visit(node)

    def _classify_import(self, mod: str, lineno: int) -> None:
        if mod in _NETWORK_MODULES:
            self._add("network", f"import {mod}", line=lineno)
        elif mod == "subprocess":
            self._add("subprocess", f"import {mod}", line=lineno)
        elif mod == "os":
            self._add("env", f"import os (env/subprocess surface)", line=lineno)
        elif mod in ("shutil", "pathlib"):
            self._add("filesystem", f"import {mod}", line=lineno)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev = self.current_tool
        if node.name in self.mcp_tools:
            self.current_tool = node.name
        self.generic_visit(node)
        self.current_tool = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        prev = self.current_tool
        if node.name in self.mcp_tools:
            self.current_tool = node.name
        self.generic_visit(node)
        self.current_tool = prev

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            base = self._expr_name(func.value)
            attr = func.attr
            if base in _NETWORK_MODULES or (base == "urllib" and attr in ("urlopen", "request")):
                self._add("network", f"{base}.{attr}()", line=node.lineno)
            elif base == "subprocess" or (base == "os" and attr in _SUBPROCESS_NAMES):
                self._add("subprocess", f"{base}.{attr}()", line=node.lineno)
            elif base == "os" and attr in _ENV_NAMES:
                self._add("env", f"os.{attr}", line=node.lineno)
            elif attr in _PATH_IO_METHODS:
                cap = "file-write" if attr.startswith("write") or attr in ("unlink", "mkdir") else "file-read"
                path_hint = self._first_str_arg(node)
                if path_hint:
                    self._add(cap, f"{attr}({path_hint!r})", line=node.lineno)
                else:
                    self._add(
                        cap,
                        f"{attr}(<dynamic>)",
                        line=node.lineno,
                        confidence="cannot-determine",
                    )
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = "r"
            if len(node.args) >= 2:
                m = _literal_str(node.args[1])
                if m:
                    mode = m
            elif node.keywords:
                for kw in node.keywords:
                    if kw.arg == "mode":
                        m = _literal_str(kw.value)
                        if m:
                            mode = m
            path_hint = self._first_str_arg(node)
            cap = "file-write" if any(c in mode for c in "wax+") else "file-read"
            if path_hint:
                self._add(cap, f"open({path_hint!r}, {mode!r})", line=node.lineno)
            else:
                self._add(cap, f"open(<dynamic>, {mode!r})", line=node.lineno, confidence="cannot-determine")
        self.generic_visit(node)

    def _expr_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr if not isinstance(node.value, ast.Name) else node.value.id
        return ""

    def _first_str_arg(self, node: ast.Call) -> str | None:
        if node.args:
            return _literal_str(node.args[0])
        for kw in node.keywords:
            if kw.arg in (None, "file", "path", "dest", "src"):
                val = _literal_str(kw.value)
                if val:
                    return val
        return None


def scan_python_ast(
    root: Path,
    *,
    include_peripheral: bool = False,
) -> tuple[list[Finding], dict[str, list[str]], int, int, int]:
    """Layer (b): AST scan of Python sources."""
    all_findings: list[Finding] = []
    tool_map: dict[str, list[str]] = {}
    py_count = 0
    project_files, excluded_count = _iter_project_files(root, include_peripheral=include_peripheral)
    file_count = len(project_files)

    for path in project_files:
        if path.suffix != ".py":
            continue
        py_count += 1
        rel = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=rel)
        except (SyntaxError, OSError, UnicodeError):
            all_findings.append(
                Finding(
                    capability="parse-error",
                    detail=f"cannot parse {rel}",
                    confidence="cannot-determine",
                    source_file=rel,
                )
            )
            continue
        mcp_tools = _collect_mcp_tools(tree)
        scanner = _PythonScanner(rel, mcp_tools)
        scanner.visit(tree)
        all_findings.extend(scanner.findings)
        for tool in mcp_tools:
            caps = sorted({f.capability for f in scanner.findings if f.tool_name == tool})
            if caps:
                tool_map[tool] = caps

    return all_findings, tool_map, py_count, file_count, excluded_count


def build_blast_radius(root: Path, *, include_peripheral: bool = False) -> dict[str, Any]:
    """Run layers (a) and (b); return serializable blast-radius report."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        return BlastRadiusReport().to_dict()

    scan_scope = _SCAN_SCOPE_FULL if include_peripheral else _SCAN_SCOPE_PRODUCTION
    deps = scan_dependencies(root)
    findings, tools, py_files, scanned, excluded = scan_python_ast(
        root,
        include_peripheral=include_peripheral,
    )

    for dep in deps:
        for cat in dep.get("categories") or []:
            findings.append(
                Finding(
                    capability=cat,
                    detail=f"dependency {dep['name']} ({dep['source_file']})",
                    confidence="declared",
                    source_file=dep.get("source_file"),
                )
            )

    report = BlastRadiusReport(
        dependencies=deps,
        findings=findings,
        tools=tools,
        scanned_files=scanned,
        python_files=py_files,
        scan_scope=scan_scope,
        excluded_file_count=excluded,
    )
    return report.to_dict()


def _path_covered(target: str, allowed: list[str]) -> bool:
    if not allowed:
        return False
    norm = target.replace("\\", "/").lstrip("./")
    for prefix in allowed:
        p = str(prefix).replace("\\", "/").rstrip("/")
        if not p:
            continue
        if norm == p or norm.startswith(p + "/"):
            return True
    return False


def detect_divergences(
    blast_radius: dict[str, Any],
    manifest_data: dict[str, Any] | None,
    *,
    agent_name: str = "agent",
) -> list[str]:
    """Layer (c): declared manifest vs observed-static capabilities."""
    if not manifest_data:
        return []
    aos_val = manifest_data.get("aos_compliant") or manifest_data.get("aos_compliance")
    if not aos_val:
        return []

    permitted = manifest_data.get("permitted_output_paths") or []
    oracle = manifest_data.get("oracle_paths") or []
    if not isinstance(permitted, list):
        permitted = []
    if not isinstance(oracle, list):
        oracle = []

    divergences: list[str] = []
    findings = blast_radius.get("findings") or []

    for item in findings:
        if item.get("confidence") != "observed-static":
            continue
        cap = item.get("capability") or ""
        detail = item.get("detail") or ""
        if cap == "file-write":
            path_hint = None
            if "open(" in detail:
                m = re.search(r"open\('([^']+)'", detail)
                if m:
                    path_hint = m.group(1)
            elif "(" in detail:
                m = re.search(r"\('([^']+)'", detail)
                if m:
                    path_hint = m.group(1)
            if path_hint and not _path_covered(path_hint, permitted):
                divergences.append(
                    f"[{agent_name}] declared write to {permitted!r} but touches {path_hint!r}"
                )
        elif cap == "file-read":
            path_hint = None
            m = re.search(r"\('([^']+)'", detail)
            if m:
                path_hint = m.group(1)
            if path_hint and oracle and not _path_covered(path_hint, oracle):
                divergences.append(
                    f"[{agent_name}] declared read oracle {oracle!r} but touches {path_hint!r}"
                )
        elif cap in ("network", "subprocess", "env", "remote-access"):
            divergences.append(
                f"[{agent_name}] declared filesystem boundaries only but observed-static "
                f"{cap} access ({detail})"
            )

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for d in divergences:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique
