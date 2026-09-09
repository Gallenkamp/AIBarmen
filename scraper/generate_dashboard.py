#!/usr/bin/env python3
"""Generate an HTML dashboard from the occupancy CSV data."""

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ_BERLIN = ZoneInfo("Europe/Berlin")
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_FILE = DATA_DIR / "occupancy.csv"
DASHBOARD_FILE = DATA_DIR / "dashboard.html"

WEEKDAY_DE = {
    "Monday": "Montag",
    "Tuesday": "Dienstag",
    "Wednesday": "Mittwoch",
    "Thursday": "Donnerstag",
    "Friday": "Freitag",
    "Saturday": "Samstag",
    "Sunday": "Sonntag",
}


def read_csv() -> list[dict]:
    if not CSV_FILE.exists():
        return []
    rows = []
    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["percentage"] = int(row["percentage"])
            rows.append(row)
    return rows


def generate_dashboard(rows: list[dict]):
    now = datetime.now(TZ_BERLIN)
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    recent_rows = rows[-96:] if len(rows) > 96 else rows
    week_rows = [r for r in rows if r["date"] >= week_ago]
    month_rows = [r for r in rows if r["date"] >= month_ago]

    table_html_rows = []
    for r in reversed(recent_rows[-50:]):
        wd = WEEKDAY_DE.get(r.get("weekday", ""), r.get("weekday", ""))
        level_class = "low" if r["level"] == "LOW" else "normal" if r["level"] == "NORMAL" else "high"
        table_html_rows.append(
            f'<tr class="{level_class}">'
            f'<td>{r["date"]}</td>'
            f'<td>{r["time"]}</td>'
            f"<td>{wd}</td>"
            f'<td><div class="bar-cell"><div class="bar" style="width:{r["percentage"]}%"></div>'
            f'<span>{r["percentage"]}%</span></div></td>'
            f'<td>{r["level"]}</td>'
            f"</tr>"
        )

    week_by_day_hour = defaultdict(list)
    for r in week_rows:
        key = f'{r["date"]} {r["time"][:2]}h'
        week_by_day_hour[r["date"]].append(r["percentage"])

    week_chart_data = []
    for r in week_rows:
        week_chart_data.append({"x": f'{r["date"]} {r["time"]}', "y": r["percentage"]})

    month_avg_by_day = defaultdict(list)
    for r in month_rows:
        month_avg_by_day[r["date"]].append(r["percentage"])
    month_chart_data = []
    for date in sorted(month_avg_by_day.keys()):
        vals = month_avg_by_day[date]
        avg = round(sum(vals) / len(vals), 1)
        mx = max(vals)
        month_chart_data.append({"date": date, "avg": avg, "max": mx})

    week_heatmap = defaultdict(lambda: defaultdict(list))
    for r in week_rows:
        wd = r.get("weekday", "")
        hour = r["time"][:2]
        week_heatmap[wd][hour].append(r["percentage"])

    heatmap_data = {}
    for wd in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        heatmap_data[WEEKDAY_DE.get(wd, wd)] = {}
        for h in range(6, 24):
            hour_key = f"{h:02d}"
            vals = week_heatmap[wd].get(hour_key, [])
            heatmap_data[WEEKDAY_DE.get(wd, wd)][hour_key] = round(sum(vals) / len(vals), 1) if vals else None

    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Fitness Wuppertal - Studioauslastung</title>
<style>
:root {{
  --bg: #0f172a;
  --surface: #1e293b;
  --border: #334155;
  --text: #e2e8f0;
  --text-muted: #94a3b8;
  --accent: #3b82f6;
  --low: #22c55e;
  --normal: #f59e0b;
  --high: #ef4444;
  --bar-bg: #334155;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  padding: 1rem;
  max-width: 1200px;
  margin: 0 auto;
}}
h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
.subtitle {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem; }}
.section {{ background: var(--surface); border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; border: 1px solid var(--border); }}
.section h2 {{ font-size: 1.1rem; margin-bottom: 0.75rem; color: var(--accent); }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
th, td {{ padding: 0.4rem 0.6rem; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ color: var(--text-muted); font-weight: 600; position: sticky; top: 0; background: var(--surface); }}
.bar-cell {{ display: flex; align-items: center; gap: 0.5rem; }}
.bar {{ height: 1rem; background: var(--low); border-radius: 0.2rem; min-width: 2px; transition: width 0.3s; }}
tr.normal .bar {{ background: var(--normal); }}
tr.high .bar {{ background: var(--high); }}
.table-wrap {{ max-height: 400px; overflow-y: auto; }}
.chart-container {{ position: relative; width: 100%; height: 300px; }}
canvas {{ width: 100% !important; height: 100% !important; }}
.tabs {{ display: flex; gap: 0.5rem; margin-bottom: 1rem; }}
.tab {{ padding: 0.4rem 1rem; border-radius: 0.3rem; border: 1px solid var(--border); background: transparent;
  color: var(--text-muted); cursor: pointer; font-size: 0.85rem; }}
.tab.active {{ background: var(--accent); color: white; border-color: var(--accent); }}
.heatmap {{ display: grid; gap: 2px; font-size: 0.7rem; }}
.heatmap-row {{ display: flex; gap: 2px; align-items: center; }}
.heatmap-label {{ width: 80px; text-align: right; padding-right: 0.5rem; color: var(--text-muted); flex-shrink: 0; }}
.heatmap-cell {{
  flex: 1; text-align: center; padding: 0.3rem 0.1rem; border-radius: 0.2rem;
  min-width: 30px; font-size: 0.65rem;
}}
.heatmap-header {{ display: flex; gap: 2px; margin-left: 82px; }}
.heatmap-header span {{ flex: 1; text-align: center; color: var(--text-muted); font-size: 0.65rem; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }}
.stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.75rem; text-align: center; }}
.stat-value {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
.stat-label {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; }}
.no-data {{ color: var(--text-muted); text-align: center; padding: 2rem; }}
</style>
</head>
<body>
<h1>AI Fitness Wuppertal Barmen</h1>
<p class="subtitle">Studioauslastung — aktualisiert {generated_at}</p>

<div class="stats" id="stats"></div>

<div class="tabs">
  <button class="tab active" onclick="showTab('table')">Tabelle</button>
  <button class="tab" onclick="showTab('week')">Woche</button>
  <button class="tab" onclick="showTab('month')">Monat</button>
  <button class="tab" onclick="showTab('heatmap')">Heatmap</button>
</div>

<div id="tab-table" class="section">
  <h2>Letzte Messungen</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Datum</th><th>Zeit</th><th>Tag</th><th>Auslastung</th><th>Level</th></tr></thead>
      <tbody>{''.join(table_html_rows) if table_html_rows else '<tr><td colspan="5" class="no-data">Noch keine Daten</td></tr>'}</tbody>
    </table>
  </div>
</div>

<div id="tab-week" class="section" style="display:none">
  <h2>Wochenverlauf (letzte 7 Tage)</h2>
  <div class="chart-container"><canvas id="weekChart"></canvas></div>
</div>

<div id="tab-month" class="section" style="display:none">
  <h2>Monatsverlauf (letzte 30 Tage)</h2>
  <div class="chart-container"><canvas id="monthChart"></canvas></div>
</div>

<div id="tab-heatmap" class="section" style="display:none">
  <h2>Wochen-Heatmap (Durchschnitt)</h2>
  <div id="heatmap"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<script>
const weekData = {json.dumps(week_chart_data)};
const monthData = {json.dumps(month_chart_data)};
const heatmapData = {json.dumps(heatmap_data)};

// Stats
const allPercentages = weekData.map(d => d.y);
const statsEl = document.getElementById('stats');
if (allPercentages.length > 0) {{
  const current = allPercentages[allPercentages.length - 1];
  const avg = Math.round(allPercentages.reduce((a,b)=>a+b,0) / allPercentages.length);
  const max = Math.max(...allPercentages);
  const total = {len(rows)};
  statsEl.innerHTML = `
    <div class="stat"><div class="stat-value">${{current}}%</div><div class="stat-label">Aktuell</div></div>
    <div class="stat"><div class="stat-value">${{avg}}%</div><div class="stat-label">Schnitt (7 Tage)</div></div>
    <div class="stat"><div class="stat-value">${{max}}%</div><div class="stat-label">Maximum (7 Tage)</div></div>
    <div class="stat"><div class="stat-value">${{total}}</div><div class="stat-label">Messungen gesamt</div></div>
  `;
}}

function showTab(name) {{
  document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).style.display = '';
  event.target.classList.add('active');
}}

// Week chart
if (weekData.length > 0) {{
  new Chart(document.getElementById('weekChart'), {{
    type: 'line',
    data: {{
      labels: weekData.map(d => d.x),
      datasets: [{{
        label: 'Auslastung %',
        data: weekData.map(d => d.y),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 1,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      scales: {{
        x: {{
          ticks: {{ color: '#94a3b8', maxRotation: 45, maxTicksLimit: 20, font: {{ size: 10 }} }},
          grid: {{ color: '#334155' }}
        }},
        y: {{
          min: 0, max: 100,
          ticks: {{ color: '#94a3b8', callback: v => v + '%' }},
          grid: {{ color: '#334155' }}
        }}
      }},
      plugins: {{
        legend: {{ labels: {{ color: '#e2e8f0' }} }},
        tooltip: {{ callbacks: {{ label: ctx => ctx.parsed.y + '%' }} }}
      }}
    }}
  }});
}}

// Month chart
if (monthData.length > 0) {{
  new Chart(document.getElementById('monthChart'), {{
    type: 'bar',
    data: {{
      labels: monthData.map(d => d.date),
      datasets: [
        {{
          label: 'Durchschnitt %',
          data: monthData.map(d => d.avg),
          backgroundColor: 'rgba(59,130,246,0.7)',
          borderRadius: 3,
        }},
        {{
          label: 'Maximum %',
          data: monthData.map(d => d.max),
          backgroundColor: 'rgba(239,68,68,0.4)',
          borderRadius: 3,
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      scales: {{
        x: {{
          ticks: {{ color: '#94a3b8', maxRotation: 45, font: {{ size: 10 }} }},
          grid: {{ color: '#334155' }}
        }},
        y: {{
          min: 0, max: 100,
          ticks: {{ color: '#94a3b8', callback: v => v + '%' }},
          grid: {{ color: '#334155' }}
        }}
      }},
      plugins: {{
        legend: {{ labels: {{ color: '#e2e8f0' }} }}
      }}
    }}
  }});
}}

// Heatmap
const heatmapEl = document.getElementById('heatmap');
const hours = [];
for (let h = 6; h < 24; h++) hours.push(String(h).padStart(2, '0'));

let heatHtml = '<div class="heatmap-header">';
hours.forEach(h => heatHtml += `<span>${{h}}</span>`);
heatHtml += '</div>';

function heatColor(val) {{
  if (val === null) return 'background:var(--border);color:var(--text-muted)';
  if (val < 20) return 'background:#166534;color:#bbf7d0';
  if (val < 40) return 'background:#15803d;color:#dcfce7';
  if (val < 60) return 'background:#a16207;color:#fef3c7';
  if (val < 80) return 'background:#c2410c;color:#fed7aa';
  return 'background:#991b1b;color:#fecaca';
}}

for (const [day, hourData] of Object.entries(heatmapData)) {{
  heatHtml += `<div class="heatmap-row"><div class="heatmap-label">${{day}}</div>`;
  hours.forEach(h => {{
    const val = hourData[h];
    const display = val !== null ? val + '%' : '-';
    heatHtml += `<div class="heatmap-cell" style="${{heatColor(val)}}">${{display}}</div>`;
  }});
  heatHtml += '</div>';
}}
heatmapEl.innerHTML = heatHtml;
</script>
</body>
</html>"""

    DASHBOARD_FILE.write_text(html)
    print(f"Dashboard generated: {DASHBOARD_FILE}")

    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.html").write_text(html)
    print(f"Dashboard copied: {docs_dir / 'index.html'}")


if __name__ == "__main__":
    rows = read_csv()
    generate_dashboard(rows)
