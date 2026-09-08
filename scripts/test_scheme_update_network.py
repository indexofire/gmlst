#!/usr/bin/env python3
"""Network resilience tests for `gmlst scheme update` code paths.

Exercises the real network stack against live PubMLST to verify:
1. Basic connectivity and API responsiveness
2. Rate-limit behavior under burst vs. paced sequential requests
3. Timeout configuration sanity (fetch_json timeout vs. retry budget)
4. full update_catalog path with generous wall-clock budget

Usage:
    pixi run python scripts/test_scheme_update_network.py [--quick]

    --quick  skip the full catalog refresh (stages 1-3 only, ~2 min)
"""

from __future__ import annotations

import argparse
import sys
import time

PUBMLST_BASE = "https://rest.pubmlst.org/db"
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 30.0


def _fmt_result(idx: int, total: int, status: str, elapsed: float, note: str) -> None:
    print(
        f"  #{idx:>3}/{total}: {status:>12} {elapsed:5.1f}s  {note[:60]}",
        flush=True,
    )


def stage1_connectivity() -> bool:
    print("\n[Stage 1] Basic connectivity", flush=True)
    import requests

    t0 = time.perf_counter()
    try:
        r = requests.get(PUBMLST_BASE, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        elapsed = time.perf_counter() - t0
        ok = r.status_code == 200
        print(
            f"  root endpoint: HTTP {r.status_code} in {elapsed:.1f}s "
            f"({'OK' if ok else 'UNEXPECTED'})",
            flush=True,
        )
        return ok
    except Exception as exc:
        print(f"  root endpoint: FAIL {type(exc).__name__}: {exc}", flush=True)
        return False


def stage2_burst_rate_limit() -> dict[str, int]:
    print("\n[Stage 2] Burst behavior (no delay, 12 rapid requests)", flush=True)
    import requests

    orgs = requests.get(PUBMLST_BASE, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)).json()
    urls: list[str] = []
    for org in orgs:
        for db in org.get("databases", []):
            if "seqdef" in db.get("name", ""):
                urls.append(f"{PUBMLST_BASE}/{db['name']}/schemes")
            if len(urls) >= 12:
                break
        if len(urls) >= 12:
            break

    stats = {"ok": 0, "rate_limited": 0, "other_fail": 0}
    for i, url in enumerate(urls):
        t0 = time.perf_counter()
        try:
            r = requests.get(url, timeout=(CONNECT_TIMEOUT, 10))
            stats["ok"] += 1
            _fmt_result(i + 1, 12, str(r.status_code), time.perf_counter() - t0, "")
        except requests.exceptions.ConnectTimeout:
            stats["rate_limited"] += 1
            _fmt_result(
                i + 1, 12, "RATE-LIMIT", time.perf_counter() - t0, "connect timeout"
            )
        except Exception as exc:
            stats["other_fail"] += 1
            _fmt_result(
                i + 1, 12, type(exc).__name__, time.perf_counter() - t0, str(exc)[:50]
            )
    print(
        f"  → {stats['ok']} ok / {stats['rate_limited']} rate-limited / "
        f"{stats['other_fail']} other",
        flush=True,
    )
    return stats


def stage3_recovery_time() -> float:
    print("\n[Stage 3] Rate-limit recovery time", flush=True)
    import requests

    # Trigger rate limiting with a burst
    burst = 0
    for i in range(15):
        try:
            requests.get(
                f"{PUBMLST_BASE}/pubmlst_abaumannii_seqdef/schemes",
                timeout=(2, 10),
            )
        except Exception:
            burst += 1
    print(f"  burst: {burst}/15 requests failed (triggered limit)", flush=True)

    recovery = -1.0
    for wait in (1, 2, 5, 10, 30):
        time.sleep(wait)
        try:
            r = requests.get(
                f"{PUBMLST_BASE}/pubmlst_bordetella_seqdef/schemes",
                timeout=(CONNECT_TIMEOUT, 10),
            )
            recovery = float(wait)
            print(f"  recovered after ~{wait}s wait (HTTP {r.status_code})", flush=True)
            break
        except Exception:
            print(f"  still limited after {wait}s", flush=True)
    if recovery < 0:
        print("  WARNING: no recovery within 30s", flush=True)
    return recovery


def stage4_sequential_catalog(duration_budget: float = 600.0) -> tuple[int, int, float]:
    print(
        f"\n[Stage 4] Full sequential seqdef sweep ({duration_budget:.0f}s budget)",
        flush=True,
    )
    import requests

    orgs = requests.get(PUBMLST_BASE, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)).json()
    urls: list[str] = []
    for org in orgs:
        for db in org.get("databases", []):
            if "seqdef" in db.get("name", ""):
                urls.append(f"{PUBMLST_BASE}/{db['name']}/schemes")

    ok, limited = 0, 0
    t_start = time.perf_counter()
    for i, url in enumerate(urls):
        if time.perf_counter() - t_start > duration_budget:
            print(f"  budget exhausted at request {i + 1}/{len(urls)}", flush=True)
            break
        try:
            requests.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            ok += 1
        except requests.exceptions.ConnectTimeout:
            limited += 1
            time.sleep(1)
        except Exception:
            limited += 1
        if (i + 1) % 30 == 0:
            print(
                f"  progress {i + 1}/{len(urls)}: ok={ok} limited={limited} "
                f"({time.perf_counter() - t_start:.0f}s)",
                flush=True,
            )
    elapsed = time.perf_counter() - t_start
    print(
        f"  → {ok} ok / {limited} limited / total {len(urls)} in {elapsed:.0f}s "
        f"({ok / max(len(urls), 1) * 100:.0f}% success)",
        flush=True,
    )
    return ok, limited, elapsed


def stage5_update_catalog() -> None:
    print("\n[Stage 5] Real cache.update_catalog('pubmlst') — no timeout imposed",
          flush=True)
    from gmlst.database.cache import DatabaseCache

    cache = DatabaseCache()
    t0 = time.perf_counter()
    try:
        schemes = cache.update_catalog("pubmlst", scheme_type="all")
        elapsed = time.perf_counter() - t0
        print(
            f"  ✓ update_catalog: {len(schemes)} schemes in {elapsed:.0f}s "
            f"({elapsed / 60:.1f} min)",
            flush=True,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(
            f"  ✗ update_catalog FAIL after {elapsed:.0f}s: "
            f"{type(exc).__name__}: {str(exc)[:200]}",
            flush=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="skip stages 4-5")
    args = parser.parse_args()

    if not stage1_connectivity():
        print("\nRESULT: FAIL — PubMLST unreachable; server down or network blocked")
        return 1

    burst = stage2_burst_rate_limit()
    recovery = stage3_recovery_time()

    if args.quick:
        print("\nRESULT: quick mode complete (stages 1-3)")
        return 0

    ok, limited, elapsed = stage4_sequential_catalog()
    stage5_update_catalog()

    print("\n" + "=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)
    print(f"  burst limit threshold: ~{burst['rate_limited'] > 0 and 'yes' or 'no'}")
    print(f"  recovery time: ~{recovery:.0f}s" if recovery >= 0 else "  recovery: >30s")
    print(f"  sequential sweep: {ok} ok, {limited} limited, {elapsed:.0f}s")
    print()
    if limited == 0:
        print("  CONCLUSION: service is UP; slowness is inherent to the serial")
        print("  request pattern (~1 req/s × 148 seqdef + ~740 locus_count calls).")
        print("  A full `scheme update --force` needs ~10-20 minutes wall clock.")
    elif burst["rate_limited"] > 0:
        print("  CONCLUSION: server rate-limits bursts (recovers in seconds).")
        print("  fetch_json's 60s connect timeout × 3 retries amplifies each")
        print("  rate-limited request into a 3-minute stall.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
