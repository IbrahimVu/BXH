const tabList = document.querySelector(".occasion-tabs");
const tabs = Array.from(tabList.querySelectorAll("a"));
const form = document.querySelector(".filters");
const company = form.elements.namedItem("company");
const minimum = form.elements.namedItem("minimum");
const year = form.elements.namedItem("year");
const headingYear = document.getElementById("heading-year");
const defaultYear = year.value;
const minimumError = document.querySelector("#minimum-error");

function searchText(value) {
  return value.toLocaleLowerCase("vi").normalize("NFD")
    .replace(/\p{M}/gu, "").replace(/đ/g, "d").trim();
}

function placeKey(value) {
  const key = searchText(value).replace(/[^a-z0-9]/g, "");
  return key.replace(/(?:thanhpho|tp)?hanoi$/, "") || key;
}

const countFormat = new Intl.NumberFormat("vi-VN");
const panelsByYear = new Map(Array.from(year.options, ({ value }) => [value, []]));
for (const panel of document.querySelectorAll(".ranking[data-year]")) {
  const body = panel.querySelector(".company-results tbody");
  const remaining = panel.querySelector(".remaining-rows");
  const labels = new Map();
  const industries = new Map();
  const rows = [...body.rows, ...remaining.content.querySelectorAll("tr")].map((element) => {
    const names = element.querySelector(".company-place").textContent.split(/\s+\/\s+/);
    const places = [];
    for (const name of names) {
      const key = placeKey(name);
      if (!key) continue;
      places.push(key);
      const label = name.trim().replace(/^\p{Ll}/u, (letter) => letter.toLocaleUpperCase("vi"));
      if (!labels.has(key) || label.length < labels.get(key).length) labels.set(key, label);
    }
    const industryLabel = element.querySelector(".company-industry").textContent;
    const industryKey = searchText(industryLabel);
    if (!industries.has(industryKey)) industries.set(industryKey, industryLabel);
    const high = element.dataset.high === "" ? null : Number(element.dataset.high);
    return { element, name: searchText(element.querySelector(".company-name").textContent), places, industry: industryKey, high };
  });
  panelsByYear.get(panel.dataset.year).push({
    panel,
    rows,
    places: [...labels].sort((a, b) => a[1].localeCompare(b[1], "vi")),
    industries: [...industries].sort((a, b) => a[1].localeCompare(b[1], "vi")),
    count: panel.querySelector(".filter-count"),
    table: panel.querySelector(".table-wrap"),
    results: panel.querySelector(".company-results"),
    hasSummary: Boolean(panel.querySelector(".archive-summary")),
    body,
    pageSize: Number(panel.dataset.pageSize),
    pagination: panel.querySelector(".pagination"),
    previous: panel.querySelector(".previous-page"),
    next: panel.querySelector(".next-page"),
    pageNumber: panel.querySelector(".page-number"),
    matches: [],
  });
}

let panels = panelsByYear.get(defaultYear);
let activeIndex;
function searchableFilter(id, normalize, allLabel) {
  const input = document.getElementById(id);
  const menu = input.parentElement.querySelector(".filter-menu");
  const options = menu.querySelector('[role="listbox"]');
  const empty = menu.querySelector(".filter-empty");
  let choices = [];
  let labels = new Map();
  const selected = new Set();
  let highlighted = -1;

  function close() {
    menu.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    const selectedLabels = [...selected].map((key) => labels.get(key));
    input.value = selectedLabels.length > 1 ? `Đã chọn ${selectedLabels.length} mục` : selectedLabels[0] ?? "";
    input.title = selectedLabels.join(", ");
  }

  function highlight(index, scroll = true) {
    options.children[highlighted]?.removeAttribute("data-active");
    highlighted = index;
    const option = options.children[index];
    if (!option) {
      input.removeAttribute("aria-activedescendant");
      return;
    }
    option.setAttribute("data-active", "");
    input.setAttribute("aria-activedescendant", option.id);
    if (scroll) option.scrollIntoView({ block: "nearest" });
  }

  function open(value = "") {
    const query = normalize(value);
    const matches = choices.filter(([key]) => key.includes(query));
    if (!query) {
      matches.sort(([a], [b]) => Number(selected.has(b)) - Number(selected.has(a)));
      matches.unshift(["", allLabel]);
    }
    options.replaceChildren(...matches.map(([key, label], index) => {
      const option = document.createElement("li");
      option.id = `${options.id}-${index}`;
      option.dataset.key = key;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(key ? selected.has(key) : selected.size === 0));
      option.textContent = label;
      return option;
    }));
    empty.hidden = matches.length > 0;
    menu.hidden = false;
    menu.scrollTop = 0;
    input.setAttribute("aria-expanded", "true");
    highlighted = -1;
    highlight(query && matches.length ? 0 : -1, false);
  }

  function choose(option) {
    const key = option.dataset.key;
    if (!key) selected.clear();
    else if (selected.has(key)) selected.delete(key);
    else selected.add(key);

    for (const item of options.children) {
      const itemKey = item.dataset.key;
      item.setAttribute("aria-selected", String(itemKey ? selected.has(itemKey) : selected.size === 0));
    }
    input.select();
    filterRows();
  }

  function edit() {
    open(input.value);
  }

  function openAll() {
    input.value = "";
    open();
  }

  input.addEventListener("focus", openAll);
  input.addEventListener("click", () => {
    if (menu.hidden) openAll();
  });
  input.addEventListener("input", (event) => {
    if (!event.isComposing) edit();
  });
  input.addEventListener("compositionend", edit);
  input.addEventListener("blur", close);
  input.addEventListener("keydown", (event) => {
    if (event.isComposing) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (menu.hidden) openAll();
      const count = options.children.length;
      if (!count) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      const index = highlighted < 0 ? (step > 0 ? 0 : count - 1) : highlighted + step;
      highlight(Math.max(0, Math.min(count - 1, index)));
    } else if (event.key === "Enter" && !menu.hidden) {
      event.preventDefault();
      const option = options.children[highlighted];
      if (option) choose(option);
    } else if (event.key === "Escape" && !menu.hidden) {
      event.preventDefault();
      close();
    }
  });
  options.addEventListener("pointerdown", (event) => {
    if (event.target.closest('[role="option"]')) event.preventDefault();
  });
  options.addEventListener("click", (event) => {
    const option = event.target.closest('[role="option"]');
    if (option) choose(option);
  });

  return {
    selected,
    setChoices(next) {
      choices = next;
      labels = new Map(choices);
      for (const key of selected) {
        if (!labels.has(key)) selected.delete(key);
      }
      close();
    },
    reset() {
      selected.clear();
      close();
    },
  };
}

function allChoices(field) {
  return [...new Map(panels.flatMap((panel) => panel[field]))]
    .sort((a, b) => a[1].localeCompare(b[1], "vi"));
}

const place = searchableFilter("place-search", placeKey, "Tất cả địa bàn");
const industry = searchableFilter("industry-search", searchText, "Tất cả ngành/lĩnh vực");

function showPage(state, page) {
  const { body, count, table, results, hasSummary, rows, matches, pageSize, pagination, previous, next, pageNumber } = state;
  const pages = Math.ceil(matches.length / pageSize);
  const start = (page - 1) * pageSize;
  const visible = matches.slice(start, start + pageSize);
  body.replaceChildren(...visible.map((row) => row.element));
  table.scrollTop = 0;
  count.textContent = visible.length
    ? `Hiển thị ${countFormat.format(start + 1)}–${countFormat.format(start + visible.length)} trong ${countFormat.format(matches.length)} kết quả.`
    : rows.length ? "Không tìm thấy doanh nghiệp phù hợp."
      : "Chưa có dữ liệu công khai đủ điều kiện xếp hạng doanh nghiệp cho dịp này.";
  count.hidden = false;
  results.hidden = visible.length === 0;
  table.hidden = visible.length === 0 && !hasSummary;
  pagination.hidden = pages <= 1;
  if (pageNumber.options.length !== pages) {
    pageNumber.replaceChildren(...Array.from({ length: pages }, (_, index) =>
      new Option(`${index + 1} / ${pages}`, index + 1)));
  }
  pageNumber.value = String(page);
  previous.disabled = page <= 1;
  next.disabled = page >= pages;
}

function filterRows() {
  const state = panels[activeIndex];
  const query = searchText(company.value);
  const places = place.selected;
  const industries = industry.selected;
  const input = minimum.value.trim();
  const valid = input === "" || /^\d+(?:[.,]\d+)?$/.test(input);
  const threshold = valid ? Number(input.replace(",", ".")) : 0;
  minimumError.hidden = valid;
  minimum.setAttribute("aria-invalid", String(!valid));

  state.matches = state.rows.filter((row) => row.name.includes(query)
    && (!places.size || row.places.some((key) => places.has(key)))
    && (!industries.size || industries.has(row.industry))
    && (!valid || input === "" || (row.high !== null && row.high >= threshold)));
  showPage(state, 1);
}

function activate(index, updateUrl = false) {
  activeIndex = index;
  tabs.forEach((tab, position) => {
    const selected = position === index;
    tab.setAttribute("aria-selected", String(selected));
    tab.setAttribute("aria-controls", panels[position].panel.id);
    tab.tabIndex = selected ? 0 : -1;
    panels[position].panel.hidden = !selected;
  });

  filterRows();

  if (updateUrl) {
    const url = new URL(location.href);
    url.hash = tabs[index].hash;
    if (year.value === defaultYear) url.searchParams.delete("year");
    else url.searchParams.set("year", year.value);
    if (url.href !== location.href) history.pushState(null, "", url);
  }
}

function updateYear(value) {
  year.value = value;
  headingYear.textContent = value;
  document.title = `Bảng xếp hạng thưởng Tết ${value} tại Hà Nội`;
  panels = panelsByYear.get(value);
  for (const state of [...panelsByYear.values()].flat()) state.panel.hidden = true;
  for (const item of document.querySelectorAll("[data-summary-year]")) {
    item.hidden = item.dataset.summaryYear !== value;
  }
  place.setChoices(allChoices("places"));
  industry.setChoices(allChoices("industries"));
}

function activateFromUrl() {
  const value = new URLSearchParams(location.search).get("year");
  updateYear(panelsByYear.has(value) ? value : defaultYear);
  const index = tabs.findIndex((tab) => tab.hash === location.hash);
  activate(index === -1 ? 0 : index);
}

tabList.setAttribute("role", "tablist");
tabs.forEach((tab, index) => {
  tab.id = `tab-${tab.hash.slice(1)}`;
  tab.setAttribute("role", "tab");
  tab.addEventListener("click", (event) => {
    event.preventDefault();
    activate(index, true);
  });
  tab.addEventListener("keydown", (event) => {
    let next;
    switch (event.key) {
      case "ArrowRight": next = (index + 1) % tabs.length; break;
      case "ArrowLeft": next = (index + tabs.length - 1) % tabs.length; break;
      case "Home": next = 0; break;
      case "End": next = tabs.length - 1; break;
      case " ": next = index; break;
      default: return;
    }
    event.preventDefault();
    activate(next, true);
    tabs[next].focus();
  });
  for (const states of panelsByYear.values()) {
    const state = states[index];
    const { panel, previous, next, pageNumber } = state;
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", tab.id);
    previous.addEventListener("click", () => showPage(state, Number(pageNumber.value) - 1));
    next.addEventListener("click", () => showPage(state, Number(pageNumber.value) + 1));
    pageNumber.addEventListener("change", () => showPage(state, Number(pageNumber.value)));
  }
});

company.addEventListener("input", filterRows);
minimum.addEventListener("input", filterRows);
form.addEventListener("submit", (event) => event.preventDefault());
form.addEventListener("reset", (event) => {
  event.preventDefault();
  company.value = "";
  industry.reset();
  place.reset();
  minimum.value = "";
  filterRows();
});
year.addEventListener("change", () => {
  updateYear(year.value);
  activate(activeIndex, true);
});
window.addEventListener("popstate", activateFromUrl);
window.addEventListener("hashchange", activateFromUrl);
activateFromUrl();
form.hidden = false;
document.body.classList.add("results-ready");
