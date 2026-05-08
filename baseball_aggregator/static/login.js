// Login page JS: signup form validation, logo color extraction, live preview.
// Depends on utils.js being loaded first (teamThemeTokens, rgbToHex).

(function () {
  "use strict";

  const setupPanel      = document.getElementById("setupPanel");
  const signupForm      = document.getElementById("signupForm");
  const slugInput       = document.getElementById("slugInput");
  const slugError       = document.getElementById("slugError");
  const pwInput         = document.getElementById("pwInput");
  const pw2Input        = document.getElementById("pw2Input");
  const pwError         = document.getElementById("pwError");
  const logoFile        = document.getElementById("logoFile");
  const logoFileName    = document.getElementById("logoFileName");
  const logoUrlInput    = document.getElementById("logoUrlInput");
  const colorPrimary    = document.getElementById("colorPrimary");
  const colorSecondary  = document.getElementById("colorSecondary");
  const colorAccent     = document.getElementById("colorAccent");
  const previewStrip    = document.getElementById("signupPreview");

  if (!setupPanel || !signupForm) return;

  // ── Live preview ───────────────────────────────────────────────────────────

  function updatePreview() {
    if (!colorPrimary || !colorSecondary || !colorAccent) return;
    const settings = {
      brand_primary:   colorPrimary.value,
      brand_secondary: colorSecondary.value,
      brand_accent:    colorAccent.value,
    };
    const mode = document.documentElement.getAttribute("data-theme") || "dark";
    const tokens = teamThemeTokens(settings, mode);
    const root = document.documentElement;
    for (const [key, value] of Object.entries(tokens)) {
      root.style.setProperty(key, value);
    }
    if (previewStrip) {
      previewStrip.style.background =
        `linear-gradient(90deg, ${settings.brand_primary}, ${settings.brand_secondary}, ${settings.brand_accent})`;
    }
  }

  if (colorPrimary)   colorPrimary.addEventListener("input", updatePreview);
  if (colorSecondary) colorSecondary.addEventListener("input", updatePreview);
  if (colorAccent)    colorAccent.addEventListener("input", updatePreview);

  // Run once on load so the preview strip reflects default colors
  updatePreview();

  // ── Color extraction (Canvas API) ─────────────────────────────────────────

  function pixelHue(r, g, b) {
    const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    if (d === 0) return 0;
    let h = max === r ? ((g - b) / d % 6) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return Math.round(h * 60 + 360) % 360;
  }

  function extractDominantColors(imageData) {
    const { data } = imageData;
    const buckets = {};
    for (let i = 0; i < data.length; i += 16) {
      const r = data[i], g = data[i + 1], b = data[i + 2], a = data[i + 3];
      if (a < 128) continue;
      const brightness = (r + g + b) / 3;
      const maxC = Math.max(r, g, b);
      const sat = maxC === 0 ? 0 : (maxC - Math.min(r, g, b)) / maxC;
      if (brightness > 230 || brightness < 20 || sat < 0.15) continue;
      const key = Math.round(pixelHue(r, g, b) / 30) * 30;
      if (!buckets[key]) buckets[key] = { count: 0, r: 0, g: 0, b: 0 };
      buckets[key].count++;
      buckets[key].r += r;
      buckets[key].g += g;
      buckets[key].b += b;
    }
    return Object.values(buckets)
      .filter(b => b.count >= 5)
      .sort((a, b) => b.count - a.count)
      .slice(0, 3)
      .map(b => rgbToHex({ r: Math.round(b.r / b.count), g: Math.round(b.g / b.count), b: Math.round(b.b / b.count) }));
  }

  function applyExtractedColors(colors) {
    const [c0, c1, c2] = colors;
    if (c0 && colorPrimary)   colorPrimary.value   = c0;
    if (c1 && colorSecondary) colorSecondary.value = c1;
    if (c2 && colorAccent)    colorAccent.value    = c2;
    else if (c0 && colorAccent) colorAccent.value  = c0;
    updatePreview();
  }

  if (logoFile) {
    logoFile.addEventListener("change", () => {
      const file = logoFile.files[0];
      if (!file) return;
      if (logoFileName) logoFileName.textContent = file.name;

      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target.result;

        // Persist small logos as data URLs
        if (logoUrlInput) {
          logoUrlInput.value = dataUrl.length < 200_000 ? dataUrl : "";
        }

        // Extract colors via canvas
        const img = new Image();
        img.onload = () => {
          const maxDim = 128;
          const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
          const w = Math.round(img.width * scale);
          const h = Math.round(img.height * scale);
          const canvas = document.createElement("canvas");
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, w, h);
          const imageData = ctx.getImageData(0, 0, w, h);
          const colors = extractDominantColors(imageData);
          if (colors.length) applyExtractedColors(colors);
        };
        img.src = dataUrl;
      };
      reader.readAsDataURL(file);
    });
  }

  // ── Client-side validation ─────────────────────────────────────────────────

  const SLUG_RE = /^[a-z0-9][a-z0-9\-]{1,29}$/;

  function showError(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.hidden = !msg;
  }

  if (slugInput) {
    slugInput.addEventListener("input", () => {
      const v = slugInput.value.toLowerCase();
      slugInput.value = v;
      if (v && !SLUG_RE.test(v)) {
        showError(slugError, "Use 2–30 lowercase letters, numbers, or hyphens.");
      } else {
        showError(slugError, "");
      }
    });
  }

  if (pw2Input) {
    pw2Input.addEventListener("input", () => {
      if (pw2Input.value && pwInput && pw2Input.value !== pwInput.value) {
        showError(pwError, "Passwords do not match.");
      } else {
        showError(pwError, "");
      }
    });
  }

  if (signupForm) {
    signupForm.addEventListener("submit", (e) => {
      let ok = true;

      const slug = slugInput ? slugInput.value.trim() : "";
      if (!SLUG_RE.test(slug) || slug === "default") {
        showError(slugError, "Valid team code required (2–30 lowercase letters, numbers, hyphens).");
        ok = false;
      }

      if (pw2Input && pwInput && pw2Input.value !== pwInput.value) {
        showError(pwError, "Passwords do not match.");
        ok = false;
      }

      if (!ok) e.preventDefault();
    });
  }
}());
