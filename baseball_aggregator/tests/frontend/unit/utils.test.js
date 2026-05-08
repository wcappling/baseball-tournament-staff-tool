/**
 * Unit tests for utils.js pure functions.
 * Uses Node vm.Script to load the plain-<script> globals without ESM refactor.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { createContext, Script } from "vm";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(resolve(__dirname, "../../../static/utils.js"), "utf8");

let ctx;
beforeAll(() => {
  ctx = createContext({});
  new Script(src).runInContext(ctx);
});

// ─── sourceLabel ──────────────────────────────────────────────────────────────

describe("sourceLabel", () => {
  it("maps ncs", () => expect(ctx.sourceLabel("ncs")).toBe("NCS"));
  it("maps usssa", () => expect(ctx.sourceLabel("usssa")).toBe("USSSA"));
  it("maps perfect_game", () =>
    expect(ctx.sourceLabel("perfect_game")).toBe("Perfect Game"));
  it("passes through unknown sources", () =>
    expect(ctx.sourceLabel("other")).toBe("other"));
});

// ─── formatDate ───────────────────────────────────────────────────────────────

describe("formatDate", () => {
  it("returns TBD when no start", () => expect(ctx.formatDate(null, null)).toBe("TBD"));
  it("returns start only when end equals start", () =>
    expect(ctx.formatDate("2026-06-01", "2026-06-01")).toBe("2026-06-01"));
  it("returns range when end differs", () =>
    expect(ctx.formatDate("2026-06-01", "2026-06-03")).toBe("2026-06-01 - 2026-06-03"));
  it("returns start only when no end", () =>
    expect(ctx.formatDate("2026-06-01", null)).toBe("2026-06-01"));
});

// ─── formatDistance ───────────────────────────────────────────────────────────

describe("formatDistance", () => {
  it("returns Unknown for null", () =>
    expect(ctx.formatDistance(null)).toBe("Unknown"));
  it("returns Unknown for undefined", () =>
    expect(ctx.formatDistance(undefined)).toBe("Unknown"));
  it("rounds and appends mi", () =>
    expect(ctx.formatDistance(42.7)).toBe("43 mi"));
  it("rounds down", () =>
    expect(ctx.formatDistance(99.2)).toBe("99 mi"));
  it("handles zero", () =>
    expect(ctx.formatDistance(0)).toBe("0 mi"));
});

// ─── escapeHtml ───────────────────────────────────────────────────────────────

describe("escapeHtml", () => {
  it("escapes ampersand", () =>
    expect(ctx.escapeHtml("a&b")).toBe("a&amp;b"));
  it("escapes less-than", () =>
    expect(ctx.escapeHtml("<script>")).toBe("&lt;script&gt;"));
  it("escapes double-quote", () =>
    expect(ctx.escapeHtml('"hello"')).toBe("&quot;hello&quot;"));
  it("escapes single-quote", () =>
    expect(ctx.escapeHtml("it's")).toBe("it&#039;s"));
  it("returns empty string for null", () =>
    expect(ctx.escapeHtml(null)).toBe(""));
  it("returns empty string for undefined", () =>
    expect(ctx.escapeHtml(undefined)).toBe(""));
  it("does not double-escape already-safe text", () =>
    expect(ctx.escapeHtml("hello world")).toBe("hello world"));
  it("escapes XSS payload", () =>
    expect(ctx.escapeHtml('<img src=x onerror="alert(1)">')).not.toContain("<"));
});

// ─── skillLevel ───────────────────────────────────────────────────────────────

describe("skillLevel — USSSA", () => {
  it("Major → Elite / National", () =>
    expect(ctx.skillLevel("usssa", "12U Major")).toBe("Elite / National"));
  it("AAA → High Competitive", () =>
    expect(ctx.skillLevel("usssa", "12U AAA")).toBe("High Competitive"));
  it("AA → Middle Competitive", () =>
    expect(ctx.skillLevel("usssa", "12U AA")).toBe("Middle Competitive"));
  it("A → Developmental", () =>
    expect(ctx.skillLevel("usssa", "10U A")).toBe("Developmental"));
  it("unknown → null", () =>
    expect(ctx.skillLevel("usssa", "12U Open")).toBeNull());
});

describe("skillLevel — NCS", () => {
  it("D1 → High Competitive", () =>
    expect(ctx.skillLevel("ncs", "12U D1")).toBe("High Competitive"));
  it("D2 → Middle Competitive", () =>
    expect(ctx.skillLevel("ncs", "12U D2")).toBe("Middle Competitive"));
  it("D3 → Developmental", () =>
    expect(ctx.skillLevel("ncs", "12U D3")).toBe("Developmental"));
  it("Division 1 long form", () =>
    expect(ctx.skillLevel("ncs", "12U Division 1")).toBe("High Competitive"));
});

describe("skillLevel — Perfect Game", () => {
  it("Major → Elite / National", () =>
    expect(ctx.skillLevel("perfect_game", "12U Major")).toBe("Elite / National"));
  it("AAA → High Competitive", () =>
    expect(ctx.skillLevel("perfect_game", "12U AAA")).toBe("High Competitive"));
  it("AA → Middle Competitive", () =>
    expect(ctx.skillLevel("perfect_game", "12U AA")).toBe("Middle Competitive"));
});

describe("skillLevel — fallback", () => {
  it("unknown source → null", () =>
    expect(ctx.skillLevel("other", "Major")).toBeNull());
  it("empty division → null", () =>
    expect(ctx.skillLevel("usssa", "")).toBeNull());
});

// ─── statusClass ──────────────────────────────────────────────────────────────

describe("statusClass", () => {
  it("null → status-open", () => expect(ctx.statusClass(null)).toBe("status-open"));
  it("Watch → status-open", () => expect(ctx.statusClass("Watch")).toBe("status-open"));
  it("Interested → status-interested", () =>
    expect(ctx.statusClass("Interested")).toBe("status-interested"));
  it("Registered → status-registered", () =>
    expect(ctx.statusClass("Registered")).toBe("status-registered"));
  it("Declined → status-declined", () =>
    expect(ctx.statusClass("Declined")).toBe("status-declined"));
});

// ─── normalizeHex ─────────────────────────────────────────────────────────────

describe("normalizeHex", () => {
  it("returns lowercase with #", () =>
    expect(ctx.normalizeHex("#FF0000", "#000000")).toBe("#ff0000"));
  it("adds missing # prefix", () =>
    expect(ctx.normalizeHex("00ff00", "#000000")).toBe("#00ff00"));
  it("returns fallback for invalid", () =>
    expect(ctx.normalizeHex("zzz", "#aabbcc")).toBe("#aabbcc"));
  it("returns fallback for empty", () =>
    expect(ctx.normalizeHex("", "#123456")).toBe("#123456"));
});

// ─── hexToRgb / rgbToHex ──────────────────────────────────────────────────────

describe("hexToRgb", () => {
  it("parses white", () =>
    expect(ctx.hexToRgb("#ffffff")).toEqual({ r: 255, g: 255, b: 255 }));
  it("parses black", () =>
    expect(ctx.hexToRgb("#000000")).toEqual({ r: 0, g: 0, b: 0 }));
  it("parses a mid color", () =>
    expect(ctx.hexToRgb("#0f766e")).toEqual({ r: 15, g: 118, b: 110 }));
});

describe("rgbToHex", () => {
  it("converts white", () =>
    expect(ctx.rgbToHex({ r: 255, g: 255, b: 255 })).toBe("#ffffff"));
  it("converts black", () =>
    expect(ctx.rgbToHex({ r: 0, g: 0, b: 0 })).toBe("#000000"));
});

describe("hexToRgb / rgbToHex roundtrip", () => {
  it("roundtrips teal brand color", () => {
    const hex = "#0f766e";
    expect(ctx.rgbToHex(ctx.hexToRgb(hex))).toBe(hex);
  });
});

// ─── mixHex ───────────────────────────────────────────────────────────────────

describe("mixHex", () => {
  it("weight=0 returns color unchanged", () =>
    expect(ctx.mixHex("#ff0000", "#0000ff", 0)).toBe("#ff0000"));
  it("weight=1 returns base unchanged", () =>
    expect(ctx.mixHex("#ff0000", "#0000ff", 1)).toBe("#0000ff"));
  it("weight=0.5 is midpoint of red and blue", () =>
    // Math.round(127.5) === 128 === 0x80 in JS
    expect(ctx.mixHex("#ff0000", "#0000ff", 0.5)).toBe("#800080"));
  it("clamps weight below 0", () =>
    expect(ctx.mixHex("#ff0000", "#0000ff", -1)).toBe("#ff0000"));
  it("clamps weight above 1", () =>
    expect(ctx.mixHex("#ff0000", "#0000ff", 2)).toBe("#0000ff"));
});

// ─── relativeLuminance ────────────────────────────────────────────────────────

describe("relativeLuminance", () => {
  it("black = 0", () =>
    expect(ctx.relativeLuminance("#000000")).toBeCloseTo(0));
  it("white = 1", () =>
    expect(ctx.relativeLuminance("#ffffff")).toBeCloseTo(1));
  it("mid-gray is between 0 and 1", () => {
    const l = ctx.relativeLuminance("#808080");
    expect(l).toBeGreaterThan(0);
    expect(l).toBeLessThan(1);
  });
});

// ─── contrastRatio ────────────────────────────────────────────────────────────

describe("contrastRatio", () => {
  it("black vs white = 21", () =>
    expect(ctx.contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 0));
  it("same color = 1", () =>
    expect(ctx.contrastRatio("#123456", "#123456")).toBeCloseTo(1));
  it("is symmetric", () => {
    const a = ctx.contrastRatio("#0f766e", "#ffffff");
    const b = ctx.contrastRatio("#ffffff", "#0f766e");
    expect(a).toBeCloseTo(b);
  });
  it("white-on-teal passes WCAG AA (≥4.5) or not — just verifies numeric", () => {
    const ratio = ctx.contrastRatio("#0f766e", "#ffffff");
    expect(ratio).toBeGreaterThan(1);
    expect(ratio).toBeLessThan(21);
  });
});

// ─── formatWinPct ─────────────────────────────────────────────────────────────

describe("formatWinPct", () => {
  it("null → —", () => expect(ctx.formatWinPct(null)).toBe("—"));
  it("undefined → —", () => expect(ctx.formatWinPct(undefined)).toBe("—"));
  it("NaN → —", () => expect(ctx.formatWinPct(NaN)).toBe("—"));
  it("0 → .000", () => expect(ctx.formatWinPct(0)).toBe(".000"));
  it("1 → 1.000", () => expect(ctx.formatWinPct(1)).toBe("1.000"));
  it("0.5 → .500", () => expect(ctx.formatWinPct(0.5)).toBe(".500"));
  it("0.333 → .333", () => expect(ctx.formatWinPct(1 / 3)).toBe(".333"));
});

// ─── teamThemeTokens ──────────────────────────────────────────────────────────

describe("teamThemeTokens", () => {
  const settings = {
    brand_primary: "#0f766e",
    brand_secondary: "#115e59",
    brand_accent: "#0f766e",
  };

  it("returns all required CSS variable keys in light mode", () => {
    const tokens = ctx.teamThemeTokens(settings, "light");
    const required = [
      "--brand-primary", "--brand-secondary", "--brand-accent",
      "--brand-on-primary", "--accent", "--accent-dark", "--focus",
      "--page", "--surface", "--panel", "--input-bg", "--detail",
      "--line", "--pill", "--ink", "--muted", "--th-ink", "--link",
      "--link-hover", "--sidebar-bg",
    ];
    for (const key of required) {
      expect(tokens).toHaveProperty(key);
    }
  });

  it("dark mode produces different surface than light mode", () => {
    const light = ctx.teamThemeTokens(settings, "light");
    const dark = ctx.teamThemeTokens(settings, "dark");
    expect(light["--surface"]).not.toBe(dark["--surface"]);
  });

  it("dark mode sidebar is darker than light mode sidebar", () => {
    const light = ctx.teamThemeTokens(settings, "light");
    const dark = ctx.teamThemeTokens(settings, "dark");
    const lightLum = ctx.relativeLuminance(light["--sidebar-bg"]);
    const darkLum = ctx.relativeLuminance(dark["--sidebar-bg"]);
    expect(darkLum).toBeLessThan(lightLum);
  });

  it("uses fallback colors when settings are empty", () => {
    const tokens = ctx.teamThemeTokens({}, "light");
    expect(tokens["--brand-primary"]).toBe("#0f766e");
  });

  it("--brand-on-primary is either white or near-black for contrast", () => {
    const tokens = ctx.teamThemeTokens(settings, "light");
    const onPrimary = tokens["--brand-on-primary"];
    expect(["#ffffff", "#07101b"]).toContain(onPrimary);
  });
});
