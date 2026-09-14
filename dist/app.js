const DATA_URL = "./data/report-data.json";

const state = {
  days: [],
  scope: "day",
  period: "",
  personalRows: [],
};

const byId = (id) => document.getElementById(id);
const formatNumber = (value, digits = 0) => Number(value || 0).toFixed(digits);
const scoreClass = (value) => value > 0 ? "positive" : value < 0 ? "negative" : "";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));

function dateParts(dateString) {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day, 12, 0, 0);
}

function weekKey(dateString) {
  const date = dateParts(dateString);
  const day = date.getDay() || 7;
  date.setDate(date.getDate() - day + 1);
  const start = new Date(date);
  const end = new Date(date);
  end.setDate(end.getDate() + 6);
  const iso = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  return `${iso(start)}~${iso(end)}`;
}

function monthKey(dateString) {
  return dateString.slice(0, 7);
}

function compareRows(a, b, metric = "score") {
  return (b[metric] - a[metric]) || (b.plus - a.plus) || (a.failure - b.failure) || (a.qc - b.qc) || String(a.name).localeCompare(String(b.name), "zh-CN");
}

function availablePeriods(scope) {
  const values = state.days.map((item) => scope === "day" ? item.date : scope === "week" ? weekKey(item.date) : monthKey(item.date));
  return [...new Set(values)].sort().reverse();
}

function periodLabel(scope, period) {
  if (!period) return "暂无数据";
  if (scope === "day") {
    const [year, month, day] = period.split("-");
    return `${year}年${Number(month)}月${Number(day)}日`;
  }
  if (scope === "week") {
    const [start, end] = period.split("~");
    return `${start.replaceAll("-", ".")} — ${end.replaceAll("-", ".")}`;
  }
  const [year, month] = period.split("-");
  return `${year}年${Number(month)}月`;
}

function matchingDays() {
  return state.days.filter((item) => {
    if (state.scope === "day") return item.date === state.period;
    if (state.scope === "week") return weekKey(item.date) === state.period;
    return monthKey(item.date) === state.period;
  });
}

function aggregateReport(days) {
  const people = new Map();
  for (const day of days) {
    for (const row of day.personal || []) {
      if (!people.has(row.name)) {
        people.set(row.name, {
          name: row.name,
          bigGroup: row.bigGroup || "待确认班组",
          smallGroup: row.smallGroup || "待确认小组",
          matched: row.matched !== false && row.bigGroup !== "待确认班组",
          plus: 0,
          failure: 0,
          qc: 0,
          score: 0,
        });
      }
      const target = people.get(row.name);
      target.bigGroup = row.bigGroup || target.bigGroup;
      target.smallGroup = row.smallGroup || target.smallGroup;
      target.matched = row.matched !== false && target.bigGroup !== "待确认班组";
      target.plus += Number(row.plus || 0);
      target.failure += Number(row.failure || 0);
      target.qc += Number(row.qc || 0);
      target.score += Number(row.score ?? (row.plus || 0) - (row.failure || 0) - (row.qc || 0));
    }
  }

  const personal = [...people.values()].sort(compareRows).map((row, index) => ({ ...row, rank: index + 1 }));
  const matched = personal.filter((row) => row.matched);

  const aggregateGroup = (field) => {
    const groups = new Map();
    for (const row of matched) {
      const name = row[field];
      if (!groups.has(name)) {
        groups.set(name, { name, bigGroup: row.bigGroup, members: new Set(), plus: 0, failure: 0, qc: 0, score: 0 });
      }
      const target = groups.get(name);
      target.members.add(row.name);
      target.plus += row.plus;
      target.failure += row.failure;
      target.qc += row.qc;
      target.score += row.score;
    }
    return [...groups.values()]
      .map((row) => ({ ...row, headcount: row.members.size, average: row.members.size ? row.score / row.members.size : 0 }))
      .sort((a, b) => compareRows(a, b, "average"))
      .map((row, index) => ({ ...row, rank: index + 1 }));
  };

  return {
    personal,
    smallGroups: aggregateGroup("smallGroup"),
    bigGroups: aggregateGroup("bigGroup"),
    plus: personal.reduce((sum, row) => sum + row.plus, 0),
    failure: personal.reduce((sum, row) => sum + row.failure, 0),
    qc: personal.reduce((sum, row) => sum + row.qc, 0),
    total: personal.reduce((sum, row) => sum + row.score, 0),
    unmatched: personal.filter((row) => !row.matched),
  };
}

function renderRankList(elementId, rows, kind, bottom = false) {
  const element = byId(elementId);
  const selected = bottom ? [...rows].slice(-3).reverse() : rows.slice(0, 3);
  element.innerHTML = selected.map((row, index) => {
    const name = kind === "personal" ? row.name : row.name;
    const context = kind === "personal" ? `${row.bigGroup} · ${row.smallGroup}` : kind === "small" ? `${row.bigGroup} · ${row.headcount}人` : `${row.headcount}人`;
    const metric = kind === "personal" ? row.score : row.average;
    return `<li>
      <span class="rank-number">${row.rank}</span>
      <span class="rank-name">${escapeHtml(name)}</span>
      <span class="rank-context">${escapeHtml(context)}</span>
      <span class="rank-score ${scoreClass(metric)}">${formatNumber(metric, kind === "personal" ? 0 : 2)}</span>
    </li>`;
  }).join("");
}

function rowClass(index, length) {
  if (index < 3) return "rank-top";
  if (index >= length - 3) return "rank-bottom";
  return "";
}

function renderPersonalTable(rows, query = "") {
  const normalized = query.trim().toLocaleLowerCase("zh-CN");
  const filtered = normalized ? rows.filter((row) => `${row.name} ${row.bigGroup} ${row.smallGroup}`.toLocaleLowerCase("zh-CN").includes(normalized)) : rows;
  byId("personal-table").innerHTML = filtered.map((row) => {
    const originalIndex = rows.indexOf(row);
    return `<tr class="${rowClass(originalIndex, rows.length)}">
      <td>${row.rank}</td><td><strong>${escapeHtml(row.name)}</strong></td>
      <td>${row.matched ? escapeHtml(row.bigGroup) : '<span class="pending-label">待确认</span>'}</td>
      <td>${row.matched ? escapeHtml(row.smallGroup) : '<span class="pending-label">待确认</span>'}</td>
      <td class="numeric">${row.plus}</td><td class="numeric">${row.failure}</td><td class="numeric">${row.qc}</td>
      <td class="numeric"><span class="score-pill ${scoreClass(row.score)}">${row.score}</span></td>
    </tr>`;
  }).join("");
}

function renderGroupTable(elementId, rows, kind) {
  byId(elementId).innerHTML = rows.map((row, index) => `<tr class="${rowClass(index, rows.length)}">
    <td>${row.rank}</td>
    ${kind === "small" ? `<td>${escapeHtml(row.bigGroup)}</td><td><strong>${escapeHtml(row.name)}</strong></td>` : `<td><strong>${escapeHtml(row.name)}</strong></td>`}
    <td class="numeric">${row.headcount}</td><td class="numeric">${row.plus}</td><td class="numeric">${row.failure}</td><td class="numeric">${row.qc}</td>
    <td class="numeric">${row.score}</td><td class="numeric"><span class="score-pill ${scoreClass(row.average)}">${formatNumber(row.average, 2)}</span></td>
  </tr>`).join("");
}

function refreshPeriodPicker() {
  const picker = byId("period-picker");
  const periods = availablePeriods(state.scope);
  if (!periods.includes(state.period)) state.period = periods[0] || "";
  picker.innerHTML = periods.map((period) => `<option value="${escapeHtml(period)}" ${period === state.period ? "selected" : ""}>${escapeHtml(periodLabel(state.scope, period))}</option>`).join("");
  picker.disabled = periods.length === 0;
}

function render() {
  refreshPeriodPicker();
  const days = matchingDays();
  const hasData = days.length > 0;
  document.querySelectorAll(".rank-section, .kpi-grid, .report-heading").forEach((element) => { element.hidden = !hasData; });
  byId("empty-state").hidden = hasData;
  if (!hasData) return;

  const report = aggregateReport(days);
  state.personalRows = report.personal;
  const labels = { day: "降档低签挽留日报", week: "降档低签挽留周报", month: "降档低签挽留月报" };
  byId("scope-label").textContent = labels[state.scope];
  byId("report-title").textContent = `${periodLabel(state.scope, state.period)}考核排名通报`;
  byId("kpi-plus").textContent = report.plus;
  byId("kpi-failure").textContent = report.failure;
  byId("kpi-qc").textContent = report.qc;
  byId("kpi-total").textContent = report.total;
  byId("kpi-days").textContent = `统计天数 ${days.length}`;
  byId("image-button").disabled = state.scope !== "day";
  byId("image-button").title = state.scope === "day" ? "下载当前日期的PNG日报" : "日报图片仅按日生成";

  renderRankList("personal-top", report.personal, "personal");
  renderRankList("personal-bottom", report.personal, "personal", true);
  renderRankList("small-top", report.smallGroups, "small");
  renderRankList("small-bottom", report.smallGroups, "small", true);
  renderRankList("big-top", report.bigGroups, "big");
  renderRankList("big-bottom", report.bigGroups, "big", true);
  renderPersonalTable(report.personal, byId("person-search").value);
  renderGroupTable("small-table", report.smallGroups, "small");
  renderGroupTable("big-table", report.bigGroups, "big");

  byId("unmatched-panel").hidden = report.unmatched.length === 0;
  byId("unmatched-count").textContent = `${report.unmatched.length}人`;
  byId("unmatched-names").textContent = report.unmatched.map((row) => row.name).join("、");
}

function exportCsv() {
  if (!state.personalRows.length) return;
  const rows = [["位次", "姓名", "大组", "小组", "成功", "失败", "质检", "积分"], ...state.personalRows.map((row) => [row.rank, row.name, row.bigGroup, row.smallGroup, row.plus, row.failure, row.qc, row.score])];
  const csv = `\uFEFF${rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\r\n")}`;
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.period.replace("~", "_")}-${state.scope}-ranking.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function downloadDailyImage() {
  if (state.scope !== "day" || !state.period) return;
  const anchor = document.createElement("a");
  anchor.href = `./images/reports/${state.period}.png`;
  anchor.download = `${state.period}_降档低签挽留日报.png`;
  anchor.click();
}

async function loadData() {
  try {
    const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error("data unavailable");
    const payload = await response.json();
    state.days = Array.isArray(payload.days) ? payload.days.sort((a, b) => a.date.localeCompare(b.date)) : [];
    byId("data-status").innerHTML = "<i></i>已更新";
    byId("updated-at").textContent = payload.updatedAt ? `更新时间 ${payload.updatedAt}` : "";
  } catch {
    state.days = [];
    byId("data-status").innerHTML = "<i></i>暂无数据";
    byId("updated-at").textContent = "";
  }
  render();
}

document.querySelectorAll(".scope-tab").forEach((button) => button.addEventListener("click", () => {
  state.scope = button.dataset.scope;
  state.period = "";
  document.querySelectorAll(".scope-tab").forEach((item) => {
    const active = item === button;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-selected", String(active));
  });
  render();
}));

byId("period-picker").addEventListener("change", (event) => { state.period = event.target.value; render(); });
byId("person-search").addEventListener("input", (event) => renderPersonalTable(state.personalRows, event.target.value));
byId("print-button").addEventListener("click", () => window.print());
byId("export-button").addEventListener("click", exportCsv);
byId("image-button").addEventListener("click", downloadDailyImage);

loadData();
