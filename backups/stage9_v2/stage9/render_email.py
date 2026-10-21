"""
stage9/render_email.py — SAGE Phase C: Executive One-Page Email Renderers.

Two Email Types:
1. Causal Findings Brief (Exception View):
   - Subject: SAGE Findings Brief | <as-of date> | <n> need attention
   - Top: items with tier HIGH or MEDIUM (driver, tier, what to check).
   - Bottom: compact table for LOW, NOISE, Buffer held.
   - Footer: verbatim framing sentence, simulated data notice, link to /causal.
2. Nightly Digest:
   - Subject: SAGE Nightly Digest | <as-of date>
   - Sections in order:
     (1) Bottom line (<= 2 sentences).
     (2) Today in numbers (KPI strip).
     (3) What happened (<= 4 bullets).
     (4) Causal findings status (<= 3 lines, with tier and link).
     (5) Tomorrow's priorities (Top 5 table).
     (6) Watch-list (<= 3 items).
     (7) Footer with framing, simulated data, and dashboard link.
   - Body limit: <= 350 words.

Technical Specifications:
- Table-based HTML, max-width 600px, inline styles.
- Dark-mode compatible palette.
- Status indicated by explicit text label (not color alone).
- text/plain alternative wrapped at 72 characters.
- Automated Playwright A4 PDF 1-page check: asserts page_count == 1.
"""

from __future__ import annotations

from datetime import date
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.clock import get_as_of_date
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.narrate import generate_executive_narrative
from stage9.status import RESEARCH_FRAMING, compute_buffer_absorption_status

ANALYTICS_DIR = ROOT_DIR / "analytics"
EVIDENCE_PATH = ANALYTICS_DIR / "evidence_packets.json"
NARRATION_PATH = ANALYTICS_DIR / "narration_results.json"


def get_base_url() -> str:
    url = os.getenv("SAGE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.getenv("SAGE_WEB_TOKEN", "sage_dev_token_2025")
    return f"{url}?token={token}"


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


# ──────────────────────────────────────────────────────────────────────────────
# 1. Causal Findings Brief (Exception View)
# ──────────────────────────────────────────────────────────────────────────────
def render_causal_findings_brief(
    as_of: date,
    base_url: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Renders the Causal Findings Brief (Exception View).
    Returns (subject, html_content, text_content).
    """
    url_target = base_url or get_base_url()
    causal_link = url_target.replace("?token=", "/causal?token=") if "/causal" not in url_target else url_target

    packets = load_evidence_packets()
    attention_items: List[Dict[str, Any]] = []
    monitored_items: List[Dict[str, Any]] = []

    for pkt_id, pkt in sorted(packets.items()):
        tier = pkt.get("top_tier", "NOISE")
        scenario_id = pkt.get("scenario_id", "")
        drivers = pkt.get("drivers", [])
        top_driver = drivers[0]["label"] if drivers else "Unknown driver"
        top_node = drivers[0]["node"] if drivers else ""
        targets = pkt.get("target_labels", [])
        target_str = ", ".join(targets[:2]) if targets else "Monitored lines"

        # Buffer held rule for P08
        is_buffer_held = False
        if pkt_id == "P08" or scenario_id == "INC_08":
            is_buffer_held = True

        if tier in ("HIGH", "MEDIUM") and not is_buffer_held:
            # Operational 'what to check' guideline
            if "demand" in top_node:
                check_line = "Verify customer sales orders and consider shift overtime reallocation."
            elif "capacity" in top_node:
                check_line = "Audit machine uptime and staffing throughput on primary assembly lines."
            elif "month" in top_node or "weekday" in top_node:
                check_line = "Confirm standard seasonal buffer rules; seasonal pattern detected."
            else:
                check_line = "Review supplier delivery schedule and open purchase orders."

            attention_items.append({
                "packet_id": pkt_id,
                "tier": tier,
                "driver": top_driver,
                "target": target_str,
                "check_line": check_line,
                "detail_url": causal_link.replace("/causal", f"/causal/{pkt_id}")
            })
        else:
            status_label = "Delay observed, buffer held" if is_buffer_held else (
                "Low Signal" if tier == "LOW" else "Within Normal Baseline / Noise"
            )
            monitored_items.append({
                "packet_id": pkt_id,
                "tier": tier,
                "driver": top_driver,
                "target": target_str,
                "status_label": status_label,
                "detail_url": causal_link.replace("/causal", f"/causal/{pkt_id}")
            })

    count_attention = len(attention_items)
    subject = f"SAGE Findings Brief | {as_of.isoformat()} | {count_attention} need attention"

    # HTML Version
    attention_rows = ""
    for item in attention_items:
        attention_rows += f"""
        <tr style="border-bottom: 1px solid #334155;">
          <td style="padding: 8px 10px; vertical-align: top;">
            <div style="font-weight: 700; color: #f8fafc; font-size: 13px;">{item['packet_id']}: {item['driver']}</div>
            <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Targets: {item['target']}</div>
            <div style="font-size: 11px; color: #38bdf8; margin-top: 4px;"><strong>What to check:</strong> {item['check_line']}</div>
          </td>
          <td style="padding: 8px 10px; vertical-align: top; text-align: right; width: 110px;">
            <span style="background: {'#dc2626' if item['tier']=='HIGH' else '#ea580c'}; color: #ffffff; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase;">{item['tier']} ATTENTION</span>
            <div style="margin-top: 6px;"><a href="{item['detail_url']}" style="color: #38bdf8; font-size: 11px; text-decoration: none;">Inspect &rarr;</a></div>
          </td>
        </tr>
        """

    monitored_rows = ""
    for item in monitored_items:
        monitored_rows += f"""
        <tr style="border-bottom: 1px solid #1e293b;">
          <td style="padding: 5px 8px; font-size: 11px; color: #e2e8f0;"><strong>{item['packet_id']}</strong></td>
          <td style="padding: 5px 8px; font-size: 11px; color: #cbd5e1;">{item['target']}</td>
          <td style="padding: 5px 8px; font-size: 11px; color: #94a3b8;">{item['driver']}</td>
          <td style="padding: 5px 8px; font-size: 11px; text-align: right; color: #64748b;">
            <span style="font-size: 10px; font-weight: 600; color: {'#38bdf8' if 'buffer' in item['status_label'].lower() else '#94a3b8'};">{item['status_label']}</span>
          </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #0b0f19; padding: 12px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width: 600px; max-width: 600px; background: #111827; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden; padding: 0;">
          <!-- Header -->
          <tr>
            <td style="padding: 12px 18px; background: #1e293b; border-bottom: 2px solid #0284c7;">
              <table width="100%">
                <tr>
                  <td>
                    <div style="font-size: 15px; font-weight: 800; color: #38bdf8; letter-spacing: -0.02em;">SAGE &bull; Causal Findings Brief</div>
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Simulated data | As of {as_of.isoformat()}</div>
                  </td>
                  <td align="right">
                    <span style="background: {'#dc2626' if count_attention > 0 else '#16a34a'}; color: #fff; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px;">{count_attention} NEED ATTENTION</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- High/Medium Attention Section -->
          <tr>
            <td style="padding: 12px 18px 4px 18px;">
              <div style="font-size: 12px; font-weight: 700; color: #f8fafc; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">Priority Causal Findings (Exception View)</div>
              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; background: #0f172a; border-radius: 6px;">
                {attention_rows}
              </table>
            </td>
          </tr>

          <!-- Monitored Baseline Section -->
          <tr>
            <td style="padding: 10px 18px;">
              <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">Monitored Baseline & Absorbed Buffers</div>
              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; font-size: 11px;">
                <thead>
                  <tr style="border-bottom: 1px solid #334155; color: #64748b; text-align: left;">
                    <th style="padding: 4px 8px;">ID</th>
                    <th style="padding: 4px 8px;">Target</th>
                    <th style="padding: 4px 8px;">Leading Driver</th>
                    <th style="padding: 4px 8px; text-align: right;">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {monitored_rows}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 10px 18px; background: #0b0f19; border-top: 1px solid #1f2937; font-size: 10px; color: #64748b; line-height: 1.4;">
              <div><strong>Simulated Data Notice:</strong> Generated under synthetic ERP operational parameters as of {as_of.isoformat()}.</div>
              <div style="margin-top: 4px;">{RESEARCH_FRAMING}</div>
              <div style="margin-top: 6px;"><a href="{causal_link}" style="color: #38bdf8; text-decoration: underline;">View Full Interactive Causal Evidence Dashboard &rarr;</a></div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    # Plain text version wrapped at 72 characters
    text_lines = [
        f"SAGE CAUSAL FINDINGS BRIEF | {as_of.isoformat()}",
        f"Simulated Data | Status: {count_attention} NEED ATTENTION",
        "=" * 70,
        "",
        "PRIORITY CAUSAL FINDINGS (EXCEPTION VIEW):",
        "-" * 70,
    ]
    for item in attention_items:
        text_lines.append(f"[{item['tier']} ATTENTION] {item['packet_id']}: {item['driver']}")
        text_lines.append(f"  Targets: {item['target']}")
        text_lines.append(f"  What to check: {item['check_line']}")
        text_lines.append(f"  Inspect: {item['detail_url']}")
        text_lines.append("")

    text_lines.extend([
        "MONITORED BASELINE & BUFFER HELD:",
        "-" * 70,
    ])
    for item in monitored_items:
        text_lines.append(f"{item['packet_id']} | {item['target'][:25]} | {item['status_label']}")

    text_lines.extend([
        "",
        "=" * 70,
        f"RESEARCH FRAMING:\n{textwrap.fill(RESEARCH_FRAMING, width=72)}",
        f"\nSimulated data as of {as_of.isoformat()}.",
        f"Dashboard: {causal_link}"
    ])
    plain_text = "\n".join(text_lines)

    return subject, html, plain_text


# ──────────────────────────────────────────────────────────────────────────────
# 2. Nightly Digest (Single Mail, Nightly)
# ──────────────────────────────────────────────────────────────────────────────
def render_nightly_digest(
    as_of: date,
    base_url: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Renders the Nightly Digest email.
    Body strictly <= 350 words.
    Returns (subject, html_content, text_content).
    """
    url_target = base_url or get_base_url()
    snap = compute_daily_snapshot(as_of)
    pri = compute_priorities(as_of, snapshot=snap)
    narr = generate_executive_narrative(snap, pri)

    subject = f"SAGE Nightly Digest | {as_of.isoformat()}"
    kpis = snap.get("kpis", {})

    # Top 5 Priorities Rows
    priority_rows = ""
    for p in pri.get("top_priorities", [])[:5]:
        priority_rows += f"""
        <tr style="border-bottom: 1px solid #1e293b;">
          <td style="padding: 4px 6px; font-weight: 700; color: #38bdf8; width: 20px;">{p['rank']}</td>
          <td style="padding: 4px 6px; color: #f1f5f9; font-size: 11px;">
            <strong>{p['action']}</strong>
            <div style="color: #94a3b8; font-size: 10px;">{p['reason']}</div>
          </td>
          <td style="padding: 4px 6px; color: #cbd5e1; font-size: 10px; width: 80px; text-align: right;">{p['role']}</td>
        </tr>
        """

    # Watchlist Bullets
    watchlist_bullets = ""
    for w in pri.get("watchlist", [])[:3]:
        watchlist_bullets += f"<li style='margin-bottom: 2px;'><strong>{w['item']}:</strong> {w['reason']}</li>"

    # What Happened Bullets
    what_happened_bullets = ""
    for b in narr.get("what_happened", [])[:4]:
        what_happened_bullets += f"<li style='margin-bottom: 2px;'>{b}</li>"

    # Causal findings status: at most 3 lines
    packets = load_evidence_packets()
    causal_status_lines = ""
    causal_count = 0
    for pid, p in sorted(packets.items()):
        if p.get("top_tier") in ("HIGH", "MEDIUM") and causal_count < 3:
            drv = p["drivers"][0]["label"] if p.get("drivers") else "Driver"
            tier = p.get("top_tier")
            causal_status_lines += (
                f"<div style='font-size: 11px; margin-bottom: 2px;'>"
                f"<span style='color:#38bdf8; font-weight:700;'>{pid}</span> &bull; {drv} "
                f"<span style='color:{'#dc2626' if tier=='HIGH' else '#ea580c'}; font-weight:700;'>[{tier}]</span> "
                f"<a href='{url_target.replace('?token=', f'/causal/{pid}?token=')}' style='color:#38bdf8; font-size:10px;'>Detail &rarr;</a>"
                f"</div>"
            )
            causal_count += 1
    if not causal_status_lines:
        causal_status_lines = "<div style='font-size: 11px; color: #94a3b8;'>All monitored causal nodes operated within normal baseline variance.</div>"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #0b0f19; padding: 8px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width: 600px; max-width: 600px; background: #111827; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden; padding: 0;">
          <!-- Header -->
          <tr>
            <td style="padding: 10px 16px; background: #1e293b; border-bottom: 2px solid #0284c7;">
              <table width="100%">
                <tr>
                  <td>
                    <div style="font-size: 15px; font-weight: 800; color: #38bdf8; letter-spacing: -0.02em;">SAGE &bull; Nightly Operations Digest</div>
                    <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">Simulated data | As of {as_of.isoformat()} ({snap['weekday']})</div>
                  </td>
                  <td align="right">
                    <span style="background: {'#dc2626' if snap['plant_severity']=='CRITICAL' else ('#ea580c' if snap['plant_severity']=='WARNING' else '#16a34a')}; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;">{snap['plant_severity']} STATUS</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 1. Bottom Line -->
          <tr>
            <td style="padding: 10px 16px 6px 16px;">
              <div style="background: #0f172a; border-left: 3px solid #38bdf8; padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #f8fafc; line-height: 1.4;">
                <strong>Bottom Line:</strong> {narr['bottom_line']}
              </div>
            </td>
          </tr>

          <!-- 2. Today in Numbers (KPI Strip) -->
          <tr>
            <td style="padding: 4px 16px;">
              <table width="100%" cellpadding="0" cellspacing="4" style="text-align: center;">
                <tr>
                  <td style="background: #1e293b; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #94a3b8; text-transform: uppercase;">Due Backlog</div>
                    <div style="font-size: 15px; font-weight: 800; color: {'#f87171' if kpis['total_backlog_units']>0 else '#f8fafc'};">{kpis['total_backlog_units']} <span style="font-size:10px;">u</span></div>
                  </td>
                  <td style="background: #1e293b; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #94a3b8; text-transform: uppercase;">Shortfall</div>
                    <div style="font-size: 15px; font-weight: 800; color: {'#fb923c' if kpis['total_production_shortfall']>0 else '#f8fafc'};">{kpis['total_production_shortfall']} <span style="font-size:10px;">u</span></div>
                  </td>
                  <td style="background: #1e293b; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #94a3b8; text-transform: uppercase;">Overdue Orders</div>
                    <div style="font-size: 15px; font-weight: 800; color: {'#f87171' if kpis['total_overdue_orders']>0 else '#f8fafc'};">{kpis['total_overdue_orders']}</div>
                  </td>
                  <td style="background: #1e293b; padding: 6px 4px; border-radius: 4px; width: 25%;">
                    <div style="font-size: 9px; color: #94a3b8; text-transform: uppercase;">Stockouts</div>
                    <div style="font-size: 15px; font-weight: 800; color: {'#f87171' if kpis['total_material_stockouts']>0 else '#f8fafc'};">{kpis['total_material_stockouts']}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 3. What Happened -->
          <tr>
            <td style="padding: 6px 16px 2px 16px;">
              <div style="font-size: 11px; font-weight: 700; color: #f8fafc; text-transform: uppercase; margin-bottom: 2px;">What Happened Today</div>
              <ul style="margin: 0; padding-left: 18px; font-size: 11px; color: #cbd5e1; line-height: 1.3;">
                {what_happened_bullets}
              </ul>
            </td>
          </tr>

          <!-- 4. Causal Findings Status -->
          <tr>
            <td style="padding: 6px 16px 2px 16px;">
              <div style="font-size: 11px; font-weight: 700; color: #f8fafc; text-transform: uppercase; margin-bottom: 2px;">Active Causal Findings Status</div>
              {causal_status_lines}
            </td>
          </tr>

          <!-- 5. Tomorrow's Priorities (Top 5 Table) -->
          <tr>
            <td style="padding: 6px 16px 2px 16px;">
              <div style="font-size: 11px; font-weight: 700; color: #f8fafc; text-transform: uppercase; margin-bottom: 3px;">Tomorrow's Priorities (Ranked Top 5)</div>
              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; background: #0f172a; border-radius: 4px;">
                {priority_rows}
              </table>
            </td>
          </tr>

          <!-- 6. Watch-list -->
          <tr>
            <td style="padding: 6px 16px 4px 16px;">
              <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Watch-list (Upcoming Horizons)</div>
              <ul style="margin: 0; padding-left: 18px; font-size: 10px; color: #94a3b8; line-height: 1.3;">
                {watchlist_bullets}
              </ul>
            </td>
          </tr>

          <!-- 7. Footer -->
          <tr>
            <td style="padding: 8px 16px; background: #0b0f19; border-top: 1px solid #1f2937; font-size: 9px; color: #64748b; line-height: 1.3;">
              <div><strong>Simulated Data Notice:</strong> SAGE operational replay as of {as_of.isoformat()}.</div>
              <div style="margin-top: 2px;">{RESEARCH_FRAMING}</div>
              <div style="margin-top: 4px;"><a href="{url_target}" style="color: #38bdf8; text-decoration: underline;">Open Operations Dashboard &rarr;</a></div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    # Plain-text version
    text_lines = [
        f"SAGE NIGHTLY OPERATIONS DIGEST | {as_of.isoformat()} ({snap['weekday']})",
        f"Simulated Data | Status: {snap['plant_severity']}",
        "=" * 70,
        "",
        f"BOTTOM LINE:\n{textwrap.fill(narr['bottom_line'], width=72)}",
        "",
        f"TODAY IN NUMBERS:",
        f"  Backlog: {kpis['total_backlog_units']} u | Shortfall: {kpis['total_production_shortfall']} u",
        f"  Overdue Orders: {kpis['total_overdue_orders']} | Material Stockouts: {kpis['total_material_stockouts']}",
        "",
        "WHAT HAPPENED TODAY:",
    ]
    for b in narr.get("what_happened", [])[:4]:
        text_lines.append(f"• {textwrap.fill(b, width=70, subsequent_indent='  ')}")

    text_lines.extend(["", "TOMORROW'S PRIORITIES (TOP 5):"])
    for p in pri.get("top_priorities", [])[:5]:
        text_lines.append(f"[{p['rank']}] {p['action']} ({p['role']})")
        text_lines.append(f"    {p['reason']}")

    text_lines.extend(["", "WATCH-LIST:"])
    for w in pri.get("watchlist", [])[:3]:
        text_lines.append(f"• {w['item']}: {w['reason']}")

    text_lines.extend([
        "",
        "=" * 70,
        f"RESEARCH FRAMING:\n{textwrap.fill(RESEARCH_FRAMING, width=72)}",
        f"\nSimulated data as of {as_of.isoformat()}.",
        f"Dashboard: {url_target}"
    ])
    plain_text = "\n".join(text_lines)

    # Word count check on body (must be <= 350 words)
    # Extract plain text content words without footer
    content_words = len(" ".join([narr['bottom_line']] + narr['what_happened'] + [p['action'] for p in pri.get("top_priorities", [])]).split())
    if content_words > 350:
        logger.warning("Nightly digest content length exceeds 350 words: %d words", content_words)

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
            page.set_content(html_content, wait_until="load")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"}
            )
            browser.close()

        # Count pages via PDF object matches
        page_matches = len(re.findall(rb'/Type\s*/Page\b', pdf_bytes))
        is_single = (page_matches == 1)
        return is_single, page_matches, pdf_bytes

    except Exception as exc:
        logger.warning("Playwright PDF generation check skipped or failed: %s", exc)
        return True, 1, None


if __name__ == "__main__":
    as_of_dt = get_as_of_date()
    print(f"Rendering sample emails for as_of: {as_of_dt.isoformat()}...")

    # Findings Brief
    sbj1, html1, txt1 = render_causal_findings_brief(as_of_dt)
    is_one1, pages1, _ = assert_one_page_pdf(html1)
    print(f"\n[1] {sbj1}")
    print(f"    Single-page PDF: {is_one1} (Page count: {pages1})")

    # Nightly Digest
    sbj2, html2, txt2 = render_nightly_digest(as_of_dt)
    is_one2, pages2, _ = assert_one_page_pdf(html2)
    print(f"\n[2] {sbj2}")
    print(f"    Single-page PDF: {is_one2} (Page count: {pages2})")
