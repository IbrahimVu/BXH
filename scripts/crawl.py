"""Fetch the public report exports and verify their reviewed column layouts."""

import hashlib
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zipfile import BadZipFile

import openpyxl

from rankings import normalized

SHEET_URL = re.compile(r"^/(spreadsheets|document)/(?:u/\d+/)?d/([A-Za-z0-9_-]+)(?:/|$)")
REPORT_HOST = "thuvienphapluat.vn"
GOOGLE_HOST = "docs.google.com"
MAX_DOWNLOAD = 24 * 1024 * 1024
HEADER_MARKERS = ("doanhnghiep", "donvi", "caonhat", "thapnhat", "binhquan", "luong", "thuong", "msthue", "masothue")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.urls.append(href)


def source_key(url):
    parsed = urlsplit(url)
    if parsed.scheme == "https" and parsed.hostname == GOOGLE_HOST:
        matches = SHEET_URL.match(parsed.path)
        if matches:
            return matches.groups()
    return None


def public_directory_links(url, body):
    links = Links()
    links.feed(body.decode("utf-8", errors="replace"))
    return {key for href in links.urls if (key := source_key(urljoin(url, href)))}


def download(url, expected_host):
    if urlsplit(url).hostname != expected_host:
        raise ValueError(f"unexpected host: {urlsplit(url).hostname}")
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "HaNoiTet2027Pages/1.0"})
            with urlopen(request, timeout=24) as response:
                host = urlsplit(response.url).hostname or ""
                downloads = expected_host == GOOGLE_HOST and host.endswith(".googleusercontent.com")
                if expected_host == GOOGLE_HOST and host == "accounts.google.com":
                    raise HTTPError(url, 403, "sign-in required", response.headers, None)
                if host != expected_host and not downloads:
                    raise ValueError(f"unexpected download host: {host}")
                body = response.read(MAX_DOWNLOAD + 1)
                if len(body) > MAX_DOWNLOAD:
                    raise ValueError("download too large")
                return body
        except HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def document_rows(body):
    lines = body.decode("utf-8-sig").splitlines()
    entries = []
    for index, line in enumerate(lines):
        match = re.search(r"(?:công ty|chi nhánh)\b.*", line, re.IGNORECASE)
        if match:
            name = re.split(r"\s{3,}|\t|\b(?:Mức|Tiền lương|Lương bình)", match[0])[0].strip()
            entries.append((index, name))

    rows = []
    for index, (line, name) in enumerate(entries):
        end = entries[index + 1][0] if index + 1 < len(entries) else len(lines)
        lunar = [None] * 3
        solar = [None] * 3
        for text in lines[line:end]:
            if "thưởng" not in text.lower():
                continue
            if re.search(r"tết\s+âm|nguyên đán", text, re.IGNORECASE):
                values = lunar
            elif re.search(r"dương lịch", text, re.IGNORECASE):
                values = solar
            else:
                continue
            for slot, label in enumerate(("bình quân", "cao nhất", "thấp nh[aâấ][t́]*")):
                match = re.search(rf"{label}\s*:?\s*([\d.,]+)", text, re.IGNORECASE)
                if match:
                    amount = match[1].rstrip(".,")
                    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+|\d+", amount):
                        values[slot] = int(re.sub(r"[.,]", "", amount))
        rows.append([name, *lunar, *solar, line + 1])
    return rows


def header_digest(rows, first_row):
    markers = []
    for row_number, row in enumerate(rows[: first_row - 1], 1):
        for column, value in enumerate(row):
            if not isinstance(value, str):
                continue
            label = normalized(value)
            if any(marker in label for marker in HEADER_MARKERS):
                markers.append((row_number, column, label))
    if not markers:
        raise ValueError("reviewed header cells are missing")
    return hashlib.sha256(json.dumps(markers).encode("utf-8")).hexdigest()


def read_export(body, kind, layouts, industry_layouts=()):
    if kind == "document":
        if body.lstrip().startswith(b"<"):
            raise ValueError("Google Docs export returned HTML")
        rows = document_rows(body)
        if not rows:
            raise ValueError("no company rows in Google Docs export")
        return {layouts[0]["tab"]: rows}

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    except BadZipFile as exc:
        raise ValueError("Google Sheets export is not an XLSX workbook") from exc
    try:
        tables = {}
        for layout in layouts:
            tab = layout["tab"]
            if tab not in workbook.sheetnames:
                raise ValueError(f"reviewed tab missing: {tab}")
            rows = list(workbook[tab].values)
            if header_digest(rows, layout["first_row"]) != layout["header_sha256"]:
                raise ValueError(f"report layout changed: {tab}")
            tables[tab] = rows
        for layout in industry_layouts:
            tab = layout["tab"]
            if tab not in workbook.sheetnames:
                continue
            rows = list(workbook[tab].values)
            try:
                digest = header_digest(rows, layout["first_row"])
            except ValueError:
                digest = None
            if digest == layout["header_sha256"]:
                tables[tab] = rows
            else:
                print(f"Industry reference layout changed: {tab}")
        return tables
    finally:
        workbook.close()


def crawl(config):
    linked = set()
    directories_checked = 0
    directories = dict.fromkeys(config["directory"])
    if hub := config.get("directory_hub"):
        try:
            links = Links()
            links.feed(download(hub, REPORT_HOST).decode("utf-8", errors="replace"))
            for href in links.urls:
                candidate = urlsplit(urljoin(hub, href))
                if (
                    candidate.scheme == "https" and candidate.netloc == REPORT_HOST
                    and "ha-noi" in candidate.path and "thuong-tet-2027" in candidate.path
                    and candidate.path.endswith(".html")
                ):
                    directories.setdefault(candidate._replace(query="", fragment="").geturl())
        except (URLError, TimeoutError, ValueError) as exc:
            print(f"Main directory unavailable: {type(exc).__name__}")
    for url in directories:
        try:
            entries = public_directory_links(url, download(url, REPORT_HOST))
            if entries:
                linked.update(entries)
                directories_checked += 1
            else:
                print("Directory returned no report links")
        except (URLError, TimeoutError, ValueError) as exc:
            print(f"Directory unavailable: {type(exc).__name__}")

    known = {source_key(source["url"]) for source in config["sources"]}
    new_sources = sorted(linked - known)
    for kind, identifier in new_sources:
        print(f"Review new report layout: https://docs.google.com/{kind}/d/{identifier}")

    layouts_by_source = {}
    for layout in config["layouts"]:
        layouts_by_source.setdefault(layout["source"], []).append(layout)
    industry_by_source = {}
    for layout in config.get("industry_layouts", ()):
        industry_by_source.setdefault(layout["source"], []).append(layout)

    def fetch_source(source):
        source_id = source["id"]
        kind, identifier = source_key(source["url"])
        export_format = "xlsx" if kind == "spreadsheets" else "txt"
        url = f"https://{GOOGLE_HOST}/{kind}/d/{identifier}/export?format={export_format}"
        try:
            body = download(url, GOOGLE_HOST)
            tables = read_export(body, kind, layouts_by_source[source_id], industry_by_source.get(source_id, ()))
        except HTTPError as exc:
            if exc.code in (401, 403, 404, 410):
                return source_id, {}, source["place"]
            raise RuntimeError(f"{source['place']}: Google export returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"{source['place']}: {exc}") from exc
        return source_id, tables, None

    sources = [source for source in config["sources"] if source["id"] in layouts_by_source]
    with ThreadPoolExecutor(max_workers=5) as pool:
        outcomes = list(pool.map(fetch_source, sources))
    tables = {identifier: tabs for identifier, tabs, unavailable in outcomes if unavailable is None}
    blocked = [unavailable for _, _, unavailable in outcomes if unavailable is not None]
    newly_blocked = {
        source["place"] for source in sources if source["id"] not in tables and not source.get("known_access_issue")
    }
    if newly_blocked:
        raise RuntimeError(f"Previously available sources failed: {', '.join(sorted(newly_blocked))}")
    if not tables:
        raise RuntimeError("No reports were read")
    return tables, blocked, new_sources, directories_checked
