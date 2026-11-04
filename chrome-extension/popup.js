import { SENTIMENTS, summarize } from "./batches.js";
import { MAX_COMMENTS, watchVideoId } from "./config.js";

const $ = (id) => document.getElementById(id);
const analyze = $("analyze");
const filter = $("filter");
const theme = $("theme");
const darkPreference = matchMedia("(prefers-color-scheme: dark)");
const labels = { positive: "Positive", neutral: "Neutral", negative: "Negative", skipped: "Skipped" };
let tabId, videoId, stateKey;
let state = { status: "idle", rows: [] };

function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  theme.setAttribute("aria-pressed", String(dark));
  theme.textContent = dark ? "Light" : "Dark";
}

const saved = await chrome.storage.local.get("dark");
setTheme(saved.dark ?? darkPreference.matches);
theme.onclick = async () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  setTheme(dark);
  await chrome.storage.local.set({ dark });
};

function visibleRows() {
  return state.rows.filter((row) => filter.value === "all" || filter.value === (row.sentiment ?? "skipped"));
}

function renderRows() {
  const rows = visibleRows();
  const items = rows.map((row) => {
    const li = document.createElement("li");
    const badge = document.createElement("span");
    const label = row.sentiment ?? "skipped";
    badge.className = "badge " + label;
    badge.textContent = labels[label] + (row.confidence == null ? "" : " · " + Math.round(row.confidence * 100) + "% confidence");
    const text = document.createElement("p");
    text.textContent = row.text;
    li.append(badge, text);
    return li;
  });
  $("comments").replaceChildren(...items);
  $("no-matches").hidden = rows.length > 0;
  $("copy").disabled = $("export").disabled = !rows.length;
}

function render() {
  const summary = summarize(state.rows);
  const running = state.status === "running";
  const messages = {
    idle: "Scroll to the comments on YouTube to load them, then analyze up to " + MAX_COMMENTS + " comments.",
    running: state.total ? "Analyzing " + state.processed + " of " + state.total + " comments…" : "Collecting loaded comments…",
    empty: "No loaded comments found. Scroll to the comments and try again.",
    done: summary.analyzed ? "Analysis complete for the comments loaded on this video." : "The loaded comments contained no usable text.",
    partial: state.error || "Some comments could not be analyzed.",
    error: state.error || "The analysis failed.",
  };
  $("status").textContent = videoId ? messages[state.status] : "Open a YouTube video to analyze its comments.";
  $("count").textContent = state.rows.length ? summary.analyzed + " analyzed" : "";
  analyze.disabled = !videoId || running;
  analyze.textContent = running ? "Analyzing…" : state.rows.length ? "Analyze again" : "Analyze comments";
  $("results").hidden = $("distribution").hidden = !state.rows.length;
  $("chart").replaceChildren(...SENTIMENTS.map((label) => {
    const segment = document.createElement("span");
    segment.className = label;
    segment.style.width = summary.percentages[label] + "%";
    return segment;
  }));
  $("legend").replaceChildren(...SENTIMENTS.map((label) => {
    const entry = document.createElement("li");
    const dot = document.createElement("span");
    dot.className = "dot " + label;
    entry.append(dot, labels[label] + " " + summary.percentages[label].toFixed(1) + "%");
    return entry;
  }));
  $("metadata").textContent = state.rows.length
    ? Math.round(state.latencyMs) + " ms API time · " + summary.skipped + " skipped · Model " + state.modelVersion
    : "";
  renderRows();
}

async function loadTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  tabId = tab?.id;
  videoId = watchVideoId(tab?.url);
  stateKey = "analysis:" + tabId + ":" + videoId;
  const key = stateKey;
  const next = videoId ? await chrome.runtime.sendMessage({ type: "state", tabId, videoId }) : null;
  if (key !== stateKey) return;
  state = next ?? { status: "idle", rows: [] };
  render();
}

analyze.onclick = async () => {
  $("feedback").textContent = "";
  state = { status: "running", rows: [], processed: 0, total: 0 };
  render();
  try {
    const result = await chrome.runtime.sendMessage({ type: "start", tabId, videoId });
    if (!result?.ok) throw new Error("Open a YouTube video and try again.");
  } catch (error) {
    state = { status: "error", error: error.message, rows: [] };
    render();
  }
};

filter.onchange = renderRows;
$("copy").onclick = async () => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(visibleRows(), null, 2));
    $("feedback").textContent = "Copied the filtered results.";
  } catch {
    $("feedback").textContent = "Clipboard unavailable. Use Export JSON instead.";
  }
};
$("export").onclick = () => {
  const rows = visibleRows();
  const data = { videoId, modelVersion: state.modelVersion, summary: summarize(rows), comments: rows };
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "youtube-sentiment-" + videoId + ".json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("feedback").textContent = "Exported the filtered results.";
};

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes[stateKey]?.newValue) {
    state = changes[stateKey].newValue;
    render();
  }
});
chrome.tabs.onUpdated.addListener((id, change) => {
  if (id === tabId && change.url) void loadTab();
});
await loadTab();
