"""Deterministic LaTeX fragment rendering from selected paper artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ait.paper.models import PaperArtifactsManifest, load_paper_artifacts_manifest

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

GENERATED_HEADER_PREFIX = "% GENERATED FILE — DO NOT EDIT"
MANIFEST_LABEL = "configs/paper_artifacts.yaml"
GENERATOR_LABEL = "ait.paper.render_tables"

FRAGMENT_NAMES = (
    "mock_detection_results",
    "platform_scenario_results",
    "live_results",
    "replay_results",
    "risk_sensitivity",
    "benchmark_results",
    "robustness_results",
    "tool_comparison",
    "artifact_provenance",
)

CATEGORY_LABELS = {
    "hidden_endpoint": "Hidden Endpoint",
    "sensitive_field_access": "Sensitive Field",
    "behavioral_divergence": "Behavioral Divergence",
    "policy_violation": "Policy Violation",
}


def latex_escape(value: str) -> str:
    """Escape LaTeX special characters in plain text."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out: list[str] = []
    for char in value:
        out.append(replacements.get(char, char))
    return "".join(out)

PLATFORM_ORDER = (
    "platform-slack-bot-token-overaccess",
    "platform-github-broad-token-repos",
    "platform-google-readonly-write-attempt",
    "platform-notion-readonly-mutation",
    "platform-trello-read-token-card-create",
    "platform-slack-compliant-bot",
    "platform-github-compliant-app",
)

PLATFORM_META = {
    "platform-slack-bot-token-overaccess": ("Slack", "Bot token over-access"),
    "platform-github-broad-token-repos": ("GitHub", "PAT broad scope"),
    "platform-google-readonly-write-attempt": ("Google", "Readonly token write attempt"),
    "platform-notion-readonly-mutation": ("Notion", "Read-only integration mutation"),
    "platform-trello-read-token-card-create": ("Trello", "Read token card creation"),
    "platform-slack-compliant-bot": ("Slack", "Compliant bot"),
    "platform-github-compliant-app": ("GitHub", "Compliant app"),
}


def format_metric(value: float | None) -> str:
    if value is None:
        return "---"
    return f"{float(value):.3f}"


def format_risk(value: float | None) -> str:
    if value is None:
        return "NOT RUN"
    score = float(value)
    if abs(score - round(score)) < 1e-9:
        return str(int(round(score)))
    return f"{score:.2f}"


def format_timing(value: float) -> str:
    return f"{float(value):.3f}"


def _severity_band(score: float) -> str:
    if score <= 25:
        return "Low" if score > 0 else "N/A"
    if score <= 50:
        return "Medium"
    if score <= 75:
        return "High"
    return "Critical"


def _templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates"


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_templates_dir())),
        undefined=StrictUndefined,
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _header() -> str:
    return (
        f"{GENERATED_HEADER_PREFIX}\n"
        f"% Source manifest: {MANIFEST_LABEL}\n"
        f"% Generator: {GENERATOR_LABEL}\n"
    )


def _resolve_path(root: Path, rel: str) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else root / path


def _results_tree_root(manifest: PaperArtifactsManifest, root: Path) -> Path:
    """Directory containing ``derived/`` and ``raw/`` (repo ``results/`` or fixture root)."""
    for name in ("scenario_metrics", "offline_manifest", "benchmark_summary"):
        ref = manifest.ref_for(name)
        if ref is None:
            continue
        full = _resolve_path(root, ref.path)
        if full.parent.name == "derived":
            return full.parent.parent
    candidate = root / "results"
    return candidate if candidate.is_dir() else root


def _read_selected(
    manifest: PaperArtifactsManifest, root: Path, name: str
) -> dict[str, Any] | None:
    ref = manifest.ref_for(name)
    if ref is None:
        return None
    return json.loads(_resolve_path(root, ref.path).read_text(encoding="utf-8"))


def _platform_rows(manifest: PaperArtifactsManifest, root: Path) -> list[dict[str, Any]]:
    metrics = _read_selected(manifest, root, "scenario_metrics")
    if metrics is None:
        return []
    results = {
        row["scenario_id"]: row
        for row in metrics.get("payload", {}).get("scenario_results", [])
    }
    tree = _results_tree_root(manifest, root)
    rows: list[dict[str, Any]] = []
    for index, scenario_id in enumerate(PLATFORM_ORDER, start=1):
        if scenario_id not in results:
            continue
        meta = PLATFORM_META[scenario_id]
        raw_path = tree / "raw" / "scenarios" / f"{scenario_id}.json"
        if not raw_path.is_file():
            # Fall back: mark unavailable rather than invent risk
            rows.append(
                {
                    "index": index,
                    "platform": meta[0],
                    "scenario": meta[1],
                    "risk": "NOT RUN",
                    "severity": "---",
                    "detected": "NOT RUN",
                }
            )
            continue
        payload = json.loads(raw_path.read_text(encoding="utf-8"))["payload"]
        risk = float(payload["report"]["risk_score"])
        expected = payload.get("expected_categories") or []
        observed = payload.get("observed_categories") or []
        if expected:
            detected = "Yes" if results[scenario_id].get("passed") else "No"
        else:
            detected = "No" if not observed else "Yes"
        rows.append(
            {
                "index": index,
                "platform": meta[0],
                "scenario": meta[1],
                "risk": format_risk(risk),
                "severity": _severity_band(risk),
                "detected": detected,
            }
        )
    return rows


def _mock_rows(metrics: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    payload = metrics["payload"]
    rows: list[dict[str, Any]] = []
    for cat in sorted(payload.get("categories", []), key=lambda c: c["category"]):
        name = cat["category"]
        if name == "policy_violation" and cat.get("tp", 0) == 0 and cat.get("fp", 0) == 0:
            # Keep for transparency but mark metrics as unavailable when undefined
            pass
        rows.append(
            {
                "category": CATEGORY_LABELS.get(name, name),
                "precision": format_metric(cat.get("precision")),
                "recall": format_metric(cat.get("recall")),
                "f1": format_metric(cat.get("f1")),
                "tp": int(cat.get("tp", 0)),
                "fp": int(cat.get("fp", 0)),
                "fn": int(cat.get("fn", 0)),
                "tn": int(cat.get("tn", 0)),
            }
        )
    micro = payload["micro"]
    overall = {
        "precision": format_metric(micro.get("precision")),
        "recall": format_metric(micro.get("recall")),
        "f1": format_metric(micro.get("f1")),
        "tp": int(micro.get("tp", 0)),
        "fp": int(micro.get("fp", 0)),
        "fn": int(micro.get("fn", 0)),
        "tn": int(micro.get("tn", 0)),
    }
    count = int(metrics.get("configuration", {}).get("scenario_count", 0))
    return rows, overall, count


def _sensitivity_rows(manifest: PaperArtifactsManifest, root: Path) -> list[dict[str, Any]]:
    rows_doc = _read_selected(manifest, root, "sensitivity_rows")
    if rows_doc is None:
        summary = _read_selected(manifest, root, "sensitivity_summary")
        if summary is None:
            return []
        out = []
        for sc in sorted(summary["payload"]["scenarios"], key=lambda s: s["scenario_id"]):
            out.append(
                {
                    "scenario": latex_escape(sc["scenario_id"]),
                    "weight": r"all ($\pm30\%$)",
                    "minus": format_risk(sc["min_score"]),
                    "base": "---",
                    "plus": format_risk(sc["max_score"]),
                }
            )
        return out

    wanted = {
        ("crm-s1-hidden-both-phases", "hidden_endpoint"),
        ("crm-s2-sensitive-allowed-path", "sensitive_field"),
        ("crm-s3-combined", "hidden_endpoint"),
        ("crm-s3-combined", "sensitive_field"),
        ("crm-s3-combined", "divergence"),
    }
    weight_label = {
        "hidden_endpoint": "$w_H$",
        "sensitive_field": "$w_F$",
        "divergence": "$w_D$",
    }
    by_key: dict[tuple[str, str], dict[float, float]] = {}
    for row in rows_doc["payload"]["rows"]:
        key = (row["scenario_id"], row["varied_weight"])
        if key not in wanted:
            continue
        by_key.setdefault(key, {})[float(row["multiplier"])] = float(row["score"])

    out: list[dict[str, Any]] = []
    for scenario_id, weight in sorted(by_key.keys()):
        scores = by_key[(scenario_id, weight)]
        out.append(
            {
                "scenario": latex_escape(scenario_id),
                "weight": weight_label.get(weight, latex_escape(weight)),
                "minus": format_risk(scores.get(0.7)),
                "base": format_risk(scores.get(1.0)),
                "plus": format_risk(scores.get(1.3)),
            }
        )
    return out


def _replay_rows(doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    if doc is None:
        return [
            {
                "incident": "---",
                "expected": "NOT RUN",
                "observed": "NOT RUN",
                "match": "NOT RUN",
            }
        ]
    rows = []
    for match in sorted(doc["payload"]["matches"], key=lambda m: m["incident_id"]):
        rows.append(
            {
                "incident": latex_escape(match["incident_id"]),
                "expected": latex_escape(", ".join(match.get("expected_categories", []))),
                "observed": latex_escape(", ".join(match.get("observed_categories", []))),
                "match": "Yes" if match.get("exact_match") else "No",
            }
        )
    return rows


def _benchmark_rows(doc: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if doc is None:
        return (
            [
                {
                    "width": "---",
                    "median": "NOT RUN",
                    "p95": "NOT RUN",
                    "mad": "NOT RUN",
                    "risk": "NOT RUN",
                }
            ],
            {"host": "NOT RUN", "repetitions": "NOT RUN", "warmups": "NOT RUN"},
        )
    cfg = doc.get("configuration", {})
    host = doc["payload"].get("host", {})
    meta = {
        "host": f"{host.get('os', 'unknown')} / Python {host.get('python_version', '?')}",
        "repetitions": int(cfg.get("repetitions", 0)),
        "warmups": int(cfg.get("warmups", 0)),
    }
    rows = []
    for summary in sorted(doc["payload"]["summaries"], key=lambda s: s["width"]):
        risks = summary.get("risk_scores") or []
        risk = format_risk(risks[0]) if risks else "---"
        rows.append(
            {
                "width": int(summary["width"]),
                "median": format_timing(summary["median_ms"]),
                "p95": format_timing(summary["p95_ms"]),
                "mad": format_timing(summary["mad_ms"]),
                "risk": risk,
            }
        )
    return rows, meta


def _live_rows(
    manifest: PaperArtifactsManifest,
    documents: dict[str, dict[str, Any] | None],
) -> list[dict[str, Any]]:
    specs = [
        ("GitHub", "Live scope boundary", "github_readonly"),
        ("Notion", "Read-path validation", "notion_readonly"),
        ("Google", "OAuth userinfo scope", "google_readonly"),
        ("GitHub", "REST smoke probe", "github_smoke"),
        ("Google", "Cloud Resource Manager smoke", "google_smoke"),
    ]
    rows = []
    for index, (platform, scenario, key) in enumerate(specs, start=1):
        available = manifest.is_available(key)
        if not available:
            rows.append(
                {
                    "index": index,
                    "platform": platform,
                    "scenario": scenario,
                    "violation": "---",
                    "risk": "NOT RUN",
                    "severity": "---",
                    "detected": "BLOCKED",
                }
            )
            continue
        doc = documents.get(key) or {}
        payload = doc.get("payload") if isinstance(doc, dict) else {}
        report = (payload or {}).get("report") or {}
        hidden = report.get("hidden_endpoints") or []
        findings = report.get("findings") or []
        categories = sorted({f.get("category") for f in findings if f.get("category")})
        if hidden:
            violation = "Hidden endpoint: " + ", ".join(str(h) for h in hidden)
            detected = "Yes"
        elif findings:
            violation = ", ".join(str(c) for c in categories)
            detected = "Yes"
        else:
            violation = "None"
            detected = "No FP"
        severities = [f.get("severity") for f in findings if f.get("severity")]
        severity = severities[0] if severities else "---"
        if isinstance(severity, str):
            severity = severity.capitalize()
        rows.append(
            {
                "index": index,
                "platform": platform,
                "scenario": scenario,
                "violation": violation,
                "risk": format_risk(report.get("risk_score")),
                "severity": severity if findings else "---",
                "detected": detected,
            }
        )
    return rows


def _robustness_context(doc: dict[str, Any] | None) -> dict[str, Any]:
    if doc is None:
        return {
            "available": False,
            "rows": [{"label": "Robustness suite", "status": "NOT RUN"}],
        }
    payload = doc.get("payload", {})
    rows: list[dict[str, Any]] = []

    def _slice_rows(label: str, slice_payload: dict[str, Any]) -> None:
        micro = slice_payload.get("micro") or {}
        count = int(slice_payload.get("scenario_count", 0))
        passed = slice_payload.get("passed")
        if passed is None and "scenario_results" in slice_payload:
            results = slice_payload.get("scenario_results") or []
            passed = bool(results) and all(r.get("passed") for r in results)
        status = "PASS" if passed else ("FAIL" if passed is False else "---")
        prec_iv = micro.get("precision_interval") or {}
        rec_iv = micro.get("recall_interval") or {}
        rows.append(
            {
                "label": latex_escape(f"{label} (n={count})"),
                "status": status,
            }
        )
        rows.append(
            {
                "label": latex_escape(f"{label} micro P/R/F1"),
                "status": (
                    f"{format_metric(micro.get('precision'))}/"
                    f"{format_metric(micro.get('recall'))}/"
                    f"{format_metric(micro.get('f1'))}"
                ),
            }
        )
        rows.append(
            {
                "label": latex_escape(f"{label} Wilson P/R"),
                "status": (
                    f"[{format_metric(prec_iv.get('lower'))},"
                    f"{format_metric(prec_iv.get('upper'))}] / "
                    f"[{format_metric(rec_iv.get('lower'))},"
                    f"{format_metric(rec_iv.get('upper'))}]"
                ),
            }
        )
        rows.append(
            {
                "label": latex_escape(f"{label} counts TP/FP/FN/TN"),
                "status": (
                    f"{int(micro.get('tp', 0))}/{int(micro.get('fp', 0))}/"
                    f"{int(micro.get('fn', 0))}/{int(micro.get('tn', 0))}"
                ),
            }
        )

    in_scope = payload.get("in_scope")
    if isinstance(in_scope, dict):
        _slice_rows("in_scope", in_scope)
    boundary = payload.get("model_boundary")
    if isinstance(boundary, dict):
        _slice_rows("model_boundary", boundary)
    if payload.get("in_scope_passed") is True:
        rows.insert(0, {"label": latex_escape("in_scope_passed"), "status": "PASS"})
    elif payload.get("in_scope_passed") is False:
        rows.insert(0, {"label": latex_escape("in_scope_passed"), "status": "FAIL"})
    if not rows:
        rows.append({"label": latex_escape("robustness_metrics"), "status": "present"})
    return {"available": True, "rows": rows}


def _tool_context(doc: dict[str, Any] | None) -> dict[str, Any]:
    if doc is None:
        not_run = "NOT RUN"
        rows = [
            {
                "category": category,
                "ait": "---",
                "restler": not_run,
                "evomaster": not_run,
            }
            for category in (
                "Hidden Endpoint Access",
                "Sensitive Field Access",
                "Behavioral Divergence",
                "Server-side Input Errors",
                "OpenAPI Spec Violations",
            )
        ]
        return {"available": False, "rows": rows}
    # Structured comparison artifact when present
    return {"available": True, "rows": doc.get("payload", {}).get("rows", [])}


def _provenance_rows(manifest: PaperArtifactsManifest, root: Path) -> list[dict[str, Any]]:
    rows = []
    for name, ref in sorted(manifest.selected_refs().items()):
        path = _resolve_path(root, ref.path)
        rows.append(
            {
                "name": latex_escape(name),
                "path": latex_escape(ref.path),
                "sha256": ref.sha256,
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    for name in (
        "tool_comparison",
        "robustness_metrics",
        "reproducibility",
        "github_readonly",
        "github_smoke",
        "notion_readonly",
        "google_readonly",
        "google_smoke",
    ):
        if not manifest.is_available(name):
            rows.append(
                {
                    "name": latex_escape(name),
                    "path": "null",
                    "sha256": "NOT RUN",
                    "bytes": 0,
                }
            )
    return rows


def render_all(
    manifest_path: Path,
    output_dir: Path,
    *,
    root: Path | None = None,
) -> list[Path]:
    manifest_path = Path(manifest_path)
    base = Path(root) if root is not None else manifest_path.parent.parent
    manifest = load_paper_artifacts_manifest(manifest_path, root=base, verify=True)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = _jinja_env()
    metrics = _read_selected(manifest, base, "scenario_metrics")
    mock_rows, overall, scenario_count = (
        _mock_rows(metrics) if metrics is not None else ([], {}, 0)
    )

    contexts: dict[str, dict[str, Any]] = {
        "mock_detection_results": {
            "rows": mock_rows,
            "overall": overall,
            "scenario_count": scenario_count,
            "available": metrics is not None,
        },
        "platform_scenario_results": {
            "rows": _platform_rows(manifest, base),
            "available": metrics is not None,
        },
        "live_results": {
            "rows": _live_rows(
                manifest,
                {
                    "github_readonly": _read_selected(manifest, base, "github_readonly"),
                    "notion_readonly": _read_selected(manifest, base, "notion_readonly"),
                    "google_readonly": _read_selected(manifest, base, "google_readonly"),
                    "github_smoke": _read_selected(manifest, base, "github_smoke"),
                    "google_smoke": _read_selected(manifest, base, "google_smoke"),
                },
            )
        },
        "replay_results": {
            "rows": _replay_rows(_read_selected(manifest, base, "replay_match_table")),
            "available": manifest.is_available("replay_match_table"),
        },
        "risk_sensitivity": {
            "rows": _sensitivity_rows(manifest, base),
            "available": manifest.is_available("sensitivity_rows")
            or manifest.is_available("sensitivity_summary"),
        },
        "benchmark_results": {},
        "robustness_results": _robustness_context(
            _read_selected(manifest, base, "robustness_metrics")
        ),
        "tool_comparison": _tool_context(_read_selected(manifest, base, "tool_comparison")),
        "artifact_provenance": {"rows": _provenance_rows(manifest, base)},
    }
    bench_rows, bench_meta = _benchmark_rows(_read_selected(manifest, base, "benchmark_summary"))
    contexts["benchmark_results"] = {
        "rows": bench_rows,
        "meta": bench_meta,
        "available": manifest.is_available("benchmark_summary"),
    }

    written: list[Path] = []
    for name in FRAGMENT_NAMES:
        template = env.get_template(f"{name}.tex.j2")
        body = template.render(**contexts[name])
        path = output_dir / f"{name}.tex"
        path.write_text(_header() + body, encoding="utf-8")
        written.append(path)
    return written


@app.command()
def main(
    manifest: Path = typer.Option(Path("configs/paper_artifacts.yaml"), "--manifest"),
    output: Path = typer.Option(Path("results/generated"), "--output"),
    root: Path | None = typer.Option(None, "--root", help="Artifact root (default: repo root)"),
) -> None:
    base = root if root is not None else Path.cwd()
    paths = render_all(manifest, output, root=base)
    for path in paths:
        typer.echo(f"WROTE {path}")
    typer.echo(f"Rendered {len(paths)} fragment(s)")


if __name__ == "__main__":
    app()
