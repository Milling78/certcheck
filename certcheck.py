#!/usr/bin/env python3
"""certcheck — a tiny, dependency-light TLS certificate expiry checker.

Connects to each host, fetches the server certificate (without validating trust),
and reports the common name, SANs, issuer, and days-to-expiry. The process exit
code reflects the worst status found, so it drops cleanly into cron or CI:

    0  all OK
    1  at least one WARNING (expiring soon)
    2  at least one CRITICAL (expired, expiring imminently, or unreachable)
    3  usage error (no targets)

Usage:
    certcheck example.com google.com:443
    certcheck --file hosts.txt --warn 45 --crit 10
    certcheck example.com --json
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum

from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID

__version__ = "1.0.0"


class Status(IntEnum):
    OK = 0
    WARNING = 1
    CRITICAL = 2


@dataclass
class CertResult:
    host: str
    port: int
    status: int                      # Status value
    cn: str = ""
    sans: list[str] = field(default_factory=list)
    issuer: str = ""
    not_after: str = ""              # ISO-8601 UTC
    days_remaining: int | None = None
    error: str = ""


def classify(days_remaining: int | None, warn_days: int, crit_days: int) -> Status:
    """Map days-to-expiry to a status. None (couldn't read a cert) is CRITICAL."""
    if days_remaining is None:
        return Status.CRITICAL
    if days_remaining <= crit_days:
        return Status.CRITICAL
    if days_remaining <= warn_days:
        return Status.WARNING
    return Status.OK


def check_cert(host: str, port: int = 443, timeout: float = 5.0,
               warn_days: int = 30, crit_days: int = 7) -> CertResult:
    """Fetch and inspect one host's leaf certificate. Trust is intentionally not
    validated — the goal is expiry/identity visibility, including self-signed and
    internal CAs."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
    except Exception as e:                                   # noqa: BLE001
        return CertResult(host, port, int(Status.CRITICAL), error=str(e)[:200])

    try:
        cert = x509.load_der_x509_certificate(der)
    except Exception as e:                                   # noqa: BLE001
        return CertResult(host, port, int(Status.CRITICAL), error=f"parse failed: {e}")

    cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    cn = cn_attrs[0].value if cn_attrs else ""

    sans: list[str] = []
    try:
        ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        for name in ext.value:
            if isinstance(name, x509.DNSName):
                sans.append(f"DNS:{name.value}")
            elif isinstance(name, x509.IPAddress):
                sans.append(f"IP:{name.value}")
            elif isinstance(name, x509.RFC822Name):
                sans.append(f"email:{name.value}")
    except x509.ExtensionNotFound:
        pass

    issuer_o = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
    issuer_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    if issuer_o:
        issuer = issuer_o[0].value
    elif issuer_cn:
        issuer = issuer_cn[0].value
    else:
        issuer = cert.issuer.rfc4514_string()

    not_after = cert.not_valid_after_utc
    days_remaining = (not_after - datetime.now(timezone.utc)).days
    status = classify(days_remaining, warn_days, crit_days)

    return CertResult(
        host=host, port=port, status=int(status), cn=cn, sans=sans, issuer=issuer,
        not_after=not_after.strftime("%Y-%m-%dT%H:%M:%SZ"), days_remaining=days_remaining,
    )


def check_many(targets: list[tuple[str, int]], timeout: float = 5.0,
               warn_days: int = 30, crit_days: int = 7, workers: int = 8) -> list[CertResult]:
    if not targets:
        return []
    results: list[CertResult] = []
    with ThreadPoolExecutor(max_workers=min(len(targets), workers)) as ex:
        futures = {
            ex.submit(check_cert, host, port, timeout, warn_days, crit_days): (host, port)
            for host, port in targets
        }
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:                           # noqa: BLE001
                host, port = futures[fut]
                results.append(CertResult(host, port, int(Status.CRITICAL),
                                          error=f"unexpected: {str(e)[:160]}"))
    # Soonest-to-expire first; unreachable (None) sorts to the very top.
    results.sort(key=lambda r: (r.days_remaining if r.days_remaining is not None else -10**9))
    return results


def parse_target(entry: str, default_port: int = 443) -> tuple[str, int] | None:
    """Parse a target into (host, port).

    - 'host'                -> (host, default_port)
    - 'host:port'           -> (host, port)        (exactly one colon)
    - '[2001:db8::1]:443'   -> ('2001:db8::1', 443) (bracketed IPv6 with port)
    - '2001:db8::1'         -> ('2001:db8::1', default_port) (bare IPv6, >1 colon)
    """
    entry = entry.strip()
    if not entry:
        return None
    if entry.startswith("["):                       # bracketed IPv6, optional :port
        host, sep, rest = entry[1:].partition("]")
        if sep:
            if rest.startswith(":") and rest[1:].isdigit():
                return (host, int(rest[1:]))
            return (host, default_port)
    if entry.count(":") == 1:                        # host:port (IPv6 has >=2 colons)
        host, _, port = entry.partition(":")
        if host and port.isdigit():
            return (host, int(port))
    return (entry, default_port)


# ── CLI ─────────────────────────────────────────────────────────────────────

_COLOR = {Status.OK: "\033[32m", Status.WARNING: "\033[33m", Status.CRITICAL: "\033[31m"}
_RESET = "\033[0m"
_LABEL = {Status.OK: "OK", Status.WARNING: "WARN", Status.CRITICAL: "CRIT"}


def _use_color(flag: str) -> bool:
    if flag == "always":
        return True
    if flag == "never":
        return False
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _render_table(results: list[CertResult], color: bool) -> str:
    rows = []
    for r in results:
        st = Status(r.status)
        days = "—" if r.days_remaining is None else str(r.days_remaining)
        detail = r.error or f"{r.cn or '?'}  ({r.issuer or '?'})"
        label = _LABEL[st]
        if color:
            label = f"{_COLOR[st]}{label:<4}{_RESET}"
        else:
            label = f"{label:<4}"
        rows.append(f"  {label}  {r.host}:{r.port:<5}  {days:>5}d  {detail}")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="certcheck",
        description="Tiny TLS certificate expiry checker. Exit code = worst status (0/1/2).",
    )
    p.add_argument("hosts", nargs="*", help="host or host:port (default port 443)")
    p.add_argument("-f", "--file", help="file with one host[:port] per line (# comments ok)")
    p.add_argument("-w", "--warn", type=int, default=30, help="warn at <= N days (default 30)")
    p.add_argument("-c", "--crit", type=int, default=7, help="critical at <= N days (default 7)")
    p.add_argument("-t", "--timeout", type=float, default=5.0, help="per-host timeout seconds (default 5)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    p.add_argument("-V", "--version", action="version", version=f"certcheck {__version__}")
    args = p.parse_args(argv)

    entries = list(args.hosts)
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                for line in fh:
                    line = line.split("#", 1)[0].strip()
                    if line:
                        entries.append(line)
        except OSError as e:
            print(f"certcheck: cannot read {args.file}: {e}", file=sys.stderr)
            return 3

    targets = [t for t in (parse_target(e) for e in entries) if t]
    if not targets:
        print("certcheck: no targets given (pass host[:port] args or --file)", file=sys.stderr)
        return 3

    results = check_many(targets, timeout=args.timeout, warn_days=args.warn, crit_days=args.crit)

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print(_render_table(results, _use_color(args.color)))

    worst = max((r.status for r in results), default=int(Status.OK))
    return int(worst)


if __name__ == "__main__":
    raise SystemExit(main())
