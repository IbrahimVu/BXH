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
ARCHIVE = ROOT / "data" / "archive.json"
CURRENT_YEAR = "2027"
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


def source_link(url, label):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def render_summary(rows):
    if not rows:
        return ""
    body = "\n".join(
        f'<tr><th scope="row">{escape(row["group"])}</th>'
        f'<td class="high">{format_number(row["high"])}</td>'
        f'<td class="amount">{format_number(row["mean"])}</td>'
        f'<td class="amount">{format_number(row["low"])}</td>'
        f'<td>{source_link(row["source"], row["source_label"])}</td>'
        f'<td>{escape(row["published_on"])}</td></tr>'
        for row in sorted(rows, key=lambda row: row["high"] if row["high"] is not None else -1, reverse=True)
    )
    return f"""
    <div class="archive-summary">
      <h3 class="archive-heading">Số liệu tổng hợp theo loại hình doanh nghiệp</h3>
      <p class="archive-note">Số liệu kế hoạch trong báo cáo tổng hợp cấp thành phố. Nguồn không nêu tên doanh nghiệp ứng với mức cao nhất, thấp nhất.</p>
      <table aria-label="Thống kê thưởng theo loại hình doanh nghiệp">
        <thead><tr>
          <th scope="col">Loại hình doanh nghiệp</th><th scope="col">Cao nhất</th>
          <th scope="col">Bình quân</th><th scope="col">Thấp nhất</th>
          <th scope="col">Nguồn</th><th scope="col">Ngày báo đăng</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
    </div>"""


def render_table(ranking, anchor, title, year, summary):
    current = year == CURRENT_YEAR
    if not current:
        anchor = f"{anchor}-{year}"
    table_rows = []
    references = ranking.get("references", [])
    for row in [*ranking["rows"], *references]:
        source = "—"
        if row.get("source"):
            source = source_link(row["source"], row["source_label"])
        published = escape(row.get("published_on") or "Chưa rõ")
        status = " <small>(kỳ trước, chưa xác minh lại)</small>" if row.get("prior") else ""
        if row.get("status"):
            status = f' <small>({escape(row["status"])})</small>'
        high = row["high"]
        rank = f'{row["rank"]:02d}' if row.get("rank") else "—"
        industry_note = row.get("industry_reference")
        industry_title = f' title="{escape(industry_note, quote=True)}"' if industry_note else ""
        industry = row.get("industry") or "Chưa rõ"
        industry_text = escape(industry)
        if len(industry) > 24:
            industry_text = (
                '<details class="industry-detail"><summary>'
                f'<span>{industry_text}</span></summary></details>'
            )
        table_rows.append(
            f'<tr data-high="{high if high is not None else ""}"><td class="rank">{rank}</td>'
            f'<th scope="row"><span class="company-name">{escape(public_company_name(row["name"]))}</span>{status}</th>'
            f'<td class="high">{format_number(row["high"])}</td>'
            f'<td class="company-place">{escape(row["place"])}</td>'
            f'<td class="company-industry"{industry_title}>{industry_text}</td>'
            f'<td class="amount">{format_number(row["mean"])}</td>'
            f'<td class="amount">{format_number(row["low"])}</td>'
            f'<td>{source}</td><td>{published}</td></tr>'
        )
    first_page = "\n".join(table_rows[:PAGE_SIZE])
    remaining_rows = "\n".join(table_rows[PAGE_SIZE:])
    hidden = "" if current else " hidden"
    count = format_number(ranking["total"])
    coverage = f"{count} doanh nghiệp xếp hạng theo kê khai" if current else f"{count} doanh nghiệp xếp hạng"
    if references:
        coverage += f" · {format_number(len(references))} doanh nghiệp chỉ có số liệu tham khảo"
    date_label = "Ngày công bố" if current else "Ngày nguồn đăng"
    place_label = "Phường/xã báo cáo" if current else "Địa bàn"
    return f"""
<section class="ranking" id="{anchor}" aria-labelledby="title-{anchor}" data-page-size="{PAGE_SIZE}" data-year="{year}"{hidden}>
  <div class="section-heading">
    <h2 id="title-{anchor}">{title} {year}</h2>
    <p class="ranking-total">{coverage}</p>
    <p class="filter-count" role="status" hidden></p>
    <span class="ranking-unit">Triệu đồng/người</span>
  </div>
  <div class="table-wrap" tabindex="0" role="region" aria-label="Bảng thưởng {title}">
    <table class="company-results">
      <thead><tr>
        <th scope="col">Hạng</th><th scope="col">Doanh nghiệp</th>
        <th scope="col">Cao nhất</th>
        <th scope="col">{place_label}</th><th scope="col">Ngành/lĩnh vực</th>
        <th scope="col">Bình quân</th><th scope="col">Thấp nhất</th>
        <th scope="col">Nguồn</th><th scope="col">{date_label}</th>
      </tr></thead>
      <tbody>{first_page}</tbody>
    </table>
    {render_summary(summary)}
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
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    years = {CURRENT_YEAR: report, **archive}
    sections = []
    for year, data in years.items():
        for occasion, (anchor, title) in OCCASION_LABELS.items():
            ranking = data["rankings"][occasion]
            if ranking["total"] != len(ranking["rows"]):
                raise ValueError(f"Invalid {year} {occasion} ranking count")
            sections.append(render_table(ranking, anchor, title, year, data.get("summary", {}).get(occasion, [])))
    sources = [
        f'<div data-summary-year="{CURRENT_YEAR}">'
        f'<p class="scope">{escape(" ".join(scope))}</p>'
        f'<p>{source_link(report["directory"], "Danh mục báo cáo của các phường, xã")} · '
        f'{source_link(report.get("directory_hub") or report["directory"], "Danh mục báo cáo theo tỉnh, thành")}</p></div>'
    ]
    timestamps = [
        f'<p class="timestamp" data-summary-year="{CURRENT_YEAR}">Dữ liệu lúc '
        f'<time datetime="{checked_at.isoformat()}">{checked_at:%H:%M %d/%m/%Y}</time> (giờ Việt Nam)</p>'
    ]
    for year, data in archive.items():
        links = " · ".join(source_link(source["url"], source["label"]) for source in data["sources"])
        sources.append(f'<div hidden data-summary-year="{year}"><p>{escape(data["coverage_note"])}</p><p>{links}</p></div>')
        timestamps.append(f'<p class="timestamp" hidden data-summary-year="{year}">Dữ liệu lưu trữ từ nguồn công khai</p>')
    page = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        default_year=CURRENT_YEAR,
        timestamps="\n".join(timestamps),
        year_options="".join(f'<option value="{year}">{year}</option>' for year in years),
        sections="\n".join(sections),
        style_version=sha256(STYLESHEET.read_bytes()).hexdigest()[:12],
        script_version=sha256(SCRIPT.read_bytes()).hexdigest()[:12],
        sources="\n".join(sources),
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
