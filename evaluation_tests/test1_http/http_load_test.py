#!/usr/bin/env python3
import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import httpx


# -------------------------
# Stats
# -------------------------

def percentile(values: List[float], p: float) -> float:
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

    def summary(self) -> Dict[str, object]:
        l = self.lat_ms
        return {
            "name": self.name,
            "count": self.count,
            "ok": self.ok,
            "fail": self.fail,
            "timeouts": self.timeouts,
            "http_4xx": self.http_4xx,
            "http_5xx": self.http_5xx,
            "other_err": self.other_err,
            "avg_ms": statistics.fmean(l) if l else None,
            "p50_ms": percentile(l, 50),
            "p95_ms": percentile(l, 95),
            "p99_ms": percentile(l, 99),
            "max_ms": max(l) if l else None,
        }


def make_stats_map() -> Dict[str, EndpointStats]:
    keys = [
        "GET /health",
        "POST /api/parking-lots",
        "DELETE /api/parking-lots/{id}",
        "POST /api/occupancy",
        "POST /api/payment/enter",
        "GET /api/payment/check",
        "POST /api/payment/pay",
        "DELETE /api/payment/exit",
    ]
    return {k: EndpointStats(k) for k in keys}


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
        if 400 <= sc < 500:
            stats.add_fail(dt_ms, "4xx")
            return False, sc
        if 500 <= sc < 600:
            stats.add_fail(dt_ms, "5xx")
            return False, sc
        stats.add_fail(dt_ms, "other")
        return False, sc
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout):
        dt_ms = (time.perf_counter() - t0) * 1000.0
        stats.add_fail(dt_ms, "timeout")
        return False, None
    except Exception:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        stats.add_fail(dt_ms, "other")
        return False, None


# -------------------------
# Helpers
# -------------------------

def gen_city_lots(n: int):
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


async def register_lots(client: httpx.AsyncClient, base_url: str, max_capacity: int, stats: Dict[str, EndpointStats], lots):
    ep = stats["POST /api/parking-lots"]
    for park_id, lat, lng in lots:
        payload = {"parkId": park_id, "maxCapacity": max_capacity, "lat": lat, "lng": lng}
        await measured_request(client, "POST", f"{base_url}/api/parking-lots", ep, json_body=payload)


async def deregister_lots(client: httpx.AsyncClient, base_url: str, stats: Dict[str, EndpointStats], lots):
    ep = stats["DELETE /api/parking-lots/{id}"]
    for park_id, _, _ in lots:
        await measured_request(client, "DELETE", f"{base_url}/api/parking-lots/{park_id}", ep)


# -------------------------
# Rate control
# -------------------------

async def paced_loop(stop_at: float, interval: float):
    """
    A pacer that keeps steady intervals using next_deadline.
    If the loop lags, it will catch up (no giant sleep).
    """
    next_t = time.perf_counter()
    while time.perf_counter() < stop_at:
        next_t += interval
        now = time.perf_counter()
        sleep_s = next_t - now
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)
        else:
            # behind schedule: yield control but don't sleep long
            await asyncio.sleep(0)


# -------------------------
# Workload producers
# -------------------------

async def health_producer(stop_at: float, base_url: str, client: httpx.AsyncClient, sem: asyncio.Semaphore, stats):
    ep = stats["GET /health"]
    interval = 1.0  # can be made configurable
    next_t = time.perf_counter()
    while time.perf_counter() < stop_at:
        next_t += interval
        await sem.acquire()
        asyncio.create_task(_do_req(sem, measured_request(client, "GET", f"{base_url}/health", ep)))
        sleep_s = next_t - time.perf_counter()
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)
        else:
            await asyncio.sleep(0)


async def occupancy_producer(
    stop_at: float,
    base_url: str,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    stats,
    park_id: str,
    max_capacity: int,
    updates_per_sec: float,
    occ_state: Dict[str, int],
    poisson: bool,
):
    """
    One producer = one edge (or edge-worker) for occupancy updates.
    """
    ep = stats["POST /api/occupancy"]
    if updates_per_sec <= 0:
        return

    # For constant rate: interval fixed.
    interval = 1.0 / updates_per_sec

    while time.perf_counter() < stop_at:
        if poisson:
            # Exponential inter-arrival times for a more "real-ish" stream.
            dt = random.expovariate(updates_per_sec)
            await asyncio.sleep(dt)
        else:
            # steady pacing
            await asyncio.sleep(interval)

        cur = occ_state[park_id]
        cur = max(0, min(max_capacity, cur + random.choice([-1, 0, 1])))
        occ_state[park_id] = cur
        payload = {"parkId": park_id, "currentOccupancy": cur}

        await sem.acquire()
        asyncio.create_task(_do_req(sem, measured_request(client, "POST", f"{base_url}/api/occupancy", ep, json_body=payload)))


async def payment_producer(
    stop_at: float,
    base_url: str,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    stats,
    park_ids: list[str],
    sessions_per_sec_total: float,
    checks: int,
    check_interval: float,
    poisson: bool,
    payment_tasks: set[asyncio.Task],
):
    """
    Spawns payment session task chains and tracks them in `payment_tasks`
    so we can cancel/await them at the end of the step (no pending-task warnings).
    """
    if sessions_per_sec_total <= 0:
        return

    enter_ep = stats["POST /api/payment/enter"]
    check_ep = stats["GET /api/payment/check"]
    pay_ep = stats["POST /api/payment/pay"]
    exit_ep = stats["DELETE /api/payment/exit"]

    while time.perf_counter() < stop_at:
        if poisson:
            await asyncio.sleep(random.expovariate(sessions_per_sec_total))
        else:
            await asyncio.sleep(1.0 / sessions_per_sec_total)

        park_id = random.choice(park_ids)
        plate = f"{park_id}-PLATE-{random.randint(1, 99999999)}"

        t = asyncio.create_task(
            _payment_session(
                base_url, client, sem,
                enter_ep, check_ep, pay_ep, exit_ep,
                plate, checks, check_interval
            )
        )
        payment_tasks.add(t)
        t.add_done_callback(payment_tasks.discard)



async def _payment_session(
    base_url: str,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    enter_ep: EndpointStats,
    check_ep: EndpointStats,
    pay_ep: EndpointStats,
    exit_ep: EndpointStats,
    plate: str,
    checks: int,
    check_interval: float,
):
    # enter
    await sem.acquire()
    await _do_req(sem, measured_request(client, "POST", f"{base_url}/api/payment/enter", enter_ep, json_body={"licensePlate": plate}))
    # checks
    for _ in range(max(0, checks)):
        await asyncio.sleep(max(0.0, check_interval + random.uniform(-0.2, 0.2)))
        await sem.acquire()
        await _do_req(sem, measured_request(client, "GET", f"{base_url}/api/payment/check", check_ep, params={"licensePlate": plate}))
    # pay
    await sem.acquire()
    await _do_req(sem, measured_request(client, "POST", f"{base_url}/api/payment/pay", pay_ep, json_body={"licensePlate": plate}))
    # exit
    await sem.acquire()
    await _do_req(sem, measured_request(client, "DELETE", f"{base_url}/api/payment/exit", exit_ep, params={"licensePlate": plate}))


async def _do_req(sem: asyncio.Semaphore, req_coro):
    try:
        await req_coro
    finally:
        sem.release()


# -------------------------
# Step runner
# -------------------------

def count_payment_requests(stats: Dict[str, EndpointStats]) -> int:
    return (
        stats["POST /api/payment/enter"].count
        + stats["GET /api/payment/check"].count
        + stats["POST /api/payment/pay"].count
        + stats["DELETE /api/payment/exit"].count
    )


async def run_step(
    base_url: str,
    client: httpx.AsyncClient,
    lots,
    *,
    step_duration: int,
    warmup: float,
    max_capacity: int,
    edges: int,
    updates_per_edge: float,
    occ_workers_per_edge: int,
    inflight: int,
    include_payment: bool,
    payment_sessions_per_sec: float,
    payment_checks: int,
    payment_check_interval: float,
    poisson: bool,
):
    stats = make_stats_map()
    park_ids = [p for (p, _, _) in lots]
    occ_state = {p: 0 for p in park_ids}

    async def phase(duration_s: float, measure: bool):
        phase_stats = stats if measure else make_stats_map()
        sem = asyncio.Semaphore(inflight)
        stop_at = time.perf_counter() + duration_s

        # Track all spawned payment session tasks to cancel/await them cleanly
        payment_tasks: set[asyncio.Task] = set()

        tasks = []

        # health
        tasks.append(asyncio.create_task(
            health_producer(stop_at, base_url, client, sem, phase_stats)
        ))

        # occupancy producers
        per_worker_rate = updates_per_edge / max(1, occ_workers_per_edge)
        for park_id in park_ids:
            for _ in range(max(1, occ_workers_per_edge)):
                tasks.append(asyncio.create_task(
                    occupancy_producer(
                        stop_at, base_url, client, sem, phase_stats,
                        park_id, max_capacity, per_worker_rate, occ_state, poisson
                    )
                ))

        # payment producer (spawns background session tasks -> tracked)
        if include_payment and payment_sessions_per_sec > 0:
            tasks.append(asyncio.create_task(
                payment_producer(
                    stop_at, base_url, client, sem, phase_stats,
                    park_ids,
                    payment_sessions_per_sec,
                    payment_checks,
                    payment_check_interval,
                    poisson,
                    payment_tasks,   # <-- new
                )
            ))

        # wait for producers to stop
        await asyncio.gather(*tasks, return_exceptions=True)

        # IMPORTANT: stop outstanding payment session chains cleanly
        if payment_tasks:
            for t in list(payment_tasks):
                t.cancel()
            await asyncio.gather(*payment_tasks, return_exceptions=True)
            payment_tasks.clear()

        # Drain in-flight HTTP requests (no request running means we can acquire all permits)
        for _ in range(inflight):
            await sem.acquire()

    start = time.time()

    if warmup > 0:
        await phase(warmup, measure=False)

    t0 = time.perf_counter()
    await phase(step_duration, measure=True)
    measured_elapsed = time.perf_counter() - t0
    end = time.time()

    # aggregate
    all_lat = []
    total_count = total_ok = total_fail = total_timeouts = 0
    for st in stats.values():
        total_count += st.count
        total_ok += st.ok
        total_fail += st.fail
        total_timeouts += st.timeouts
        all_lat.extend(st.lat_ms)

    occ_count = stats["POST /api/occupancy"].count
    pay_count = count_payment_requests(stats)
    health_count = stats["GET /health"].count

    return {
        "step": {
            "updates_per_sec_per_edge": updates_per_edge,
            "target_occupancy_rps": edges * updates_per_edge,
            "occ_workers_per_edge": occ_workers_per_edge,
            "inflight_limit": inflight,
            "payment_sessions_per_sec_total": payment_sessions_per_sec if include_payment else 0.0,
            "payment_checks": payment_checks if include_payment else 0,
            "payment_check_interval_s": payment_check_interval if include_payment else 0.0,
            "poisson_arrivals": poisson,
            "warmup_s": warmup,
            "measured_duration_s": step_duration,
        },
        "time": {
            "started_epoch": start,
            "ended_epoch": end,
            "measured_elapsed_s": measured_elapsed,
        },
        "rates": {
            "actual_total_rps": total_count / max(measured_elapsed, 1e-9),
            "actual_occupancy_rps": occ_count / max(measured_elapsed, 1e-9),
            "actual_payment_rps": pay_count / max(measured_elapsed, 1e-9),
            "actual_health_rps": health_count / max(measured_elapsed, 1e-9),
        },
        "overall": {
            "total_requests": total_count,
            "ok": total_ok,
            "fail": total_fail,
            "timeouts": total_timeouts,
            "success_rate": (total_ok / total_count * 100.0) if total_count else 0.0,
            "latency_ms": {
                "avg": statistics.fmean(all_lat) if all_lat else None,
                "p50": percentile(all_lat, 50),
                "p95": percentile(all_lat, 95),
                "p99": percentile(all_lat, 99),
                "max": max(all_lat) if all_lat else None,
            },
        },
        "endpoints": {k: stats[k].summary() for k in stats},
    }



# -------------------------
# CLI
# -------------------------

def parse_steps(s: str) -> List[float]:
    out = []
    for part in s.split(","):
        part = part.strip()
        if part:
            out.append(float(part))
    if not out:
        raise ValueError("--steps must not be empty")
    return out


def print_step(result: dict, i: int, n: int, base_url: str, edges: int):
    step = result["step"]
    rates = result["rates"]
    overall = result["overall"]
    lat = overall["latency_ms"]

    print("\n" + "=" * 72)
    print(f"STEP {i}/{n}  base={base_url}  edges={edges}")
    print("=" * 72)
    print(f"occ target: {step['target_occupancy_rps']:.2f} rps  (per-edge={step['updates_per_sec_per_edge']:.2f}, workers/edge={step['occ_workers_per_edge']})")
    print(f"occ actual: {rates['actual_occupancy_rps']:.2f} rps")
    print(f"pay target sessions: {step['payment_sessions_per_sec_total']:.2f}/s  | pay actual req: {rates['actual_payment_rps']:.2f} rps")
    print(f"TOTAL actual: {rates['actual_total_rps']:.2f} rps  | inflight_limit={step['inflight_limit']}")
    print(f"ok={overall['ok']} fail={overall['fail']} timeouts={overall['timeouts']} success={overall['success_rate']:.2f}%")
    if lat["avg"] is not None:
        print(f"lat ms avg={lat['avg']:.1f} p50={lat['p50']:.1f} p95={lat['p95']:.1f} p99={lat['p99']:.1f} max={lat['max']:.1f}")
    print("=" * 72)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--edges", type=int, default=10)
    ap.add_argument("--max-capacity", type=int, default=67)

    ap.add_argument("--step-duration", type=int, default=60)
    ap.add_argument("--warmup", type=float, default=10.0)
    ap.add_argument("--cooldown", type=float, default=2.0)
    ap.add_argument("--steps", required=True, help="comma-separated occupancy updates/s PER EDGE")

    ap.add_argument("--timeout", type=float, default=5.0)

    # This is the key control now:
    ap.add_argument("--inflight", type=int, default=2000, help="max concurrent in-flight HTTP requests")
    ap.add_argument("--occ-workers-per-edge", type=int, default=1, help="more producers per edge to reach high rps")
    ap.add_argument("--poisson", action="store_true", help="poisson arrivals instead of constant pacing")

    ap.add_argument("--include-payment", action="store_true")
    ap.add_argument("--payment-sessions-per-sec", type=float, default=0.0)
    ap.add_argument("--payment-checks", type=int, default=3)
    ap.add_argument("--payment-check-interval", type=float, default=1.0)

    ap.add_argument("--out", default="http_test_v2")
    ap.add_argument("--keep-parking-lots", action="store_true")

    args = ap.parse_args()
    base_url = args.base_url.rstrip("/")
    edges = max(1, args.edges)
    steps = parse_steps(args.steps)

    lots = gen_city_lots(edges)

    limits = httpx.Limits(
        max_connections=args.inflight,
        max_keepalive_connections=args.inflight,
        keepalive_expiry=30.0,
    )
    timeout = httpx.Timeout(args.timeout)

    agg = []

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        # sanity check
        check_stats = make_stats_map()
        ok, _ = await measured_request(client, "GET", f"{base_url}/health", check_stats["GET /health"])
        if not ok:
            print(f"[ERROR] /health not reachable: {base_url}")
            return

        setup_stats = make_stats_map()
        await register_lots(client, base_url, args.max_capacity, setup_stats, lots)

        for idx, per_edge in enumerate(steps, start=1):
            res = await run_step(
                base_url, client, lots,
                step_duration=args.step_duration,
                warmup=args.warmup,
                max_capacity=args.max_capacity,
                edges=edges,
                updates_per_edge=per_edge,
                occ_workers_per_edge=max(1, args.occ_workers_per_edge),
                inflight=max(1, args.inflight),
                include_payment=bool(args.include_payment),
                payment_sessions_per_sec=max(0.0, args.payment_sessions_per_sec),
                payment_checks=max(0, args.payment_checks),
                payment_check_interval=max(0.0, args.payment_check_interval),
                poisson=bool(args.poisson),
            )

            print_step(res, idx, len(steps), base_url, edges)

            out_path = f"{args.out}_step{idx:02d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
            print(f"Saved: {out_path}")

            agg.append({
                "step": idx,
                "updates_per_sec_per_edge": per_edge,
                "target_occ_rps": res["step"]["target_occupancy_rps"],
                "actual_occ_rps": res["rates"]["actual_occupancy_rps"],
                "actual_total_rps": res["rates"]["actual_total_rps"],
                "success_rate": res["overall"]["success_rate"],
                "timeouts": res["overall"]["timeouts"],
                "p95_ms": res["overall"]["latency_ms"]["p95"],
                "p99_ms": res["overall"]["latency_ms"]["p99"],
            })

            if args.cooldown > 0:
                await asyncio.sleep(args.cooldown)

        if not args.keep_parking_lots:
            cleanup_stats = make_stats_map()
            await deregister_lots(client, base_url, cleanup_stats, lots)

    agg_path = f"{args.out}_aggregate.json"
    with open(agg_path, "w", encoding="utf-8") as f:
        json.dump({"config": vars(args), "summary": agg}, f, indent=2)
    print(f"\nSaved aggregate: {agg_path}")


if __name__ == "__main__":
    asyncio.run(main())
