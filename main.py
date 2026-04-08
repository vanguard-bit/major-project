"""
main.py – Adversarial Integration Tester CLI
Phase 7: Orchestration pipeline

Usage:
    python main.py --config config/test_config.yaml
    python main.py --config config/test_config.yaml --no-server
"""

import sys
import time
import subprocess
import argparse
import yaml
import os

from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich import box

console = Console()


# ── Config loader ──────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Banner ─────────────────────────────────────────────────────────────────────

def print_banner():
    banner = """
╔═══════════════════════════════════════════════════════╗
║     ADVERSARIAL INTEGRATION TESTER  v1.0              ║
║     SaaS API Security Research Framework               ║
║     Fuzzing · Taint Tracking · Behavioral Analysis    ║
╚═══════════════════════════════════════════════════════╝
"""
    console.print(banner, style="bold cyan")


# ── Pipeline ───────────────────────────────────────────────────────────────────

def run_pipeline(config: dict, start_server: bool = True):
    # Lazy imports here so the modules are only loaded after path setup
    from adapters.mock_adapter  import MockAdapter
    from fuzzer.fuzzer           import Fuzzer
    from taint.taint_injector    import TaintInjector
    from analyzer.response_analyzer import ResponseAnalyzer
    from core.divergence_engine  import DivergenceEngine
    from runner.report_engine    import ReportEngine

    target_cfg  = config["target"]
    ep_configs  = config["endpoints"]
    fuzz_cfg    = config.get("fuzzer", {})
    taint_cfg   = config.get("taint", {})
    report_cfg  = config.get("reporting", {})

    base_url    = target_cfg["base_url"]
    auth_token  = target_cfg.get("auth_token")
    target_name = target_cfg.get("name", base_url)

    server_proc = None

    # ─── Step 0: Optionally start mock server ─────────────────────────────────
    if start_server:
        console.rule("[bold yellow]Step 0 – Starting Mock Server")
        console.print(f"  Launching mock FastAPI server at {base_url} …", style="dim")
        try:
            server_proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "mock_server:app",
                 "--host", "127.0.0.1", "--port", "8888", "--log-level", "warning"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)  # wait for startup
            console.print("  ✅ Mock server started (PID {})".format(server_proc.pid), style="green")
        except Exception as exc:
            console.print(f"  ❌ Failed to start mock server: {exc}", style="red")
            console.print("  → Run `uvicorn mock_server:app --host 127.0.0.1 --port 8888` manually.", style="yellow")

    total_start = time.time()

    try:
        # ─── Step 1: Adapter + Auth ───────────────────────────────────────────
        console.rule("[bold yellow]Step 1 – Adapter Initialization")
        adapter = MockAdapter(base_url=base_url, auth_token=auth_token)
        ok = adapter.authenticate()
        if ok:
            console.print(f"  ✅ Authenticated with {target_name}", style="green")
        else:
            console.print(f"  ⚠️  Auth check failed – proceeding anyway", style="yellow")

        endpoints = ep_configs  # from config
        console.print(f"  Endpoints configured: {[e['path'] for e in endpoints]}")

        # ─── Step 2: Fuzzing ──────────────────────────────────────────────────
        console.rule("[bold yellow]Step 2 – Fuzzer")
        fuzzer = Fuzzer(
            adapter=adapter,
            endpoints=endpoints,
            iterations=fuzz_cfg.get("iterations", 5),
            strategies=fuzz_cfg.get("mutation_strategies"),
        )
        console.print("  Running fuzzer …", style="dim")
        fuzzer_results = fuzzer.run()
        console.print(f"  ✅ Fuzzer completed – {len(fuzzer_results)} requests sent", style="green")

        # ─── Step 3: Taint Injection ──────────────────────────────────────────
        console.rule("[bold yellow]Step 3 – Taint Injection")
        injector = TaintInjector(
            adapter=adapter,
            endpoints=endpoints,
            taint_fields=taint_cfg.get("fields_to_taint"),
            marker_prefix=taint_cfg.get("marker_prefix", "TAINT"),
        )
        console.print("  Injecting tainted payloads …", style="dim")
        taint_results = injector.inject_and_collect()
        console.print(f"  ✅ Taint injection done – {len(taint_results)} requests sent", style="green")

        # Now scan ALL responses (fuzzer + taint) for leaked markers
        all_responses = fuzzer_results + taint_results
        taint_leaks = injector.scan_responses_for_taint(all_responses)
        _unexpected = [l for l in taint_leaks if l.get("unexpected")]
        console.print(f"  🔍 Taint leaks found: {len(taint_leaks)}  "
                      f"({len(_unexpected)} unexpected)", style="bold magenta")

        # ─── Step 4: Response Analysis ────────────────────────────────────────
        console.rule("[bold yellow]Step 4 – Response Analyzer")
        analyzer = ResponseAnalyzer(endpoint_configs=ep_configs)
        analyzer_findings = analyzer.analyze(all_responses)
        console.print(f"  ✅ Analyzer findings: {len(analyzer_findings)}", style="green")

        # ─── Step 5: Behavioral Divergence ───────────────────────────────────
        console.rule("[bold yellow]Step 5 – Behavioral Divergence Engine")
        divergence = DivergenceEngine(endpoint_configs=ep_configs)
        anomalies = divergence.analyze(all_responses)
        console.print(f"  ✅ Divergence anomalies: {len(anomalies)}", style="green")

        # ─── Step 6: Report Generation ────────────────────────────────────────
        console.rule("[bold yellow]Step 6 – Report Generation")
        elapsed = time.time() - total_start
        reporter = ReportEngine(output_dir=report_cfg.get("output_dir", "reports"))
        report = reporter.build_report(
            target_name=target_name,
            config=config,
            fuzzer_results=fuzzer_results,
            taint_results=taint_results,
            taint_leaks=taint_leaks,
            analyzer_findings=analyzer_findings,
            divergence_anomalies=anomalies,
            elapsed_seconds=elapsed,
        )

        formats = report_cfg.get("formats", ["json", "markdown"])
        saved_paths = []
        if "json" in formats:
            p = reporter.save_json(report)
            saved_paths.append(("JSON", p))
            console.print(f"  💾 JSON report  → {p}", style="cyan")
        if "markdown" in formats:
            p = reporter.save_markdown(report)
            saved_paths.append(("Markdown", p))
            console.print(f"  💾 MD   report  → {p}", style="cyan")

        # ─── Final Summary Table ───────────────────────────────────────────────
        _print_summary(report)

    finally:
        if server_proc:
            server_proc.terminate()
            console.print("\n  [dim]Mock server stopped.[/dim]")


# ── Summary table ──────────────────────────────────────────────────────────────

def _print_summary(report: dict):
    s = report["summary"]
    risk = s["risk_level"]
    risk_color = {"CRITICAL": "red", "HIGH": "yellow", "MEDIUM": "cyan", "LOW": "green"}.get(risk, "white")

    table = Table(title="📊 Report Summary", box=box.DOUBLE_EDGE, style="bold")
    table.add_column("Metric", style="bold white")
    table.add_column("Value",  style="bold cyan", justify="right")

    rows = [
        ("Endpoints Tested",         str(s["endpoints_tested"])),
        ("Total Requests Sent",       str(s["total_requests"])),
        ("Total Findings",            str(s["total_findings"])),
        ("Critical Findings",         str(s["critical_findings"])),
        ("High Findings",             str(s["high_findings"])),
        ("Taint Leaks Detected",      str(s["taint_leaks_detected"])),
        ("Unexpected Taint Leaks",    str(s["unexpected_taint_leaks"])),
        ("Execution Time (s)",        str(report["metrics"]["execution_time_sec"])),
    ]
    for metric, value in rows:
        table.add_row(metric, value)

    console.print()
    console.print(table)
    console.print(
        Panel(f"[bold {risk_color}]⚠ Risk Level: {risk}[/bold {risk_color}]",
              border_style=risk_color, expand=False)
    )
    console.print()


# ── CLI entry ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Adversarial Integration Tester – SaaS API Security Framework"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/test_config.yaml",
        help="Path to YAML test config (default: config/test_config.yaml)",
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Skip auto-starting the mock server (use if already running)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.config):
        console.print(f"[red]Config file not found: {args.config}[/red]")
        sys.exit(1)

    print_banner()
    config = load_config(args.config)
    run_pipeline(config, start_server=not args.no_server)


if __name__ == "__main__":
    main()
