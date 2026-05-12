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
const singleDayFilter = document.querySelector("#singleDayFilter");
const includeUnknownFilter = document.querySelector("#includeUnknownFilter");
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
  const showUnknown = includeUnknownFilter ? includeUnknownFilter.checked : true;
  for (const item of sortRows(tournaments)) {
    if (!showUnknown && item.distance_miles === null) continue;
    if (item.shortlist_status === "Declined") {
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
        <option value="" ${!item.shortlist_status || item.shortlist_status === "Watch" ? "selected" : ""}>Open</option>
        ${["Interested", "Registered", "Declined"].map((status) => (
          `<option value="${status}" ${status === item.shortlist_status ? "selected" : ""}>${status}</option>`
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
  applyStatusClass(tr, item.shortlist_status || "");
}

function bindRowEvents() {
  document.querySelectorAll(".teams-toggle").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = button.closest("tr").nextElementSibling;
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
  if (!status || status === "Watch") return "status-open";
  return `status-${String(status).toLowerCase()}`;
}

function applyStatusClass(row, status) {
  row.classList.remove("status-open", "status-interested", "status-registered", "status-declined");
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
  if (analysisAgeFilterEl) analysisAgeFilterEl.value = settings.target_age_division;
  if (statsAgeFilterEl)    statsAgeFilterEl.value    = settings.target_age_division;
  await loadAvailableSeasons();
}

async function loadAvailableSeasons() {
  try {
    const data = await api("/api/available-seasons");
    const seasons = data.seasons || [];
    const current = data.current || "";
    [statsSeasonFilterEl, analysisSeasonFilterEl].forEach(el => {
      if (!el) return;
      el.innerHTML = seasons.map(s =>
        `<option value="${s}"${s === current ? " selected" : ""}>${s}</option>`
      ).join("");
      const show = seasons.length > 1;
      el.hidden = !show;
      if (el.parentElement) el.parentElement.hidden = !show;
    });
  } catch { /* seasons unavailable — keep selects hidden */ }
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
  if (teamLogoEl && teamLogoFrame) {
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

  const isAdmin = settings.team_id === "default";
  [sidebarSettingsBtn, mobileSettingsBtn].forEach((b) => { if (b) b.hidden = isAdmin; });
  [sidebarAdminBtn,    mobileAdminBtn   ].forEach((b) => { if (b) b.hidden = !isAdmin; });
}

function teamThemeTokens(settings, mode) {
  const primary = normalizeHex(settings.brand_primary, "#0f766e");
  const secondary = normalizeHex(settings.brand_secondary, "#115e59");
  const accent = normalizeHex(settings.brand_accent, secondary);
  const darkMode = mode === "dark";
  const pageBase = darkMode ? "#080808" : "#eef3f8";
  const surfaceBase = darkMode ? "#131313" : "#ffffff";
  const panelBase = darkMode ? "#191919" : "#edf2f7";
  const inputBase = darkMode ? "#0c0c0c" : "#ffffff";
  const inkBase = darkMode ? "#f3f7fc" : "#142133";
  const mutedBase = darkMode ? "#a9b9cb" : "#56687b";
  const linkBase = darkMode ? "#75d8ff" : "#0f4fd8";
  const lineBase = darkMode ? "#2a2a2a" : "#cdd8e5";
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
    "--detail": mixHex(primary, darkMode ? "#0d0d0d" : "#f6f9fc", darkMode ? 0.82 : 0.96),
    "--line": mixHex(secondary, lineBase, darkMode ? 0.72 : 0.82),
    "--pill": mixHex(primary, darkMode ? "#222222" : "#dce6ef", darkMode ? 0.74 : 0.86),
    "--ink": inkBase,
    "--muted": mutedBase,
    "--th-ink": darkMode ? "#dce8f5" : "#273648",
    "--link": mixHex(secondary, linkBase, darkMode ? 0.30 : 0.62),
    "--link-hover": mixHex(accent, linkBase, darkMode ? 0.20 : 0.50),
    "--sidebar-bg": darkMode
      ? mixHex(primary, "#030303", 0.88)
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
  if (singleDayFilter?.checked) params.set("single_day", "true");
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

function formatRelativeTime(isoStr) {
  const date = new Date(isoStr);
  if (isNaN(date.getTime())) return isoStr;
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function parseChangeLines(field, oldVal, newVal, agePrefix = "") {
  const matchesAge = div => !agePrefix || div.toUpperCase().startsWith(agePrefix.toUpperCase());
  try {
    if (field === "registered_teams") {
      const o = Number(oldVal), n = Number(newVal);
      if (!isNaN(o) && !isNaN(n)) {
        const delta = n - o;
        const sign = delta > 0 ? "+" : "";
        return [`Registered teams: ${o} → ${n} (${sign}${delta})`];
      }
      return [`Registered teams: ${oldVal} → ${newVal}`];
    }

    if (field === "division_teams") {
      const oldDivs = JSON.parse(oldVal || "{}");
      const newDivs = JSON.parse(newVal || "{}");
      const lines = [];
      const allDivs = new Set([...Object.keys(oldDivs), ...Object.keys(newDivs)]);
      for (const div of [...allDivs].sort()) {
        if (/^\d{1,2}U$/i.test(div)) continue;
        if (!matchesAge(div)) continue;
        const oldTeams = new Map((oldDivs[div] || []).map(t => [
          (t.team_name || String(t)).toLowerCase(), t.team_name || String(t)
        ]));
        const newTeams = new Map((newDivs[div] || []).map(t => [
          (t.team_name || String(t)).toLowerCase(), t.team_name || String(t)
        ]));
        for (const [k, name] of newTeams) {
          if (!oldTeams.has(k)) lines.push(`${div}: + ${name}`);
        }
        for (const [k, name] of oldTeams) {
          if (!newTeams.has(k)) lines.push(`${div}: removed ${name}`);
        }
      }
      return lines.length ? lines : null;
    }

    if (field === "division_details") {
      const oldD = JSON.parse(oldVal || "{}");
      const newD = JSON.parse(newVal || "{}");
      const NOISE = new Set(["pending_entries", "deadline_passed", "division_id", "raw_division"]);
      const LABELS = {
        max_entries: "max entries", entry_fee: "entry fee", min_games: "min games",
        event_format: "format", stature: "stature", location: "location", gate_fee: "gate fee",
      };
      const lines = [];
      const allDivs = new Set([...Object.keys(oldD), ...Object.keys(newD)]);
      for (const div of [...allDivs].sort()) {
        if (/^\d{1,2}U$/i.test(div)) continue;
        if (!matchesAge(div)) continue;
        const o = oldD[div] || {};
        const n = newD[div] || {};
        const allKeys = new Set([...Object.keys(o), ...Object.keys(n)]);
        for (const key of allKeys) {
          if (NOISE.has(key) || o[key] === n[key]) continue;
          if (key === "sold_out") {
            lines.push(`${div}: ${n.sold_out ? "SOLD OUT" : "now open"}`);
          } else {
            const label = LABELS[key] ?? key.replace(/_/g, " ");
            const fmt = v => v == null ? "—" : String(v);
            lines.push(`${div}: ${label} ${fmt(o[key])} → ${fmt(n[key])}`);
          }
        }
      }
      return lines.length ? lines : null;
    }

    if (field === "division_confirmed_counts") {
      const o = JSON.parse(oldVal || "{}");
      const n = JSON.parse(newVal || "{}");
      const lines = [];
      const allDivs = new Set([...Object.keys(o), ...Object.keys(n)]);
      for (const div of [...allDivs].sort()) {
        if (/^\d{1,2}U$/i.test(div)) continue;
        if (!matchesAge(div)) continue;
        if (o[div] !== n[div]) lines.push(`${div}: confirmed ${o[div] ?? "?"} → ${n[div] ?? "?"}`);
      }
      return lines.length ? lines : null;
    }

    if (field === "division_team_counts") {
      const o = JSON.parse(oldVal || "{}");
      const n = JSON.parse(newVal || "{}");
      const lines = [];
      const allDivs = new Set([...Object.keys(o), ...Object.keys(n)]);
      for (const div of [...allDivs].sort()) {
        if (/^\d{1,2}U$/i.test(div)) continue;
        if (!matchesAge(div)) continue;
        if (o[div] !== n[div]) lines.push(`${div}: teams ${o[div] ?? "?"} → ${n[div] ?? "?"}`);
      }
      return lines.length ? lines : null;
    }

    return [`${field.replace(/_/g, " ")}: ${oldVal || "(none)"} → ${newVal || "(none)"}`];
  } catch (_e) {
    return [`${field.replace(/_/g, " ")}: updated`];
  }
}

async function loadChanges() {
  changesLoaded = true;
  const changes = await api("/api/changes");
  changesEl.innerHTML = "";

  if (!changes.length) {
    changesEl.innerHTML = '<p class="subtle">No changes recorded yet.</p>';
    const recentBannerEmpty = document.querySelector("#recentChangesBanner");
    if (recentBannerEmpty) recentBannerEmpty.hidden = true;
    return;
  }

  // Group by tournament + time bucket (minute granularity)
  const groups = new Map();
  for (const change of changes) {
    const timeBucket = (change.detected_at || "").slice(0, 16);
    const key = `${change.tournament_id || change.source_id}__${timeBucket}`;
    if (!groups.has(key)) {
      groups.set(key, {
        name: change.tournament_name || change.source_id || "Unknown tournament",
        detectedAt: change.detected_at,
        lines: [],
      });
    }
    const agePrefix = currentTeamSettings?.target_age_division || "";
    const parsed = parseChangeLines(change.field, change.old_value, change.new_value, agePrefix);
    if (parsed) groups.get(key).lines.push(...parsed);
  }

  // Recent changes banner (last 6 hours)
  const recentBanner = document.querySelector("#recentChangesBanner");
  if (recentBanner) {
    const sixHoursAgo = Date.now() - 6 * 60 * 60 * 1000;
    const recentGroups = [...groups.values()].filter(g => {
      if (!g.detectedAt) return false;
      return new Date(g.detectedAt).getTime() >= sixHoursAgo && g.lines.length > 0;
    });
    if (recentGroups.length > 0) {
      recentBanner.hidden = false;
      recentBanner.innerHTML = `
        <div class="recent-changes-banner">
          <div class="recent-changes-title">Recent changes (last 6 hours)</div>
          <ul class="recent-changes-list">
            ${recentGroups.map(g => `
              <li>
                <strong>${escapeHtml(g.name)}</strong>
                ${g.lines.length ? `<span class="subtle"> — ${escapeHtml(g.lines[0])}</span>` : ""}
              </li>
            `).join("")}
          </ul>
        </div>
      `;
    } else {
      recentBanner.hidden = true;
    }
  }

  for (const group of groups.values()) {
    if (!group.lines.length) continue;
    const div = document.createElement("div");
    div.className = "change";
    div.innerHTML = `
      <div class="change-header">
        <strong class="change-tournament">${escapeHtml(group.name)}</strong>
        <span class="change-time subtle">${escapeHtml(formatRelativeTime(group.detectedAt || ""))}</span>
      </div>
      <ul class="change-lines">
        ${group.lines.map(l => `<li>${escapeHtml(l)}</li>`).join("")}
      </ul>
    `;
    changesEl.appendChild(div);
  }

  if (!changesEl.children.length) {
    changesEl.innerHTML = '<p class="subtle">No displayable changes recorded yet.</p>';
  }
}

document.querySelector("#applyFilters").addEventListener("click", loadTournaments);
if (includeUnknownFilter) includeUnknownFilter.addEventListener("change", renderRows);
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
    if (activeView === "upcoming")       renderUpcomingView();
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
const statsAgeFilterEl = document.querySelector("#statsAgeFilter");
const statsSeasonFilterEl = document.querySelector("#statsSeasonFilter");
const statsTeamSearchEl = document.querySelector("#statsTeamSearch");
const statsMinGamesEl = document.querySelector("#statsMinGames");
const statsApplyFilterEl = document.querySelector("#statsApplyFilter");
const statsCompareBtnEl = document.querySelector("#statsCompareBtn");
const statsClearSelectionEl = document.querySelector("#statsClearSelection");

let teamStatsData = [];
let teamStatsSortKey = "team_name";
let teamStatsSortDir = 1;
let statsSelectedTeams = new Set();
let statsCompareMode = false;

function updateStatsCompareBtn() {
  if (statsCompareBtnEl) statsCompareBtnEl.hidden = statsSelectedTeams.size === 0;
}

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

function getStatsFiltered(teams) {
  const search = statsTeamSearchEl ? statsTeamSearchEl.value.trim().toLowerCase() : "";
  const minGames = statsMinGamesEl ? Number(statsMinGamesEl.value) || 0 : 0;
  return teams.filter((team) => {
    if (statsCompareMode && !statsSelectedTeams.has(team.team_name)) return false;
    if (team.total_games < minGames) return false;
    if (search && !team.team_name.toLowerCase().includes(search)) return false;
    return true;
  });
}

function renderTeamStatsRows(teams) {
  if (!teamStatsRowsEl) return;
  teamStatsRowsEl.innerHTML = "";
  const filtered = getStatsFiltered(teams);
  const sorted = sortTeamStats(filtered);
  // Float selected teams to top
  const selected = sorted.filter((t) => statsSelectedTeams.has(t.team_name));
  const unselected = sorted.filter((t) => !statsSelectedTeams.has(t.team_name));
  const display = [...selected, ...unselected];
  for (const team of display) {
    const isSelected = statsSelectedTeams.has(team.team_name);
    const tr = document.createElement("tr");
    if (isSelected) tr.classList.add("team-row-selected");
    tr.innerHTML = `
      <td class="col-select" data-label="Select"><input type="checkbox" class="team-select-cb" data-name="${escapeHtml(team.team_name)}" ${isSelected ? "checked" : ""}></td>
      <td data-label="Team">${escapeHtml(team.team_name)}</td>
      <td data-label="City/State">${escapeHtml(team.city_state || "")}</td>
      <td class="col-ncs record-cell" data-label="NCS">${escapeHtml(team.ncs_record || "—")}</td>
      <td class="col-usssa record-cell" data-label="USSSA">${escapeHtml(team.usssa_record || "—")}</td>
      <td class="col-pg record-cell" data-label="Perfect Game">${escapeHtml(team.perfect_game_record || "—")}</td>
      <td class="record-cell record-cumulative" data-label="Cumulative">${escapeHtml(team.cumulative_record || "—")}</td>
      <td class="win-pct" data-label="Win%">${formatWinPct(team.win_pct)}</td>
      <td class="win-pct" data-label="Games">${team.total_games}</td>
    `;
    teamStatsRowsEl.appendChild(tr);
  }
  // Bind checkbox events
  teamStatsRowsEl.querySelectorAll(".team-select-cb").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) statsSelectedTeams.add(cb.dataset.name);
      else statsSelectedTeams.delete(cb.dataset.name);
      updateStatsCompareBtn();
      renderTeamStatsRows(teamStatsData);
    });
  });
}

async function loadTeamStats() {
  if (!teamStatsRowsEl) return;
  const age = (statsAgeFilterEl ? statsAgeFilterEl.value : "") || (ageFilter ? ageFilter.value : "");
  const season = statsSeasonFilterEl ? statsSeasonFilterEl.value : "";
  const params = new URLSearchParams();
  if (age) params.set("age", age);
  if (season) params.set("season", season);
  const paramStr = params.toString() ? `?${params.toString()}` : "";
  try {
    const data = await api(`/api/team-stats${paramStr}`);
    teamStatsData = data.teams || [];
    if (teamStatsCount) {
      teamStatsCount.textContent = teamStatsData.length ? `(${teamStatsData.length} teams)` : "";
    }
    if (teamStatsNote) teamStatsNote.textContent = data.note || "";
    renderTeamStatsRows(teamStatsData);
  } catch {
    if (teamStatsRowsEl) {
      teamStatsRowsEl.innerHTML = '<tr><td colspan="9" class="subtle">Could not load team stats.</td></tr>';
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

if (statsTeamSearchEl) statsTeamSearchEl.addEventListener("input", () => renderTeamStatsRows(teamStatsData));
if (statsTeamSearchEl) statsTeamSearchEl.addEventListener("input", () => renderTeamStatsRows(teamStatsData));
if (statsApplyFilterEl) statsApplyFilterEl.addEventListener("click", () => renderTeamStatsRows(teamStatsData));
if (statsCompareBtnEl) statsCompareBtnEl.addEventListener("click", () => {
  statsCompareMode = true;
  renderTeamStatsRows(teamStatsData);
});
if (statsClearSelectionEl) statsClearSelectionEl.addEventListener("click", () => {
  statsSelectedTeams.clear();
  statsCompareMode = false;
  updateStatsCompareBtn();
  renderTeamStatsRows(teamStatsData);
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
const upcomingView         = document.querySelector("#upcomingView");
const teamsAnalysisView    = document.querySelector("#teamsAnalysisView");
const teamsStatsView       = document.querySelector("#teamsStatsView");
const changelogView        = document.querySelector("#changelogView");
const settingsView         = document.querySelector("#settingsView");
const adminView            = document.querySelector("#adminView");
const toolbarEl            = document.querySelector(".toolbar");

const sidebarTournamentsBtn    = document.querySelector("#sidebarTournamentsBtn");
const sidebarUpcomingBtn       = document.querySelector("#sidebarUpcomingBtn");
const sidebarTeamsBtn          = document.querySelector("#sidebarTeamsBtn");
const sidebarTeamsAnalysisBtn  = document.querySelector("#sidebarTeamsAnalysisBtn");
const sidebarTeamsStatsBtn     = document.querySelector("#sidebarTeamsStatsBtn");
const sidebarChangelogBtn      = document.querySelector("#sidebarChangelogBtn");
const sidebarSettingsBtn       = document.querySelector("#sidebarSettingsBtn");
const sidebarAdminBtn          = document.querySelector("#sidebarAdminBtn");
const mobileTournamentsBtn     = document.querySelector("#mobileTournamentsBtn");
const mobileUpcomingBtn        = document.querySelector("#mobileUpcomingBtn");
const mobileTeamsBtn           = document.querySelector("#mobileTeamsBtn");
const mobileTeamsStatsBtn      = document.querySelector("#mobileTeamsStatsBtn");
const mobileChangelogBtn       = document.querySelector("#mobileChangelogBtn");
const mobileSettingsBtn        = document.querySelector("#mobileSettingsBtn");
const mobileAdminBtn           = document.querySelector("#mobileAdminBtn");

let activeView = "tournaments";
let teamAnalysisLoaded = false;
let changesLoaded = false;

const ALL_VIEWS = {
  "tournaments":    tournamentsView,
  "upcoming":       upcomingView,
  "teams-analysis": teamsAnalysisView,
  "teams-stats":    teamsStatsView,
  "changelog":      changelogView,
  "settings":       settingsView,
  "admin":          adminView,
};

const ALL_NAV_BTNS = {
  "tournaments":    [sidebarTournamentsBtn, mobileTournamentsBtn],
  "upcoming":       [sidebarUpcomingBtn, mobileUpcomingBtn],
  "teams-analysis": [sidebarTeamsAnalysisBtn, sidebarTeamsBtn, mobileTeamsBtn],
  "teams-stats":    [sidebarTeamsStatsBtn, mobileTeamsStatsBtn],
  "changelog":      [sidebarChangelogBtn, mobileChangelogBtn],
  "settings":       [sidebarSettingsBtn, mobileSettingsBtn],
  "admin":          [sidebarAdminBtn, mobileAdminBtn],
};

const upcomingRowsEl = document.querySelector("#upcomingRows");

function renderUpcomingView() {
  if (!upcomingRowsEl) return;
  upcomingRowsEl.innerHTML = "";
  const interested = tournaments
    .filter((t) => t.shortlist_status === "Interested" || t.shortlist_status === "Registered")
    .slice()
    .sort((a, b) => {
      const ad = a.start_date || "";
      const bd = b.start_date || "";
      if (ad < bd) return -1;
      if (ad > bd) return 1;
      return 0;
    });
  if (!interested.length) {
    upcomingRowsEl.innerHTML = '<tr><td colspan="11" class="subtle" style="text-align:center;padding:24px;">No upcoming tournaments. Mark tournaments as Interested or Registered to see them here.</td></tr>';
    return;
  }
  for (const item of interested) {
    renderTournamentRow(item, upcomingRowsEl);
  }
  bindRowEvents();
}

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
  // Show toolbar only on tournaments view
  if (toolbarEl) toolbarEl.hidden = view !== "tournaments";
  if (view === "upcoming")       renderUpcomingView();
  if (view === "teams-analysis" && !teamAnalysisLoaded) loadTeamAnalysis();
  if (view === "teams-stats"    && teamStatsData.length === 0) loadTeamStats();
  if (view === "changelog"      && !changesLoaded) loadChanges();
  if (view === "settings")       loadSettingsView();
  if (view === "admin")          loadAdminView();
  if (mobileNav && isMobileLayout()) mobileNav.hidden = true;
}

if (sidebarTournamentsBtn)   sidebarTournamentsBtn.addEventListener("click",   () => switchView("tournaments"));
if (sidebarUpcomingBtn)      sidebarUpcomingBtn.addEventListener("click",      () => switchView("upcoming"));
if (sidebarTeamsBtn)         sidebarTeamsBtn.addEventListener("click",         () => switchView("teams-analysis"));
if (sidebarTeamsAnalysisBtn) sidebarTeamsAnalysisBtn.addEventListener("click", () => switchView("teams-analysis"));
if (sidebarTeamsStatsBtn)    sidebarTeamsStatsBtn.addEventListener("click",    () => switchView("teams-stats"));
if (sidebarChangelogBtn)     sidebarChangelogBtn.addEventListener("click",     () => switchView("changelog"));
if (mobileTournamentsBtn)    mobileTournamentsBtn.addEventListener("click",    () => switchView("tournaments"));
if (mobileUpcomingBtn)       mobileUpcomingBtn.addEventListener("click",       () => switchView("upcoming"));
if (mobileTeamsBtn)          mobileTeamsBtn.addEventListener("click",          () => switchView("teams-analysis"));
if (mobileTeamsStatsBtn)     mobileTeamsStatsBtn.addEventListener("click",     () => switchView("teams-stats"));
if (mobileChangelogBtn)      mobileChangelogBtn.addEventListener("click",      () => switchView("changelog"));
if (sidebarSettingsBtn)      sidebarSettingsBtn.addEventListener("click",      () => switchView("settings"));
if (sidebarAdminBtn)         sidebarAdminBtn.addEventListener("click",         () => switchView("admin"));
if (mobileSettingsBtn)       mobileSettingsBtn.addEventListener("click",       () => switchView("settings"));
if (mobileAdminBtn)          mobileAdminBtn.addEventListener("click",          () => switchView("admin"));


// ── Team Analysis Page ───────────────────────────────────────────────────────

const teamAnalysisRowsEl = document.querySelector("#teamAnalysisRows");
const teamAnalysisNote = document.querySelector("#teamAnalysisNote");
const teamAnalysisEmpty = document.querySelector("#teamAnalysisEmpty");
const analysisAgeFilterEl = document.querySelector("#analysisAgeFilter");
const analysisSeasonFilterEl = document.querySelector("#analysisSeasonFilter");
const analysisTeamSearchEl = document.querySelector("#analysisTeamSearch");
const analysisMinGamesEl = document.querySelector("#analysisMinGames");
const analysisTournamentFilterEl = document.querySelector("#analysisTournamentFilter");
const analysisCompareBtnEl = document.querySelector("#analysisCompareBtn");
const analysisClearSelectionEl = document.querySelector("#analysisClearSelection");

let teamAnalysisData = [];
let teamAnalysisSortKey = "team_name";
let teamAnalysisSortDir = 1;
let analysisSelectedTeams = new Set();
let analysisCompareMode = false;

function sortTeamAnalysis(items) {
  return [...items].sort((a, b) => {
    const av = a[teamAnalysisSortKey] ?? "";
    const bv = b[teamAnalysisSortKey] ?? "";
    if (av < bv) return -1 * teamAnalysisSortDir;
    if (av > bv) return 1 * teamAnalysisSortDir;
    return 0;
  });
}

function getAnalysisFiltered(teams) {
  const search = analysisTeamSearchEl ? analysisTeamSearchEl.value.trim().toLowerCase() : "";
  const minGames = analysisMinGamesEl ? Number(analysisMinGamesEl.value) || 0 : 0;
  const tournamentId = analysisTournamentFilterEl ? analysisTournamentFilterEl.value : "";
  return teams.filter((team) => {
    if (analysisCompareMode && !analysisSelectedTeams.has(team.team_name)) return false;
    if (team.total_games < minGames) return false;
    if (search && !team.team_name.toLowerCase().includes(search)) return false;
    if (tournamentId && !(team.appearances || []).some((a) => String(a.id) === tournamentId)) return false;
    return true;
  });
}

function updateAnalysisCompareBtn() {
  if (analysisCompareBtnEl) analysisCompareBtnEl.hidden = analysisSelectedTeams.size === 0;
}

function renderTeamAnalysisRows(teams) {
  if (!teamAnalysisRowsEl) return;
  teamAnalysisRowsEl.innerHTML = "";

  const filtered = getAnalysisFiltered(teams);

  if (!filtered.length) {
    if (teamAnalysisEmpty) teamAnalysisEmpty.hidden = false;
    return;
  }
  if (teamAnalysisEmpty) teamAnalysisEmpty.hidden = true;

  const sorted = sortTeamAnalysis(filtered);
  const selected = sorted.filter((t) => analysisSelectedTeams.has(t.team_name));
  const unselected = sorted.filter((t) => !analysisSelectedTeams.has(t.team_name));
  const display = [...selected, ...unselected];

  for (const team of display) {
    const isSelected = analysisSelectedTeams.has(team.team_name);
    const activeTournamentId = analysisTournamentFilterEl ? analysisTournamentFilterEl.value : "";
    const appearanceNames = (team.appearances || [])
      .map((a) => {
        const date = a.start_date ? ` (${a.start_date})` : "";
        const rec = a.record ? ` ${escapeHtml(a.record)}` : "";
        const isActive = activeTournamentId && String(a.id) === activeTournamentId;
        const activeClass = isActive ? " appearance-chip--active" : "";
        return `<span class="appearance-chip appearance-chip--clickable${activeClass}" data-tournament-id="${escapeHtml(String(a.id))}">${escapeHtml(a.name)}${date}${rec}</span>`;
      })
      .join("");

    const tr = document.createElement("tr");
    if (isSelected) tr.classList.add("team-row-selected");
    tr.innerHTML = `
      <td class="col-select" data-label="Select"><input type="checkbox" class="team-select-cb" data-name="${escapeHtml(team.team_name)}" ${isSelected ? "checked" : ""}></td>
      <td data-label="Team">${escapeHtml(team.team_name)}</td>
      <td data-label="City/State">${escapeHtml(team.city_state || "")}</td>
      <td class="col-ncs record-cell" data-label="NCS">${escapeHtml(team.ncs_record || "—")}</td>
      <td class="col-usssa record-cell" data-label="USSSA">${escapeHtml(team.usssa_record || "—")}</td>
      <td class="col-pg record-cell" data-label="Perfect Game">${escapeHtml(team.perfect_game_record || "—")}</td>
      <td class="record-cell record-cumulative" data-label="Cumulative">${escapeHtml(team.cumulative_record || "—")}</td>
      <td class="win-pct" data-label="Win%">${formatWinPct(team.win_pct)}</td>
      <td class="win-pct" data-label="Games">${team.total_games}</td>
      <td class="appearance-list" data-label="Tournaments">${appearanceNames || '<span class="subtle">—</span>'}</td>
    `;
    teamAnalysisRowsEl.appendChild(tr);
  }
  // Bind checkbox events
  teamAnalysisRowsEl.querySelectorAll(".team-select-cb").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) analysisSelectedTeams.add(cb.dataset.name);
      else analysisSelectedTeams.delete(cb.dataset.name);
      updateAnalysisCompareBtn();
      renderTeamAnalysisRows(teamAnalysisData);
    });
  });
}

async function loadTeamAnalysis() {
  if (!teamAnalysisRowsEl) return;
  const age = (analysisAgeFilterEl ? analysisAgeFilterEl.value : "") || (ageFilter ? ageFilter.value : "");
  const season = analysisSeasonFilterEl ? analysisSeasonFilterEl.value : "";
  const params = new URLSearchParams();
  if (age) params.set("age", age);
  if (season) params.set("season", season);
  const paramStr = params.toString() ? `?${params.toString()}` : "";
  try {
    const data = await api(`/api/team-analysis${paramStr}`);
    teamAnalysisData = data.teams || [];
    teamAnalysisLoaded = true;
    if (teamAnalysisNote) teamAnalysisNote.textContent = data.note || "";
    populateAnalysisTournamentFilter(data.tournaments || []);
    renderTeamAnalysisRows(teamAnalysisData);
  } catch {
    if (teamAnalysisRowsEl) {
      teamAnalysisRowsEl.innerHTML = '<tr><td colspan="10" class="subtle">Could not load team analysis.</td></tr>';
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

function populateAnalysisTournamentFilter(tournaments) {
  if (!analysisTournamentFilterEl) return;
  const current = analysisTournamentFilterEl.value;
  while (analysisTournamentFilterEl.options.length > 1) analysisTournamentFilterEl.remove(1);
  const sorted = [...tournaments].sort((a, b) => (a.start_date || "").localeCompare(b.start_date || ""));
  for (const t of sorted) {
    const opt = document.createElement("option");
    opt.value = String(t.id);
    opt.textContent = t.name + (t.start_date ? ` (${t.start_date})` : "");
    analysisTournamentFilterEl.appendChild(opt);
  }
  if ([...analysisTournamentFilterEl.options].some((o) => o.value === current)) {
    analysisTournamentFilterEl.value = current;
  }
}

if (analysisTeamSearchEl) analysisTeamSearchEl.addEventListener("input", () => renderTeamAnalysisRows(teamAnalysisData));
if (analysisMinGamesEl) analysisMinGamesEl.addEventListener("change", () => renderTeamAnalysisRows(teamAnalysisData));
if (analysisTournamentFilterEl) analysisTournamentFilterEl.addEventListener("change", () => renderTeamAnalysisRows(teamAnalysisData));
if (teamAnalysisRowsEl) teamAnalysisRowsEl.addEventListener("click", (e) => {
  const chip = e.target.closest(".appearance-chip--clickable");
  if (!chip || !analysisTournamentFilterEl) return;
  const id = chip.dataset.tournamentId;
  analysisTournamentFilterEl.value = analysisTournamentFilterEl.value === id ? "" : id;
  renderTeamAnalysisRows(teamAnalysisData);
});
if (analysisCompareBtnEl) analysisCompareBtnEl.addEventListener("click", () => {
  analysisCompareMode = true;
  renderTeamAnalysisRows(teamAnalysisData);
});
if (analysisClearSelectionEl) analysisClearSelectionEl.addEventListener("click", () => {
  analysisSelectedTeams.clear();
  analysisCompareMode = false;
  updateAnalysisCompareBtn();
  renderTeamAnalysisRows(teamAnalysisData);
});

// Inline age selectors in each stats view
if (analysisAgeFilterEl) {
  analysisAgeFilterEl.addEventListener("change", () => {
    teamAnalysisLoaded = false;
    loadTeamAnalysis();
  });
}
if (statsAgeFilterEl) {
  statsAgeFilterEl.addEventListener("change", () => {
    teamStatsData = [];
    loadTeamStats();
  });
}
if (analysisSeasonFilterEl) {
  analysisSeasonFilterEl.addEventListener("change", () => {
    teamAnalysisLoaded = false;
    loadTeamAnalysis();
  });
}
if (statsSeasonFilterEl) {
  statsSeasonFilterEl.addEventListener("change", () => {
    teamStatsData = [];
    loadTeamStats();
  });
}

// Toolbar age filter: sync inline selects so they stay consistent
if (ageFilter) {
  ageFilter.addEventListener("change", () => {
    if (analysisAgeFilterEl) analysisAgeFilterEl.value = ageFilter.value;
    if (statsAgeFilterEl)    statsAgeFilterEl.value    = ageFilter.value;
    if (activeView === "teams-analysis") { teamAnalysisLoaded = false; loadTeamAnalysis(); }
    if (activeView === "teams-stats")    { teamStatsData = []; loadTeamStats(); }
  });
}

// ── Settings view ────────────────────────────────────────────────────────────

function _settingsShowMsg(elId, text, type) {
  const el = document.querySelector(`#${elId}`);
  if (!el) return;
  el.textContent = text;
  el.className = `settings-msg ${type} visible`;
  setTimeout(() => el.classList.remove("visible"), 4000);
}

function _settingsPixelHue(r, g, b) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  if (d === 0) return 0;
  let h = max === r ? ((g - b) / d % 6) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return Math.round(h * 60 + 360) % 360;
}

function _settingsExtractColors(imageData) {
  const { data } = imageData;
  const buckets = {};
  for (let i = 0; i < data.length; i += 16) {
    const r = data[i], g = data[i + 1], b = data[i + 2], a = data[i + 3];
    if (a < 128) continue;
    const brightness = (r + g + b) / 3;
    const maxC = Math.max(r, g, b);
    const sat = maxC === 0 ? 0 : (maxC - Math.min(r, g, b)) / maxC;
    if (brightness > 230 || brightness < 20 || sat < 0.15) continue;
    const key = Math.round(_settingsPixelHue(r, g, b) / 30) * 30;
    if (!buckets[key]) buckets[key] = { count: 0, r: 0, g: 0, b: 0 };
    buckets[key].count++;
    buckets[key].r += r; buckets[key].g += g; buckets[key].b += b;
  }
  return Object.values(buckets)
    .filter((b) => b.count >= 5)
    .sort((a, b) => b.count - a.count)
    .slice(0, 3)
    .map((b) => rgbToHex({ r: Math.round(b.r / b.count), g: Math.round(b.g / b.count), b: Math.round(b.b / b.count) }));
}

function _settingsUpdatePreview() {
  const cp = document.querySelector("#settingsColorPrimary");
  const cs = document.querySelector("#settingsColorSecondary");
  const ca = document.querySelector("#settingsColorAccent");
  const strip = document.querySelector("#settingsPreviewStrip");
  if (!cp || !cs || !ca || !strip) return;
  strip.style.background = `linear-gradient(90deg, ${cp.value}, ${cs.value}, ${ca.value})`;
}

function loadSettingsView() {
  const s = currentTeamSettings;
  if (!s) return;

  const dn = document.querySelector("#settingsDisplayName");
  const sl = document.querySelector("#settingsSlug");
  const age = document.querySelector("#settingsAgeDivision");
  const radius = document.querySelector("#settingsRadius");
  const home = document.querySelector("#settingsHomeLabel");
  const cp = document.querySelector("#settingsColorPrimary");
  const cs = document.querySelector("#settingsColorSecondary");
  const ca = document.querySelector("#settingsColorAccent");

  if (dn)     dn.value     = s.team_display_name || "";
  if (sl)     sl.value     = s.team_slug || "";
  if (age)    age.value    = s.target_age_division || "8U";
  if (radius) radius.value = s.radius_miles || "200";
  if (home)   home.value   = s.home_label || "";
  if (cp)     cp.value     = s.brand_primary   || "#6750A4";
  if (cs)     cs.value     = s.brand_secondary || "#625B71";
  if (ca)     ca.value     = s.brand_accent    || "#7D5260";
  _settingsUpdatePreview();
}

// Settings — save profile
const settingsSaveProfileBtn = document.querySelector("#settingsSaveProfileBtn");
if (settingsSaveProfileBtn) {
  settingsSaveProfileBtn.addEventListener("click", async () => {
    const payload = {
      team_display_name: document.querySelector("#settingsDisplayName")?.value.trim() || "",
      target_age_division: document.querySelector("#settingsAgeDivision")?.value || "",
      radius_miles: document.querySelector("#settingsRadius")?.value || "",
      home_label: document.querySelector("#settingsHomeLabel")?.value.trim() || "",
    };
    try {
      await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
      Object.assign(currentTeamSettings, payload);
      applyTeamBrand(currentTeamSettings);
      _settingsShowMsg("settingsProfileMsg", "Profile saved.", "success");
    } catch {
      _settingsShowMsg("settingsProfileMsg", "Save failed.", "error");
    }
  });
}

// Settings — logo upload & color extraction
const settingsLogoFileEl = document.querySelector("#settingsLogoFile");
if (settingsLogoFileEl) {
  settingsLogoFileEl.addEventListener("change", () => {
    const file = settingsLogoFileEl.files[0];
    if (!file) return;
    const nameEl = document.querySelector("#settingsLogoFileName");
    if (nameEl) nameEl.textContent = file.name;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      const img = new Image();
      img.onload = () => {
        const maxDim = 128;
        const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
        const w = Math.round(img.width * scale), h = Math.round(img.height * scale);
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        const colors = _settingsExtractColors(canvas.getContext("2d").getImageData(0, 0, w, h));
        const [c0, c1, c2] = colors;
        const cp = document.querySelector("#settingsColorPrimary");
        const cs = document.querySelector("#settingsColorSecondary");
        const ca = document.querySelector("#settingsColorAccent");
        if (c0 && cp) cp.value = c0;
        if (c1 && cs) cs.value = c1;
        if (c2 && ca) ca.value = c2;
        else if (c0 && ca) ca.value = c0;
        _settingsUpdatePreview();
        if (currentTeamSettings) {
          currentTeamSettings._pendingLogoUrl = dataUrl.length < 200_000 ? dataUrl : "";
        }
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  });
}

[
  document.querySelector("#settingsColorPrimary"),
  document.querySelector("#settingsColorSecondary"),
  document.querySelector("#settingsColorAccent"),
].forEach((el) => { if (el) el.addEventListener("input", _settingsUpdatePreview); });

// Settings — save branding
const settingsSaveBrandBtn = document.querySelector("#settingsSaveBrandBtn");
if (settingsSaveBrandBtn) {
  settingsSaveBrandBtn.addEventListener("click", async () => {
    const cp = document.querySelector("#settingsColorPrimary")?.value || "#6750A4";
    const cs = document.querySelector("#settingsColorSecondary")?.value || "#625B71";
    const ca = document.querySelector("#settingsColorAccent")?.value || "#7D5260";
    const payload = { brand_primary: cp, brand_secondary: cs, brand_accent: ca };
    const pending = currentTeamSettings?._pendingLogoUrl;
    if (pending !== undefined) payload.logo_url = pending;
    try {
      await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
      Object.assign(currentTeamSettings, { brand_primary: cp, brand_secondary: cs, brand_accent: ca });
      if (pending !== undefined) {
        currentTeamSettings.logo_url = pending;
        delete currentTeamSettings._pendingLogoUrl;
      }
      applyTeamBrand(currentTeamSettings);
      _settingsShowMsg("settingsBrandMsg", "Branding saved.", "success");
    } catch {
      _settingsShowMsg("settingsBrandMsg", "Save failed.", "error");
    }
  });
}

// Settings — change password
const settingsSavePwBtn = document.querySelector("#settingsSavePwBtn");
if (settingsSavePwBtn) {
  settingsSavePwBtn.addEventListener("click", async () => {
    const current = document.querySelector("#settingsCurrentPw")?.value || "";
    const next    = document.querySelector("#settingsNewPw")?.value || "";
    const confirm = document.querySelector("#settingsConfirmPw")?.value || "";
    if (next !== confirm) {
      _settingsShowMsg("settingsPwMsg", "New passwords do not match.", "error");
      return;
    }
    if (next.length < 8) {
      _settingsShowMsg("settingsPwMsg", "Password must be at least 8 characters.", "error");
      return;
    }
    try {
      await api("/api/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next, confirm_password: confirm }),
      });
      ["#settingsCurrentPw", "#settingsNewPw", "#settingsConfirmPw"].forEach((sel) => {
        const el = document.querySelector(sel);
        if (el) el.value = "";
      });
      _settingsShowMsg("settingsPwMsg", "Password updated.", "success");
    } catch (err) {
      _settingsShowMsg("settingsPwMsg", err.message || "Update failed.", "error");
    }
  });
}

// Settings — delete team
const settingsDeleteBtn        = document.querySelector("#settingsDeleteBtn");
const settingsDeleteConfirmDiv = document.querySelector("#settingsDeleteConfirm");
const settingsDeleteCancelBtn  = document.querySelector("#settingsDeleteCancelBtn");
const settingsDeleteConfirmBtn = document.querySelector("#settingsDeleteConfirmBtn");

if (settingsDeleteBtn) {
  settingsDeleteBtn.addEventListener("click", () => {
    if (settingsDeleteBtn) settingsDeleteBtn.hidden = true;
    if (settingsDeleteConfirmDiv) settingsDeleteConfirmDiv.hidden = false;
  });
}
if (settingsDeleteCancelBtn) {
  settingsDeleteCancelBtn.addEventListener("click", () => {
    if (settingsDeleteBtn) settingsDeleteBtn.hidden = false;
    if (settingsDeleteConfirmDiv) settingsDeleteConfirmDiv.hidden = true;
    const inp = document.querySelector("#settingsDeleteSlugConfirm");
    if (inp) inp.value = "";
  });
}
if (settingsDeleteConfirmBtn) {
  settingsDeleteConfirmBtn.addEventListener("click", async () => {
    const typed = document.querySelector("#settingsDeleteSlugConfirm")?.value.trim() || "";
    const slug  = currentTeamSettings?.team_slug || "";
    if (typed !== slug) {
      _settingsShowMsg("settingsDeleteMsg", "Team code does not match.", "error");
      return;
    }
    try {
      await api("/api/team", { method: "DELETE" });
      window.location.href = "/login";
    } catch (err) {
      _settingsShowMsg("settingsDeleteMsg", err.message || "Delete failed.", "error");
    }
  });
}

// ── Admin view ────────────────────────────────────────────────────────────────

async function loadAdminView() {
  const tbody = document.querySelector("#adminTeamRows");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" class="subtle" style="padding:16px;">Loading…</td></tr>';
  try {
    const teams = await api("/api/admin/teams");
    tbody.innerHTML = "";
    if (!teams.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="subtle" style="padding:16px;">No teams found.</td></tr>';
      return;
    }
    for (const team of teams) {
      tbody.appendChild(_adminTeamRow(team));
    }
  } catch {
    tbody.innerHTML = '<tr><td colspan="5" class="subtle" style="padding:16px;">Failed to load teams.</td></tr>';
  }
}

function _adminTeamRow(team) {
  const tr = document.createElement("tr");
  const created = team.created_at ? team.created_at.slice(0, 10) : "—";
  const isDefault = team.slug === "default";
  tr.innerHTML = `
    <td>${escapeHtml(team.slug)}</td>
    <td>${escapeHtml(team.display_name || "")}</td>
    <td>${created}</td>
    <td>${team.active ? '<span class="admin-badge--active">Active</span>' : '<span class="admin-badge--inactive">Inactive</span>'}</td>
    <td class="col-actions">
      ${isDefault ? "" : `
        <button class="admin-toggle-btn" data-id="${team.id}" data-active="${team.active ? "1" : "0"}" type="button">
          ${team.active ? "Disable" : "Enable"}
        </button>
        <button class="admin-delete-btn" data-id="${team.id}" data-slug="${escapeHtml(team.slug)}" type="button"
          style="color:var(--warn);border-color:var(--warn);background:transparent;">Delete</button>
      `}
    </td>`;
  return tr;
}

const adminTeamRowsEl = document.querySelector("#adminTeamRows");
if (adminTeamRowsEl) {
  adminTeamRowsEl.addEventListener("click", async (e) => {
    const toggleBtn = e.target.closest(".admin-toggle-btn");
    const deleteBtn = e.target.closest(".admin-delete-btn");

    if (toggleBtn) {
      const id = toggleBtn.dataset.id;
      const active = toggleBtn.dataset.active !== "1";
      try {
        await api(`/api/admin/teams/${id}/active`, { method: "PUT", body: JSON.stringify({ active }) });
        loadAdminView();
      } catch { /* ignore */ }
    }

    if (deleteBtn) {
      const slug = deleteBtn.dataset.slug;
      if (!confirm(`Delete team "${slug}"? This cannot be undone.`)) return;
      try {
        await api(`/api/admin/teams/${deleteBtn.dataset.id}`, { method: "DELETE" });
        loadAdminView();
      } catch { /* ignore */ }
    }
  });
}

const adminRefreshBtn = document.querySelector("#adminRefreshBtn");
if (adminRefreshBtn) adminRefreshBtn.addEventListener("click", loadAdminView);

// ── Collapsible filter toggles ────────────────────────────────────────────────

function setupFilterToggle(toggleBtnId, containerSelector) {
  const btn = document.querySelector(`#${toggleBtnId}`);
  if (!btn) return;
  const container = document.querySelector(containerSelector);
  if (!container) return;
  const labelEl = btn.querySelector(".filter-toggle-btn-label") || btn.querySelector("span:last-child");
  btn.addEventListener("click", () => {
    const collapsed = container.classList.toggle("collapsed");
    btn.setAttribute("aria-expanded", String(!collapsed));
    if (labelEl) labelEl.textContent = collapsed ? "Show" : "Hide";
  });
}

setupFilterToggle("toolbarToggle", ".toolbar");
setupFilterToggle("analysisFiltersToggle", ".inline-filters");

// ── Init ─────────────────────────────────────────────────────────────────────

initTheme();
setDefaultDateFilters();
loadSettings()
  .then(loadDivisions)
  .then(() => Promise.all([loadTournaments(), loadTeamStatsMap()]));
