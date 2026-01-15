#!/usr/bin/env python3
"""
NATS RTT Load Test (Request/Reply)

Measures end-to-end round-trip time for NATS request/reply on subjects like:
  entry_<camera_id>.trigger
  exit_<camera_id>.trigger

Example:
  python3 nats_rtt_load_test.py --nats nats://localhost:4223 --camera-id vienna_0 --mode both --rate 20 --concurrency 50 --duration 60
"""

import argparse
import asyncio
import random
import string
import time
from dataclasses import dataclass
from typing import List, Dict, Optional

from nats.aio.client import Client as NATS
from nats.errors import NoRespondersError, TimeoutError as NATSTimeoutError


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


@dataclass
class Stats:
    sent: int = 0
    ok: int = 0
    timeout: int = 0
    no_responders: int = 0
    other_err: int = 0
    rtts_ms: List[float] = None

    def __post_init__(self):
        if self.rtts_ms is None:
            self.rtts_ms = []

    def summary_row(self, name: str) -> str:
        vals = sorted(self.rtts_ms)
        avg = (sum(vals) / len(vals)) if vals else float("nan")
        p50 = percentile(vals, 50)
        p95 = percentile(vals, 95)
        p99 = percentile(vals, 99)
        mx = vals[-1] if vals else float("nan")
        return (
            f"{name},{self.sent},{self.ok},{self.timeout},{self.no_responders},{self.other_err},"
            f"{avg},{p50},{p95},{p99},{mx}"
        )


def make_payload(size_kb: int) -> bytes:
    # deterministic-ish payload (not just zeros)
    size = size_kb * 1024
    seed = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64)).encode()
    out = bytearray()
    while len(out) < size:
        out.extend(seed)
    return bytes(out[:size])


async def worker(
    nc: NATS,
    subject: str,
    payload: bytes,
    timeout_s: float,
    end_time: float,
    rate_per_worker: float,
    stats: Stats,
    name: str,
):
    """
    Each worker sends requests at its own pace until end_time.
    rate_per_worker: requests/sec for this worker
    """
    # interval between requests per worker
    interval = 1.0 / rate_per_worker if rate_per_worker > 0 else 0.0

    while time.perf_counter() < end_time:
        t0 = now_ms()
        stats.sent += 1
        try:
            await nc.request(subject, payload, timeout=timeout_s)
            t1 = now_ms()
            stats.ok += 1
            stats.rtts_ms.append(t1 - t0)
        except NoRespondersError:
            stats.no_responders += 1
        except NATSTimeoutError:
            stats.timeout += 1
        except Exception:
            stats.other_err += 1

        # pace
        if interval > 0:
            # try to keep roughly constant rate
            await asyncio.sleep(interval)


async def run_test(args) -> Dict[str, Stats]:
    subjects = []
    if args.mode in ("entry", "both"):
        subjects.append(("entry", f"entry_{args.camera_id}.trigger"))
    if args.mode in ("exit", "both"):
        subjects.append(("exit", f"exit_{args.camera_id}.trigger"))

    payload = make_payload(args.msg_kb)

    nc = NATS()
    await nc.connect(servers=[args.nats], connect_timeout=args.timeout)

    results: Dict[str, Stats] = {name: Stats() for name, _ in subjects}

    # We split rate across (stream * workers) so total ~= args.rate per stream.
    tasks = []
    end_time = time.perf_counter() + args.duration

    for name, subj in subjects:
        # rate per worker so total rate per stream ~= args.rate
        per_worker_rate = (args.rate / args.concurrency) if args.concurrency > 0 else args.rate
        for _ in range(args.concurrency):
            tasks.append(
                asyncio.create_task(
                    worker(
                        nc=nc,
                        subject=subj,
                        payload=payload,
                        timeout_s=args.timeout,
                        end_time=end_time,
                        rate_per_worker=per_worker_rate,
                        stats=results[name],
                        name=name,
                    )
                )
            )

    await asyncio.gather(*tasks)
    await nc.drain()
    return results


def print_report(args, results: Dict[str, Stats]):
    print("\nRESULTS (NATS RTT Load Test)")
    print(f"NATS: {args.nats}")
    print(
        f"camera_id: {args.camera_id} | mode: {args.mode} | msg_kb: {args.msg_kb} | "
        f"rate: {args.rate}/s per stream | concurrency: {args.concurrency} | duration: {args.duration}s | timeout: {args.timeout}s"
    )
    print("-" * 96)
    print("stream,sent,ok,timeout,no_responders,other_err,avg_rtt_ms,p50_ms,p95_ms,p99_ms,max_ms")
    for name, st in results.items():
        print(st.summary_row(name))
    print("-" * 96)
    print("Notes:")
    print("- 'no_responders' > 0 => subject has no active subscriber responding (e.g., barrier not running).")
    print("- 'timeout' > 0 => responder too slow / overloaded / network issues.")
    print("- RTT includes: client->NATS->responder->NATS->client.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nats", required=True, help="e.g., nats://localhost:4223")
    ap.add_argument("--camera-id", required=True, help="e.g., vienna_0 (subjects become entry_vienna_0.trigger)")
    ap.add_argument("--mode", choices=["entry", "exit", "both"], default="both")
    ap.add_argument("--msg-kb", type=int, default=1, help="payload size in KB for each request")
    ap.add_argument("--rate", type=float, default=10.0, help="requests/sec per stream")
    ap.add_argument("--concurrency", type=int, default=20, help="number of concurrent workers per stream")
    ap.add_argument("--duration", type=float, default=60.0, help="seconds")
    ap.add_argument("--timeout", type=float, default=2.0, help="NATS request timeout in seconds")
    args = ap.parse_args()

    results = asyncio.run(run_test(args))
    print_report(args, results)


if __name__ == "__main__":
    main()
