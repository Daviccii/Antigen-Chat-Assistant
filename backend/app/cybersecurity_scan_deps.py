"""Dependency vulnerability scanning via OSV.dev — Google's open, free,
no-API-key-required vulnerability database covering PyPI, npm, and most
other ecosystems. No local vulnerability DB to maintain, no scanner
binary to install.

This only ever reads a manifest (requirements.txt / package.json)
either as raw text the user pastes in, or a file path (path access is
validated by the Security Gateway in gated_execution.py before this
module ever sees it). It never modifies anything.
"""
import json
import logging
import re
from typing import List, Dict, Any, Tuple

import httpx

logger = logging.getLogger(__name__)

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
MAX_PACKAGES_PER_SCAN = 150  # keep a pasted monorepo lockfile from taking minutes to scan


class ManifestParseError(Exception):
    pass


def parse_requirements_txt(content: str) -> List[Tuple[str, str]]:
    """Parses a requirements.txt-style file. Only handles pinned
    (==) and minimum (>=) specs — the common cases — and skips
    -r/-e includes, comments, and unpinned bare package names (nothing
    to look up a specific version's vulnerabilities against).
    """
    packages = []
    for line in content.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith(("-r ", "-e ", "--")):
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)\s*(==|>=)\s*([A-Za-z0-9._-]+)", line)
        if match:
            name, _, version = match.groups()
            packages.append((name, version))
    return packages


def parse_package_json(content: str) -> List[Tuple[str, str]]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ManifestParseError(f"Invalid package.json: {e}")

    packages = []
    for section in ("dependencies", "devDependencies"):
        for name, version_spec in data.get(section, {}).items():
            # Strip common range prefixes (^1.2.3, ~1.2.3, >=1.2.3) down
            # to a concrete version OSV can look up — approximate, but
            # good enough to catch known-vulnerable pinned/caret ranges.
            version = re.sub(r"^[\^~>=<]+", "", version_spec).strip()
            if version and version[0].isdigit():
                packages.append((name, version))
    return packages


def _osv_ecosystem_name(ecosystem: str) -> str:
    return {"pypi": "PyPI", "npm": "npm"}.get(ecosystem.lower(), ecosystem)


def query_osv(package_name: str, version: str, ecosystem: str) -> List[Dict[str, Any]]:
    """Single-package OSV lookup. Returns a possibly-empty list of
    vulnerability records. Network/parse failures are logged and treated
    as "no findings for this package" rather than aborting the whole scan.
    """
    try:
        resp = httpx.post(
            OSV_QUERY_URL,
            json={
                "package": {"name": package_name, "ecosystem": _osv_ecosystem_name(ecosystem)},
                "version": version,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("vulns", [])
    except Exception as e:
        logger.warning(f"OSV query failed for {package_name}=={version}: {e}")
        return []


def scan_manifest(content: str, ecosystem: str) -> Dict[str, Any]:
    if ecosystem.lower() == "pypi":
        packages = parse_requirements_txt(content)
    elif ecosystem.lower() == "npm":
        packages = parse_package_json(content)
    else:
        raise ManifestParseError(f"Unsupported ecosystem '{ecosystem}'. Use 'pypi' or 'npm'.")

    if not packages:
        return {"ecosystem": ecosystem, "packages_scanned": 0, "vulnerable_packages": [], "note": "No pinned packages found to check."}

    truncated = len(packages) > MAX_PACKAGES_PER_SCAN
    packages = packages[:MAX_PACKAGES_PER_SCAN]

    vulnerable = []
    for name, version in packages:
        vulns = query_osv(name, version, ecosystem)
        if vulns:
            vulnerable.append({
                "package": name,
                "version": version,
                "vulnerabilities": [
                    {
                        "id": v.get("id"),
                        "summary": (v.get("summary") or v.get("details", ""))[:300],
                        "severity": _extract_severity(v),
                        "aliases": v.get("aliases", []),
                    }
                    for v in vulns
                ],
            })

    return {
        "ecosystem": ecosystem,
        "packages_scanned": len(packages),
        "truncated": truncated,
        "vulnerable_packages": vulnerable,
        "clean_packages": len(packages) - len(vulnerable),
    }


def _extract_severity(vuln: Dict[str, Any]) -> str:
    for sev in vuln.get("severity", []):
        if sev.get("type") == "CVSS_V3":
            return sev.get("score", "UNKNOWN")
    # Some OSV records only carry a database-specific severity string.
    db_specific = vuln.get("database_specific", {})
    return db_specific.get("severity", "UNKNOWN")