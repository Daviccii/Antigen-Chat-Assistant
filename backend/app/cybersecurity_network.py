"""Local network awareness — what's listening on this machine and what
process owns it. Deliberately scoped to localhost only: this reads your
own machine's connection table via the OS, it does not scan any other
host or IP range. Port-scanning other machines is reconnaissance for an
attack, not a defensive capability, and isn't what this does.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_listening_ports() -> Dict[str, Any]:
    import psutil

    results = []
    access_denied_count = 0

    for conn in psutil.net_connections(kind="inet"):
        if conn.status != psutil.CONN_LISTEN:
            continue

        process_name = None
        if conn.pid:
            try:
                process_name = psutil.Process(conn.pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                access_denied_count += 1

        results.append({
            "port": conn.laddr.port if conn.laddr else None,
            "address": conn.laddr.ip if conn.laddr else None,
            "pid": conn.pid,
            "process_name": process_name,
        })

    results.sort(key=lambda r: (r["port"] or 0))

    note = None
    if access_denied_count:
        note = (
            f"Process names for {access_denied_count} connection(s) could not be resolved — "
            "run with elevated privileges to see process ownership for all listeners."
        )

    return {"listening": results, "count": len(results), "note": note}