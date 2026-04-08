from __future__ import annotations

import json
from pathlib import Path

import httpx
import typer


app = typer.Typer(help="Adversarial Integration Tester CLI")


@app.command("target-add")
def target_add(
    config_path: Path = typer.Argument(..., exists=True, readable=True),
    api_url: str = typer.Option("http://127.0.0.1:8000", help="AIT API base URL"),
) -> None:
    payload = json.loads(config_path.read_text())
    response = httpx.post(f"{api_url}/targets", json=payload, timeout=15)
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command("run-start")
def run_start(
    target_name: str = typer.Argument(...),
    api_url: str = typer.Option("http://127.0.0.1:8000", help="AIT API base URL"),
) -> None:
    response = httpx.post(f"{api_url}/runs", json={"target_name": target_name}, timeout=60)
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command("run-status")
def run_status(
    run_id: str = typer.Argument(...),
    api_url: str = typer.Option("http://127.0.0.1:8000", help="AIT API base URL"),
) -> None:
    response = httpx.get(f"{api_url}/runs/{run_id}", timeout=15)
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command("report-export")
def report_export(
    run_id: str = typer.Argument(...),
    output_path: Path = typer.Argument(...),
    format: str = typer.Option("json", help="json or html"),
    api_url: str = typer.Option("http://127.0.0.1:8000", help="AIT API base URL"),
) -> None:
    response = httpx.get(f"{api_url}/runs/{run_id}/report", params={"format": format}, timeout=15)
    response.raise_for_status()
    output_path.write_text(
        response.text if format == "html" else json.dumps(response.json(), indent=2)
    )
    typer.echo(f"Wrote {format} report to {output_path}")
