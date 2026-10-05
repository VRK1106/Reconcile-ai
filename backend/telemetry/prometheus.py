"""
Prometheus Metrics Exporter & System Telemetry Collector.
Provides standard Prometheus scrape format (/metrics) and JSON telemetry for real-time monitoring.
"""
import time
import psutil
import os
from typing import Dict, Any, List
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY
)

# Metric Definitions
INVOICE_PROCESSED_TOTAL = Counter(
    "reconcile_invoices_processed_total",
    "Total count of processed invoices",
    ["source", "status", "confidence"]
)

RECONCILIATION_LATENCY = Histogram(
    "reconcile_processing_latency_seconds",
    "End-to-end reconciliation latency per invoice",
    ["decision"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
)

GUARDRAIL_VIOLATIONS_TOTAL = Counter(
    "reconcile_guardrail_violations_total",
    "Count of Layer 2 guardrail violations caught",
    ["rule_type"]
)

TOOL_EXECUTIONS_TOTAL = Counter(
    "reconcile_tool_executions_total",
    "Count of Layer 3 tool executions",
    ["tool_name"]
)

TOOL_LATENCY_HISTOGRAM = Histogram(
    "reconcile_tool_latency_seconds",
    "Execution duration for individual reconciliation tools",
    ["tool_name"],
    buckets=[0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1]
)

AUTO_RESOLUTION_GAUGE = Gauge(
    "reconcile_auto_resolution_rate_percent",
    "Live percentage of invoices auto-resolved with zero human intervention"
)

SYSTEM_CPU_PERCENT = Gauge(
    "reconcile_system_cpu_usage_percent",
    "Current CPU usage percentage of the host server"
)

SYSTEM_MEMORY_MB = Gauge(
    "reconcile_system_memory_resident_mb",
    "Process Resident Memory in Megabytes"
)

ACTIVE_HITL_TASKS = Gauge(
    "reconcile_hitl_pending_tasks_gauge",
    "Current count of open Human-in-the-Loop approval tasks"
)

# In-Memory Latency Rolling Window for SLA / p50 / p95 / p99 stats
class PerformanceTracker:
    def __init__(self, max_samples: int = 500):
        self.max_samples = max_samples
        self.latencies: List[float] = [] # in milliseconds
        self.tool_latencies: Dict[str, List[float]] = {}
        self.start_time = time.time()
        self.total_processed = 0
        self.auto_resolved = 0
        self.hitl_count = 0
        self.blocked_count = 0

    def record_invoice(self, duration_ms: float, decision: str, confidence: str, guardrail_passed: bool):
        self.total_processed += 1
        self.latencies.append(duration_ms)
        if len(self.latencies) > self.max_samples:
            self.latencies.pop(0)

        if decision == "AUTO_RESOLVE_PAID":
            self.auto_resolved += 1
        elif confidence == "MEDIUM":
            self.hitl_count += 1
        elif not guardrail_passed or decision == "BLOCKED_BY_GUARDRAIL":
            self.blocked_count += 1

        rate = (self.auto_resolved / self.total_processed * 100.0) if self.total_processed > 0 else 0.0
        AUTO_RESOLUTION_GAUGE.set(rate)

    def record_tool(self, tool_name: str, duration_ms: float):
        if tool_name not in self.tool_latencies:
            self.tool_latencies[tool_name] = []
        self.tool_latencies[tool_name].append(duration_ms)
        if len(self.tool_latencies[tool_name]) > self.max_samples:
            self.tool_latencies[tool_name].pop(0)

    def get_summary(self) -> Dict[str, Any]:
        uptime_sec = round(time.time() - self.start_time, 1)
        proc = psutil.Process(os.getpid())
        mem_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
        cpu_pct = round(psutil.cpu_percent(interval=None), 1)

        SYSTEM_CPU_PERCENT.set(cpu_pct)
        SYSTEM_MEMORY_MB.set(mem_mb)

        sorted_lat = sorted(self.latencies) if self.latencies else [0.0]
        n = len(sorted_lat)
        p50 = sorted_lat[int(n * 0.50)] if n else 0.0
        p95 = sorted_lat[int(n * 0.95)] if n else 0.0
        p99 = sorted_lat[int(n * 0.99)] if n else 0.0
        avg_lat = round(sum(sorted_lat) / n, 2) if n else 0.0

        tool_breakdown = {}
        for t_name, l_list in self.tool_latencies.items():
            tool_breakdown[t_name] = {
                "invocations": len(l_list),
                "avg_ms": round(sum(l_list) / len(l_list), 3) if l_list else 0.0,
                "p95_ms": round(sorted(l_list)[int(len(l_list) * 0.95)], 3) if l_list else 0.0
            }

        return {
            "uptime_seconds": uptime_sec,
            "host_telemetry": {
                "cpu_percent": cpu_pct,
                "memory_rss_mb": mem_mb,
                "active_threads": proc.num_threads()
            },
            "sla_performance": {
                "total_invoices_reconciled": self.total_processed,
                "avg_latency_ms": avg_lat,
                "p50_latency_ms": round(p50, 2),
                "p95_latency_ms": round(p95, 2),
                "p99_latency_ms": round(p99, 2),
                "sla_target_ms": 100.0,
                "sla_compliance_pct": round(len([l for l in sorted_lat if l <= 100.0]) / n * 100, 1) if n else 100.0
            },
            "conversion_rates": {
                "auto_resolution_rate_pct": round((self.auto_resolved / self.total_processed * 100.0), 1) if self.total_processed else 0.0,
                "human_in_loop_rate_pct": round((self.hitl_count / self.total_processed * 100.0), 1) if self.total_processed else 0.0,
                "guardrail_block_rate_pct": round((self.blocked_count / self.total_processed * 100.0), 1) if self.total_processed else 0.0
            },
            "tool_telemetry": tool_breakdown
        }

perf_tracker = PerformanceTracker()
