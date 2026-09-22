const TOKEN_STORAGE_KEY = "kabekanji.token";
let token = null; // set during init()
let shortcutUrl = ""; // fetched from /api/app-info during init()

// DOM refs
const $ = (sel) => document.querySelector(sel);

// Header date
// Japanese weekday kanji (Sun–Sat)
const WEEKDAY_KANJI = ["日", "月", "火", "水", "木", "金", "土"];
function updateHeaderDate() {
  const now = new Date();
  const y = document.getElementById("dateYear");
  const m = document.getElementById("dateMonth");
  const d = document.getElementById("dateDay");
  const w = document.getElementById("dateWeekday");
  if (y) y.textContent = now.getFullYear();
  if (m) m.textContent = now.getMonth() + 1;
  if (d) d.textContent = now.getDate();
  if (w) w.textContent = WEEKDAY_KANJI[now.getDay()];
}
updateHeaderDate();
const previewImg = $("#previewImg");
const overlayImg = $("#overlayImg");
const phoneScreen = $("#phoneScreen");
const topLine = $("#topMarginLine");
const bottomLine = $("#bottomMarginLine");

// Sliders
const topSlider = $("#topMargin");
const bottomSlider = $("#bottomMargin");
const topVal = $("#topMarginVal");
const bottomVal = $("#bottomMarginVal");
const recencySlider = $("#recencyWindow");
const recencyVal = $("#recencyWindowVal");

// Screen
const presetSelect = $("#screenPreset");
const customRow = $("#customSizeRow");
const widthInput = $("#screenWidth");
const heightInput = $("#screenHeight");

// Toggles
const toggles = {
  show_gothic: $("#showGothic"),
  show_mincho: $("#showMincho"),
  show_handwritten: $("#showHandwritten"),
  show_sinovi: $("#showSinovi"),
  show_vocabulary: $("#showVocabulary"),
};

// Color pickers
const bgColorInput = $("#bgColor");
const textColorInput = $("#textColor");

// State
let config = {};

// Init
async function init() {
  const [appInfo, resolvedToken] = await Promise.all([
    fetchAppInfo(),
    ensureToken(),
  ]);
  shortcutUrl = appInfo.shortcut_url || "";
  token = resolvedToken;
  config = await fetchConfig(token);
  populateUI();
  updateMarginLines();
  refreshPreview();
}

async function fetchAppInfo() {
  const res = await fetch("/api/app-info");
  if (!res.ok) return { shortcut_url: "" };
  return await res.json();
}

async function ensureToken() {
  const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (stored) {
    // Verify server still knows this token; if not, generate a new one
    const res = await fetch(`/api/config?token=${encodeURIComponent(stored)}`);
    if (res.ok) return stored;
  }
  return await mintToken();
}

async function mintToken() {
  const res = await fetch("/api/tokens", { method: "POST" });
  if (!res.ok) throw new Error(`token mint failed (${res.status})`);
  const { token: newToken } = await res.json();
  localStorage.setItem(TOKEN_STORAGE_KEY, newToken);
  return newToken;
}

async function fetchConfig(t) {
  const res = await fetch(`/api/config?token=${encodeURIComponent(t)}`);
  if (!res.ok) throw new Error(`config fetch failed (${res.status})`);
  return await res.json();
}

function populateUI() {
  topSlider.value = config.top_margin;
  topVal.textContent = config.top_margin;
  bottomSlider.value = config.bottom_margin;
  bottomVal.textContent = config.bottom_margin;
  recencySlider.value = config.recency_window;
  recencyVal.textContent = config.recency_window;

  widthInput.value = config.screen_width;
  heightInput.value = config.screen_height;

  // Match a preset or show custom
  const key = `${config.screen_width}x${config.screen_height}`;
  const option = [...presetSelect.options].find((o) => o.value === key);
  if (option) {
    presetSelect.value = key;
    customRow.classList.add("hidden");
  } else {
    presetSelect.value = "custom";
    customRow.classList.remove("hidden");
  }

  for (const [cfgKey, el] of Object.entries(toggles)) {
    el.checked = config[cfgKey] ?? false;
  }

  bgColorInput.value = config.bg_color || "#121214";
  textColorInput.value = config.text_color || "#F0F0F5";

  updateTokenDisplay();
}

// Margin lines
function updateMarginLines() {
  const screenH = config.screen_height || 2622;
  const frameH = phoneScreen.clientHeight;
  const scale = frameH / screenH;

  const topPx = config.top_margin * scale;
  const bottomPx = config.bottom_margin * scale;

  topLine.style.top = `${topPx}px`;
  topLine.dataset.label = `${config.top_margin}px`;

  bottomLine.style.bottom = `${bottomPx}px`;
  bottomLine.dataset.label = `${config.bottom_margin}px`;
}

// Preview
let previewTimeout = null;

function schedulePreview() {
  clearTimeout(previewTimeout);
  previewTimeout = setTimeout(refreshPreview, 400);
}

async function refreshPreview() {
  if (!token) return;
  const params = new URLSearchParams({ token });
  const char = $("#previewChar")?.value.trim();
  if (char) params.set("char", char);

  const uiConfig = readConfigFromUI();
  const loader = $("#previewLoader");
  const errorEl = $("#previewError");

  previewImg.style.opacity = "0.4";
  errorEl.classList.add("hidden");
  loader.classList.remove("hidden");
  let failed = false;
  try {
    const res = await fetch(`/api/preview?${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(uiConfig),
    });
    if (!res.ok) throw new Error(`preview ${res.status}`);
    const blob = await res.blob();
    const newUrl = URL.createObjectURL(blob);
    const oldUrl = previewImg.src;
    previewImg.src = newUrl;
    if (oldUrl && oldUrl.startsWith("blob:")) URL.revokeObjectURL(oldUrl);
  } catch (e) {
    console.error("Preview failed:", e);
    failed = true;
  } finally {
    previewImg.style.opacity = "1";
    loader.classList.add("hidden");
    if (failed) errorEl.classList.remove("hidden");
  }
}

// Config read from UI
function readConfigFromUI() {
  return {
    screen_width: parseInt(widthInput.value, 10),
    screen_height: parseInt(heightInput.value, 10),
    top_margin: parseInt(topSlider.value, 10),
    bottom_margin: parseInt(bottomSlider.value, 10),
    recency_window: parseInt(recencySlider.value, 10),
    bg_color: bgColorInput.value,
    text_color: textColorInput.value,
    show_gothic: toggles.show_gothic.checked,
    show_mincho: toggles.show_mincho.checked,
    show_handwritten: toggles.show_handwritten.checked,
    show_sinovi: toggles.show_sinovi.checked,
    show_vocabulary: toggles.show_vocabulary.checked,
  };
}

// Save
async function saveConfig() {
  config = readConfigFromUI();
  await fetch(`/api/config?token=${encodeURIComponent(token)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  updateMarginLines();
  refreshPreview();
  updateTokenDisplay();

  const btn = $("#saveConfig");
  const orig = btn.textContent;
  btn.textContent = "Saved";
  setTimeout(() => (btn.textContent = orig), 1200);
}

function updateTokenDisplay() {
  const base = window.location.origin;
  $("#apiToken").textContent = token;
  $("#apiUrl").textContent = `${base}/api/wallpaper?token=${token}`;
  const installBtn = $("#installShortcut");
  const installPlaceholder = $("#installShortcutPlaceholder");
  if (installBtn && installPlaceholder) {
    if (shortcutUrl) {
      installBtn.href = shortcutUrl;
      installBtn.classList.remove("hidden");
      installPlaceholder.classList.add("hidden");
    } else {
      installBtn.classList.add("hidden");
      installPlaceholder.classList.remove("hidden");
    }
  }
}

async function switchToken(newToken) {
  const t = newToken.trim();
  if (!t) return;
  const res = await fetch(`/api/config?token=${encodeURIComponent(t)}`);
  if (!res.ok) {
    flashInvalidToken();
    return;
  }
  token = t;
  localStorage.setItem(TOKEN_STORAGE_KEY, t);
  config = await res.json();
  populateUI();
  updateMarginLines();
  refreshPreview();
}

function flashInvalidToken() {
  const input = $("#loadToken");
  input.classList.add("invalid");
  setTimeout(() => input.classList.remove("invalid"), 1200);
}

// Overlay upload
function handleOverlayUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (ev) => {
    overlayImg.src = ev.target.result;
    overlayImg.classList.remove("hidden");
    $("#clearOverlay").disabled = false;
  };
  reader.readAsDataURL(file);
}

function clearOverlay() {
  overlayImg.src = "";
  overlayImg.classList.add("hidden");
  $("#clearOverlay").disabled = true;
  $("#overlayUpload").value = "";
}

// Copy helper: writes text to clipboard and flashes the given button
async function copyToClipboard(text, btn) {
  const flashOk = () => {
    btn.textContent = "○";
    btn.classList.add("copied");
    setTimeout(() => {
      btn.textContent = "Copy";
      btn.classList.remove("copied");
    }, 1200);
  };
  try {
    await navigator.clipboard.writeText(text);
    flashOk();
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    flashOk();
  }
}

// Event listeners

// Margin sliders: live update lines, debounced preview
topSlider.addEventListener("input", () => {
  config.top_margin = parseInt(topSlider.value, 10);
  topVal.textContent = topSlider.value;
  updateMarginLines();
});
topSlider.addEventListener("change", schedulePreview);

bottomSlider.addEventListener("input", () => {
  config.bottom_margin = parseInt(bottomSlider.value, 10);
  bottomVal.textContent = bottomSlider.value;
  updateMarginLines();
});
bottomSlider.addEventListener("change", schedulePreview);

recencySlider.addEventListener("input", () => {
  recencyVal.textContent = recencySlider.value;
});

// Screen preset
presetSelect.addEventListener("change", () => {
  if (presetSelect.value === "custom") {
    customRow.classList.remove("hidden");
  } else {
    customRow.classList.add("hidden");
    const [w, h] = presetSelect.value.split("x").map(Number);
    widthInput.value = w;
    heightInput.value = h;
    config.screen_width = w;
    config.screen_height = h;
    updateMarginLines();
    schedulePreview();
  }
});

// Custom width/height inputs (only visible when preset is custom)
widthInput.addEventListener("change", () => {
  config.screen_width = parseInt(widthInput.value, 10);
  updateMarginLines();
  schedulePreview();
});
heightInput.addEventListener("change", () => {
  config.screen_height = parseInt(heightInput.value, 10);
  updateMarginLines();
  schedulePreview();
});

// Toggles; live preview on change
Object.values(toggles).forEach((el) => el.addEventListener("change", schedulePreview));

// Color pickers; live preview while dragging (input) and on close (change)
[bgColorInput, textColorInput].forEach((el) => {
  el.addEventListener("input", schedulePreview);
  el.addEventListener("change", schedulePreview);
});

// Buttons
$("#saveConfig").addEventListener("click", saveConfig);
$("#refreshPreview").addEventListener("click", refreshPreview);
$("#overlayUpload").addEventListener("change", handleOverlayUpload);
$("#clearOverlay").addEventListener("click", clearOverlay);
$("#copyUrl").addEventListener("click", (e) =>
  copyToClipboard($("#apiUrl").textContent, e.currentTarget),
);
$("#copyToken").addEventListener("click", (e) =>
  copyToClipboard($("#apiToken").textContent, e.currentTarget),
);
$("#loadTokenBtn").addEventListener("click", () => switchToken($("#loadToken").value));
$("#loadToken").addEventListener("keydown", (e) => {
  if (e.key === "Enter") switchToken(e.currentTarget.value);
});

// Kanji preview input
const previewCharInput = $("#previewChar");
const clearCharBtn = $("#clearChar");

previewCharInput.addEventListener("input", () => {
  // Keep only the last typed character (handles paste of multi-char strings)
  const val = previewCharInput.value;
  if (val.length > 1) previewCharInput.value = val.slice(-1);
  schedulePreview();
});

clearCharBtn.addEventListener("click", () => {
  previewCharInput.value = "";
  refreshPreview();
});

// Resize recalculates margin lines
window.addEventListener("resize", updateMarginLines);

// Pull-me-up floating button (shows when scrolled down; scrolls to preview on click)
const pullMeUpBtn = $("#pullMeUp");
if (pullMeUpBtn) {
  const updatePullMeUp = () => {
    pullMeUpBtn.classList.toggle("visible", window.scrollY > 240);
  };
  window.addEventListener("scroll", updatePullMeUp, { passive: true });
  pullMeUpBtn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  updatePullMeUp();
}

init();
