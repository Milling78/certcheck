"""Unit tests for certcheck — the pure logic (no network)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from certcheck import Status, classify, parse_target


# ── classify ──────────────────────────────────────────────────────────────────

def test_classify_ok():
    assert classify(60, warn_days=30, crit_days=7) is Status.OK

def test_classify_warning_boundary():
    assert classify(30, warn_days=30, crit_days=7) is Status.WARNING
    assert classify(8, warn_days=30, crit_days=7) is Status.WARNING

def test_classify_critical_boundary():
    assert classify(7, warn_days=30, crit_days=7) is Status.CRITICAL
    assert classify(0, warn_days=30, crit_days=7) is Status.CRITICAL

def test_classify_expired_negative():
    assert classify(-5, warn_days=30, crit_days=7) is Status.CRITICAL

def test_classify_unknown_is_critical():
    assert classify(None, warn_days=30, crit_days=7) is Status.CRITICAL


# ── parse_target ────────────────────────────────────────────────────────────

def test_parse_bare_host_defaults_443():
    assert parse_target("example.com") == ("example.com", 443)

def test_parse_host_with_port():
    assert parse_target("example.com:8443") == ("example.com", 8443)

def test_parse_strips_whitespace():
    assert parse_target("  example.com:443  ") == ("example.com", 443)

def test_parse_empty_is_none():
    assert parse_target("") is None
    assert parse_target("   ") is None

def test_parse_ipv6_without_port_kept_whole():
    # Bare IPv6 (>1 colon) -> treated as a host, default port (not misparsed as :port).
    assert parse_target("2001:db8::1") == ("2001:db8::1", 443)

def test_parse_ipv6_bracketed_with_port():
    assert parse_target("[2001:db8::1]:8443") == ("2001:db8::1", 8443)

def test_parse_ipv6_bracketed_no_port():
    assert parse_target("[2001:db8::1]") == ("2001:db8::1", 443)

def test_parse_default_port_override():
    assert parse_target("example.com", default_port=8443) == ("example.com", 8443)
