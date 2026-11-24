"""Build a static GitHub Pages site from a live crawl or a reviewed snapshot."""

import argparse
import json
import re
import shutil
from datetime import datetime
from hashlib import sha256
from html import escape
from pathlib import Path
from string import Template
from unicodedata import normalize
from zoneinfo import ZoneInfo

from crawl import crawl
from rankings import site_rankings

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site" / "index.html"
STYLESHEET = ROOT / "site" / "style.css"
SCRIPT = ROOT / "site" / "rankings.js"
CONFIG = ROOT / "data" / "sources.json"
SNAPSHOT = ROOT / "data" / "snapshot.json"
PAGE_SIZE = 30

OCCASION_LABELS = {
    "lunar": ("nguyen-dan", "Tết Nguyên đán"),
    "solar": ("duong-lich", "Tết Dương lịch"),
}


def format_number(amount):
    if amount is None:
        return "—"
    text = f"{amount:,.6f}".rstrip("0").rstrip(".")
    return text.translate(str.maketrans(",.", ".,"))


def public_company_name(name):
    name = re.sub(r"\bMST\s*:?\s*\d{10}(?:-\d{3})?\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b0\d{9}\b", "", name)
    name = re.sub(r"\(\s*\)", "", name)
    return name.strip(" -–—") or "Doanh nghiệp"


def render_table(ranking, anchor, title):
    table_rows = []
    for row in ranking["rows"]:
        source = "—"
        if row.get("source"):
            source = f'<a href="{escape(row["source"], quote=True)}">{escape(row["source_label"])}</a>'
        published = escape(row.get("published_on") or "Chưa rõ")
        status = " <small>(kỳ trước, chưa xác minh lại)</small>" if row.get("prior") else ""
        table_rows.append(
            f'<tr data-high="{row["high"]}"><td class="rank">{row["rank"]:02d}</td>'
            f'<th scope="row"><span class="company-name">{escape(public_company_name(row["name"]))}</span>{status}</th>'
            f'<td class="company-place">{escape(row["place"])}</td>'
            f'<td class="high">{format_number(row["high"])}</td>'
            f'<td class="amount">{format_number(row["mean"])}</td>'
            f'<td class="amount">{format_number(row["low"])}</td>'
            f'<td>{source}</td><td>{published}</td></tr>'
        )
    first_page = "\n".join(table_rows[:PAGE_SIZE])
    remaining_rows = "\n".join(table_rows[PAGE_SIZE:])
    return f"""
<section class="ranking" id="{anchor}" aria-labelledby="title-{anchor}" data-page-size="{PAGE_SIZE}">
  <div class="section-heading">
    <h2 id="title-{anchor}">{title}</h2>
    <p>{format_number(ranking["total"])} doanh nghiệp đủ điều kiện xếp hạng</p>
  </div>
  <p class="filter-count" role="status" hidden></p>
  <div class="table-wrap" tabindex="0" role="region" aria-label="Bảng thưởng {title}">
    <table>
      <thead><tr>
        <th scope="col">Hạng</th><th scope="col">Doanh nghiệp</th>
        <th scope="col">Phường/xã báo cáo</th><th scope="col">Cao nhất</th>
        <th scope="col">Bình quân</th><th scope="col">Thấp nhất</th>
        <th scope="col">Nguồn</th><th scope="col">Ngày công bố</th>
      </tr></thead>
      <tbody>{first_page}</tbody>
    </table>
  </div>
  <template class="remaining-rows"><table><tbody>{remaining_rows}</tbody></table></template>
  <nav class="pagination" aria-label="Phân trang {title}" hidden>
    <button type="button" class="previous-page">Trang trước</button>
    <label>Trang <select class="page-number"></select></label>
    <button type="button" class="next-page">Trang sau</button>
  </nav>
</section>
"""


def render_site(report, output):
    if any(not ranking["rows"] or ranking["total"] != len(ranking["rows"]) for ranking in report["rankings"].values()):
        raise RuntimeError("Missing ranking rows, publication stopped")
    timestamp = datetime.fromisoformat(report["checked_at"])
    checked_at = timestamp.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    scope = []
    if report.get("coverage_note"):
        scope.append(report["coverage_note"])
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
        style_version=sha256(STYLESHEET.read_bytes()).hexdigest()[:12],
        script_version=sha256(SCRIPT.read_bytes()).hexdigest()[:12],
        scope=f'<p class="scope">{escape(" ".join(scope))}</p>' if scope else "",
        directory=escape(report["directory"], quote=True),
        directory_hub=escape(report.get("directory_hub") or report["directory"], quote=True),
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(normalize("NFC", page), encoding="utf-8")
    shutil.copyfile(STYLESHEET, output / "style.css")
    shutil.copyfile(SCRIPT, output / "rankings.js")
    shutil.copytree(TEMPLATE.parent / "fonts", output / "fonts", dirs_exist_ok=True)
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
