#!/usr/bin/env python3
"""
HTTP load test for the Akka Cloud Parking System.

What it measures (report-friendly):
- Throughput (requests/sec)
- Latency distribution (avg, p50, p95, p99, max) per endpoint + overall
- Error rate (timeouts, 4xx/5xx) per endpoint + overall
- Exports results as JSON + CSV for your report

Example:
  python3 http_load_test.py --base-url http://54.167.216.74:8080 --edges 20 --duration 60 --updates-per-sec 1

Notes:
- This simulates N edge servers by registering N parking lots and sending occupancy updates.
- It does NOT require running your edge/camera/barrier locally.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import statistics
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import httpx


# ---------------------------
# Stats helpers
# ---------------------------

def percentile(values: List[float], p: float) -> float:
    """p in [0, 100]. Values are assumed to be non-empty."""
    if not values:
        return float("nan")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


@dataclass
class EndpointStats:
    name: str
    count: int = 0
    ok: int = 0
    fail: int = 0
    timeouts: int = 0
    http_4xx: int = 0
    http_5xx: int = 0
    other_err: int = 0
    lat_ms: List[float] = None

    def __post_init__(self):
        if self.lat_ms is None:
            self.lat_ms = []

    def add_ok(self, ms: float):
        self.count += 1
        self.ok += 1
        self.lat_ms.append(ms)

    def add_fail(self, ms: Optional[float], kind: str):
        self.count += 1
        self.fail += 1
        if ms is not None:
            self.lat_ms.append(ms)
        if kind == "timeout":
            self.timeouts += 1
        elif kind == "4xx":
            self.http_4xx += 1
        elif kind == "5xx":
            self.http_5xx += 1
        else:
            self.other_err += 1

    def summary(self) -> Dict:
        lats = self.lat_ms
        if lats:
            return {
                "name": self.name,
                "count": self.count,
                "ok": self.ok,
                "fail": self.fail,
                "timeout": self.timeouts,
                "http_4xx": self.http_4xx,
                "http_5xx": self.http_5xx,
                "other_err": self.other_err,
                "avg_ms": statistics.fmean(lats),
                "p50_ms": percentile(lats, 50),
                "p95_ms": percentile(lats, 95),
                "p99_ms": percentile(lats, 99),
                "max_ms": max(lats),
            }
        else:
            return {
                "name": self.name,
                "count": self.count,
                "ok": self.ok,
                "fail": self.fail,
                "timeout": self.timeouts,
                "http_4xx": self.http_4xx,
                "http_5xx": self.http_5xx,
                "other_err": self.other_err,
                "avg_ms": float("nan"),
                "p50_ms": float("nan"),
                "p95_ms": float("nan"),
                "p99_ms": float("nan"),
                "max_ms": float("nan"),
            }


@dataclass
class Config:
    base_url: str
    edges: int
    duration_s: int
    updates_per_sec: float
    max_capacity: int
    timeout_s: float
    concurrency: int
    out_prefix: str
    keep_parking_lots: bool
    include_payment: bool


# ---------------------------
# HTTP calls (measured)
# ---------------------------

async def measured_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    stats: EndpointStats,
    *,
    json_body: Optional[dict] = None,
    params: Optional[dict] = None,
) -> Tuple[bool, Optional[int]]:
    t0 = time.perf_counter()
    try:
        resp = await client.request(method, url, json=json_body, params=params)
        dt_ms = (time.perf_counter() - t0) * 1000.0

        sc = resp.status_code
        if 200 <= sc < 300 or sc in (202,):
            stats.add_ok(dt_ms)
            return True, sc
        elif 400 <= sc < 500:
            stats.add_fail(dt_ms, "4xx")
            return False, sc
        elif 500 <= sc < 600:
            stats.add_fail(dt_ms, "5xx")
            return False, sc
        else:
            stats.add_fail(dt_ms, "other")
            return False, sc

    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout, httpx.TimeoutException):
        dt_ms = (time.perf_counter() - t0) * 1000.0
        stats.add_fail(dt_ms, "timeout")
        return False, None
    except Exception:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        stats.add_fail(dt_ms, "other")
        return False, None


# ---------------------------
# Scenario
# ---------------------------

def gen_city_lots(n: int) -> List[Tuple[str, float, float]]:
    # Simple Austria-ish set; if n > 6 we just append numbered ones nearby.
    base = [
        ("Parking_Vienna", 48.2082, 16.3738),
        ("Parking_Graz", 47.0707, 15.4395),
        ("Parking_Linz", 48.3069, 14.2858),
        ("Parking_Salzburg", 47.8095, 13.0550),
        ("Parking_Innsbruck", 47.2682, 11.3923),
        ("Parking_Klagenfurt", 46.6247, 14.3053),
    ]
    out = base[:]
    while len(out) < n:
        name, lat, lng = random.choice(base)
        k = len(out) + 1
        out.append((f"{name}_{k}", lat + random.uniform(-0.02, 0.02), lng + random.uniform(-0.02, 0.02)))
    return out[:n]


async def register_all(client: httpx.AsyncClient, cfg: Config, stats_map: Dict[str, EndpointStats], lots):
    ep = stats_map["POST /api/parking-lots"]
    for (park_id, lat, lng) in lots:
        payload = {"parkId": park_id, "maxCapacity": cfg.max_capacity, "lat": lat, "lng": lng}
        await measured_request(client, "POST", f"{cfg.base_url}/api/parking-lots", ep, json_body=payload)


async def deregister_all(client: httpx.AsyncClient, cfg: Config, stats_map: Dict[str, EndpointStats], lots):
    ep = stats_map["DELETE /api/parking-lots/{id}"]
    for (park_id, _, _) in lots:
        await measured_request(client, "DELETE", f"{cfg.base_url}/api/parking-lots/{park_id}", ep)


async def edge_worker(
    client: httpx.AsyncClient,
    cfg: Config,
    stats_map: Dict[str, EndpointStats],
    park_id: str,
    stop_at: float,
    limiter: asyncio.Semaphore,
):
    occ = 0
    occ_ep = stats_map["POST /api/occupancy"]
    pay_enter_ep = stats_map["POST /api/payment/enter"]
    pay_pay_ep = stats_map["POST /api/payment/pay"]
    pay_check_ep = stats_map["GET /api/payment/check"]
    pay_exit_ep = stats_map["DELETE /api/payment/exit"]

    # per-edge interval, with slight jitter so they don't all spike at once
    base_interval = 1.0 / max(cfg.updates_per_sec, 0.0001)

    while time.perf_counter() < stop_at:
        await asyncio.sleep(base_interval + random.uniform(0, base_interval * 0.25))

        # occupancy "random walk"
        step = random.choice([-1, 0, 1])
        occ = max(0, min(cfg.max_capacity, occ + step))

        payload = {"parkId": park_id, "currentOccupancy": occ}

        async with limiter:
            await measured_request(client, "POST", f"{cfg.base_url}/api/occupancy", occ_ep, json_body=payload)

        # Optional small payment traffic (very light)
        if cfg.include_payment and random.random() < 0.10:
            plate = f"{park_id}-PLATE-{random.randint(1, 9999)}"
            async with limiter:
                await measured_request(client, "POST", f"{cfg.base_url}/api/payment/enter", pay_enter_ep, json_body={"licensePlate": plate})
            async with limiter:
                await measured_request(client, "GET", f"{cfg.base_url}/api/payment/check", pay_check_ep, params={"licensePlate": plate})
            async with limiter:
                await measured_request(client, "POST", f"{cfg.base_url}/api/payment/pay", pay_pay_ep, json_body={"licensePlate": plate})
            async with limiter:
                await measured_request(client, "DELETE", f"{cfg.base_url}/api/payment/exit", pay_exit_ep, params={"licensePlate": plate})


async def health_pinger(client: httpx.AsyncClient, cfg: Config, stats_map: Dict[str, EndpointStats], stop_at: float, limiter: asyncio.Semaphore):
    ep = stats_map["GET /health"]
    while time.perf_counter() < stop_at:
        await asyncio.sleep(1.0)
        async with limiter:
            await measured_request(client, "GET", f"{cfg.base_url}/health", ep)


# ---------------------------
# Main
# ---------------------------

def make_stats_map() -> Dict[str, EndpointStats]:
    keys = [
        "GET /health",
        "POST /api/parking-lots",
        "DELETE /api/parking-lots/{id}",
        "POST /api/occupancy",
        "POST /api/payment/enter",
        "POST /api/payment/pay",
        "GET /api/payment/check",
        "DELETE /api/payment/exit",
    ]
    return {k: EndpointStats(k) for k in keys}


def print_report(cfg: Config, started_at: float, ended_at: float, stats_map: Dict[str, EndpointStats]):
    total_s = max(ended_at - started_at, 1e-9)

    # overall
    all_lat = []
    total_count = total_ok = total_fail = 0
    for st in stats_map.values():
        total_count += st.count
        total_ok += st.ok
        total_fail += st.fail
        all_lat.extend(st.lat_ms)

    rps = total_count / total_s
    ok_rate = (total_ok / total_count * 100.0) if total_count else 0.0

    print("\n" + "=" * 72)
    print("HTTP LOAD TEST REPORT (copy/paste into your report)")
    print("=" * 72)
    print(f"Base URL:           {cfg.base_url}")
    print(f"Simulated edges:    {cfg.edges}")
    print(f"Duration:           {cfg.duration_s}s")
    print(f"Updates per edge:   {cfg.updates_per_sec:.2f} req/s (occupancy)")
    print(f"Concurrency limit:  {cfg.concurrency}")
    print(f"Timeout:            {cfg.timeout_s:.2f}s")
    print(f"Total requests:     {total_count}")
    print(f"Throughput:         {rps:.2f} requests/sec")
    print(f"Success rate:       {ok_rate:.2f}%  (ok={total_ok}, fail={total_fail})")
    if all_lat:
        print(f"Overall latency ms: avg={statistics.fmean(all_lat):.1f}  p50={percentile(all_lat,50):.1f}  "
              f"p95={percentile(all_lat,95):.1f}  p99={percentile(all_lat,99):.1f}  max={max(all_lat):.1f}")
    else:
        print("Overall latency ms: (no data)")

    print("\nPer-endpoint:")
    header = f"{'endpoint':32} {'count':>7} {'ok':>7} {'fail':>7} {'avg':>8} {'p95':>8} {'p99':>8} {'max':>8} {'timeouts':>9}"
    print(header)
    print("-" * len(header))
    for key in stats_map:
        s = stats_map[key].summary()
        print(f"{s['name'][:32]:32} {s['count']:7d} {s['ok']:7d} {s['fail']:7d} "
              f"{s['avg_ms']:8.1f} {s['p95_ms']:8.1f} {s['p99_ms']:8.1f} {s['max_ms']:8.1f} {s['timeout']:9d}")
    print("=" * 72)


def save_outputs(cfg: Config, stats_map: Dict[str, EndpointStats], started_at: float, ended_at: float):
    out_json = f"{cfg.out_prefix}.json"
    out_csv = f"{cfg.out_prefix}.csv"

    duration = max(ended_at - started_at, 1e-9)

    # JSON
    payload = {
        "config": asdict(cfg),
        "started_epoch": started_at,
        "ended_epoch": ended_at,
        "duration_s": duration,
        "endpoints": {k: stats_map[k].summary() for k in stats_map},
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # CSV (one row per endpoint)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "endpoint", "count", "ok", "fail", "timeout", "http_4xx", "http_5xx", "other_err",
            "avg_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms"
        ])
        w.writeheader()
        for k in stats_map:
            s = stats_map[k].summary()
            s["endpoint"] = s.pop("name")
            w.writerow(s)

    print(f"\nSaved: {out_json}")
    print(f"Saved: {out_csv}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="e.g. http://54.167.216.74:8080")
    ap.add_argument("--edges", type=int, default=10, help="how many parking lots (edge servers) to simulate")
    ap.add_argument("--duration", type=int, default=60, help="test duration in seconds")
    ap.add_argument("--updates-per-sec", type=float, default=1.0, help="occupancy updates per second per edge")
    ap.add_argument("--max-capacity", type=int, default=67)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--concurrency", type=int, default=50, help="global max in-flight HTTP requests")
    ap.add_argument("--out", default="http_load_results", help="output prefix (writes .json and .csv)")
    ap.add_argument("--keep-parking-lots", action="store_true", help="do NOT deregister parking lots at the end")
    ap.add_argument("--include-payment", action="store_true", help="add small payment traffic (optional)")
    args = ap.parse_args()

    cfg = Config(
        base_url=args.base_url.rstrip("/"),
        edges=max(1, args.edges),
        duration_s=max(1, args.duration),
        updates_per_sec=max(0.01, args.updates_per_sec),
        max_capacity=max(1, args.max_capacity),
        timeout_s=max(0.2, args.timeout),
        concurrency=max(1, args.concurrency),
        out_prefix=args.out,
        keep_parking_lots=bool(args.keep_parking_lots),
        include_payment=bool(args.include_payment),
    )

    stats_map = make_stats_map()
    lots = gen_city_lots(cfg.edges)

    limits = httpx.Limits(max_connections=cfg.concurrency, max_keepalive_connections=cfg.concurrency)
    timeout = httpx.Timeout(cfg.timeout_s)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        # quick health check
        ok, _ = await measured_request(client, "GET", f"{cfg.base_url}/health", stats_map["GET /health"])
        if not ok:
            print(f"[ERROR] /health not reachable at {cfg.base_url}. Abort.")
            return

        # register lots
        await register_all(client, cfg, stats_map, lots)

        # run load
        limiter = asyncio.Semaphore(cfg.concurrency)
        started = time.perf_counter()
        stop_at = started + cfg.duration_s

        tasks = [
            asyncio.create_task(health_pinger(client, cfg, stats_map, stop_at, limiter))
        ]
        for (park_id, _, _) in lots:
            tasks.append(asyncio.create_task(edge_worker(client, cfg, stats_map, park_id, stop_at, limiter)))

        await asyncio.gather(*tasks)
        ended = time.perf_counter()

        # cleanup
        if not cfg.keep_parking_lots:
            await deregister_all(client, cfg, stats_map, lots)

    # report + export
    print_report(cfg, started, ended, stats_map)
    save_outputs(cfg, stats_map, time.time() - (ended - started), time.time())


if __name__ == "__main__":
    asyncio.run(main())
