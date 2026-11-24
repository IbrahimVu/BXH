const tabList = document.querySelector(".occasion-tabs");
const tabs = Array.from(tabList.querySelectorAll("a"));
const form = document.querySelector(".filters");
const company = form.elements.namedItem("company");
const industry = form.elements.namedItem("industry");
const industrySuggestions = document.querySelector("#industry-suggestions");
const place = document.querySelector("#place-search");
const placeMenu = document.querySelector(".place-menu");
const placeOptions = document.querySelector("#place-options");
const placeEmpty = document.querySelector(".place-empty");
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
    industries: [...industries.values()].sort((a, b) => a.localeCompare(b, "vi")),
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
let selectedPlace = "";
let selectedPlaceLabel = "";
let highlightedPlace = -1;

function closePlaceMenu() {
  placeMenu.hidden = true;
  place.setAttribute("aria-expanded", "false");
  place.removeAttribute("aria-activedescendant");
  place.value = selectedPlaceLabel;
}

function highlightPlace(index, scroll = true) {
  placeOptions.children[highlightedPlace]?.setAttribute("aria-selected", "false");
  highlightedPlace = index;
  const option = placeOptions.children[index];
  if (!option) {
    place.removeAttribute("aria-activedescendant");
    return;
  }
  option.setAttribute("aria-selected", "true");
  place.setAttribute("aria-activedescendant", option.id);
  if (scroll) option.scrollIntoView({ block: "nearest" });
}

function searchPlaces(value = "") {
  const query = placeKey(value);
  const choices = panels[activeIndex].places.filter(([key]) => key.includes(query));
  if (!query) choices.unshift(["", "Tất cả địa bàn"]);
  placeOptions.replaceChildren(...choices.map(([key, label], index) => {
    const option = document.createElement("li");
    option.id = `place-option-${index}`;
    option.dataset.key = key;
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    option.textContent = label;
    return option;
  }));
  placeEmpty.hidden = choices.length > 0;
  placeMenu.hidden = false;
  placeMenu.scrollTop = 0;
  place.setAttribute("aria-expanded", "true");
  highlightedPlace = -1;
  highlightPlace(query && choices.length ? 0 : -1, false);
}

function choosePlace(option) {
  selectedPlace = option.dataset.key;
  selectedPlaceLabel = selectedPlace ? option.textContent : "";
  closePlaceMenu();
  filterRows();
}

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
  const industryQuery = searchText(industry.value);
  const input = minimum.value.trim();
  const valid = input === "" || /^\d+(?:[.,]\d+)?$/.test(input);
  const threshold = valid ? Number(input.replace(",", ".")) : 0;
  minimumError.hidden = valid;
  minimum.setAttribute("aria-invalid", String(!valid));

  state.matches = state.rows.filter((row) => row.name.includes(query)
    && (selectedPlace === "" || row.places.includes(selectedPlace))
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

  const selection = panels[index].places.find(([key]) => key === selectedPlace);
  [selectedPlace, selectedPlaceLabel] = selection ?? ["", ""];
  industrySuggestions.replaceChildren(...panels[index].industries.map((label) => new Option(label, label)));
  closePlaceMenu();
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

place.addEventListener("focus", () => {
  place.select();
  searchPlaces();
});
place.addEventListener("click", () => {
  if (placeMenu.hidden) {
    place.select();
    searchPlaces();
  }
});
place.addEventListener("input", (event) => {
  if (!event.isComposing) searchPlaces(place.value);
});
place.addEventListener("compositionend", () => searchPlaces(place.value));
place.addEventListener("blur", closePlaceMenu);
place.addEventListener("keydown", (event) => {
  if (event.isComposing) return;
  const { key } = event;
  if (key === "ArrowDown" || key === "ArrowUp") {
    event.preventDefault();
    if (placeMenu.hidden) searchPlaces();
    const count = placeOptions.children.length;
    if (!count) return;
    const index = highlightedPlace === -1
      ? (key === "ArrowDown" ? 0 : count - 1)
      : Math.min(count - 1, Math.max(0, highlightedPlace + (key === "ArrowDown" ? 1 : -1)));
    highlightPlace(index);
  } else if (key === "Enter" && !placeMenu.hidden) {
    event.preventDefault();
    const option = placeOptions.children[highlightedPlace];
    if (option) choosePlace(option);
  } else if (key === "Escape" && !placeMenu.hidden) {
    event.preventDefault();
    closePlaceMenu();
  }
});
placeOptions.addEventListener("pointerdown", (event) => {
  if (event.target.closest('[role="option"]')) event.preventDefault();
});
placeOptions.addEventListener("click", (event) => {
  const option = event.target.closest('[role="option"]');
  if (option) choosePlace(option);
});

company.addEventListener("input", filterRows);
industry.addEventListener("input", filterRows);
minimum.addEventListener("input", filterRows);
form.addEventListener("submit", (event) => event.preventDefault());
form.addEventListener("reset", (event) => {
  event.preventDefault();
  company.value = "";
  industry.value = "";
  selectedPlace = "";
  selectedPlaceLabel = "";
  closePlaceMenu();
  minimum.value = "";
  filterRows();
});
window.addEventListener("hashchange", activateFromHash);
activateFromHash();
form.hidden = false;
document.body.classList.add("results-ready");
