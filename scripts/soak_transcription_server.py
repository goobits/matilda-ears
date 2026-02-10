#!/usr/bin/env python3
"""Long-running soak test for Matilda Ears WebSocket transcription server."""

import argparse
import asyncio
import base64
import json
import math
import statistics
import time
import uuid
from pathlib import Path

import aiohttp
import numpy as np
import websockets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Soak test Matilda Ears server for latency and resource drift.")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8769", help="WebSocket URL")
    parser.add_argument("--health-url", default="http://127.0.0.1:8770/health", help="Health endpoint URL")
    parser.add_argument("--iterations", type=int, default=200, help="Number of stream sessions")
    parser.add_argument("--chunks-per-iteration", type=int, default=20, help="PCM chunks per stream session")
    parser.add_argument("--chunk-ms", type=int, default=100, help="Chunk size in milliseconds")
    parser.add_argument("--sleep-ms", type=int, default=50, help="Pause between iterations in milliseconds")
    parser.add_argument("--sample-rate", type=int, default=16000, help="PCM sample rate")
    parser.add_argument("--report-every", type=int, default=10, help="Progress report interval")
    parser.add_argument("--server-pid", type=int, default=0, help="Optional PID for RSS reporting")
    parser.add_argument(
        "--out",
        default=".artifacts/logs/ears_soak_metrics.jsonl",
        help="JSONL output file for per-iteration metrics",
    )
    return parser.parse_args()


def generate_pcm_chunk(sample_rate: int, duration_ms: int, phase: float) -> tuple[np.ndarray, float]:
    sample_count = max(1, int(sample_rate * duration_ms / 1000))
    t = np.arange(sample_count, dtype=np.float32) / sample_rate
    # Simple synthetic voiced-like tone plus noise, keeps payload non-empty and deterministic enough for soak.
    tone = 0.25 * np.sin(2.0 * math.pi * 220.0 * t + phase)
    noise = 0.03 * np.random.standard_normal(sample_count).astype(np.float32)
    samples = np.clip((tone + noise) * 32767.0, -32768, 32767).astype(np.int16)
    phase_out = phase + (2.0 * math.pi * 220.0 * (sample_count / sample_rate))
    return samples, phase_out


async def fetch_health(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
            return await response.json()
    except Exception as e:
        return {"health_error": str(e)}


def rss_for_pid(pid: int) -> int | None:
    if pid <= 0:
        return None
    try:
        import psutil

        return int(psutil.Process(pid).memory_info().rss)
    except Exception:
        return None


async def wait_for_session_response(ws, session_id: str, timeout_s: float = 45.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for session {session_id} response")
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        payload = json.loads(raw)
        task = payload.get("task")
        result = payload.get("result") or {}
        error = payload.get("error") or {}

        if task in {"stream_transcription_complete", "error"}:
            result_session_id = result.get("session_id")
            error_session_id = error.get("session_id")
            if result_session_id == session_id or error_session_id == session_id:
                return payload
            if task == "error" and "Unknown session" in str(error.get("message", "")):
                return payload


async def run() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    latencies_ms: list[float] = []
    failures = 0
    phase = 0.0
    started = time.monotonic()

    async with aiohttp.ClientSession() as http_session:
        async with websockets.connect(args.ws_url, max_size=50 * 1024 * 1024) as ws:
            for i in range(1, args.iterations + 1):
                session_id = f"soak-{uuid.uuid4().hex[:12]}"
                await ws.send(
                    json.dumps(
                        {
                            "type": "start_stream",
                            "session_id": session_id,
                            "sample_rate": args.sample_rate,
                            "channels": 1,
                            "binary": False,
                        }
                    )
                )

                for _ in range(args.chunks_per_iteration):
                    pcm, phase = generate_pcm_chunk(args.sample_rate, args.chunk_ms, phase)
                    await ws.send(
                        json.dumps(
                            {
                                "type": "pcm_chunk",
                                "session_id": session_id,
                                "audio_data": base64.b64encode(pcm.tobytes()).decode("ascii"),
                            }
                        )
                    )

                end_sent = time.monotonic()
                await ws.send(json.dumps({"type": "end_stream", "session_id": session_id}))

                ok = False
                error_message = ""
                try:
                    payload = await wait_for_session_response(ws, session_id)
                    if payload.get("task") == "stream_transcription_complete":
                        ok = True
                    else:
                        error_message = str((payload.get("error") or {}).get("message", "unknown error"))
                except Exception as e:
                    error_message = str(e)

                latency_ms = (time.monotonic() - end_sent) * 1000.0
                latencies_ms.append(latency_ms)
                if not ok:
                    failures += 1

                health = await fetch_health(http_session, args.health_url)
                metric = {
                    "iteration": i,
                    "ok": ok,
                    "latency_ms": round(latency_ms, 2),
                    "error": error_message,
                    "health": health,
                    "rss_bytes": rss_for_pid(args.server_pid),
                    "elapsed_s": round(time.monotonic() - started, 2),
                }
                with out_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(metric, ensure_ascii=True) + "\n")

                if i % args.report_every == 0:
                    p50 = statistics.median(latencies_ms) if latencies_ms else 0.0
                    p95 = (
                        statistics.quantiles(latencies_ms, n=100, method="inclusive")[94]
                        if len(latencies_ms) >= 20
                        else max(latencies_ms)
                    )
                    print(
                        f"[{i}/{args.iterations}] failures={failures}, latency_ms p50={p50:.1f}, p95={p95:.1f}, "
                        f"health={health}"
                    )

                if args.sleep_ms > 0:
                    await asyncio.sleep(args.sleep_ms / 1000.0)

    p50 = statistics.median(latencies_ms) if latencies_ms else 0.0
    p95 = (
        statistics.quantiles(latencies_ms, n=100, method="inclusive")[94] if len(latencies_ms) >= 20 else max(latencies_ms)
    )
    print(
        f"Completed {args.iterations} iterations in {time.monotonic() - started:.1f}s. "
        f"Failures={failures}, latency_ms p50={p50:.1f}, p95={p95:.1f}, out={out_path}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
