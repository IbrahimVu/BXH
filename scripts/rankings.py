"""Normalize amounts and rank companies using the reviewed Hanoi report layouts."""

import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation

OCCASIONS = ("lunar", "solar")
COMPANY_NAME = re.compile(
    r"công|cong|cty|ct |c\.ty|tnhh|hợp tác|htx|chi nhánh|văn phòng|viện|liên hiệp|trung tâm|tổng công|vpđd",
    re.IGNORECASE,
)
SAMPLE_NAMES = ("tnhhabc", "thuongmaixyz", "doanhnghiepmau")
GROUP_NAMES = {
    "hoptacxadichvutonghop",
    "congtytnhhmtvdonnnamgiu100vondieule",
    "congtycocophanvongopchiphoicuanhanuoc",
    "doanhnghiepdan doanh",
}
SALARY_COLUMNS = {
    2: (5, 6, 7), 3: (7, 8, 9), 4: (8, 9, 10), 6: (9, 10, 11),
    7: (8, 9, 10), 10: (3, 4, 5), 11: (10, 11, 12), 14: (8, 9, 10),
    17: (10, 11, 12), 21: (4, 5, 6), 24: (5, 6, 7),
}


def normalized(value):
    value = unicodedata.normalize("NFKD", str(value).lower().replace("đ", "d"))
    return re.sub(r"[^a-z0-9]", "", value)


def cell(row, column):
    return row[column] if column is not None and column < len(row) else None


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def number(value):
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() else None
    text = str(value).strip().replace(" ", "")
    if not re.fullmatch(r"-?\d+[.,\d]*", text):
        return None
    if re.fullmatch(r"-?\d{1,3}([.,]\d{3}){2,}", text):
        text = text.replace(",", "").replace(".", "")
    elif ("," in text and "." in text) or re.fullmatch(r"-?\d{1,3}[.,]\d{3}", text):
        return None  # A text entry such as 1.000 can mean 1 or 1000.
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None


def pending(row, source_id, columns, occasion):
    no_bonus = as_text(cell(row, columns[f"no_{occasion}"]))
    if no_bonus.lower() in ("1", "x", "có") or "chuacodukien" in normalized(no_bonus):
        return True
    status = normalized(cell(row, columns[f"status_{occasion}"]))
    if "chua" in status or "khongthuong" in status or status == "khong":
        return True
    if source_id not in (0, 1, 11):
        return False
    note = normalized(cell(row, 26 if source_id == 11 else 7))
    solar = "duonglich" in note
    if source_id == 11:
        lunar = "amlich" in note
        applies = (not lunar and not solar) or (lunar if occasion == "lunar" else solar and not lunar)
        return applies and any(word in note for word in ("chuacoquyetdinh", "chuaxacdinh", "chuacokehoach"))
    lunar = any(word in note for word in ("nguyendan", "tetam", "amlich"))
    applies = (not lunar and not solar) or (lunar if occasion == "lunar" else solar)
    return applies and "chuaco" in note and "dukien" in note


def amounts(row, layout, occasion):
    source_id = layout["source"]
    columns = layout["columns"]
    unit = 1 if source_id == 15 and occasion == "solar" else layout["unit"]
    raw = [cell(row, column) for column in columns[occasion]]
    values = [number(value) for value in raw]
    present = [value for value in values if value is not None]
    salary = [number(cell(row, col)) for col in SALARY_COLUMNS.get(source_id, ())]
    mean, high, low = values
    valid = (
        unit is not None
        and not (source_id in (9, 15) and occasion == "lunar")
        and not pending(row, source_id, columns, occasion)
        and high is not None and high > 0
        and all(original is None or value is not None for original, value in zip(raw, values))
        and not any(value < 0 for value in present)
        and not (mean is not None and (mean > high or (low is not None and mean < low)))
        and not (low is not None and low > high)
    )
    if unit == 1_000_000:
        valid &= (
            not any(abs(value) > 1000 for value in present)
            and not (low is not None and low >= 100)
            and not (
                any(value is not None and value > 10000 for value in salary)
                and any(value >= 100 for value in present)
            )
        )
    if unit == 1000:
        valid &= not any(abs(value) >= 100000 for value in present)
    if unit == 1:
        valid &= not any(0 < value < 1000 for value in present)

    multipliers = [unit or 1] * 3
    if source_id == 15 and occasion == "lunar":
        multipliers = [1, 1_000_000, 1]
    amounts_vnd = tuple(
        value * multiplier if value is not None else None
        for value, multiplier in zip(values, multipliers)
    )
    return amounts_vnd, valid


def company_records(config, tables):
    places = {source["id"]: source["place"] for source in config["sources"]}
    primary_keys = set()
    records = []
    for layout in config["layouts"]:
        source = layout["source"]
        tab = layout["tab"]
        columns = layout["columns"]
        rows = tables.get(source, {}).get(tab, ())
        first_row = layout["first_row"]
        for row_number, row in enumerate(rows[first_row - 1 :], first_row):
            name = cell(row, columns["name"])
            if not isinstance(name, str) or not COMPANY_NAME.search(name):
                continue
            name = " ".join(name.split())
            normalized_name = normalized(name)
            if (
                len(name) < 5 or name.lower().startswith(("tên", "chỉ tiêu"))
                or (columns["name"] == 1 and re.fullmatch(r"[IVX]+", as_text(cell(row, 0))))
                or any(sample in normalized_name for sample in SAMPLE_NAMES)
                or normalized_name in GROUP_NAMES
                or re.fullmatch(r"công ty[.\s]+", name, re.IGNORECASE)
            ):
                continue
            tax = re.sub(r"[.\s]", "", as_text(cell(row, columns["tax"])))
            address = normalized(as_text(cell(row, columns["address"])))
            if re.fullmatch(r"\d{10}(?:-?\d{3})?", tax):
                key = f"mst:{tax.replace('-', '')}"
            else:
                key = f"name:{normalized_name}|{address}"

            if layout.get("supplemental") and (source, key) in primary_keys:
                continue
            if not layout.get("supplemental"):
                primary_keys.add((source, key))
            records.append({
                "key": key, "identity": (normalized_name, address), "name": name,
                "place": places[source], "source": source, "tab": tab,
                "row": int(cell(row, 7)) if source == 5 else row_number,
                "amounts": {occasion: amounts(row, layout, occasion) for occasion in OCCASIONS},
                "generic": normalized_name in ("congty", "congtytnhh", "congtyco"),
            })
    return records


def group_records(records):
    tax_by_identity = defaultdict(set)
    for record in records:
        if record["identity"][1] and record["key"].startswith("mst:"):
            tax_by_identity[record["identity"]].add(record["key"])
    grouped = defaultdict(list)
    for record in records:
        key = record["key"]
        if key.startswith("name:") and record["identity"][1]:
            matches = tax_by_identity[record["identity"]]
            if len(matches) == 1:
                key = next(iter(matches))
        grouped[key].append(record)
    return grouped


def site_rankings(config, tables, checked_at, blocked=(), new_sources=(), directories_checked=None):
    grouped = group_records(company_records(config, tables))
    source_urls = {source["id"]: source["url"] for source in config["sources"]}
    rankings = {}
    for occasion in OCCASIONS:
        ranked = []
        for observations in grouped.values():
            first = observations[0]
            values, eligible = first["amounts"][occasion]
            if not eligible or first["generic"]:
                continue
            if any(record["amounts"][occasion][0] != values for record in observations[1:]):
                continue
            ranked.append((values[1], normalized(first["name"]), first, values))
        ranked.sort(key=lambda record: (-record[0], record[1]))
        ranked_rows = []
        previous = None
        rank = 0
        for position, (highest, _, record, values) in enumerate(ranked, 1):
            if highest != previous:
                rank = position
            mean, high, low = (float(amount / 1_000_000) if amount is not None else None for amount in values)
            ranked_rows.append(dict(
                rank=rank, name=record["name"], place=record["place"], high=high, mean=mean, low=low,
                source=source_urls[record["source"]], source_label=f'{record["tab"]}, dòng {record["row"]}',
            ))
            previous = highest
        rankings[occasion] = {"total": len(ranked_rows), "rows": ranked_rows}
    return {
        "checked_at": checked_at,
        "rankings": rankings,
        "blocked": list(blocked),
        "new_sources": len(new_sources),
        "directories_checked": directories_checked,
        "directory": config["directory"][0],
        "directory_hub": config.get("directory_hub"),
    }
