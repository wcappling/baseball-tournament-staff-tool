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
const teamNameEl = document.querySelector("#teamName");
const teamLogoEl = document.querySelector("#teamLogo");
const teamLogoFrame = document.querySelector("#teamLogoFrame");
const themeToggle = document.querySelector("#themeToggle");
const logoutBtn = document.querySelector("#logoutBtn");
const tableWrap = document.querySelector(".table-wrap");

let tournaments = [];
let sortKey = "target_team_count";
let sortDirection = -1;
const THEME_KEY = "staff_tool_theme";
let scrollHintRaf = null;
let currentTeamSettings = null;

// Global lookup map: normalized team name -> stats object (cumulative record etc.)
// Populated from /api/team-stats on page load and after each refresh.
let teamStatsMap = new Map();

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

function todayLocalDateValue() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function setDefaultDateFilters() {
  if (startDateFilter && !startDateFilter.value) {
    startDateFilter.value = todayLocalDateValue();
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Skill level    USSSA     NCS              PG
// Elite/Nat      Major     —                Majors
// High Comp      AAA       D1: Division 1   AAA
// Middle Comp    AA        D2: Division 2   AA
// Developmental  A         D3: Division 3   —
function skillLevel(source, division) {
  const d = (division || "").toLowerCase();
  if (source === "usssa") {
    if (d.includes("major")) return "Elite / National";
    if (d.includes("aaa"))   return "High Competitive";
    if (d.includes("aa"))    return "Middle Competitive";
    if (/\ba\b/.test(d))     return "Developmental";
  } else if (source === "ncs") {
    if (d.includes("d1") || d.includes("division 1")) return "High Competitive";
    if (d.includes("d2") || d.includes("division 2")) return "Middle Competitive";
    if (d.includes("d3") || d.includes("division 3")) return "Developmental";
  } else if (source === "perfect_game") {
    if (d.includes("major")) return "Elite / National";
    if (d.includes("aaa"))   return "High Competitive";
    if (d.includes("aa"))    return "Middle Competitive";
  }
  return null;
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
        .map((division) => {
          const level = skillLevel(item.source, division);
          const levelBadge = level ? `<span class="skill-badge skill-badge--${level.toLowerCase().replace(/[^a-z]/g, "-")}">${escapeHtml(level)}</span>` : "";
          return `
          <section class="team-division-group">
            <h3>${escapeHtml(division)} ${levelBadge}</h3>
            <table class="team-list">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Team</th>
                  <th>Confirmed</th>
                  <th>City/State</th>
                  <th>W-L-T</th>
                  <th>Cumulative</th>
                  <th>Class</th>
                </tr>
              </thead>
              <tbody>
                ${teamsByDivision[division].map((team, index) => {
                  const statsEntry = teamStatsMap.get((team.team_name || "").trim().toLowerCase());
                  const cumulative = statsEntry ? escapeHtml(statsEntry.cumulative_record) : '<span class="subtle">—</span>';
                  return `
                  <tr>
                    <td>${escapeHtml(team.number || index + 1)}</td>
                    <td>${team.detail_url ? `<a href="${escapeHtml(team.detail_url)}" target="_blank" rel="noreferrer">${escapeHtml(team.team_name)}</a>` : escapeHtml(team.team_name)}</td>
                    <td>${team.confirmed ? '<span class="confirmed">Yes</span>' : '<span class="subtle">No</span>'}</td>
                    <td>${escapeHtml(team.city_state)}</td>
                    <td>${escapeHtml(team.record)}</td>
                    <td class="record-cumulative">${cumulative}</td>
                    <td>${escapeHtml(team.team_class || "")}</td>
                  </tr>
                `}).join("")}
              </tbody>
            </table>
          </section>
        `}).join("")}
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
  // Keep change log fresh if it's already been loaded
  if (changesLoaded) await loadChanges();
}

async function loadSettings() {
  const settings = await api("/api/settings");
  applyTeamBrand(settings);
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

function applyTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", normalized);
  document.body.dataset.theme = normalized;
  const nextTheme = normalized === "dark" ? "light" : "dark";
  themeToggle.setAttribute("aria-label", `Switch to ${nextTheme} mode`);
  themeToggle.setAttribute("title", `Switch to ${nextTheme} mode`);
  localStorage.setItem(THEME_KEY, normalized);
  if (currentTeamSettings) {
    applyTeamBrand(currentTeamSettings);
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);
}

function applyTeamBrand(settings) {
  currentTeamSettings = settings;
  const root = document.documentElement;
  const tokens = teamThemeTokens(settings, root.getAttribute("data-theme") || "dark");
  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(key, value);
  }

  if (teamNameEl) {
    teamNameEl.textContent = settings.team_display_name || "Tournament Staff Tool";
  }
  if (!teamLogoEl || !teamLogoFrame) return;
  if (settings.logo_url) {
    teamLogoEl.src = settings.logo_url;
    teamLogoEl.alt = `${settings.team_display_name || "Team"} logo`;
    teamLogoFrame.hidden = false;
  } else {
    teamLogoEl.removeAttribute("src");
    teamLogoEl.alt = "";
    teamLogoFrame.hidden = true;
  }
}

function teamThemeTokens(settings, mode) {
  const primary = normalizeHex(settings.brand_primary, "#0f766e");
  const secondary = normalizeHex(settings.brand_secondary, "#115e59");
  const accent = normalizeHex(settings.brand_accent, secondary);
  const darkMode = mode === "dark";
  const pageBase = darkMode ? "#07101b" : "#eef3f8";
  const surfaceBase = darkMode ? "#111d2b" : "#ffffff";
  const panelBase = darkMode ? "#162638" : "#edf2f7";
  const inputBase = darkMode ? "#0b1624" : "#ffffff";
  const inkBase = darkMode ? "#f3f7fc" : "#142133";
  const mutedBase = darkMode ? "#a9b9cb" : "#56687b";
  const linkBase = darkMode ? "#75d8ff" : "#0f4fd8";
  const lineBase = darkMode ? "#2b3d52" : "#cdd8e5";
  const brandOnPrimary = contrastRatio(primary, "#ffffff") >= 4.5 ? "#ffffff" : "#07101b";

  return {
    "--brand-primary": primary,
    "--brand-secondary": secondary,
    "--brand-accent": accent,
    "--brand-on-primary": brandOnPrimary,
    "--accent": primary,
    "--accent-dark": mixHex(primary, "#000000", darkMode ? 0.24 : 0.18),
    "--focus": contrastRatio(accent, pageBase) >= 3 ? accent : secondary,
    "--page": mixHex(primary, pageBase, darkMode ? 0.82 : 0.92),
    "--surface": mixHex(primary, surfaceBase, darkMode ? 0.78 : 0.96),
    "--panel": mixHex(primary, panelBase, darkMode ? 0.70 : 0.90),
    "--input-bg": mixHex(primary, inputBase, darkMode ? 0.86 : 0.98),
    "--detail": mixHex(primary, darkMode ? "#0e1928" : "#f6f9fc", darkMode ? 0.82 : 0.96),
    "--line": mixHex(secondary, lineBase, darkMode ? 0.72 : 0.82),
    "--pill": mixHex(primary, darkMode ? "#293c52" : "#dce6ef", darkMode ? 0.74 : 0.86),
    "--ink": inkBase,
    "--muted": mutedBase,
    "--th-ink": darkMode ? "#dce8f5" : "#273648",
    "--link": mixHex(secondary, linkBase, darkMode ? 0.30 : 0.62),
    "--link-hover": mixHex(accent, linkBase, darkMode ? 0.20 : 0.50),
    "--sidebar-bg": darkMode
      ? mixHex(primary, "#030a12", 0.88)
      : mixHex(secondary, "#000000", 0.1),
  };
}

function normalizeHex(value, fallback) {
  const raw = String(value || "").trim();
  const match = raw.match(/^#?([0-9a-f]{6})$/i);
  return match ? `#${match[1].toLowerCase()}` : fallback;
}

function mixHex(color, base, baseWeight) {
  const a = hexToRgb(color);
  const b = hexToRgb(base);
  const weight = Math.max(0, Math.min(1, baseWeight));
  return rgbToHex({
    r: Math.round(a.r * (1 - weight) + b.r * weight),
    g: Math.round(a.g * (1 - weight) + b.g * weight),
    b: Math.round(a.b * (1 - weight) + b.b * weight),
  });
}

function hexToRgb(hex) {
  const clean = normalizeHex(hex, "#000000").slice(1);
  return {
    r: parseInt(clean.slice(0, 2), 16),
    g: parseInt(clean.slice(2, 4), 16),
    b: parseInt(clean.slice(4, 6), 16),
  };
}

function rgbToHex(rgb) {
  return `#${[rgb.r, rgb.g, rgb.b].map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

function contrastRatio(first, second) {
  const light = Math.max(relativeLuminance(first), relativeLuminance(second));
  const dark = Math.min(relativeLuminance(first), relativeLuminance(second));
  return (light + 0.05) / (dark + 0.05);
}

function relativeLuminance(hex) {
  const rgb = hexToRgb(hex);
  const values = [rgb.r, rgb.g, rgb.b].map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
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

async function loadTeamStatsMap() {
  const age = ageFilter ? ageFilter.value : "";
  const params = age ? `?age=${encodeURIComponent(age)}` : "";
  try {
    const data = await api(`/api/team-stats${params}`);
    teamStatsMap = new Map(
      (data.teams || []).map((t) => [t.team_name.trim().toLowerCase(), t])
    );
  } catch {
    // non-fatal: cumulative column just shows —
  }
}

async function loadChanges() {
  changesLoaded = true;
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
document.addEventListener("click", (event) => {
  closeDivisionMenu(event);
  // Close mobile nav on outside click (mobileNav ref wired below)
  const nav = document.querySelector("#mobileNav");
  const toggle = document.querySelector("#sidebarToggle");
  if (nav && !nav.hidden && !nav.contains(event.target) && toggle && !toggle.contains(event.target)) {
    nav.hidden = true;
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    divisionOptions.hidden = true;
    divisionMenuButton.setAttribute("aria-expanded", "false");
  }
});
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
    await Promise.all([loadTournaments(), loadTeamStatsMap()]);
    // Reload whichever view is currently open
    if (activeView === "teams-analysis") { teamAnalysisLoaded = false; await loadTeamAnalysis(); }
    if (activeView === "teams-stats")    { teamStatsData = []; await loadTeamStats(); }
    if (activeView === "changelog")      { changesLoaded = false; await loadChanges(); }
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

// ── Team Stats ──────────────────────────────────────────────────────────────

const teamStatsCount = document.querySelector("#teamStatsCount");
const teamStatsNote = document.querySelector("#teamStatsNote");
const teamStatsRowsEl = document.querySelector("#teamStatsRows");

let teamStatsData = [];
let teamStatsSortKey = "win_pct";
let teamStatsSortDir = -1;

function formatWinPct(value) {
  if (value === null || value === undefined || isNaN(value)) return "—";
  return value.toFixed(3).replace(/^0/, "");
}

function sortTeamStats(items) {
  return [...items].sort((a, b) => {
    const av = a[teamStatsSortKey] ?? "";
    const bv = b[teamStatsSortKey] ?? "";
    if (av < bv) return -1 * teamStatsSortDir;
    if (av > bv) return 1 * teamStatsSortDir;
    return 0;
  });
}

function renderTeamStatsRows(teams) {
  if (!teamStatsRowsEl) return;
  teamStatsRowsEl.innerHTML = "";
  for (const team of sortTeamStats(teams)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(team.team_name)}</td>
      <td>${escapeHtml(team.city_state || "")}</td>
      <td class="record-cell">${escapeHtml(team.ncs_record || "—")}</td>
      <td class="record-cell">${escapeHtml(team.usssa_record || "—")}</td>
      <td class="record-cell">${escapeHtml(team.perfect_game_record || "—")}</td>
      <td class="record-cell record-cumulative">${escapeHtml(team.cumulative_record || "—")}</td>
      <td class="win-pct">${formatWinPct(team.win_pct)}</td>
      <td class="win-pct">${team.total_games}</td>
    `;
    teamStatsRowsEl.appendChild(tr);
  }
}

async function loadTeamStats() {
  if (!teamStatsRowsEl) return;
  const age = ageFilter ? ageFilter.value : "";
  const params = age ? `?age=${encodeURIComponent(age)}` : "";
  try {
    const data = await api(`/api/team-stats${params}`);
    teamStatsData = data.teams || [];
    if (teamStatsCount) {
      teamStatsCount.textContent = teamStatsData.length ? `(${teamStatsData.length} teams)` : "";
    }
    if (teamStatsNote) teamStatsNote.textContent = data.note || "";
    renderTeamStatsRows(teamStatsData);
  } catch {
    if (teamStatsRowsEl) {
      teamStatsRowsEl.innerHTML = '<tr><td colspan="8" class="subtle">Could not load team stats.</td></tr>';
    }
  }
}

document.querySelectorAll("th[data-stats-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const next = th.dataset.statsSort;
    teamStatsSortDir = teamStatsSortKey === next ? teamStatsSortDir * -1 : -1;
    teamStatsSortKey = next;
    renderTeamStatsRows(teamStatsData);
  });
});

// ── Sidebar toggle (hamburger) ───────────────────────────────────────────────

const sidebar = document.querySelector("#sidebar");
const sidebarToggleBtn = document.querySelector("#sidebarToggle");
const mobileNav = document.querySelector("#mobileNav");

const SIDEBAR_KEY = "staff_tool_sidebar";

function isMobileLayout() {
  return window.innerWidth < 768;
}

let sidebarOpen = localStorage.getItem(SIDEBAR_KEY) !== "closed" && !isMobileLayout();

function applySidebarState() {
  if (sidebar) sidebar.classList.toggle("closed", !sidebarOpen);
}

applySidebarState();

if (sidebarToggleBtn) {
  sidebarToggleBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    if (isMobileLayout()) {
      if (mobileNav) mobileNav.hidden = !mobileNav.hidden;
    } else {
      sidebarOpen = !sidebarOpen;
      localStorage.setItem(SIDEBAR_KEY, sidebarOpen ? "open" : "closed");
      applySidebarState();
    }
  });
}

window.addEventListener("resize", () => {
  if (!isMobileLayout() && mobileNav && !mobileNav.hidden) {
    mobileNav.hidden = true;
  }
});

// ── View switching ───────────────────────────────────────────────────────────

const tournamentsView      = document.querySelector("#tournamentsView");
const teamsAnalysisView    = document.querySelector("#teamsAnalysisView");
const teamsStatsView       = document.querySelector("#teamsStatsView");
const changelogView        = document.querySelector("#changelogView");

const sidebarTournamentsBtn    = document.querySelector("#sidebarTournamentsBtn");
const sidebarTeamsAnalysisBtn  = document.querySelector("#sidebarTeamsAnalysisBtn");
const sidebarTeamsStatsBtn     = document.querySelector("#sidebarTeamsStatsBtn");
const sidebarChangelogBtn      = document.querySelector("#sidebarChangelogBtn");
const mobileTournamentsBtn     = document.querySelector("#mobileTournamentsBtn");
const mobileTeamsBtn           = document.querySelector("#mobileTeamsBtn");
const mobileTeamsStatsBtn      = document.querySelector("#mobileTeamsStatsBtn");
const mobileChangelogBtn       = document.querySelector("#mobileChangelogBtn");

let activeView = "tournaments";
let teamAnalysisLoaded = false;
let changesLoaded = false;

const ALL_VIEWS = {
  "tournaments":    tournamentsView,
  "teams-analysis": teamsAnalysisView,
  "teams-stats":    teamsStatsView,
  "changelog":      changelogView,
};

const ALL_NAV_BTNS = {
  "tournaments":    [sidebarTournamentsBtn, mobileTournamentsBtn],
  "teams-analysis": [sidebarTeamsAnalysisBtn, mobileTeamsBtn],
  "teams-stats":    [sidebarTeamsStatsBtn, mobileTeamsStatsBtn],
  "changelog":      [sidebarChangelogBtn, mobileChangelogBtn],
};

function switchView(view) {
  activeView = view;
  for (const [key, el] of Object.entries(ALL_VIEWS)) {
    if (el) el.hidden = key !== view;
  }
  for (const [key, btns] of Object.entries(ALL_NAV_BTNS)) {
    for (const btn of btns) {
      if (btn) btn.classList.toggle("active", key === view);
    }
  }
  if (view === "teams-analysis" && !teamAnalysisLoaded) loadTeamAnalysis();
  if (view === "teams-stats"    && teamStatsData.length === 0) loadTeamStats();
  if (view === "changelog"      && !changesLoaded) loadChanges();
  if (mobileNav && isMobileLayout()) mobileNav.hidden = true;
}

if (sidebarTournamentsBtn)   sidebarTournamentsBtn.addEventListener("click",   () => switchView("tournaments"));
if (sidebarTeamsAnalysisBtn) sidebarTeamsAnalysisBtn.addEventListener("click", () => switchView("teams-analysis"));
if (sidebarTeamsStatsBtn)    sidebarTeamsStatsBtn.addEventListener("click",    () => switchView("teams-stats"));
if (sidebarChangelogBtn)     sidebarChangelogBtn.addEventListener("click",     () => switchView("changelog"));
if (mobileTournamentsBtn)    mobileTournamentsBtn.addEventListener("click",    () => switchView("tournaments"));
if (mobileTeamsBtn)          mobileTeamsBtn.addEventListener("click",          () => switchView("teams-analysis"));
if (mobileTeamsStatsBtn)     mobileTeamsStatsBtn.addEventListener("click",     () => switchView("teams-stats"));
if (mobileChangelogBtn)      mobileChangelogBtn.addEventListener("click",      () => switchView("changelog"));


// ── Team Analysis Page ───────────────────────────────────────────────────────

const teamAnalysisRowsEl = document.querySelector("#teamAnalysisRows");
const teamAnalysisNote = document.querySelector("#teamAnalysisNote");
const teamAnalysisEmpty = document.querySelector("#teamAnalysisEmpty");

let teamAnalysisData = [];
let teamAnalysisSortKey = "win_pct";
let teamAnalysisSortDir = -1;

function sortTeamAnalysis(items) {
  return [...items].sort((a, b) => {
    const av = a[teamAnalysisSortKey] ?? "";
    const bv = b[teamAnalysisSortKey] ?? "";
    if (av < bv) return -1 * teamAnalysisSortDir;
    if (av > bv) return 1 * teamAnalysisSortDir;
    return 0;
  });
}

function renderTeamAnalysisRows(teams) {
  if (!teamAnalysisRowsEl) return;
  teamAnalysisRowsEl.innerHTML = "";

  if (!teams.length) {
    if (teamAnalysisEmpty) teamAnalysisEmpty.hidden = false;
    return;
  }
  if (teamAnalysisEmpty) teamAnalysisEmpty.hidden = true;

  for (const team of sortTeamAnalysis(teams)) {
    const appearanceNames = (team.appearances || [])
      .map((a) => {
        const date = a.start_date ? ` (${a.start_date})` : "";
        const rec = a.record ? ` ${escapeHtml(a.record)}` : "";
        return `<span class="appearance-chip">${escapeHtml(a.name)}${date}${rec}</span>`;
      })
      .join(" ");

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(team.team_name)}</td>
      <td>${escapeHtml(team.city_state || "")}</td>
      <td class="record-cell">${escapeHtml(team.ncs_record || "—")}</td>
      <td class="record-cell">${escapeHtml(team.usssa_record || "—")}</td>
      <td class="record-cell">${escapeHtml(team.perfect_game_record || "—")}</td>
      <td class="record-cell record-cumulative">${escapeHtml(team.cumulative_record || "—")}</td>
      <td class="win-pct">${formatWinPct(team.win_pct)}</td>
      <td class="win-pct">${team.total_games}</td>
      <td class="appearance-list">${appearanceNames || '<span class="subtle">—</span>'}</td>
    `;
    teamAnalysisRowsEl.appendChild(tr);
  }
}

async function loadTeamAnalysis() {
  if (!teamAnalysisRowsEl) return;
  const age = ageFilter ? ageFilter.value : "";
  const params = age ? `?age=${encodeURIComponent(age)}` : "";
  try {
    const data = await api(`/api/team-analysis${params}`);
    teamAnalysisData = data.teams || [];
    teamAnalysisLoaded = true;
    if (teamAnalysisNote) teamAnalysisNote.textContent = data.note || "";
    renderTeamAnalysisRows(teamAnalysisData);
  } catch {
    if (teamAnalysisRowsEl) {
      teamAnalysisRowsEl.innerHTML = '<tr><td colspan="9" class="subtle">Could not load team analysis.</td></tr>';
    }
  }
}

document.querySelectorAll("th[data-analysis-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const next = th.dataset.analysisSort;
    teamAnalysisSortDir = teamAnalysisSortKey === next ? teamAnalysisSortDir * -1 : -1;
    teamAnalysisSortKey = next;
    renderTeamAnalysisRows(teamAnalysisData);
  });
});

// Reload data when age filter changes based on active view
if (ageFilter) {
  ageFilter.addEventListener("change", () => {
    if (activeView === "teams-analysis") { teamAnalysisLoaded = false; loadTeamAnalysis(); }
    if (activeView === "teams-stats")    { teamStatsData = []; loadTeamStats(); }
  });
}

// ── Init ─────────────────────────────────────────────────────────────────────

initTheme();
setDefaultDateFilters();
loadSettings()
  .then(loadDivisions)
  .then(() => Promise.all([loadTournaments(), loadTeamStatsMap()]));
