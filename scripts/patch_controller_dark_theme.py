"""
scripts/patch_controller_dark_theme.py — Update Controller to dark theme with Hero status card.
"""

from pathlib import Path
import re

dash_file = Path("controller/templates/dashboard.html")
text = dash_file.read_text(encoding="utf-8")

# 1. Update CSS styles for dark palette
old_style_pattern = r'<style>.*?</style>'
new_style = """<style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0b0f19;
      --surface: #131b2e;
      --border: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #3b82f6;
      --green: #10b981;
      --amber: #f59e0b;
      --red: #ef4444;
      --radius: 10px;
    }
    body { background: var(--bg); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           color: var(--text); -webkit-font-smoothing: antialiased; }
    /* NAV */
    nav { background: #0f172a; color: #fff; padding: 0 28px; display: flex;
          align-items: center; gap: 20px; height: 52px; border-bottom: 1px solid var(--border); }
    .nav-logo { font-size: 1.1rem; font-weight: 800; color: #fff; letter-spacing: -0.02em; flex: 1; }
    .nav-logo span { color: #60a5fa; }
    .nav-item { font-size: 0.85rem; color: #94a3b8; text-decoration: none; }
    .nav-item:hover { color: #fff; }
    .nav-badge { font-size: 0.72rem; background: rgba(245, 158, 11, 0.2); color: #fbbf24;
                 border: 1px solid rgba(245, 158, 11, 0.4); padding: 2px 8px; border-radius: 20px; font-weight: 700; }
    .logout-btn { background: none; border: 1px solid #334155; color: #94a3b8;
                  padding: 5px 12px; border-radius: 6px; cursor: pointer; font-size: 0.82rem; }
    .logout-btn:hover { background: #1e293b; color: #fff; }
    /* LAYOUT */
    .main { max-width: 1100px; margin: 0 auto; padding: 28px 24px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
    .card { background: var(--surface); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 22px 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
    .card-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
                  letter-spacing: 0.06em; color: var(--muted); margin-bottom: 14px; }
    .stat-row { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
    .stat-val { font-size: 1.8rem; font-weight: 800; color: #f8fafc; }
    .stat-label { font-size: 0.88rem; color: var(--muted); }
    /* PILLS */
    .pill { display: inline-flex; align-items: center; gap: 5px;
            padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
    .pill-green { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .pill-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .pill-red { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .pill-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .pill-gray { background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); }
    /* BUTTONS */
    .btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 18px;
           border-radius: 8px; font-size: 0.88rem; font-weight: 700; cursor: pointer;
           border: none; transition: background 0.15s; }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover { background: #2563eb; }
    .btn-success { background: #059669; color: #fff; }
    .btn-success:hover { background: #047857; }
    .btn-warning { background: var(--amber); color: #fff; }
    .btn-warning:hover { background: #b45309; }
    .btn-danger { background: var(--red); color: #fff; }
    .btn-danger:hover { background: #b91c1c; }
    .btn-ghost { background: #0b0f19; border: 1px solid var(--border); color: var(--text); }
    .btn-ghost:hover { background: #1e293b; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
    /* FORM INPUTS */
    input, select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px;
                    font-size: 0.9rem; width: 100%; background: #0b0f19; color: var(--text); }
    input:focus, select:focus { border-color: var(--accent); outline: none;
                                box-shadow: 0 0 0 3px rgba(59,130,246,0.2); background: #0f172a; }
    label { font-size: 0.78rem; font-weight: 600; color: var(--muted);
            text-transform: uppercase; letter-spacing: 0.04em; display: block;
            margin-bottom: 5px; margin-top: 12px; }
    /* TOAST */
    #toast { position: fixed; bottom: 24px; right: 24px; min-width: 260px;
             background: #1e293b; color: #fff; padding: 12px 18px; border-radius: 10px;
             font-size: 0.88rem; opacity: 0; transform: translateY(8px);
             transition: all 0.25s; z-index: 9999; pointer-events: none; border: 1px solid var(--border); }
    #toast.show { opacity: 1; transform: translateY(0); }
    #toast.success { background: #065f46; color: #34d399; border-color: #059669; }
    #toast.error { background: #7f1d1d; color: #fca5a5; border-color: #dc2626; }
    /* AUDIT LOG */
    .audit-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-top: 8px; }
    .audit-table th { text-align: left; padding: 8px 10px; font-size: 0.72rem;
                      color: var(--muted); border-bottom: 1px solid var(--border);
                      text-transform: uppercase; letter-spacing: 0.05em; }
    .audit-table td { padding: 8px 10px; border-bottom: 1px solid #1e293b;
                      vertical-align: top; color: var(--text); }
    .audit-table tr:last-child td { border-bottom: none; }
    .monospace { font-family: "SF Mono", monospace; font-size: 0.75rem; color: #94a3b8; }
    /* MODAL */
    .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.65);
                     z-index: 1000; align-items: center; justify-content: center; backdrop-filter: blur(4px); }
    .modal-overlay.open { display: flex; }
    .modal { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px;
             min-width: 380px; max-width: 500px; box-shadow: 0 8px 40px rgba(0,0,0,0.5); color: var(--text); }
    .modal-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 12px; color: #f8fafc; }
    .modal-footer { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
    /* PROGRESS */
    .progress-bar-wrap { height: 6px; background: #1e293b; border-radius: 4px;
                         margin-top: 8px; overflow: hidden; }
    .progress-bar { height: 100%; background: var(--accent); border-radius: 4px;
                    width: 0%; transition: width 0.4s; }
    /* TOGGLE */
    .toggle-row { display: flex; align-items: center; justify-content: space-between;
                  gap: 16px; }
    .toggle-label { font-size: 0.9rem; color: var(--text); }
    .toggle { position: relative; width: 44px; height: 24px; }
    .toggle input { opacity: 0; width: 0; height: 0; }
    .toggle-slider { position: absolute; inset: 0; background: #334155; border-radius: 24px;
                     cursor: pointer; transition: background 0.2s; }
    .toggle input:checked + .toggle-slider { background: var(--accent); }
    .toggle-slider::before { content: ""; position: absolute; height: 18px; width: 18px;
                              left: 3px; top: 3px; background: white; border-radius: 50%;
                              transition: transform 0.2s; }
    .toggle input:checked + .toggle-slider::before { transform: translateX(20px); }
    /* SECTION HEADER */
    .section-h { font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
                 letter-spacing: 0.06em; color: var(--muted); border-bottom: 1px solid var(--border);
                 padding-bottom: 8px; margin: 24px 0 16px; }
    .full-width { grid-column: 1 / -1; }
    /* ALLOWLIST */
    .allowlist-item { display: inline-block; background: #0b0f19; border: 1px solid var(--border); border-radius: 6px;
                      padding: 3px 10px; font-size: 0.8rem; margin: 3px; color: var(--text); }
  </style>"""

text = re.sub(old_style_pattern, new_style, text, count=1, flags=re.DOTALL)

# 2. Add Hero status card right after the dryrun-alert-banner
hero_card_html = """  <!-- ─── HERO STATUS CARD (C4) ─── -->
  <div class="card full-width hero-card" style="margin-bottom:20px; padding:24px 28px; background: linear-gradient(135deg, #131b2e 0%, #0d1527 100%); border:1px solid var(--border); border-radius:var(--radius); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:20px; position:relative; overflow:hidden;">
    <div style="flex:1; min-width:300px; z-index:2;">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
        <span class="status-indicator-dot" style="display:inline-block; width:12px; height:12px; border-radius:50%; background:{{ hero.status_color if hero else '#10b981' }}; box-shadow: 0 0 10px {{ hero.status_color if hero else '#10b981' }};"></span>
        <span style="font-size:0.75rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:{{ hero.status_color if hero else '#10b981' }}; background:rgba(0,0,0,0.3); padding:3px 10px; border-radius:20px; border:1px solid {{ hero.status_color if hero else '#10b981' }}40;">
          {{ hero.status_label if hero else 'CALM' }}
        </span>
        <span style="font-size:0.82rem; color:var(--muted); font-weight:500;">
          {{ hero.status_sub if hero else 'Factory telemetry nominal.' }}
        </span>
      </div>

      <h1 style="font-size:1.6rem; font-weight:800; letter-spacing:-0.02em; color:#f8fafc; margin-bottom:6px;">
        {{ hero.day_label if hero else current_day }}
      </h1>
      <p style="font-size:0.85rem; color:var(--muted); margin-bottom:18px; line-height:1.4;">
        Strategic Analytics for Guided Execution &bull; Operator Control Console
      </p>

      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <div style="background:rgba(15, 23, 42, 0.7); border:1px solid var(--border); border-radius:8px; padding:8px 14px; display:inline-flex; flex-direction:column;">
          <span style="font-size:0.70rem; color:var(--muted); text-transform:uppercase; font-weight:700;">Active Backorders</span>
          <span style="font-size:0.92rem; font-weight:700; color:#f8fafc;">{{ hero.backorder_val if hero else '0 units' }}</span>
        </div>
        <div style="background:rgba(15, 23, 42, 0.7); border:1px solid var(--border); border-radius:8px; padding:8px 14px; display:inline-flex; flex-direction:column;">
          <span style="font-size:0.70rem; color:var(--muted); text-transform:uppercase; font-weight:700;">Weakest Material</span>
          <span style="font-size:0.92rem; font-weight:700; color:#f8fafc;">{{ hero.weakest_material_val if hero else 'Steel (Normal)' }}</span>
        </div>
        <div style="background:rgba(15, 23, 42, 0.7); border:1px solid var(--border); border-radius:8px; padding:8px 14px; display:inline-flex; flex-direction:column;">
          <span style="font-size:0.70rem; color:var(--muted); text-transform:uppercase; font-weight:700;">Queue Position</span>
          <span style="font-size:0.92rem; font-weight:700; color:#f8fafc;">{{ hero.queue_val if hero else '10 packs remaining' }}</span>
        </div>
      </div>
    </div>

    <div style="width:180px; display:flex; justify-content:center; align-items:center; z-index:1;">
      <img src="/static/img/sage_logo_card.png" alt="SAGE Figure" style="max-height:150px; width:auto; object-fit:contain; opacity:0.92; filter: drop-shadow(0 0 16px rgba(59, 130, 246, 0.25));">
    </div>
  </div>
"""

target_marker = '  <div id="dryrun-alert-banner"'
if target_marker in text:
    end_of_banner = text.find('</div>', text.find(target_marker)) + 6
    text = text[:end_of_banner] + "\n\n" + hero_card_html + text[end_of_banner:]
    print("Inserted Hero status card.")
else:
    print("Warning: target_marker not found")

# 3. Clean up any remaining hardcoded light styles in dashboard.html
inline_replacements = [
    ("background:#fffbeb;", "background:rgba(245, 158, 11, 0.12);"),
    ("border:1px solid #fde68a;", "border:1px solid rgba(245, 158, 11, 0.3);"),
    ("color:#92400e;", "color:#fbbf24;"),
    ("background:#ecfdf5;", "background:rgba(16, 185, 129, 0.12);"),
    ("border:1px solid #a7f3d0;", "border:1px solid rgba(16, 185, 129, 0.3);"),
    ("color:#065f46;", "color:#34d399;"),
    ("background:#f8fafc;", "background:#0b0f19;"),
    ("background:#f1f5f9;", "background:#0b0f19;"),
    ("color:#1e293b;", "color:var(--text);"),
    ("color:#334155;", "color:var(--text);"),
    ("border:1px solid #e2e8f0;", "border:1px solid var(--border);"),
    ("border:1px solid #cbd5e1;", "border:1px solid var(--border);"),
    ("border:1px solid #94a3b8;", "border:1px solid var(--border);"),
]

for src, dst in inline_replacements:
    text = text.replace(src, dst)

dash_file.write_text(text, encoding="utf-8")
print("Dashboard dark theme patch complete.")
