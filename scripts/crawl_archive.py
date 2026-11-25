"""Refresh the reviewed historical bonus reports without changing the live crawl."""

import argparse
import gzip
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from crawl import download

ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "archive.json"
REPORTS = {
    "2026": {
        "url": "https://baochinhphu.vn/ha-noi-thuong-tet-nguyen-dan-2026-co-noi-cao-nhat-hon-600-trieu-dong-102260105101332906.htm",
        "label": "Báo Chính phủ · Dẫn báo cáo Sở Nội vụ Hà Nội",
        "date": "05/01/2026",
        "count": "3.182",
    },
    "2025": {
        "url": "https://vneconomy.vn/thuong-tet-2025-tai-ha-noi-tang-cao-nhat-311-trieu-dong.htm",
        "label": "VnEconomy · Dẫn báo cáo Sở Lao động – Thương binh và Xã hội Hà Nội",
        "date": "30/12/2024",
        "count": "4.420",
    },
}
GROUPS = {
    "Công ty TNHH một thành viên do Nhà nước nắm giữ 100% vốn điều lệ": "100% vốn nhà nước",
    "Công ty cổ phần có vốn góp chi phối của Nhà nước": "Cổ phần có vốn nhà nước chi phối",
    "khối doanh nghiệp dân doanh": "Dân doanh",
    "khối doanh nghiệp FDI": "Có vốn đầu tư nước ngoài (FDI)",
}
OCCASIONS = {"lunar": r"tết (?:nguyên đán|âm lịch)", "solar": r"tết dương lịch"}
AMOUNT = r"(\d+(?:\.\d{3})*(?:,\d+)?)\s*(triệu |nghìn )?đồng/người(?!/)"
SONG_NHUE = {
    "url": "https://hhtip.hanoi.gov.vn/vi/tin-tuc/giu-nhip-san-xuat-dau-xuan-bao-dam-viec-lam-va-tang-truong-2697.html",
    "label": "Ban Quản lý các Khu công nghệ cao và khu công nghiệp Hà Nội",
}
DOCUMENTS = {
    "2025": {
        "url": "https://thuvienphapluat.vn/phap-luat/ho-tro-phap-luat/mau-bao-cao-ke-hoach-thuong-tet-2025-theo-huong-dan-tai-cong-van-952ldld-ha-noi-tai-mau-bao-cao-ke--185787.html",
        "label": "Công văn 952/LĐLĐ và biểu mẫu kê khai",
    },
    "2026": {
        "url": "https://thuvienphapluat.vn/lao-dong-tien-luong/tong-hop-link-nop-mail-nop-bao-cao-tinh-hinh-su-dung-lao-dong-6-thang-cuoi-nam-2025-day-du-chi-tiet-51736.html",
        "label": "Danh mục nộp báo cáo lao động cuối năm 2025",
    },
}


class ArticleText(HTMLParser):
    """Read paragraph and body text across the reviewed publication sites."""

    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self.chunks = []
        self.in_paragraph = False
        self.ignored = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored = True
        elif tag == "p":
            self.in_paragraph = True
            self.paragraphs.append([])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignored = False
        elif tag == "p":
            self.in_paragraph = False

    def handle_data(self, value):
        if not self.ignored:
            self.chunks.append(value)
            if self.in_paragraph:
                self.paragraphs[-1].append(value)


def read_article(url):
    body = download(url, urlsplit(url).hostname)
    if body.startswith(b"\x1f\x8b"):
        body = gzip.decompress(body)
    article = ArticleText()
    article.feed(body.decode("utf-8-sig"))
    return article


def millions(number, unit):
    scale = {"triệu ": 1, "nghìn ": 1000, "": 1000000}
    return float(number.replace(".", "").replace(",", ".")) / scale[unit or ""]


def summary_for(year):
    source = REPORTS[year]
    article = read_article(source["url"])
    result = {occasion: [] for occasion in OCCASIONS}
    group = None
    for paragraph in article.paragraphs:
        line = " ".join(" ".join(paragraph).split()).lower()
        if not line.startswith(("đối với ", "trong đó,", "cũng trong ", "trong dịp ", "mức thưởng trong dịp ")):
            continue
        for marker, label in GROUPS.items():
            if marker.lower() in line:
                group = label
                break
        if line.startswith("trong đó, mức thưởng tết nguyên đán ất tỵ 2025") and "fdi" in line:
            group = GROUPS["khối doanh nghiệp FDI"]
        if group is None:
            continue
        for occasion, holiday in OCCASIONS.items():
            if not re.search(holiday, line):
                continue
            metrics = {
                key: re.search(pattern + AMOUNT, line)
                for key, pattern in {
                    "mean": r"bình quân(?: trong dịp tết dương lịch)?(?: là| đạt)?\s*:?\s*",
                    "high": r"cao nhất(?: là| đạt| thuộc về doanh nghiệp fdi với)?\s*:?\s*",
                    "low": r"thấp nhất(?: là| đạt)?\s*:?\s*",
                }.items()
            }
            if not all(metrics.values()):
                continue
            result[occasion].append({
                "group": group,
                **{key: millions(*match.groups()) for key, match in metrics.items()},
                "source": source["url"],
                "source_label": source["label"],
                "published_on": source["date"],
            })
    for occasion, rows in result.items():
        if len(rows) != len(GROUPS) or {row["group"] for row in rows} != set(GROUPS.values()):
            raise ValueError(f"Incomplete summary at {source['url']} for {occasion}")
        if any(not 0 <= row["low"] <= row["mean"] <= row["high"] for row in rows):
            raise ValueError(f"Invalid bonus range at {source['url']} for {occasion}")
    return result


def song_nhue():
    article = read_article(SONG_NHUE["url"])
    content = " ".join(" ".join(article.chunks).split())
    name = "Công ty TNHH MTV Đầu tư phát triển Thủy lợi Sông Nhuệ"
    match = re.search(re.escape(name) + r"[^.]{0,240}chi thưởng cho người lao động với mức " + AMOUNT, content)
    if not match or "Bính Ngọ 2026" not in content:
        raise ValueError(f"Missing verified bonus at {SONG_NHUE['url']}")
    return {
        "rank": 1,
        "name": name,
        "place": "Chưa rõ",
        "industry": "Thủy lợi",
        "high": millions(*match.groups()),
        "mean": None,
        "low": None,
        "status": "Mức chi được cơ quan quản lý đưa tin",
        "source": SONG_NHUE["url"],
        "source_label": SONG_NHUE["label"],
        "published_on": "20/02/2026",
    }


def build_archive(reviewed):
    archive = {}
    for year, report in REPORTS.items():
        sources = [{"url": report["url"], "label": report["label"]}, DOCUMENTS[year]]
        if year == "2026":
            sources.append(SONG_NHUE)
        rankings = {}
        for occasion in OCCASIONS:
            rows = [song_nhue()] if (year, occasion) == ("2026", "lunar") else []
            references = reviewed.get(year, {}).get("rankings", {}).get(occasion, {}).get("references", [])
            rankings[occasion] = {"total": len(rows), "rows": rows, "references": references}
            sources.extend({"url": row["source"], "label": row["source_label"]} for row in references)
        archive[year] = {
            "coverage_note": (
                f"Báo cáo nhanh cấp thành phố tổng hợp {report['count']} doanh nghiệp. "
                "Bảng xếp hạng chỉ bao gồm các doanh nghiệp có tên và mức cao nhất xác định được từ nguồn công khai. "
                "Số liệu chỉ có bình quân được hiển thị với hạng để trống."
            ),
            "sources": sources,
            "rankings": rankings,
            "summary": summary_for(year),
        }
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ARCHIVE)
    args = parser.parse_args()
    reviewed = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else {}
    archive = build_archive(reviewed)
    args.output.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for year, entry in archive.items():
        print(f"{year}: {sum(map(len, entry['summary'].values()))} rows by company type")


if __name__ == "__main__":
    main()
