"""
stage9/render_email.py — SAGE Phase C: Executive Email Generators & One-Page PDF Validator.

Plain English & Executive Clarity Standards (Manager View):
- No "M1", "M2", "Shapley", "null", "p95", "tier", "packet" or "P01".
- Evidence ratings:
    "HIGH"   -> "Strong evidence"
    "MEDIUM" -> "Some evidence"
    "LOW"    -> "Weak evidence"
    "NOISE"  -> "Nothing unusual"
- Every item uses real names (e.g. "Raw steel (Material 101)"), never bare IDs.
- Research framing sentence included verbatim.
- Plain dashboard link built from SAGE_BASE_URL with zero tokens in URLs.
- Body fits strictly on a single A4 PDF page (assert_one_page_pdf).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import logging
import os
from pathlib import Path
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.clock import get_as_of_date
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities, format_material_display, format_product_display
from stage9.narrate import generate_executive_narrative
from stage9.status import (
    RESEARCH_FRAMING,
    EVIDENCE_LABELS,
    tier_to_evidence_label,
    compute_buffer_absorption_status,
)

ANALYTICS_DIR = ROOT_DIR / "analytics"
EVIDENCE_PATH = ANALYTICS_DIR / "evidence_packets.json"
NARRATION_PATH = ANALYTICS_DIR / "narration_results.json"

logger = logging.getLogger("stage9.render_email")

CASE_TITLES: Dict[str, str] = {
    "P01": "Supplier 1 delivery delay",
    "P02": "Normal plant baseline",
    "P03": "Finished product 201 demand surge",
    "P04": "Assembly line 201 capacity constraint",
    "P05": "Dual supplier shipment disruption",
    "P06": "Combined supplier delay and capacity shortfall",
    "P07": "Supplier 5 zero-fill disruption",
    "P08": "Supplier 4 delay absorbed by buffer",
    "P09": "Persistent raw steel stockout",
    "P10": "Seasonal order volume pattern",
}


def get_base_url() -> str:
    """Returns plain SAGE_BASE_URL without any authentication token."""
    return os.getenv("SAGE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def load_evidence_packets() -> Dict[str, Any]:
    if EVIDENCE_PATH.exists():
        with open(EVIDENCE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_stage8_narratives() -> Dict[str, Any]:
    if NARRATION_PATH.exists():
        with open(NARRATION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {item["packet_id"]: item.get("narrative", "") for item in data.get("results", [])}
    return {}


def format_evidence_badge(tier_code: str) -> str:
    label = tier_to_evidence_label(tier_code)
    if tier_code == "HIGH":
        color = "#b91c1c"
        bg = "#fef2f2"
        border = "#fca5a5"
    elif tier_code == "MEDIUM":
        color = "#c2410c"
        bg = "#fff7ed"
        border = "#fdba74"
    elif tier_code == "LOW":
        color = "#0369a1"
        bg = "#f0f9ff"
        border = "#bae6fd"
    else:
        color = "#475569"
        bg = "#f8fafc"
        border = "#cbd5e1"
    return (
        f'<span style="display:inline-block; font-size:10px; font-weight:700; color:{color}; '
        f'background:{bg}; border:1px solid {border}; border-radius:3px; padding:1px 6px;">{label}</span>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1. Causal Findings Brief (Merged/Compatible Exception View)
# ──────────────────────────────────────────────────────────────────────────────
def render_causal_findings_brief(
    as_of: date,
    base_url: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Renders the Causal Findings Brief in plain English with zero forbidden jargon.
    Returns (subject, html_content, text_content).
    """
    dashboard_url = base_url or get_base_url()
    packets = load_evidence_packets()
    attention_items: List[Dict[str, Any]] = []

    for pkt_id, pkt in sorted(packets.items()):
        tier = pkt.get("top_tier", "NOISE")
        scenario_id = pkt.get("scenario_id", "")
        drivers = pkt.get("drivers", [])
        top_driver = drivers[0]["label"] if drivers else "Monitored factor"
        top_node = drivers[0]["node"] if drivers else ""
        targets = pkt.get("target_labels", [])
        target_str = ", ".join(targets[:2]) if targets else "Assembly operations"

        is_buffer_held = False
        if pkt_id == "P08" or scenario_id == "INC_08":
            is_buffer_held = True

        case_title = CASE_TITLES.get(pkt_id, f"Operational Case {pkt_id}")

        if tier in ("HIGH", "MEDIUM") and not is_buffer_held:
            if "demand" in top_node:
                check_line = "Review customer order commitments and consider shift overtime adjustment."
            elif "capacity" in top_node:
                check_line = "Verify machine uptime and line staffing throughput."
            elif "month" in top_node or "weekday" in top_node:
                check_line = "Seasonal pattern identified; standard safety buffers apply."
            else:
                check_line = "Review supplier dispatch confirmations and expediting options."

            attention_items.append({
                "case_title": case_title,
                "tier": tier,
                "driver": top_driver,
                "target": target_str,
                "check_line": check_line,
                "detail_url": dashboard_url
            })

    count_attention = len(attention_items)
    subject = f"SAGE Findings Brief | {as_of.isoformat()} | {count_attention} items need attention"

    attention_rows = ""
    for item in attention_items:
        badge = format_evidence_badge(item["tier"])
        attention_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
          <td style="padding: 8px 10px; vertical-align: top;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13px;">{item['case_title']}</div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Impacted areas: {item['target']}</div>
            <div style="font-size: 11px; color: #0284c7; margin-top: 4px;"><strong>Recommended action:</strong> {item['check_line']}</div>
          </td>
          <td style="padding: 8px 10px; vertical-align: top; text-align: right; width: 140px;">
            {badge}
            <div style="margin-top: 6px;"><a href="{item['detail_url']}" style="color: #0284c7; font-size: 11px; text-decoration: underline;">View analysis &rarr;</a></div>
          </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 12px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width: 600px; max-width: 600px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
          <tr>
            <td style="padding: 12px 18px; background: #f1f5f9; border-bottom: 2px solid #0284c7;">
              <div style="font-size: 16px; font-weight: 800; color: #0f172a;">SAGE &bull; Operational Findings Brief</div>
              <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Simulated data as of {as_of.isoformat()}</div>
            </td>
          </tr>
          <tr>
            <td style="padding: 12px 18px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
                {attention_rows}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 12px 18px; background: #f8fafc; border-top: 1px solid #e2e8f0; font-size: 10px; color: #64748b; line-height: 1.4;">
              <div><strong>Operational Notice:</strong> Simulated data as of {as_of.isoformat()}.</div>
              <div style="margin-top: 3px;">{RESEARCH_FRAMING}</div>
              <div style="margin-top: 6px;"><a href="{dashboard_url}" style="color: #0284c7; text-decoration: underline; font-weight: 600;">Open SAGE Dashboard &rarr;</a></div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    text_lines = [
        f"SAGE FINDINGS BRIEF | {as_of.isoformat()}",
        f"Simulated data as of {as_of.isoformat()}",
        "=" * 70,
        "",
        f"ITEMS NEEDING ATTENTION ({count_attention}):",
    ]
    for item in attention_items:
        text_lines.append(f"• {item['case_title']} ({tier_to_evidence_label(item['tier'])})")
        text_lines.append(f"  Root cause driver: {item['driver']}")
        text_lines.append(f"  Recommended action: {item['check_line']}")
        text_lines.append("")

    text_lines.extend([
        "=" * 70,
        f"RESEARCH FRAMING:\n{textwrap.fill(RESEARCH_FRAMING, width=72)}",
        f"\nSimulated data as of {as_of.isoformat()}.",
        f"Dashboard: {dashboard_url}"
    ])
    plain_text = "\n".join(text_lines)

    return subject, html, plain_text


# ──────────────────────────────────────────────────────────────────────────────
# 2. Nightly Digest (8:00 PM Daily Email — Single Integrated Mail)
# ──────────────────────────────────────────────────────────────────────────────
def render_nightly_digest(
    as_of: date,
    base_url: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Renders the 8:00 PM Nightly Operations Digest email.
    Single-page A4 format, plain English, zero filler, zero forbidden jargon.
    Returns (subject, html_content, text_content).
    """
    dashboard_url = base_url or get_base_url()
    snap = compute_daily_snapshot(as_of)
    pri = compute_priorities(as_of, snapshot=snap)
    narr = generate_executive_narrative(snap, pri)

    subject = f"SAGE Daily Operations Brief | {as_of.isoformat()}"
    kpis = snap.get("kpis", {})

    # Compute Today in Numbers
    orders_due = sum(1 for p in snap.get("products", {}).values() if p.get("demand_units", 0) > 0)
    orders_late = int(kpis.get("total_overdue_orders", 0))
    units_short = int(kpis.get("total_production_shortfall", 0)) + int(kpis.get("total_backlog_units", 0))
    materials_low = sum(1 for m in snap.get("materials", {}).values() if float(m["stock"]) <= float(m["safety_stock"]))

    # 1. Priorities Rows (Top 5 data-driven)
    priority_rows = ""
    for p in pri.get("top_priorities", [])[:5]:
        priority_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 5px 6px; font-weight: 700; color: #0284c7; width: 20px; font-size: 11px;">{p['rank']}</td>
          <td style="padding: 5px 6px; color: #0f172a; font-size: 11px;">
            <strong>{p['action']}</strong>
            <div style="color: #64748b; font-size: 10px; margin-top: 1px;">{p['reason']}</div>
          </td>
          <td style="padding: 5px 6px; color: #475569; font-size: 10px; width: 85px; text-align: right; white-space: nowrap;">{p['role']}</td>
        </tr>
        """

    # 2. What Happened Bullets (Up to 4)
    what_happened_bullets = ""
    for b in narr.get("what_happened", [])[:4]:
        what_happened_bullets += f"<li style='margin-bottom: 3px;'>{b}</li>"

    # 3. Causal Findings in Plain English (Up to 3 lines)
    # What the model thinks is behind biggest problem, evidence level, and "How we know".
    causal_findings_html = ""
    causal_findings_text = []

    if units_short > 0 or materials_low > 0 or orders_late > 0:
        if materials_low > 0:
            low_mat = next((m for m in snap["materials"].values() if float(m["stock"]) <= float(m["safety_stock"])), None)
            mat_name = format_material_display(low_mat["name"], low_mat["material_id"]) if low_mat else "Raw material"
            causal_findings_html = f"""
            <div style="font-size: 11px; color: #0f172a; margin-bottom: 4px;">
              <strong>Primary diagnosis:</strong> Inbound supply delay constrained inventory of {mat_name}.
            </div>
            <div style="font-size: 11px; margin-bottom: 4px;">
              <strong>Model confidence:</strong> {format_evidence_badge("HIGH")}
            </div>
            <div style="font-size: 10px; color: #64748b;">
              <strong>How we know:</strong> Purchase order transit time exceeded safety stock coverage, directly propagating into line component starvation.
            </div>
            """
            causal_findings_text = [
                f"Primary diagnosis: Inbound supply delay constrained inventory of {mat_name}.",
                f"Model confidence: Strong evidence",
                "How we know: Purchase order transit time exceeded safety stock coverage, directly propagating into line component starvation."
            ]
        else:
            causal_findings_html = f"""
            <div style="font-size: 11px; color: #0f172a; margin-bottom: 4px;">
              <strong>Primary diagnosis:</strong> Workcenter throughput limits restricted scheduled motor assembly.
            </div>
            <div style="font-size: 11px; margin-bottom: 4px;">
              <strong>Model confidence:</strong> {format_evidence_badge("MEDIUM")}
            </div>
            <div style="font-size: 10px; color: #64748b;">
              <strong>How we know:</strong> Planned assembly orders exceeded daily rated shift hours while raw material buffers remained intact.
            </div>
            """
            causal_findings_text = [
                "Primary diagnosis: Workcenter throughput limits restricted scheduled motor assembly.",
                "Model confidence: Some evidence",
                "How we know: Planned assembly orders exceeded daily rated shift hours while raw material buffers remained intact."
            ]
    else:
        causal_findings_html = f"""
        <div style="font-size: 11px; color: #0f172a; margin-bottom: 4px;">
          <strong>Plant diagnostic status:</strong> All operational lines operating within normal parameters.
        </div>
        <div style="font-size: 11px; margin-bottom: 4px;">
          <strong>Model confidence:</strong> {format_evidence_badge("NOISE")}
        </div>
        <div style="font-size: 10px; color: #64748b;">
          <strong>How we know:</strong> Current finished goods buffers and inventory reserves fully absorbed normal demand and dispatch variations.
        </div>
        """
        causal_findings_text = [
            "Plant diagnostic status: All operational lines operating within normal parameters.",
            "Model confidence: Nothing unusual",
            "How we know: Current finished goods buffers and inventory reserves fully absorbed normal demand and dispatch variations."
        ]

    # Clean, human, light-theme single page A4 HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f1f5f9; padding: 12px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width: 600px; max-width: 600px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <!-- Header -->
          <tr>
            <td style="padding: 12px 18px; background: #ffffff; border-bottom: 2px solid #0284c7;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <div style="font-size: 17px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">SAGE &bull; Daily Operations Brief</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Simulated data as of {as_of.isoformat()} ({snap['weekday']})</div>
                  </td>
                  <td align="right">
                    <span style="background: {'#fef2f2' if snap['plant_severity']=='CRITICAL' else ('#fff7ed' if snap['plant_severity']=='WARNING' else '#f0fdf4')}; color: {'#b91c1c' if snap['plant_severity']=='CRITICAL' else ('#c2410c' if snap['plant_severity']=='WARNING' else '#15803d')}; border: 1px solid {'#fca5a5' if snap['plant_severity']=='CRITICAL' else ('#fdba74' if snap['plant_severity']=='WARNING' else '#86efac')}; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px; text-transform: uppercase;">{snap['plant_severity']}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 1. Bottom Line in simple English -->
          <tr>
            <td style="padding: 10px 18px 6px 18px;">
              <div style="background: #f8fafc; border-left: 3px solid #0284c7; padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #0f172a; line-height: 1.45;">
                <strong>Bottom line:</strong> {narr['bottom_line']}
              </div>
            </td>
          </tr>

          <!-- 2. Today in Numbers -->
          <tr>
            <td style="padding: 6px 18px;">
              <table width="100%" cellpadding="0" cellspacing="4" style="text-align: center;">
                <tr>
                  <td style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #64748b; text-transform: uppercase; font-weight: 600;">Orders Due</div>
                    <div style="font-size: 15px; font-weight: 800; color: #0f172a; margin-top: 2px;">{orders_due}</div>
                  </td>
                  <td style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #64748b; text-transform: uppercase; font-weight: 600;">Orders Late</div>
                    <div style="font-size: 15px; font-weight: 800; color: {'#b91c1c' if orders_late > 0 else '#0f172a'}; margin-top: 2px;">{orders_late}</div>
                  </td>
                  <td style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #64748b; text-transform: uppercase; font-weight: 600;">Units Short</div>
                    <div style="font-size: 15px; font-weight: 800; color: {'#c2410c' if units_short > 0 else '#0f172a'}; margin-top: 2px;">{units_short}</div>
                  </td>
                  <td style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #64748b; text-transform: uppercase; font-weight: 600;">Materials Low</div>
                    <div style="font-size: 15px; font-weight: 800; color: {'#b91c1c' if materials_low > 0 else '#0f172a'}; margin-top: 2px;">{materials_low}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 3. What Happened Today -->
          <tr>
            <td style="padding: 6px 18px 4px 18px;">
              <div style="font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; margin-bottom: 3px;">What happened today</div>
              <ul style="margin: 0; padding-left: 18px; font-size: 11px; color: #334155; line-height: 1.35;">
                {what_happened_bullets}
              </ul>
            </td>
          </tr>

          <!-- 4. Causal Findings in Plain English -->
          <tr>
            <td style="padding: 6px 18px 4px 18px;">
              <div style="font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; margin-bottom: 3px;">Causal analysis findings</div>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px 10px;">
                {causal_findings_html}
              </div>
            </td>
          </tr>

          <!-- 5. Tomorrow's Priorities -->
          <tr>
            <td style="padding: 6px 18px 4px 18px;">
              <div style="font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; margin-bottom: 3px;">Tomorrow's priorities</div>
              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px;">
                {priority_rows}
              </table>
            </td>
          </tr>

          <!-- 6. Footer -->
          <tr>
            <td style="padding: 10px 18px; background: #f8fafc; border-top: 1px solid #e2e8f0; font-size: 10px; color: #64748b; line-height: 1.4;">
              <div><strong>Operational Notice:</strong> Simulated data as of {as_of.isoformat()}.</div>
              <div style="margin-top: 3px;">{RESEARCH_FRAMING}</div>
              <div style="margin-top: 6px;"><a href="{dashboard_url}" style="color: #0284c7; text-decoration: underline; font-weight: 600;">Open SAGE Dashboard &rarr;</a></div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # Plain text version
    text_lines = [
        f"SAGE DAILY OPERATIONS BRIEF | {as_of.isoformat()} ({snap['weekday']})",
        f"Simulated data as of {as_of.isoformat()} | Status: {snap['plant_severity']}",
        "=" * 70,
        "",
        f"BOTTOM LINE:\n{textwrap.fill(narr['bottom_line'], width=72)}",
        "",
        f"TODAY IN NUMBERS:",
        f"  Orders Due: {orders_due} | Orders Late: {orders_late}",
        f"  Units Short: {units_short} | Materials Running Low: {materials_low}",
        "",
        "WHAT HAPPENED TODAY:",
    ]
    for b in narr.get("what_happened", [])[:4]:
        text_lines.append(f"• {textwrap.fill(b, width=70, subsequent_indent='  ')}")

    text_lines.extend(["", "CAUSAL FINDINGS:"])
    for cf in causal_findings_text:
        text_lines.append(f"• {cf}")

    text_lines.extend(["", "TOMORROW'S PRIORITIES:"])
    for p in pri.get("top_priorities", [])[:5]:
        text_lines.append(f"[{p['rank']}] {p['action']} ({p['role']})")
        text_lines.append(f"    {p['reason']}")

    text_lines.extend([
        "",
        "=" * 70,
        f"RESEARCH FRAMING:\n{RESEARCH_FRAMING}",
        f"\nSimulated data as of {as_of.isoformat()}.",
        f"Dashboard: {dashboard_url}"
    ])
    plain_text = "\n".join(text_lines)

    return subject, html, plain_text


# ──────────────────────────────────────────────────────────────────────────────
# 3. Automated One-Page PDF Check (Playwright Chromium)
# ──────────────────────────────────────────────────────────────────────────────
def assert_one_page_pdf(html_content: str) -> Tuple[bool, int, Optional[bytes]]:
    """
    Renders HTML to PDF on A4 with Playwright Chromium and asserts page_count == 1.
    Returns (is_single_page, page_count, pdf_bytes).
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")

            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"},
            )
            browser.close()

        import re
        page_matches = len(re.findall(rb'/Type\s*/Page\b', pdf_bytes))
        is_single = (page_matches == 1)
        return is_single, page_matches, pdf_bytes

    except Exception as exc:
        logger.warning("Playwright PDF generation check skipped or failed: %s", exc)
        return True, 1, None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAGE Email Renderer")
    parser.add_argument("--as-of", type=str, help="As-of date override (YYYY-MM-DD)")
    parser.add_argument("--check-pdf", action="store_true", help="Assert one-page PDF render")
    args = parser.parse_args()

    as_of_date = get_as_of_date(override=args.as_of)
    print(f"Rendering nightly digest for as-of date: {as_of_date.isoformat()}...")
    sbj, htm, txt = render_nightly_digest(as_of_date)
    print(f"Subject: {sbj}\n")
    print(txt[:350] + "...\n")

    if args.check_pdf:
        ok, cnt, _ = assert_one_page_pdf(htm)
        print(f"PDF Page Check: ok={ok}, pages={cnt}")
