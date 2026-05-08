const rowsEl = document.querySelector("#tournamentRows");
const declinedRowsEl = document.querySelector("#declinedRows");
const declinedCountEl = document.querySelector("#declinedCount");
const changesEl = document.querySelector("#changes");
const sourceFilter = document.querySelector("#sourceFilter");
const ageFilter = document.querySelector("#ageFilter");
const divisionMenuButton = document.querySelector("#divisionMenuButton");
const divisionOptions = document.querySelector("#divisionOptions");
const thresholdFilter = document.querySelector("#thresholdFilter");
const radiusFilter = document.querySelector("#radiusFilter");
const searchFilter = document.querySelector("#searchFilter");
const startDateFilter = document.querySelector("#startDateFilter");
const endDateFilter = document.querySelector("#endDateFilter");
const profileEl = document.querySelector("#profile");
const themeToggle = document.querySelector("#themeToggle");
const logoutBtn = document.querySelector("#logoutBtn");
const menuBtn = document.querySelector("#menuBtn");
const navMenu = document.querySelector("#navMenu");
const tableWrap = document.querySelector(".table-wrap");

let tournaments = [];
let sortKey = "target_team_count";
let sortDirection = -1;
const THEME_KEY = "staff_tool_theme";
let scrollHintRaf = null;

function updateTournamentTableScrollHint() {
  if (!tableWrap) return;
  const maxScrollLeft = tableWrap.scrollWidth - tableWrap.clientWidth;
  const canScrollRight = maxScrollLeft > 1 && tableWrap.scrollLeft < maxScrollLeft - 1;
  tableWrap.classList.toggle("can-scroll-right", canScrollRight);
}

function queueTournamentTableScrollHintUpdate() {
  if (scrollHintRaf !== null) return;
  scrollHintRaf = window.requestAnimationFrame(() => {
    scrollHintRaf = null;
    updateTournamentTableScrollHint();
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("Authentication required");
  }
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function sourceLabel(source) {
  return {
    ncs: "NCS",
    usssa: "USSSA",
    perfect_game: "Perfect Game",
  }[source] || source;
}

function formatDate(start, end) {
  if (!start) return "TBD";
  if (end && end !== start) return `${start} - ${end}`;
  return start;
}

function formatDistance(distance) {
  if (distance === null || distance === undefined) return "Unknown";
  return `${Math.round(distance)} mi`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderTeamRows(item) {
  const teams = item.selected_age_teams || [];
  if (!teams.length) {
    return renderDivisionBreakdown(item);
  }
  const divisions = item.selected_age_divisions || [];
  const orderedDivisions = divisions.length
    ? divisions.map((division) => division.division)
    : [...new Set(teams.map((team) => team.division || item.target_age_division))].sort();
  const teamsByDivision = teams.reduce((groups, team) => {
    const key = team.division || item.target_age_division;
    groups[key] = groups[key] || [];
    groups[key].push(team);
    return groups;
  }, {});
  return `
    <div class="team-list-title">
      ${escapeHtml(item.target_age_division)} teams (${teams.length} registered, ${item.selected_age_confirmed_count || 0} confirmed)
    </div>
    <div class="team-division-groups">
      ${orderedDivisions
        .filter((division) => (teamsByDivision[division] || []).length)
        .map((division) => `
          <section class="team-division-group">
            <h3>${escapeHtml(division)}</h3>
            <table class="team-list">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Team</th>
                  <th>Confirmed</th>
                  <th>City/State</th>
                  <th>W-L-T</th>
                  <th>Class</th>
                </tr>
              </thead>
              <tbody>
                ${teamsByDivision[division].map((team, index) => `
                  <tr>
                    <td>${escapeHtml(team.number || index + 1)}</td>
                    <td>${team.detail_url ? `<a href="${escapeHtml(team.detail_url)}" target="_blank" rel="noreferrer">${escapeHtml(team.team_name)}</a>` : escapeHtml(team.team_name)}</td>
                    <td>${team.confirmed ? '<span class="confirmed">Yes</span>' : '<span class="subtle">No</span>'}</td>
                    <td>${escapeHtml(team.city_state)}</td>
                    <td>${escapeHtml(team.record)}</td>
                    <td>${escapeHtml(team.team_class || "")}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </section>
        `).join("")}
    </div>
  `;
}

function renderDivisionBreakdown(item) {
  const divisions = item.selected_age_divisions || [];
  if (!divisions.length) {
    return '<div class="subtle">No team list captured for this age yet.</div>';
  }
  return `
    <div class="team-list-title">
      ${escapeHtml(item.target_age_division)} division breakdown
      <span class="subtle">Team names are not captured for this source yet.</span>
    </div>
    <div class="division-breakdown">
      ${divisions.map((division) => {
        const details = division.details || {};
        return `
          <section class="division-panel">
            <h3>${escapeHtml(division.division)}</h3>
            <dl>
              <div>
                <dt>Registered</dt>
                <dd>${escapeHtml(division.registered)}${details.max_entries ? ` / ${escapeHtml(details.max_entries)}` : ""}</dd>
              </div>
              <div>
                <dt>Confirmed</dt>
                <dd>${escapeHtml(division.confirmed)}</dd>
              </div>
              <div>
                <dt>Pending</dt>
                <dd>${escapeHtml(details.pending_entries ?? 0)}</dd>
              </div>
              <div>
                <dt>Min Games</dt>
                <dd>${details.min_games ? escapeHtml(details.min_games) : "n/a"}</dd>
              </div>
              <div>
                <dt>Format</dt>
                <dd>${details.event_format ? escapeHtml(details.event_format) : "n/a"}</dd>
              </div>
              <div>
                <dt>Raw</dt>
                <dd>${details.raw_division ? escapeHtml(details.raw_division) : escapeHtml(division.division)}</dd>
              </div>
            </dl>
          </section>
        `;
      }).join("")}
    </div>
  `;
}

function renderRegisteredCounts(item) {
  const divisions = item.selected_age_divisions || [];
  if (!divisions.length) {
    return `
      <span class="pill ${item.meets_team_threshold ? "good" : item.count_warning ? "warn" : ""}">${item.target_team_count ?? "n/a"}</span>
      ${item.count_warning ? '<div class="subtle">event-level count</div>' : '<div class="subtle">division count</div>'}
    `;
  }
  return divisions.map((division) => {
    const good = division.registered >= Number(thresholdFilter.value || 0);
    const details = division.details || {};
    const maxEntries = details.max_entries ? ` / ${details.max_entries}` : "";
    return `
      <div class="division-count">
        <span class="pill ${good ? "good" : ""}">${division.registered}</span>
        <span class="subtle">${escapeHtml(maxEntries)}</span>
      </div>
    `;
  }).join("");
}


function mobileRegisteredSummary(item) {
  const divisions = item.selected_age_divisions || [];
  if (divisions.length) {
    const registered = divisions.reduce((sum, division) => sum + (Number(division.registered) || 0), 0);
    const maxTotal = divisions.reduce((sum, division) => sum + (Number(division.details?.max_entries) || 0), 0);
    return maxTotal > 0 ? `${registered} / ${maxTotal}` : `${registered}`;
  }
  const registered = item.target_team_count ?? 0;
  const maxEntries = Number(item.max_entries || 0);
  return maxEntries > 0 ? `${registered} / ${maxEntries}` : `${registered}`;
}

function renderConfirmedCounts(item) {
  const divisions = item.selected_age_divisions || [];
  if (!divisions.length) {
    return `
      <span class="pill">${item.selected_age_confirmed_count ?? 0}</span>
      <div class="subtle">confirmed</div>
    `;
  }
  return divisions.map((division) => `
    <div class="division-count">
      <span class="pill">${division.confirmed}</span>
    </div>
  `).join("");
}

function renderSelectedAgeDivisions(item) {
  const divisions = item.selected_age_divisions || [];
  if (!divisions.length) {
    return item.age_divisions.map(escapeHtml).join(", ");
  }
  return divisions.map((division) => {
    const details = division.details || {};
    const meta = [
      details.pending_entries ? `${details.pending_entries} pending` : "",
      details.min_games ? `${details.min_games} GG` : "",
      details.event_format || "",
    ].filter(Boolean).join(" - ");
    return `
      <div class="division-age">
        <div>${escapeHtml(division.division)}</div>
        ${meta ? `<div class="subtle">${escapeHtml(meta)}</div>` : ""}
      </div>
    `;
  }).join("");
}

function sortRows(items) {
  return [...items].sort((a, b) => {
    const av = a[sortKey] ?? "";
    const bv = b[sortKey] ?? "";
    if (av < bv) return -1 * sortDirection;
    if (av > bv) return 1 * sortDirection;
    return 0;
  });
}

function renderRows() {
  rowsEl.innerHTML = "";
  declinedRowsEl.innerHTML = "";
  const declinedItems = [];
  const activeItems = [];
  for (const item of sortRows(tournaments)) {
    if ((item.shortlist_status || "Watch") === "Declined") {
      declinedItems.push(item);
    } else {
      activeItems.push(item);
    }
  }
  for (const item of activeItems) {
    renderTournamentRow(item, rowsEl);
  }
  for (const item of declinedItems) {
    renderTournamentRow(item, declinedRowsEl);
  }
  if (declinedCountEl) declinedCountEl.textContent = `(${declinedItems.length})`;
  bindRowEvents();
  queueTournamentTableScrollHintUpdate();
}

function renderTournamentRow(item, container) {
  const tr = document.createElement("tr");
  const detailsTr = document.createElement("tr");
  const detailsId = `teams-${item.id}`;
  tr.innerHTML = `
    <td><button class="teams-toggle" data-id="${item.id}" data-target="${detailsId}" title="Show registered teams">Teams</button></td>
    <td>${formatDate(item.start_date, item.end_date)}</td>
    <td>
      <div class="name"><a href="${escapeHtml(item.detail_url)}" target="_blank" rel="noreferrer">${escapeHtml(item.name)}</a></div>
      <div class="subtle">${escapeHtml(item.stature || "")} ${escapeHtml(item.format || "")}</div>
    </td>
    <td class="col-source">${sourceLabel(item.source)}</td>
    <td>${escapeHtml(item.location || "TBD")}</td>
    <td class="col-distance">${formatDistance(item.distance_miles)}</td>
    <td><span class="desktop-registered">${renderRegisteredCounts(item)}</span><span class="mobile-registered">${escapeHtml(mobileRegisteredSummary(item))}</span></td>
    <td>${renderConfirmedCounts(item)}</td>
    <td>${renderSelectedAgeDivisions(item)}</td>
    <td>
      <select class="status-select" data-id="${item.id}">
        ${["Watch", "Interested", "Registered", "Declined"].map((status) => (
          `<option value="${status}" ${status === (item.shortlist_status || "Watch") ? "selected" : ""}>${status}</option>`
        )).join("")}
      </select>
    </td>
    <td>
      <textarea data-id="${item.id}" placeholder="Staff notes">${escapeHtml(item.shortlist_notes || "")}</textarea>
    </td>
  `;
  detailsTr.id = detailsId;
  detailsTr.className = "team-details-row";
  detailsTr.hidden = true;
  detailsTr.innerHTML = `<td colspan="11">${renderTeamRows(item)}</td>`;
  container.appendChild(tr);
  container.appendChild(detailsTr);
  applyStatusClass(tr, item.shortlist_status || "Watch");
}

function bindRowEvents() {
  document.querySelectorAll(".teams-toggle").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = document.querySelector(`#${button.dataset.target}`);
      const item = tournaments.find((tournament) => String(tournament.id) === button.dataset.id);
      if (!item) return;

      if (!target.hidden) {
        target.hidden = true;
        button.textContent = "Teams";
        return;
      }

      target.hidden = false;
      button.textContent = "Loading...";
      target.innerHTML = '<td colspan="11"><div class="subtle">Loading registered teams...</div></td>';
      try {
        const hydrated = await loadTournamentTeams(item);
        Object.assign(item, hydrated);
        target.innerHTML = `<td colspan="11">${renderTeamRows(item)}</td>`;
        button.textContent = "Hide";
      } catch (error) {
        target.innerHTML = `<td colspan="11"><div class="subtle">Could not load teams yet.</div></td>`;
        button.textContent = "Hide";
      }
    });
  });
  document.querySelectorAll(".status-select").forEach((select) => {
    select.addEventListener("change", () => {
      const item = tournaments.find((tournament) => String(tournament.id) === select.dataset.id);
      if (item) item.shortlist_status = select.value;
      const row = select.closest("tr");
      if (row) {
        applyStatusClass(row, select.value);
      }
      renderRows();
      saveShortlist(select.dataset.id);
    });
  });
  document.querySelectorAll("textarea[data-id]").forEach((textarea) => {
    textarea.addEventListener("blur", () => saveShortlist(textarea.dataset.id));
  });
}

function statusClass(status) {
  return `status-${String(status || "Watch").toLowerCase()}`;
}

function applyStatusClass(row, status) {
  row.classList.remove("status-watch", "status-interested", "status-registered", "status-declined");
  row.classList.add(statusClass(status));
}

async function loadTournamentTeams(item) {
  const params = new URLSearchParams({ age: item.target_age_division });
  for (const division of selectedDivisionValues()) {
    params.append("division", division);
  }
  return api(`/api/tournaments/${item.id}/teams?${params.toString()}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

async function saveShortlist(id) {
  const status = document.querySelector(`select[data-id="${id}"]`).value;
  const notes = document.querySelector(`textarea[data-id="${id}"]`).value;
  await api(`/api/tournaments/${id}/shortlist`, {
    method: "PUT",
    body: JSON.stringify({ status, priority: 3, notes }),
  });
  await loadChanges();
}

async function loadSettings() {
  const settings = await api("/api/settings");
  ageFilter.value = settings.target_age_division;
  thresholdFilter.value = settings.team_count_threshold;
  radiusFilter.value = settings.radius_miles;
  profileEl.textContent = `${settings.home_label} - ${settings.radius_miles} mile base - ${settings.target_age_division}`;
}

async function loadDivisions() {
  const previous = selectedDivisionValues();
  const params = new URLSearchParams();
  if (sourceFilter.value) params.set("source", sourceFilter.value);
  if (ageFilter.value) params.set("age", ageFilter.value);
  const divisions = await api(`/api/divisions?${params.toString()}`);
  divisionOptions.innerHTML = "";
  divisionOptions.appendChild(divisionOption("All", "", previous.length === 0));
  for (const division of divisions) {
    divisionOptions.appendChild(divisionOption(division, division, previous.includes(division)));
  }
  const restored = previous.filter((division) => divisions.includes(division));
  if (!restored.length) {
    const allOption = divisionOptions.querySelector('input[value=""]');
    if (allOption) allOption.checked = true;
  }
  updateDivisionButton();
}

function divisionOption(label, value, checked) {
  const wrapper = document.createElement("label");
  wrapper.className = "division-option";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.value = value;
  input.checked = checked;
  input.addEventListener("change", normalizeDivisionSelection);
  const text = document.createElement("span");
  text.textContent = label;
  wrapper.append(input, text);
  return wrapper;
}

function selectedDivisionValues() {
  return [...divisionOptions.querySelectorAll('input[type="checkbox"]:checked')]
    .map((input) => input.value)
    .filter(Boolean);
}

function normalizeDivisionSelection(event) {
  const changed = event.target;
  const allOption = divisionOptions.querySelector('input[value=""]');
  const divisionInputs = [...divisionOptions.querySelectorAll('input[type="checkbox"]')]
    .filter((input) => input.value);

  if (changed === allOption && allOption.checked) {
    for (const input of divisionInputs) input.checked = false;
  } else if (changed && changed.value) {
    if (allOption) allOption.checked = false;
  }

  if (!divisionInputs.some((input) => input.checked) && allOption) {
    allOption.checked = true;
  }
  updateDivisionButton();
}

function updateDivisionButton() {
  const selected = selectedDivisionValues();
  if (!selected.length) {
    divisionMenuButton.textContent = "All";
  } else if (selected.length === 1) {
    divisionMenuButton.textContent = selected[0];
  } else {
    divisionMenuButton.textContent = `${selected.length} selected`;
  }
}

function toggleDivisionMenu() {
  const nextOpen = divisionOptions.hidden;
  divisionOptions.hidden = !nextOpen;
  divisionMenuButton.setAttribute("aria-expanded", String(nextOpen));
}

function closeDivisionMenu(event) {
  if (
    divisionOptions.hidden ||
    divisionOptions.contains(event.target) ||
    divisionMenuButton.contains(event.target)
  ) {
    return;
  }
  divisionOptions.hidden = true;
  divisionMenuButton.setAttribute("aria-expanded", "false");
}

function toggleNavMenu() {
  const nextOpen = navMenu.hidden;
  navMenu.hidden = !nextOpen;
  menuBtn.setAttribute("aria-expanded", String(nextOpen));
}

function closeNavMenu(event) {
  if (navMenu.hidden || navMenu.contains(event.target) || menuBtn.contains(event.target)) return;
  navMenu.hidden = true;
  menuBtn.setAttribute("aria-expanded", "false");
}

function applyTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", normalized);
  document.body.dataset.theme = normalized;
  themeToggle.textContent = normalized === "dark" ? "Light mode" : "Dark mode";
  themeToggle.setAttribute("aria-label", `Switch to ${normalized === "dark" ? "light" : "dark"} mode`);
  localStorage.setItem(THEME_KEY, normalized);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  const domTheme = document.documentElement.getAttribute("data-theme");
  applyTheme(stored || domTheme || "dark");
}

async function loadTournaments() {
  const params = new URLSearchParams();
  if (sourceFilter.value) params.set("source", sourceFilter.value);
  if (ageFilter.value) params.set("age", ageFilter.value);
  for (const division of selectedDivisionValues()) {
    params.append("division", division);
  }
  if (thresholdFilter.value) params.set("threshold", thresholdFilter.value);
  if (radiusFilter.value) params.set("radius_miles", radiusFilter.value);
  if (searchFilter.value) params.set("q", searchFilter.value);
  if (startDateFilter.value) params.set("start_on_or_after", startDateFilter.value);
  if (endDateFilter.value) params.set("end_on_or_before", endDateFilter.value);
  tournaments = await api(`/api/tournaments?${params.toString()}`);
  renderRows();
}

async function loadChanges() {
  const changes = await api("/api/changes");
  changesEl.innerHTML = changes.length ? "" : '<p class="subtle">No changes recorded yet.</p>';
  for (const change of changes) {
    const div = document.createElement("div");
    div.className = "change";
    div.innerHTML = `
      <div><strong>${change.tournament_name || change.source_id}</strong></div>
      <div class="subtle">${change.field}: ${change.old_value || "new"} -> ${change.new_value || ""}</div>
      <div class="subtle">${change.detected_at}</div>
    `;
    changesEl.appendChild(div);
  }
}

document.querySelector("#applyFilters").addEventListener("click", loadTournaments);
sourceFilter.addEventListener("change", loadDivisions);
ageFilter.addEventListener("change", loadDivisions);
divisionMenuButton.addEventListener("click", toggleDivisionMenu);
document.addEventListener("click", closeDivisionMenu);
document.addEventListener("click", closeNavMenu);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    divisionOptions.hidden = true;
    divisionMenuButton.setAttribute("aria-expanded", "false");
    navMenu.hidden = true;
    menuBtn.setAttribute("aria-expanded", "false");
  }
});
menuBtn.addEventListener("click", toggleNavMenu);
themeToggle.addEventListener("click", toggleTheme);
logoutBtn.addEventListener("click", async () => {
  await fetch("/logout", { method: "POST" });
  window.location.href = "/login";
});
document.querySelector("#refreshBtn").addEventListener("click", async () => {
  document.querySelector("#refreshBtn").textContent = "Refreshing...";
  try {
    await api("/api/refresh", { method: "POST", body: JSON.stringify({}) });
    await loadDivisions();
    await loadTournaments();
    await loadChanges();
  } finally {
    document.querySelector("#refreshBtn").textContent = "Refresh";
  }
});

document.querySelectorAll("th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const next = th.dataset.sort;
    sortDirection = sortKey === next ? sortDirection * -1 : -1;
    sortKey = next;
    renderRows();
  });
});

if (tableWrap) {
  tableWrap.addEventListener("scroll", queueTournamentTableScrollHintUpdate, { passive: true });
  window.addEventListener("resize", queueTournamentTableScrollHintUpdate);
  const tableResizeObserver = new ResizeObserver(queueTournamentTableScrollHintUpdate);
  tableResizeObserver.observe(tableWrap);
  const tableElement = tableWrap.querySelector("table");
  if (tableElement) {
    tableResizeObserver.observe(tableElement);
    const tableMutationObserver = new MutationObserver(queueTournamentTableScrollHintUpdate);
    tableMutationObserver.observe(tableElement, { childList: true, subtree: true });
  }
  queueTournamentTableScrollHintUpdate();
}

initTheme();
loadSettings().then(loadDivisions).then(loadTournaments).then(loadChanges);
