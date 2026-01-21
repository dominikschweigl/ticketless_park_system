#!/usr/bin/env python3
"""
webserver_step_test.py
Step-wise open-loop load test for testcase 2 (webserver) using wrk2.
- Runs a ladder of target RPS steps
- Captures tail latency + error metrics
- Writes aggregate.csv (+ raw logs)

Requirements:
  - wrk2 in PATH (binary name "wrk2" or "wrk")
Usage examples:
  python3 webserver_step_test.py --url http://3.84.22.38:8080 --path /assets/index-xxxx.js

  # 2-endpoint mix (default weights 30/70):
  python3 webserver_step_test.py --url http://3.84.22.38:8080 --paths /,/assets/index-xxxx.js

  # Custom steps:
  python3 webserver_step_test.py --url http://... --path / --steps 50,100,200,400,800
"""

import argparse
import csv
import os
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---------------- parsing wrk2 output ----------------

RE_REQUESTS = re.compile(r"Requests/sec:\s+([\d\.]+)")
RE_TRANSFER = re.compile(r"Transfer/sec:\s+([\d\.]+)([KMG]?B)")
RE_NON2XX = re.compile(r"Non-2xx or 3xx responses:\s+(\d+)")
RE_SOCKET = re.compile(r"Socket errors:\s+connect (\d+), read (\d+), write (\d+), timeout (\d+)")
RE_LAT_LINE = re.compile(r"\s+(\d+\.?\d*)%\s+(\d+\.?\d*)(us|ms|s)\s*$")

UNIT_MS = {"us": 0.001, "ms": 1.0, "s": 1000.0}
UNIT_BYTES = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}

def _parse_latency_table(text: str) -> Dict[float, float]:
    """
    Parses the latency distribution table printed by wrk2 --latency.
    Returns percentile->ms, e.g. 99.0 -> 12.3
    """
    out: Dict[float, float] = {}
    for p, v, u in RE_LAT_LINE.findall(text):
        out[float(p)] = float(v) * UNIT_MS[u]
    return out

def parse_wrk2_output(text: str) -> Dict[str, object]:
    achieved = float(RE_REQUESTS.search(text).group(1)) if RE_REQUESTS.search(text) else None

    transfer_bps = None
    tm = RE_TRANSFER.search(text)
    if tm:
        transfer_bps = float(tm.group(1)) * UNIT_BYTES[tm.group(2)]

    non2xx = int(RE_NON2XX.search(text).group(1)) if RE_NON2XX.search(text) else 0

    connect_err = read_err = write_err = timeout_err = 0
    sm = RE_SOCKET.search(text)
    if sm:
        connect_err, read_err, write_err, timeout_err = map(int, sm.groups())

    pmap = _parse_latency_table(text)
    def gp(p: float) -> Optional[float]:
        return pmap.get(p)

    return {
        "achieved_rps": achieved,
        "transfer_bytes_per_s": transfer_bps,
        "p50_ms": gp(50.0),
        "p90_ms": gp(90.0),
        "p95_ms": gp(95.0),
        "p99_ms": gp(99.0),
        "p999_ms": gp(99.9),
        "max_ms": gp(100.0),
        "non2xx": non2xx,
        "sock_connect": connect_err,
        "sock_read": read_err,
        "sock_write": write_err,
        "sock_timeout": timeout_err,
    }

# ---------------- request mix (no lua) ----------------

@dataclass
class PathMix:
    paths: List[str]
    weights: List[int]

    def choose(self) -> str:
        return random.choices(self.paths, weights=self.weights, k=1)[0]

def build_mix(paths: List[str], weights: Optional[List[int]]) -> PathMix:
    if len(paths) == 1:
        return PathMix(paths=paths, weights=[1])
    if weights is None:
        # default: 30% "/" + 70% "bundle"
        # If you pass two paths, we assume first is "/" and second is the big asset.
        return PathMix(paths=paths, weights=[30] + [70] * (len(paths) - 1))
    if len(weights) != len(paths):
        raise ValueError("weights length must match paths length")
    return PathMix(paths=paths, weights=weights)

# ---------------- runner ----------------

def find_wrk2() -> str:
    # Prefer explicit "wrk2" if user installed that name; else "wrk"
    for name in ("wrk2", "wrk"):
        p = shutil.which(name)
        if p:
            return name
    raise RuntimeError("Neither 'wrk2' nor 'wrk' found in PATH. Install wrk2 and ensure it's in PATH.")

def run_wrk2_step(wrk_bin: str, url: str, path: str, threads: int, conns: int,
                 duration_s: int, rps: int, latency: bool = True) -> Tuple[int, str]:
    full = url.rstrip("/") + path
    cmd = [
        wrk_bin,
        f"-t{threads}",
        f"-c{conns}",
        f"-d{duration_s}s",
        f"-R{rps}",
    ]
    if latency:
        cmd.append("--latency")
    cmd.append(full)

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Base URL, e.g. http://3.84.22.38:8080")
    ap.add_argument("--path", help="Single path to test, e.g. /assets/index-xxxx.js")
    ap.add_argument("--paths", help="Comma-separated paths for a mix, e.g. /,/assets/index-xxxx.js")
    ap.add_argument("--weights", help="Comma-separated weights (same count as paths), e.g. 30,70")
    ap.add_argument("--steps", default="50,100,200,400,800,1200,1600,2000,2400,2800,3200",
                    help="Comma-separated target RPS steps")
    ap.add_argument("--warmup", type=int, default=10, help="Warmup seconds (not recorded)")
    ap.add_argument("--duration", type=int, default=60, help="Measured seconds per step")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--conns", type=int, default=256)
    ap.add_argument("--out", default="web_tc2_out", help="Output directory")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--raw", action="store_true", help="Write raw wrk2 output per step")
    args = ap.parse_args()

    random.seed(args.seed)

    if not args.path and not args.paths:
        ap.error("Provide either --path or --paths")

    if args.path and args.paths:
        ap.error("Use only one of --path or --paths")

    paths = [args.path] if args.path else [p.strip() for p in args.paths.split(",") if p.strip()]
    weights = None
    if args.weights:
        weights = [int(x.strip()) for x in args.weights.split(",") if x.strip()]

    mix = build_mix(paths, weights)
    steps = [int(s.strip()) for s in args.steps.split(",") if s.strip()]

    wrk_bin = find_wrk2()
    os.makedirs(args.out, exist_ok=True)

    rows = []
    for idx, rps in enumerate(steps, start=1):
        chosen_path = mix.choose()

        # warmup (same target RPS, same selected path)
        _, _ = run_wrk2_step(wrk_bin, args.url, chosen_path, args.threads, args.conns, args.warmup, rps)

        # measured
        rc, out = run_wrk2_step(wrk_bin, args.url, chosen_path, args.threads, args.conns, args.duration, rps)

        if args.raw:
            fname = os.path.join(args.out, f"step{idx:02d}_rps{rps}_{re.sub(r'[^a-zA-Z0-9]+','_',chosen_path)}.txt")
            with open(fname, "w") as f:
                f.write(out)

        parsed = parse_wrk2_output(out)
        row = {
            "step": idx,
            "target_rps": rps,
            "path": chosen_path,
            "threads": args.threads,
            "conns": args.conns,
            "warmup_s": args.warmup,
            "duration_s": args.duration,
            "exit_code": rc,
            **parsed,
        }
        rows.append(row)

        # quick console progress line
        print(
            f"[{idx:02d}] target={rps:5d} "
            f"ach={row['achieved_rps'] if row['achieved_rps'] is not None else 'NA'} rps "
            f"p99={row['p99_ms']}ms p999={row['p999_ms']}ms "
            f"to={row['sock_timeout']} non2xx={row['non2xx']} path={chosen_path}"
        )
        time.sleep(1)  # tiny cooldown to reduce burst artifacts

    out_csv = os.path.join(args.out, "aggregate.csv")
    with open(out_csv, "w", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {out_csv}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
