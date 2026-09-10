"""Static security analysis: AST-based detection of dangerous patterns in
Python source, plus regex-based secret detection across any text file.
This is a lightweight, dependency-free scanner — not a replacement for
a full SAST tool like Bandit/Semgrep, but catches the common, high-signal
issues without adding a heavy dependency.

Purely static analysis: reads text, never executes anything it scans.
"""
import ast
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

MAX_FILES_PER_SCAN = 500
MAX_FILE_SIZE_BYTES = 2_000_000  # skip anything absurdly large (generated bundles, etc.)

# ---------------------------------------------------------------------------
# Secret detection (any text file)
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key (heuristic)", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]")),
    ("Generic API key/secret/token assignment", re.compile(
        r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    )),
    ("Private key header", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
]

# Placeholder-looking values that trip the generic pattern but aren't
# real secrets — cuts a lot of noise from example/template files.
_PLACEHOLDER_HINTS = ("xxxx", "your_", "changeme", "example", "placeholder", "<", "insert_")


def scan_for_secrets(filepath: str, content: str) -> List[Dict[str, Any]]:
    findings = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        lowered = line.lower()
        if any(hint in lowered for hint in _PLACEHOLDER_HINTS):
            continue
        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "file": filepath,
                    "line": line_num,
                    "severity": "HIGH",
                    "category": "hardcoded_secret",
                    "description": f"Possible hardcoded {label}. Move this to an environment variable or secrets manager.",
                })
    return findings


# ---------------------------------------------------------------------------
# AST-based dangerous-pattern detection (Python only)
# ---------------------------------------------------------------------------

_DANGEROUS_CALLS = {
    "eval": ("HIGH", "eval() executes arbitrary code from a string — avoid on any input that isn't fully trusted."),
    "exec": ("HIGH", "exec() executes arbitrary code from a string — avoid on any input that isn't fully trusted."),
}


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.findings: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        func_name = self._resolve_call_name(node.func)

        if func_name in _DANGEROUS_CALLS:
            severity, desc = _DANGEROUS_CALLS[func_name]
            self._add(node, severity, "dangerous_call", desc)

        if func_name == "os.system":
            self._add(node, "HIGH", "shell_execution", "os.system() runs a shell command — vulnerable to injection if any part of the command includes external input.")

        if func_name in ("subprocess.run", "subprocess.call", "subprocess.Popen", "subprocess.check_output"):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self._add(node, "HIGH", "shell_execution", f"{func_name}(..., shell=True) is vulnerable to shell injection if the command includes external input.")

        if func_name in ("pickle.load", "pickle.loads"):
            self._add(node, "HIGH", "insecure_deserialization", f"{func_name}() can execute arbitrary code when deserializing untrusted data.")

        if func_name == "yaml.load":
            has_safe_loader = any(
                kw.arg == "Loader" and isinstance(kw.value, ast.Attribute) and kw.value.attr == "SafeLoader"
                for kw in node.keywords
            )
            if not has_safe_loader:
                self._add(node, "MEDIUM", "insecure_deserialization", "yaml.load() without Loader=yaml.SafeLoader can execute arbitrary code — use yaml.safe_load() instead.")

        if func_name in ("hashlib.md5", "hashlib.sha1"):
            self._add(node, "LOW", "weak_crypto", f"{func_name}() is cryptographically weak — fine for non-security checksums, but don't use it for passwords or signatures.")

        self.generic_visit(node)

    @staticmethod
    def _resolve_call_name(func_node) -> str:
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            parts = []
            node = func_node
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        return ""

    def _add(self, node: ast.AST, severity: str, category: str, description: str):
        self.findings.append({
            "file": self.filepath,
            "line": getattr(node, "lineno", None),
            "severity": severity,
            "category": category,
            "description": description,
        })


def scan_python_ast(filepath: str, content: str) -> List[Dict[str, Any]]:
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return [{"file": filepath, "line": e.lineno, "severity": "INFO", "category": "parse_error", "description": f"Could not parse as Python: {e}"}]

    visitor = _SecurityVisitor(filepath)
    visitor.visit(tree)
    return visitor.findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def analyze_path(root_path: str) -> Dict[str, Any]:
    """root_path has already been resolved and allowed-area-checked by
    the Security Gateway (see gated_execution.py) before this runs. As a
    second layer, every individual file found while walking a directory
    is still re-resolved and checked against the same root here — a
    symlink inside an otherwise-allowed folder shouldn't be able to walk
    the scan outside it.
    """
    root = Path(root_path).resolve()
    files_to_scan = []

    if root.is_file():
        files_to_scan = [root]
    elif root.is_dir():
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                candidate = Path(dirpath) / fname
                try:
                    resolved = candidate.resolve()
                except (OSError, RuntimeError):
                    continue
                if root not in resolved.parents and resolved != root:
                    continue  # symlink escaped the scanned root — skip it
                files_to_scan.append(resolved)
                if len(files_to_scan) >= MAX_FILES_PER_SCAN:
                    break
            if len(files_to_scan) >= MAX_FILES_PER_SCAN:
                break
    else:
        return {"error": f"Path does not exist: {root_path}"}

    all_findings = []
    files_scanned = 0
    for filepath in files_to_scan:
        try:
            if filepath.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        files_scanned += 1
        rel = str(filepath)
        all_findings.extend(scan_for_secrets(rel, content))
        if filepath.suffix == ".py":
            all_findings.extend(scan_python_ast(rel, content))

    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 9))

    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in all_findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    return {
        "root": str(root),
        "files_scanned": files_scanned,
        "truncated": len(files_to_scan) >= MAX_FILES_PER_SCAN,
        "findings": all_findings,
        "counts": counts,
    }