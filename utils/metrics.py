from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RequestSample:
    timestamp_ms: int
    method: str
    path: str
    status_code: int
    latency_ms: float


class MetricsRegistry:
    def __init__(self, max_samples: int = 5000) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._active_requests = 0
        self._request_count: Counter[str] = Counter()
        self._status_count: Counter[str] = Counter()
        self._endpoint_count: Counter[str] = Counter()
        self._latencies: defaultdict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
        self._samples: deque[RequestSample] = deque(maxlen=max_samples)

    def start_request(self) -> float:
        with self._lock:
            self._active_requests += 1
        return time.perf_counter()

    def finish_request(self, method: str, path: str, status_code: int, start_time: float) -> None:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        normalized_path = _normalize_path(path)
        route_key = f"{method.upper()} {normalized_path}"
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            self._request_count[route_key] += 1
            self._status_count[str(status_code)] += 1
            self._endpoint_count[normalized_path] += 1
            self._latencies[route_key].append(latency_ms)
            self._samples.append(RequestSample(int(time.time() * 1000), method.upper(), normalized_path, status_code, latency_ms))

    def snapshot(self, window_seconds: int | None = None) -> dict[str, Any]:
        cutoff_ms = None if window_seconds is None else int((time.time() - window_seconds) * 1000)
        with self._lock:
            samples = list(self._samples)
            active = self._active_requests
            started_at = self._started_at
            all_counts = Counter(self._request_count)
            all_status = Counter(self._status_count)
            all_endpoint = Counter(self._endpoint_count)
        if cutoff_ms is not None:
            samples = [s for s in samples if s.timestamp_ms >= cutoff_ms]
            request_count = Counter(f"{s.method} {s.path}" for s in samples)
            status_count = Counter(str(s.status_code) for s in samples)
            endpoint_count = Counter(s.path for s in samples)
        else:
            request_count = all_counts
            status_count = all_status
            endpoint_count = all_endpoint
        latencies = [s.latency_ms for s in samples]
        slowest = sorted(samples, key=lambda s: s.latency_ms, reverse=True)[:10]
        return {
            "status": "ok",
            "started_at_ms": int(started_at * 1000),
            "uptime_seconds": round(time.time() - started_at, 2),
            "window_seconds": window_seconds,
            "active_requests": active,
            "total_requests": sum(request_count.values()),
            "status_counts": dict(sorted(status_count.items())),
            "top_endpoints": [{"path": path, "count": count} for path, count in endpoint_count.most_common(20)],
            "top_routes": [{"route": route, "count": count} for route, count in request_count.most_common(20)],
            "error_count": sum(c for s, c in status_count.items() if s.startswith(("4", "5"))),
            "redirect_count": sum(c for s, c in status_count.items() if s.startswith("3")),
            "auth_failures": sum(1 for s in samples if s.status_code == 403),
            "validation_failures": sum(1 for s in samples if s.status_code == 422),
            "latency_ms": _latency_summary(latencies),
            "top_slowest": [asdict(s) for s in slowest],
            "timestamp_ms": int(time.time() * 1000),
        }


metrics_registry = MetricsRegistry()


def _normalize_path(path: str) -> str:
    return (path or "/").rstrip("/") or "/"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, int(round((percentile / 100) * (len(values) - 1))))
    return round(values[index], 2)


def _latency_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "p50": None, "p95": None, "p99": None, "max": None, "avg": None}
    return {
        "count": len(values),
        "min": round(min(values), 2),
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "p99": _percentile(values, 99),
        "max": round(max(values), 2),
        "avg": round(sum(values) / len(values), 2),
    }
