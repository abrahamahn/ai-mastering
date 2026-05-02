from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


Metric = dict[str, float]


def write_ai_html_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_ai_html_report(report), encoding="utf-8")


def render_ai_html_report(report: dict[str, Any]) -> str:
    candidates = report.get("candidates", [])
    source_metrics = report.get("source_metrics", {})
    best_name = report.get("best_candidate")
    title = f"{report.get('basename', 'mastering')} mastering report"

    overview_rows = "\n".join(
        _overview_row(candidate, source_metrics, best_name)
        for candidate in candidates
    )
    cards = "\n".join(_candidate_card(candidate, source_metrics, best_name) for candidate in candidates)
    intent_section = _intent_section(report.get("comment_intent") or {})

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --ink: #17130f;
      --muted: #6f665c;
      --paper: #fbf4e8;
      --panel: #fffaf2;
      --line: #d8c8ad;
      --amber: #d88f22;
      --green: #487d42;
      --red: #a84134;
      --blue: #2f6177;
      --shadow: 0 18px 60px rgba(75, 47, 17, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 14% 0%, rgba(216, 143, 34, 0.22), transparent 34rem),
        radial-gradient(circle at 92% 16%, rgba(47, 97, 119, 0.18), transparent 30rem),
        linear-gradient(135deg, #fbf4e8 0%, #f5ead6 52%, #efe0c2 100%);
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.45;
    }}
    header {{
      padding: 42px clamp(22px, 5vw, 72px) 20px;
      max-width: 1440px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(34px, 5vw, 76px);
      line-height: 0.95;
      letter-spacing: -0.05em;
      max-width: 980px;
    }}
    .subtitle {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 18px;
      max-width: 880px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 28px;
    }}
    .stat, .panel, .candidate {{
      background: rgba(255, 250, 242, 0.86);
      border: 1px solid rgba(116, 86, 48, 0.18);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}
    .stat {{
      padding: 18px;
      min-height: 112px;
    }}
    .label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .value {{
      display: block;
      margin-top: 10px;
      font-size: 24px;
      font-weight: 700;
    }}
    main {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 18px clamp(22px, 5vw, 72px) 70px;
    }}
    h2 {{
      font-size: clamp(28px, 3vw, 44px);
      letter-spacing: -0.04em;
      margin: 34px 0 14px;
    }}
    .panel {{
      padding: 20px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }}
    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 9px;
      border-radius: 999px;
      border: 1px solid rgba(23, 19, 15, 0.12);
      background: #f4ead8;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      white-space: nowrap;
    }}
    .badge.best {{ background: #e4f0d8; color: #2f6730; }}
    .badge.warn {{ background: #f6dfd9; color: #89362c; }}
    .delta {{ font-weight: 700; }}
    .delta.pos {{ color: var(--green); }}
    .delta.neg {{ color: var(--red); }}
    .delta.neutral {{ color: var(--muted); }}
    .candidate {{
      margin-top: 18px;
      padding: 22px;
    }}
    .candidate.best {{
      outline: 3px solid rgba(72, 125, 66, 0.32);
    }}
    .candidate-head {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: start;
    }}
    .candidate h3 {{
      margin: 0;
      font-size: 28px;
      letter-spacing: -0.03em;
    }}
    .description {{
      color: var(--muted);
      margin: 6px 0 0;
    }}
    audio {{
      width: min(520px, 100%);
      margin-top: 12px;
    }}
    .chain {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .stage {{
      min-width: 180px;
      max-width: 260px;
      padding: 12px;
      border: 1px solid rgba(23, 19, 15, 0.12);
      border-radius: 16px;
      background: #fbf1df;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .stage.optional {{
      background: #edf2ea;
      border-color: rgba(72, 125, 66, 0.26);
    }}
    .stage.final {{
      background: #e9f0f3;
      border-color: rgba(47, 97, 119, 0.25);
    }}
    .stage strong {{
      display: block;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 15px;
      letter-spacing: -0.01em;
      margin-bottom: 5px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .metric {{
      padding: 12px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.54);
      border: 1px solid rgba(23, 19, 15, 0.1);
      min-height: 96px;
    }}
    .bar {{
      position: relative;
      height: 8px;
      border-radius: 999px;
      background: #eadbc3;
      margin-top: 10px;
      overflow: hidden;
    }}
    .bar span {{
      position: absolute;
      top: 0;
      bottom: 0;
      left: 50%;
      width: 0;
      background: var(--green);
    }}
    .bar span.neg {{
      left: auto;
      right: 50%;
      background: var(--red);
    }}
    .notes {{
      margin-top: 14px;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .notes span {{
      display: inline-block;
      margin: 5px 6px 0 0;
      padding: 5px 8px;
      border-radius: 999px;
      background: rgba(216, 143, 34, 0.14);
    }}
    .intent {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .intent pre {{
      white-space: pre-wrap;
      margin: 10px 0 0;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    @media (max-width: 960px) {{
      .hero-grid, .metrics, .intent {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .candidate-head {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 620px) {{
      .hero-grid, .metrics, .intent {{ grid-template-columns: 1fr; }}
      .stage {{ min-width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p class="subtitle">{escape(str(report.get("style", "")))}</p>
    <div class="hero-grid">
      <div class="stat"><span class="label">Best Candidate</span><span class="value">{escape(str(best_name or "n/a"))}</span></div>
      <div class="stat"><span class="label">Target LUFS</span><span class="value">{_fmt(report.get("target_lufs"))}</span></div>
      <div class="stat"><span class="label">Source LUFS</span><span class="value">{_fmt(source_metrics.get("lufs"))}</span></div>
      <div class="stat"><span class="label">Candidates</span><span class="value">{len(candidates)}</span></div>
    </div>
  </header>
  <main>
    {intent_section}
    <h2>Candidate Overview</h2>
    <section class="panel">
      <table>
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Score</th>
            <th>LUFS</th>
            <th>Loud Crest</th>
            <th>Presence</th>
            <th>Air</th>
            <th>Punch/Mud</th>
            <th>Artifact</th>
            <th>Width</th>
            <th>Active Optional Modules</th>
          </tr>
        </thead>
        <tbody>
          {overview_rows}
        </tbody>
      </table>
    </section>
    <h2>Chain Details</h2>
    {cards}
  </main>
  <script type="application/json" id="raw-report">{escape(json.dumps(report))}</script>
</body>
</html>
"""


def _intent_section(intent: dict[str, Any]) -> str:
    if not intent:
        return ""
    tags = intent.get("tags") or []
    notes = intent.get("notes") or []
    tag_html = "".join(f'<span class="badge">{escape(str(tag))}</span>' for tag in tags) or '<span class="badge">neutral</span>'
    note_html = "".join(f"<span>{escape(str(note))}</span>" for note in notes)
    overrides = {
        "global": intent.get("global_overrides") or {},
        "candidate": intent.get("candidate_overrides") or {},
        "score_bias": intent.get("score_bias") or {},
    }
    return f"""<h2>Comment Intent</h2>
    <section class="panel intent">
      <div>
        <span class="label">Matched Tags</span>
        <div class="notes">{tag_html}</div>
        <div class="notes">{note_html}</div>
      </div>
      <div>
        <span class="label">Deterministic Overrides</span>
        <pre>{escape(json.dumps(overrides, indent=2))}</pre>
      </div>
    </section>"""


def _overview_row(candidate: dict[str, Any], source_metrics: Metric, best_name: str | None) -> str:
    metrics = candidate.get("metrics", {})
    settings = candidate.get("settings")
    modules = ", ".join(_active_optional_modules(settings)) if settings else "none"
    best = ' <span class="badge best">best</span>' if candidate.get("name") == best_name else ""
    return f"""<tr>
      <td><strong>{escape(str(candidate.get("name", "")))}</strong>{best}</td>
      <td>{_fmt(candidate.get("score"), digits=1)}</td>
      <td>{_fmt(metrics.get("lufs"), digits=2)}</td>
      <td>{_metric_delta(metrics, source_metrics, "loud_window_crest_db", "dB", positive_good=True)}</td>
      <td>{_metric_delta(metrics, source_metrics, "presence_db", "dB", positive_good=True)}</td>
      <td>{_metric_delta(metrics, source_metrics, "air_db", "dB", positive_good=False)}</td>
      <td>{_metric_delta(metrics, source_metrics, "punch_to_mud_db", "dB", positive_good=True)}</td>
      <td>{_metric_delta(metrics, source_metrics, "artifact_index", "", positive_good=False)}</td>
      <td>{_metric_delta(metrics, source_metrics, "side_to_mid_db", "dB", positive_good=True)}</td>
      <td>{escape(modules)}</td>
    </tr>"""


def _candidate_card(candidate: dict[str, Any], source_metrics: Metric, best_name: str | None) -> str:
    name = str(candidate.get("name", ""))
    settings = candidate.get("settings")
    metrics = candidate.get("metrics", {})
    is_best = name == best_name
    audio = escape(str(candidate.get("file") or ""))
    chain = "\n".join(_stage_html(stage) for stage in _chain_stages(settings))
    metric_cards = "\n".join(
        _metric_card(label, metrics, source_metrics, key, unit, positive_good, limit)
        for label, key, unit, positive_good, limit in [
            ("LUFS", "lufs", "LUFS", False, 4.0),
            ("Loud Section Crest", "loud_window_crest_db", "dB", True, 4.0),
            ("PLR", "plr_db", "dB", True, 4.0),
            ("Punch / Mud", "punch_to_mud_db", "dB", True, 4.0),
            ("Presence", "presence_db", "dB", True, 4.0),
            ("Vocal Presence", "vocal_presence_db", "dB", True, 4.0),
            ("Air / Harshness", "air_db", "dB", False, 4.0),
            ("Harsh / Vocal", "harsh_to_vocal_db", "dB", False, 4.0),
            ("Fizz / Vocal", "fizz_to_vocal_db", "dB", False, 4.0),
            ("Artifact Index", "artifact_index", "", False, 4.0),
            ("Stereo Width", "side_to_mid_db", "dB", True, 3.0),
            ("Presence Width", "presence_side_to_mid_db", "dB", True, 3.0),
            ("Side Highs", "high_side_to_mid_db", "dB", False, 3.0),
            ("High Corr", "high_band_correlation", "", True, 0.4),
            ("Sub / Low Bass", "sub_db", "dB", False, 4.0),
            ("True Peak", "true_peak_dbfs", "dBFS", False, 2.0),
            ("HF Ratio", "hf_ratio", "", False, 0.08),
        ]
    )
    notes = _notes_html(candidate)
    badge = '<span class="badge best">selected best</span>' if is_best else ""
    card_class = "candidate best" if is_best else "candidate"
    loud_range = _loud_section_range(metrics)
    return f"""<section class="{card_class}">
      <div class="candidate-head">
        <div>
          <h3>{escape(name)} {badge}</h3>
          <p class="description">{escape(str(candidate.get("description", "")))}</p>
          <audio controls preload="none" src="{audio}"></audio>
        </div>
        <div>
          <span class="badge">score {_fmt(candidate.get("score"), digits=1)}</span>
          <span class="badge">target {_fmt(candidate.get("target_lufs"), digits=1)} LUFS</span>
          <span class="badge">loudest {escape(loud_range)}</span>
        </div>
      </div>
      <div class="chain">{chain}</div>
      <div class="metrics">{metric_cards}</div>
      {notes}
    </section>"""


def _chain_stages(settings: dict[str, Any] | None) -> list[dict[str, str]]:
    if not settings:
        return [{"name": "Original Source", "kind": "final", "details": "No processing. Reference candidate."}]

    stages = [
        {"name": "Corrective EQ + Pro-Q 3", "kind": "core", "details": _on_off(settings.get("corrective_eq_enabled"))},
    ]
    if settings.get("gullfoss_enabled"):
        stages.append({
            "name": "Gullfoss Master",
            "kind": "optional",
            "details": _params(settings, ["gullfoss_recover", "gullfoss_tame", "gullfoss_brighten", "gullfoss_boost_db"]),
        })
    stages.append({"name": "VEQ-MG4+", "kind": "core", "details": "Warmth / low-mid color"})
    if settings.get("bax_enabled"):
        stages.append({
            "name": "Dangerous BAX",
            "kind": "optional",
            "details": _params(settings, ["bax_low_shelf_db", "bax_high_shelf_db"]),
        })
    if settings.get("bx_digital_enabled"):
        stages.append({
            "name": "bx_digital V3",
            "kind": "optional",
            "details": _params(settings, ["bx_stereo_width", "bx_mono_maker_enabled", "bx_mono_maker_hz"]),
        })
    stages.extend([
        {"name": "soothe2 pass 1", "kind": "core", "details": _params(settings, ["soothe_depth_scale", "soothe1_mix"])},
        {"name": "soothe2 pass 2", "kind": "core", "details": _params(settings, ["soothe2_depth_scale", "soothe2_mix"])},
        {"name": "Multipass", "kind": "core", "details": _params(settings, ["multipass_macro_cap"])},
    ])
    if settings.get("low_end_focus_enabled"):
        stages.append({
            "name": "Ozone Low End Focus",
            "kind": "optional",
            "details": _params(settings, ["low_end_focus_contrast", "low_end_focus_gain_db", "low_end_focus_mode"]),
        })
    stages.extend([
        {"name": "elysia alpha master", "kind": "core", "details": _params(settings, ["alpha_ratio", "alpha_threshold_offset"])},
        {"name": "Softube Tape", "kind": "core", "details": _params(settings, ["tape_color_scale", "tape_color_offset"])},
    ])
    if settings.get("inflator_enabled"):
        stages.append({
            "name": "Oxford Inflator",
            "kind": "optional",
            "details": _params(settings, ["inflator_effect", "inflator_curve", "inflator_output_gain"]),
        })
    if settings.get("hf_guard_enabled"):
        stages.append({
            "name": "Streaming HF Guard",
            "kind": "core",
            "details": _params(settings, [
                "hf_guard_ratio_threshold",
                "hf_guard_air_to_presence_db",
                "hf_guard_frequency_hz",
                "hf_guard_max_reduction_db",
            ]),
        })
    if settings.get("ozone_imager_enabled"):
        stages.append({
            "name": "Ozone Imager",
            "kind": "optional",
            "details": _params(settings, [
                "ozone_imager_band_1_width_percent",
                "ozone_imager_band_2_width_percent",
                "ozone_imager_band_3_width_percent",
                "ozone_imager_band_4_width_percent",
                "ozone_imager_width_scale",
            ]),
        })
    limiter = "Weiss MM-1" if settings.get("final_limiter") == "weiss_mm1" else "Ozone 9"
    limiter_details = (
        _params(settings, ["weiss_amount", "weiss_style", "weiss_out_trim_dbfs"])
        if settings.get("final_limiter") == "weiss_mm1"
        else _params(settings, ["ozone_threshold", "ozone_ceiling", "ozone_bypass_modules"])
    )
    if settings.get("streaming_profile_enabled"):
        limiter_details = "; ".join([
            limiter_details,
            _params(settings, [
                "streaming_reference_lufs",
                "streaming_normal_target_ceiling_dbfs",
                "streaming_loud_target_ceiling_dbfs",
            ]),
        ])
    stages.append({"name": f"{limiter} final", "kind": "final", "details": limiter_details})
    if settings.get("loud_section_guard_enabled"):
        stages.append({
            "name": "Loud Section Guard",
            "kind": "final",
            "details": _params(settings, [
                "loud_section_seconds",
                "loud_section_min_crest_db",
                "loud_section_max_crest_loss_db",
            ]),
        })
    if settings.get("source_match_enabled"):
        stages.append({
            "name": "Source Match Guard",
            "kind": "final",
            "details": _params(settings, ["source_match_presence_max_db", "source_match_sub_trim_max_db", "source_match_side_max_db"]),
        })
    return stages


def _active_optional_modules(settings: dict[str, Any] | None) -> list[str]:
    if not settings:
        return []
    modules = []
    mapping = [
        ("gullfoss_enabled", "Gullfoss"),
        ("bax_enabled", "BAX"),
        ("bx_digital_enabled", "bx_digital"),
        ("low_end_focus_enabled", "Low End Focus"),
        ("inflator_enabled", "Inflator"),
        ("ozone_imager_enabled", "Ozone Imager"),
    ]
    for key, label in mapping:
        if settings.get(key):
            modules.append(label)
    if settings.get("final_limiter") == "weiss_mm1":
        modules.append("Weiss final")
    return modules


def _stage_html(stage: dict[str, str]) -> str:
    kind = escape(stage.get("kind", "core"))
    return f"""<div class="stage {kind}">
      <strong>{escape(stage.get("name", ""))}</strong>
      {escape(stage.get("details", ""))}
    </div>"""


def _metric_card(
    label: str,
    metrics: Metric,
    source_metrics: Metric,
    key: str,
    unit: str,
    positive_good: bool,
    limit: float,
) -> str:
    value = metrics.get(key)
    source = source_metrics.get(key)
    delta = _num(value) - _num(source)
    return f"""<div class="metric">
      <span class="label">{escape(label)}</span>
      <span class="value">{_fmt(value, unit=unit)}</span>
      <div>{_metric_delta(metrics, source_metrics, key, unit, positive_good)}</div>
      {_bar(delta, limit)}
    </div>"""


def _metric_delta(metrics: Metric, source_metrics: Metric, key: str, unit: str, positive_good: bool) -> str:
    delta = _num(metrics.get(key)) - _num(source_metrics.get(key))
    cls = "neutral"
    if abs(delta) >= 0.01:
        good = delta > 0 if positive_good else delta < 0
        cls = "pos" if good else "neg"
    return f'<span class="delta {cls}">{_signed(delta, unit)}</span>'


def _bar(delta: float, limit: float) -> str:
    pct = max(0.0, min(50.0, abs(delta) / max(limit, 1e-9) * 50.0))
    cls = "neg" if delta < 0 else ""
    return f'<div class="bar"><span class="{cls}" style="width:{pct:.1f}%"></span></div>'


def _notes_html(candidate: dict[str, Any]) -> str:
    notes = list(candidate.get("score_notes") or []) + list(candidate.get("warnings") or [])
    moves = candidate.get("source_match_moves") or []
    for move in moves:
        notes.append(f"source match: {move}")
    if not notes:
        return ""
    items = "".join(f"<span>{escape(str(note))}</span>" for note in notes)
    return f'<div class="notes">{items}</div>'


def _loud_section_range(metrics: Metric) -> str:
    start = metrics.get("loud_section_start_seconds")
    end = metrics.get("loud_section_end_seconds")
    if start is None or end is None:
        return "n/a"
    return f"{_fmt(start, digits=1)}-{_fmt(end, digits=1)}s"


def _params(settings: dict[str, Any], keys: list[str]) -> str:
    parts = []
    for key in keys:
        value = settings.get(key)
        if value is None:
            continue
        parts.append(f"{key.replace('_', ' ')}={_fmt(value, digits=2)}")
    return ", ".join(parts) or "default"


def _on_off(value: Any) -> str:
    return "enabled" if bool(value) else "disabled"


def _fmt(value: Any, unit: str = "", digits: int = 2) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return escape(str(value)) if value is not None else "n/a"
    rendered = f"{number:.{digits}f}"
    if digits > 0:
        rendered = rendered.rstrip("0").rstrip(".")
    return f"{rendered} {unit}".strip()


def _signed(value: float, unit: str = "", digits: int = 2) -> str:
    rendered = f"{value:+.{digits}f}"
    rendered = rendered.rstrip("0").rstrip(".")
    return f"{rendered} {unit}".strip()


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
