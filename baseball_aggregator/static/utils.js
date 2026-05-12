// Pure utility functions shared between app.js and the unit test suite.
// Loaded as a plain <script> before app.js so all functions are global.
// The unit tests load this file via Node vm.Script — no DOM required.

function sourceLabel(source) {
  return { ncs: "NCS", usssa: "USSSA", perfect_game: "Perfect Game" }[source] || source;
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Skill level mapping:
//   USSSA     NCS              PG
//   Major  -> Elite/National   Major
//   AAA    -> High Comp        AAA
//   AA     -> Middle Comp      AA
//   A      -> Developmental    —
//   D1/D2/D3 (NCS only)
function skillLevel(source, division) {
  const d = (division || "").toLowerCase();
  if (source === "usssa") {
    if (d.includes("major"))          return "Elite / National";
    if (d.includes("aaa"))            return "High Competitive";
    if (d.includes("aa"))             return "Middle Competitive";
    if (/\ba\b/.test(d))              return "Developmental";
  } else if (source === "ncs") {
    if (d.includes("d1") || d.includes("division 1")) return "High Competitive";
    if (d.includes("d2") || d.includes("division 2")) return "Middle Competitive";
    if (d.includes("d3") || d.includes("division 3")) return "Developmental";
  } else if (source === "perfect_game") {
    if (d.includes("major"))          return "Elite / National";
    if (d.includes("aaa"))            return "High Competitive";
    if (d.includes("aa"))             return "Middle Competitive";
  }
  return null;
}

function statusClass(status) {
  if (!status || status === "Watch") return "status-open";
  return `status-${String(status).toLowerCase()}`;
}

function normalizeHex(value, fallback) {
  const raw = String(value || "").trim();
  const match = raw.match(/^#?([0-9a-f]{6})$/i);
  return match ? `#${match[1].toLowerCase()}` : fallback;
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
  return `#${[rgb.r, rgb.g, rgb.b]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}

function mixHex(color, base, baseWeight) {
  const a = hexToRgb(color);
  const b = hexToRgb(base);
  const w = Math.max(0, Math.min(1, baseWeight));
  return rgbToHex({
    r: Math.round(a.r * (1 - w) + b.r * w),
    g: Math.round(a.g * (1 - w) + b.g * w),
    b: Math.round(a.b * (1 - w) + b.b * w),
  });
}

function relativeLuminance(hex) {
  const { r, g, b } = hexToRgb(hex);
  const values = [r, g, b].map((ch) => {
    const n = ch / 255;
    return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
  });
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
}

function contrastRatio(first, second) {
  const light = Math.max(relativeLuminance(first), relativeLuminance(second));
  const dark  = Math.min(relativeLuminance(first), relativeLuminance(second));
  return (light + 0.05) / (dark + 0.05);
}

function teamThemeTokens(settings, mode) {
  const primary   = normalizeHex(settings.brand_primary,   "#0f766e");
  const secondary = normalizeHex(settings.brand_secondary, "#115e59");
  const accent    = normalizeHex(settings.brand_accent,    secondary);
  const darkMode  = mode === "dark";
  const pageBase    = darkMode ? "#080808" : "#eef3f8";
  const surfaceBase = darkMode ? "#131313" : "#ffffff";
  const panelBase   = darkMode ? "#191919" : "#edf2f7";
  const inputBase   = darkMode ? "#0c0c0c" : "#ffffff";
  const inkBase     = darkMode ? "#f3f7fc" : "#142133";
  const mutedBase   = darkMode ? "#a9b9cb" : "#56687b";
  const linkBase    = darkMode ? "#75d8ff" : "#0f4fd8";
  const lineBase    = darkMode ? "#2a2a2a" : "#cdd8e5";
  const brandOnPrimary = contrastRatio(primary, "#ffffff") >= 4.5 ? "#ffffff" : "#07101b";

  return {
    "--brand-primary":    primary,
    "--brand-secondary":  secondary,
    "--brand-accent":     accent,
    "--brand-on-primary": brandOnPrimary,
    "--accent":           primary,
    "--accent-dark":      mixHex(primary, "#000000", darkMode ? 0.24 : 0.18),
    "--focus":            contrastRatio(accent, pageBase) >= 3 ? accent : secondary,
    "--page":             mixHex(primary, pageBase,    darkMode ? 0.82 : 0.92),
    "--surface":          mixHex(primary, surfaceBase, darkMode ? 0.78 : 0.96),
    "--panel":            mixHex(primary, panelBase,   darkMode ? 0.70 : 0.90),
    "--input-bg":         mixHex(primary, inputBase,   darkMode ? 0.86 : 0.98),
    "--detail":           mixHex(primary, darkMode ? "#0d0d0d" : "#f6f9fc", darkMode ? 0.82 : 0.96),
    "--line":             mixHex(secondary, lineBase,  darkMode ? 0.72 : 0.82),
    "--pill":             mixHex(primary, darkMode ? "#222222" : "#dce6ef", darkMode ? 0.74 : 0.86),
    "--ink":              inkBase,
    "--muted":            mutedBase,
    "--th-ink":           darkMode ? "#dce8f5" : "#273648",
    "--link":             mixHex(secondary, linkBase, darkMode ? 0.30 : 0.62),
    "--link-hover":       mixHex(accent, linkBase,    darkMode ? 0.20 : 0.50),
    "--sidebar-bg":       darkMode
      ? mixHex(primary,   "#030303", 0.88)
      : mixHex(secondary, "#000000", 0.1),
  };
}

function formatWinPct(value) {
  if (value === null || value === undefined || isNaN(value)) return "—";
  return value.toFixed(3).replace(/^0/, "");
}
