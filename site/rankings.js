const tabList = document.querySelector(".occasion-tabs");
const tabs = Array.from(tabList.querySelectorAll("a"));
const form = document.querySelector(".filters");
const company = form.elements.namedItem("company");
const minimum = form.elements.namedItem("minimum");
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
const panels = tabs.map((tab) => {
  const panel = document.getElementById(tab.hash.slice(1));
  const body = panel.querySelector("tbody");
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
    return { element, name: searchText(element.querySelector(".company-name").textContent), places, industry: industryKey, high: Number(element.dataset.high) };
  });
  return {
    panel,
    rows,
    places: [...labels].sort((a, b) => a[1].localeCompare(b[1], "vi")),
    industries: [...industries].sort((a, b) => a[1].localeCompare(b[1], "vi")),
    count: panel.querySelector(".filter-count"),
    table: panel.querySelector(".table-wrap"),
    body,
    pageSize: Number(panel.dataset.pageSize),
    pagination: panel.querySelector(".pagination"),
    previous: panel.querySelector(".previous-page"),
    next: panel.querySelector(".next-page"),
    pageNumber: panel.querySelector(".page-number"),
    matches: [],
  };
});

let activeIndex;
function searchableFilter(id, normalize, allLabel, filterWhileTyping = false) {
  const input = document.getElementById(id);
  const menu = input.parentElement.querySelector(".filter-menu");
  const options = menu.querySelector('[role="listbox"]');
  const empty = menu.querySelector(".filter-empty");
  let choices = [];
  let selection = ["", ""];
  let highlighted = -1;

  function close() {
    menu.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    if (!filterWhileTyping) input.value = selection[1];
  }

  function highlight(index, scroll = true) {
    options.children[highlighted]?.setAttribute("aria-selected", "false");
    highlighted = index;
    const option = options.children[index];
    if (!option) {
      input.removeAttribute("aria-activedescendant");
      return;
    }
    option.setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", option.id);
    if (scroll) option.scrollIntoView({ block: "nearest" });
  }

  function open(value = "") {
    const query = normalize(value);
    const matches = choices.filter(([key]) => key.includes(query));
    if (!query) matches.unshift(["", allLabel]);
    options.replaceChildren(...matches.map(([key, label], index) => {
      const option = document.createElement("li");
      option.id = `${options.id}-${index}`;
      option.dataset.key = key;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", "false");
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
    selection = [option.dataset.key, option.dataset.key ? option.textContent : ""];
    input.value = selection[1];
    close();
    filterRows();
  }

  function edit() {
    open(input.value);
    if (filterWhileTyping) filterRows();
  }

  function openAll() {
    input.select();
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
      if (menu.hidden) open();
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
    get value() { return filterWhileTyping ? normalize(input.value) : selection[0]; },
    setChoices(values) {
      choices = values;
      selection = choices.find(([key]) => key === selection[0]) ?? ["", ""];
      close();
    },
    reset() {
      selection = ["", ""];
      input.value = "";
      close();
    },
  };
}

const place = searchableFilter("place-search", placeKey, "Tất cả địa bàn");
const industry = searchableFilter("industry-search", searchText, "Tất cả ngành/lĩnh vực", true);

function showPage(state, page) {
  const { body, count, table, matches, pageSize, pagination, previous, next, pageNumber } = state;
  const pages = Math.ceil(matches.length / pageSize);
  const start = (page - 1) * pageSize;
  const visible = matches.slice(start, start + pageSize);
  body.replaceChildren(...visible.map((row) => row.element));
  table.scrollTop = 0;
  count.textContent = visible.length
    ? `Hiển thị ${countFormat.format(start + 1)}–${countFormat.format(start + visible.length)} trong ${countFormat.format(matches.length)} kết quả.`
    : "Không tìm thấy doanh nghiệp phù hợp.";
  count.hidden = false;
  table.hidden = visible.length === 0;
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
  const industryQuery = industry.value;
  const input = minimum.value.trim();
  const valid = input === "" || /^\d+(?:[.,]\d+)?$/.test(input);
  const threshold = valid ? Number(input.replace(",", ".")) : 0;
  minimumError.hidden = valid;
  minimum.setAttribute("aria-invalid", String(!valid));

  state.matches = state.rows.filter((row) => row.name.includes(query)
    && (place.value === "" || row.places.includes(place.value))
    && row.industry.includes(industryQuery)
    && row.high >= threshold);
  showPage(state, 1);
}

function activate(index, updateUrl = false) {
  activeIndex = index;
  tabs.forEach((tab, position) => {
    const selected = position === index;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    panels[position].panel.hidden = !selected;
  });

  place.setChoices(panels[index].places);
  industry.setChoices(panels[index].industries);
  filterRows();

  const hash = tabs[index].hash;
  if (updateUrl && location.hash !== hash) history.pushState(null, "", hash);
}

function activateFromHash() {
  const index = tabs.findIndex((tab) => tab.hash === location.hash);
  activate(index === -1 ? 0 : index);
}

tabList.setAttribute("role", "tablist");
tabs.forEach((tab, index) => {
  const state = panels[index];
  const { panel, previous, next, pageNumber } = state;
  tab.id = `tab-${panel.id}`;
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-controls", panel.id);
  panel.setAttribute("role", "tabpanel");
  panel.setAttribute("aria-labelledby", tab.id);
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
  previous.addEventListener("click", () => showPage(state, Number(pageNumber.value) - 1));
  next.addEventListener("click", () => showPage(state, Number(pageNumber.value) + 1));
  pageNumber.addEventListener("change", () => showPage(state, Number(pageNumber.value)));
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
window.addEventListener("hashchange", activateFromHash);
activateFromHash();
form.hidden = false;
document.body.classList.add("results-ready");
