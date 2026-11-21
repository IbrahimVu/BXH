"""Build a static GitHub Pages site from a live crawl or a reviewed snapshot."""

import argparse
import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from crawl import crawl
from rankings import site_rankings

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site" / "index.html"
STYLESHEET = ROOT / "site" / "style.css"
CONFIG = ROOT / "data" / "sources.json"
SNAPSHOT = ROOT / "data" / "snapshot.json"

OCCASION_LABELS = {
    "lunar": ("nguyen-dan", "Tết Nguyên đán"),
    "solar": ("duong-lich", "Tết Dương lịch"),
}


def format_number(amount):
    if amount is None:
        return "—"
    text = f"{amount:,.6f}".rstrip("0").rstrip(".")
    return text.translate(str.maketrans(",.", ".,"))


def render_table(ranking, anchor, title):
    table_rows = []
    for row in ranking["top"]:
        table_rows.append(
            f'<tr><td class="rank">{row["rank"]:02d}</td>'
            f'<th scope="row">{escape(row["name"])}</th>'
            f'<td>{escape(row["place"])}</td>'
            f'<td class="high">{format_number(row["high"])}</td>'
            f'<td class="amount">{format_number(row["mean"])}</td>'
            f'<td class="amount">{format_number(row["low"])}</td></tr>'
        )
    rows = "\n".join(table_rows)
    return f"""
<section class="ranking" id="{anchor}" aria-labelledby="title-{anchor}">
  <div class="section-heading">
    <h2 id="title-{anchor}">{title}</h2>
    <p>{format_number(ranking["total"])} doanh nghiệp đủ điều kiện xếp hạng</p>
  </div>
  <div class="table-wrap" tabindex="0" role="region" aria-label="Bảng thưởng {title}">
    <table>
      <thead><tr>
        <th scope="col">Hạng</th><th scope="col">Doanh nghiệp</th>
        <th scope="col">Phường/xã báo cáo</th><th scope="col">Cao nhất</th>
        <th scope="col">Bình quân</th><th scope="col">Thấp nhất</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>
"""


def render_site(report, output):
    if any(not ranking["top"] for ranking in report["rankings"].values()):
        raise RuntimeError("Missing a ranked holiday table, publication stopped")
    timestamp = datetime.fromisoformat(report["checked_at"])
    checked_at = timestamp.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    scope = []
    if report["blocked"]:
        unavailable = ", ".join(report["blocked"])
        scope.append(f"Nguồn báo cáo chưa truy cập được tại {unavailable}.")
    if report["new_sources"]:
        scope.append(f"{report['new_sources']} liên kết mới đang chờ đối chiếu biểu mẫu.")
    if report["directories_checked"] == 0:
        scope.append("Danh mục liên kết báo cáo chưa phản hồi trong lần quét này.")
    sections = [
        render_table(report["rankings"][occasion], anchor, title)
        for occasion, (anchor, title) in OCCASION_LABELS.items()
    ]
    page = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        last_checked=checked_at.strftime("%H:%M %d/%m/%Y"),
        iso_timestamp=checked_at.isoformat(),
        sections="\n".join(sections),
        scope=f'<p class="scope">{escape(" ".join(scope))}</p>' if scope else "",
        directory=escape(report["directory"], quote=True),
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(page, encoding="utf-8")
    shutil.copyfile(STYLESHEET, output / "style.css")
    print(f"Built {output} with " + ", ".join(
        f"{name}={rank['total']}" for name, rank in report["rankings"].items()
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true", help="Render the bundled public snapshot")
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    if args.snapshot:
        report = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    else:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        tables, blocked, new_sources, directories_checked = crawl(config)
        checked_at = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
        report = site_rankings(config, tables, checked_at, blocked, new_sources, directories_checked)
    render_site(report, args.output)


if __name__ == "__main__":
    main()
