const DATA_URL = "./data/report-data.json";
const PK_DATA_URL = "./data/pk-data.json";

const state = {
  days: [],
  retentionUpdatedAt: "",
  pk: null,
  mode: "retention",
  scope: "day",
  period: "",
  personalRows: [],
};

const byId = (id) => document.getElementById(id);
const formatNumber = (value, digits = 0) => Number(value || 0).toFixed(digits);
const scoreClass = (value) => value > 0 ? "positive" : value < 0 ? "negative" : "";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));

const RETENTION_KPI_HTML = `
  <article class="kpi-card positive"><span>挽留成功加分</span><strong id="kpi-plus">—</strong><small>累计次数</small></article>
  <article class="kpi-card negative"><span>挽留失败扣分</span><strong id="kpi-failure">—</strong><small>累计次数</small></article>
  <article class="kpi-card warning"><span>质检考核扣分</span><strong id="kpi-qc">—</strong><small>累计次数</small></article>
  <article class="kpi-card total"><span>合计积分</span><strong id="kpi-total">—</strong><small id="kpi-days">统计天数 —</small></article>`;

const PK_KPI_HTML = `
  <article class="kpi-card positive"><span>累计总加分</span><strong id="pk-kpi-plus">—</strong><small>累计积分</small></article>
  <article class="kpi-card warning"><span>参赛人数</span><strong id="pk-kpi-people">—</strong><small>人</small></article>
  <article class="kpi-card negative"><span>加分项目</span><strong id="pk-kpi-projects">—</strong><small>个</small></article>
  <article class="kpi-card total"><span>最高个人积分</span><strong id="pk-kpi-top">—</strong><small id="pk-kpi-days">赛季累计</small></article>`;

const RETENTION_METHOD_HTML = `<span>计分口径</span><strong>挽留成功 +1</strong><strong>挽留失败 −1</strong><strong>质检考核 −1</strong>`;
const PK_METHOD_HTML = `<span>计分口径</span><strong>只加分不扣分</strong><strong>不同项目分值不同</strong>`;

const RETENTION_THEADS = {
  personal: `<tr><th>位次</th><th>姓名</th><th>大组</th><th>小组</th><th>成功</th><th>失败</th><th>质检</th><th>积分</th></tr>`,
  small: `<tr><th>位次</th><th>大组</th><th>小组</th><th>人数</th><th>成功</th><th>失败</th><th>质检</th><th>总分</th><th>人均分</th></tr>`,
  big: `<tr><th>位次</th><th>大组</th><th>人数</th><th>成功</th><th>失败</th><th>质检</th><th>总分</th><th>人均分</th></tr>`,
};

const PK_THEADS = {
  personal: `<tr><th>位次</th><th>姓名</th><th>大组</th><th>小组</th><th>总积分</th></tr>`,
  small: `<tr><th>位次</th><th>大组</th><th>小组</th><th>人数</th><th>总积分</th><th>人均积分</th></tr>`,
  big: `<tr><th>位次</th><th>大组</th><th>人数</th><th>总积分</th><th>人均积分</th></tr>`,
};

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

function aggregatePkGroups(rows, field) {
  const matched = rows.filter((row) => row.matched && row.bigGroup !== "待确认班组");
  const groups = new Map();
  for (const row of matched) {
    const name = row[field];
    if (!groups.has(name)) {
      groups.set(name, { name, bigGroup: row.bigGroup, members: new Set(), score: 0 });
    }
    const target = groups.get(name);
    target.members.add(row.name);
    target.score += Number(row.score || 0);
  }
  return [...groups.values()]
    .map((row) => ({ ...row, headcount: row.members.size, average: row.members.size ? row.score / row.members.size : 0 }))
    .sort((a, b) => compareRows(a, b, "average"))
    .map((row, index) => ({ ...row, rank: index + 1 }));
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

function renderPkPersonalTable(rows, query = "") {
  const normalized = query.trim().toLocaleLowerCase("zh-CN");
  const filtered = normalized ? rows.filter((row) => `${row.name} ${row.bigGroup} ${row.smallGroup}`.toLocaleLowerCase("zh-CN").includes(normalized)) : rows;
  byId("personal-table").innerHTML = filtered.map((row) => {
    const originalIndex = rows.indexOf(row);
    return `<tr class="${rowClass(originalIndex, rows.length)}">
      <td>${row.rank}</td><td><strong>${escapeHtml(row.name)}</strong></td>
      <td>${row.matched ? escapeHtml(row.bigGroup) : '<span class="pending-label">待确认</span>'}</td>
      <td>${row.matched ? escapeHtml(row.smallGroup) : '<span class="pending-label">待确认</span>'}</td>
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

function renderPkGroupTable(elementId, rows, kind) {
  byId(elementId).innerHTML = rows.map((row, index) => `<tr class="${rowClass(index, rows.length)}">
    <td>${row.rank}</td>
    ${kind === "small" ? `<td>${escapeHtml(row.bigGroup)}</td><td><strong>${escapeHtml(row.name)}</strong></td>` : `<td><strong>${escapeHtml(row.name)}</strong></td>`}
    <td class="numeric">${row.headcount}</td><td class="numeric">${row.score}</td>
    <td class="numeric"><span class="score-pill ${scoreClass(row.average)}">${formatNumber(row.average, 2)}</span></td>
  </tr>`).join("");
}

function refreshPeriodPicker() {
  const picker = byId("period-picker");
  const periods = availablePeriods(state.scope);
  if (!periods.includes(state.period)) state.period = periods[0] || "";
  picker.innerHTML = periods.map((period) => `<option value="${escapeHtml(period)}" ${period === state.period ? "selected" : ""}>${escapeHtml(periodLabel(state.scope, period))}</option>`).join("");
  picker.disabled = periods.length === 0;
}

function renderRetention() {
  byId("scope-tabs").hidden = false;
  byId("period-select").hidden = false;
  byId("image-button").hidden = false;
  byId("pk-legend").hidden = true;
  byId("kpi-grid").innerHTML = RETENTION_KPI_HTML;
  byId("method-note").innerHTML = RETENTION_METHOD_HTML;
  byId("personal-thead").innerHTML = RETENTION_THEADS.personal;
  byId("small-thead").innerHTML = RETENTION_THEADS.small;
  byId("big-thead").innerHTML = RETENTION_THEADS.big;
  byId("personal-desc").textContent = "按个人累计积分排序";
  byId("small-desc").textContent = "小组累计积分 ÷ 名单人数";
  byId("big-desc").textContent = "大组累计积分 ÷ 名单人数";
  byId("data-status").innerHTML = state.days.length ? "<i></i>已更新" : "<i></i>暂无数据";
  byId("updated-at").textContent = state.retentionUpdatedAt ? `更新时间 ${state.retentionUpdatedAt}` : "";

  refreshPeriodPicker();
  const days = matchingDays();
  const hasData = days.length > 0;
  document.querySelectorAll(".rank-section, .kpi-grid, .report-heading").forEach((element) => { element.hidden = !hasData; });
  byId("empty-state").hidden = hasData;
  byId("unmatched-panel").hidden = true;
  if (!hasData) {
    byId("empty-state").innerHTML = "<strong>暂无可展示的报表数据</strong><p>请将当天数据文件加入数据目录并重新发布。</p>";
    return;
  }

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
  byId("image-button").disabled = !["day", "week"].includes(state.scope);
  byId("image-button").textContent = state.scope === "week" ? "下载周报图片" : "下载日报图片";
  byId("image-button").title = state.scope === "day" ? "下载当前日期的PNG日报" : state.scope === "week" ? "下载本周PNG周报" : "月报暂无图片";

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

function renderPk() {
  byId("scope-tabs").hidden = true;
  byId("period-select").hidden = true;
  byId("image-button").hidden = true;
  byId("kpi-grid").innerHTML = PK_KPI_HTML;
  byId("method-note").innerHTML = PK_METHOD_HTML;
  byId("personal-thead").innerHTML = PK_THEADS.personal;
  byId("small-thead").innerHTML = PK_THEADS.small;
  byId("big-thead").innerHTML = PK_THEADS.big;
  byId("personal-desc").textContent = "按赛季累计积分排序";
  byId("small-desc").textContent = "小组累计积分 ÷ 参赛人数";
  byId("big-desc").textContent = "大组累计积分 ÷ 参赛人数";

  const personal = (state.pk && Array.isArray(state.pk.personal) ? state.pk.personal : []).map((row, index) => ({ ...row, rank: index + 1 }));
  const hasData = personal.length > 0;
  document.querySelectorAll(".rank-section, .kpi-grid, .report-heading").forEach((element) => { element.hidden = !hasData; });
  byId("pk-legend").hidden = !hasData;
  byId("empty-state").hidden = hasData;
  byId("unmatched-panel").hidden = true;
  if (!hasData) {
    byId("data-status").innerHTML = "<i></i>暂无数据";
    byId("updated-at").textContent = "";
    byId("empty-state").innerHTML = "<strong>暂无营销PK赛数据</strong><p>请业务侧按「营销PK赛模板」填写后放入「待发布PK」文件夹，再运行更新脚本。</p>";
    return;
  }

  state.personalRows = personal;
  byId("data-status").innerHTML = "<i></i>已更新";
  byId("updated-at").textContent = state.pk.updatedAt ? `更新时间 ${state.pk.updatedAt}` : "";
  byId("scope-label").textContent = "营销PK赛";
  const pkDate = state.pk && state.pk.date ? state.pk.date : "";
  byId("report-title").textContent = pkDate ? `${pkDate}营销PK赛排名通报` : "营销PK赛排名通报";

  const total = personal.reduce((sum, row) => sum + Number(row.score || 0), 0);
  const activeProjects = new Set();
  personal.forEach((row) => Object.keys(row.detail || {}).forEach((project) => activeProjects.add(project)));
  byId("pk-kpi-plus").textContent = total;
  byId("pk-kpi-people").textContent = personal.length;
  byId("pk-kpi-projects").textContent = activeProjects.size;
  byId("pk-kpi-top").textContent = personal[0] ? personal[0].score : 0;

  const smallGroups = aggregatePkGroups(personal, "smallGroup");
  const bigGroups = aggregatePkGroups(personal, "bigGroup");

  renderRankList("personal-top", personal, "personal");
  renderRankList("personal-bottom", personal, "personal", true);
  renderRankList("small-top", smallGroups, "small");
  renderRankList("small-bottom", smallGroups, "small", true);
  renderRankList("big-top", bigGroups, "big");
  renderRankList("big-bottom", bigGroups, "big", true);
  renderPkPersonalTable(personal, byId("person-search").value);
  renderPkGroupTable("small-table", smallGroups, "small");
  renderPkGroupTable("big-table", bigGroups, "big");

  const unmatched = personal.filter((row) => !row.matched);
  byId("unmatched-panel").hidden = unmatched.length === 0;
  byId("unmatched-count").textContent = `${unmatched.length}人`;
  byId("unmatched-names").textContent = unmatched.map((row) => row.name).join("、");

  byId("pk-legend-grid").innerHTML = (state.pk.projectScores || []).map((project) => `<span class="legend-item"><strong>${escapeHtml(project.name)}</strong><em>+${Number(project.score)}分</em></span>`).join("");
}

function render() {
  if (state.mode === "pk") renderPk();
  else renderRetention();
}

function exportCsv() {
  if (!state.personalRows.length) return;
  const isPk = state.mode === "pk";
  const rows = [isPk
    ? ["位次", "姓名", "大组", "小组", "总积分"]
    : ["位次", "姓名", "大组", "小组", "成功", "失败", "质检", "积分"],
  ...state.personalRows.map((row) => isPk
    ? [row.rank, row.name, row.bigGroup, row.smallGroup, row.score]
    : [row.rank, row.name, row.bigGroup, row.smallGroup, row.plus, row.failure, row.qc, row.score])];
  const csv = `\uFEFF${rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\r\n")}`;
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = isPk ? "营销PK赛-赛季排名.csv" : `${state.period.replace("~", "_")}-${state.scope}-ranking.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function downloadImage() {
  if (!["day", "week"].includes(state.scope) || !state.period) return;
  const label = state.scope === "week" ? "周报" : "日报";
  const url = `./images/reports/${state.period}.png`;
  try {
    const response = await fetch(url, { method: "HEAD", cache: "no-store" });
    if (!response.ok) throw new Error("missing");
  } catch {
    alert(`该${label}图片尚未生成，暂时无法下载。`);
    return;
  }
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.period}_降档低签挽留${label}.png`;
  anchor.click();
}

async function loadData() {
  try {
    const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error("data unavailable");
    const payload = await response.json();
    state.days = Array.isArray(payload.days) ? payload.days.sort((a, b) => a.date.localeCompare(b.date)) : [];
    state.retentionUpdatedAt = payload.updatedAt || "";
  } catch {
    state.days = [];
    state.retentionUpdatedAt = "";
  }
  try {
    const response = await fetch(`${PK_DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error("pk data unavailable");
    state.pk = await response.json();
  } catch {
    state.pk = null;
  }
  render();
}

document.querySelectorAll(".mode-tab").forEach((button) => button.addEventListener("click", () => {
  state.mode = button.dataset.mode;
  document.querySelectorAll(".mode-tab").forEach((item) => {
    const active = item === button;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-selected", String(active));
  });
  render();
}));

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
byId("person-search").addEventListener("input", (event) => {
  const query = event.target.value;
  if (state.mode === "pk") renderPkPersonalTable(state.personalRows, query);
  else renderPersonalTable(state.personalRows, query);
});
byId("print-button").addEventListener("click", () => window.print());
byId("export-button").addEventListener("click", exportCsv);
byId("image-button").addEventListener("click", downloadImage);

loadData();
