import { SENTIMENTS, summarize } from "./batches.js";
import { MAX_COMMENTS, watchVideoId } from "./config.js";

const $ = (id) => document.getElementById(id);
const analyze = $("analyze");
const filter = $("filter");
const theme = $("theme");
const overview = document.querySelector(".overview");
const commentList = $("comments");
const darkPreference = matchMedia("(prefers-color-scheme: dark)");
const percent = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });
const labels = { positive: "Positive", neutral: "Neutral", negative: "Negative", skipped: "Skipped" };
let tabId, videoId, stateKey;
let state = { status: "idle", rows: [] };

function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  theme.setAttribute("aria-pressed", String(dark));
  theme.title = dark ? "Switch to light mode" : "Switch to dark mode";
}

const saved = await chrome.storage.local.get("dark");
setTheme(saved.dark ?? darkPreference.matches);
theme.onclick = async () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  setTheme(dark);
  await chrome.storage.local.set({ dark });
};

function selectedFilter() {
  return filter.querySelector("input:checked").value;
}

function resetFilter() {
  filter.querySelector('input[value="all"]').checked = true;
}

function visibleRows() {
  const selected = selectedFilter();
  return selected === "all" ? state.rows : state.rows.filter((row) => (row.sentiment ?? "skipped") === selected);
}

function renderRows() {
  const rows = visibleRows();
  const previousScroll = commentList.scrollTop;
  const items = rows.map((row) => {
    const li = document.createElement("li");
    const meta = document.createElement("div");
    meta.className = "comment-meta";
    const badge = document.createElement("span");
    const label = row.sentiment ?? "skipped";
    badge.className = "badge " + label;
    badge.textContent = labels[label];
    meta.append(badge);
    if (row.confidence != null) {
      const confidence = document.createElement("span");
      confidence.className = "caption";
      confidence.textContent = percent.format(row.confidence) + " confidence";
      meta.append(confidence);
    }
    const body = document.createElement("p");
    body.dir = "auto";
    body.textContent = row.text;
    li.append(meta, body);
    return li;
  });
  commentList.replaceChildren(...items);
  commentList.hidden = !rows.length;
  commentList.scrollTop = previousScroll;
  const count = $("visible-count");
  count.textContent = selectedFilter() === "all" ? String(rows.length) : rows.length + " of " + state.rows.length;
  count.setAttribute("aria-label", rows.length + " of " + state.rows.length + " comments shown");
  $("no-matches").hidden = rows.length > 0;
  $("no-matches").textContent = "No comments match this filter.";
  $("copy").disabled = $("export").disabled = !rows.length;
}

function renderDistribution(summary) {
  $("chart").replaceChildren(...SENTIMENTS.filter((label) => summary.counts[label]).map((label) => {
    const segment = document.createElement("span");
    segment.className = label;
    segment.style.width = summary.percentages[label] + "%";
    return segment;
  }));
  $("legend").replaceChildren(...SENTIMENTS.map((label) => {
    const entry = document.createElement("li");
    entry.className = label;
    const name = document.createElement("span");
    name.className = "legend-label";
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.setAttribute("aria-hidden", "true");
    name.append(swatch, labels[label]);
    const value = document.createElement("strong");
    value.className = "legend-value";
    value.textContent = percent.format(summary.percentages[label] / 100);
    entry.append(name, value);
    return entry;
  }));
}

function render() {
  const summary = summarize(state.rows);
  const running = state.status === "running";
  const hasResults = state.rows.length > 0;
  const messages = {
    idle: "Scroll to the comments on YouTube, then analyze up to " + MAX_COMMENTS + ".",
    running: state.total ? "Analyzing " + state.processed + " of " + state.total + " comments…" : "Collecting loaded comments…",
    empty: "Scroll down to load comments, then try again.",
    done: summary.analyzed ? "Analysis complete. " + summary.analyzed + " comments analyzed." : "The loaded comments contained no usable text.",
    partial: state.error || "Some comments could not be analyzed.",
    error: state.error || "The analysis failed.",
  };
  overview.dataset.state = state.status;
  overview.classList.toggle("has-results", hasResults);
  $("overview-title").textContent = hasResults ? "Sentiment" : "Comment sentiment";
  $("spectrum-art").toggleAttribute("hidden", hasResults);
  $("status").textContent = videoId ? messages[state.status] : "Open a YouTube video to analyze its comments.";
  $("status").classList.toggle("sr-only", state.status === "done" && summary.analyzed > 0);
  $("count").hidden = !hasResults;
  $("count").textContent = hasResults ? summary.analyzed + " analyzed" : "";
  const progress = $("progress");
  progress.hidden = !running || !state.total;
  if (!progress.hidden) {
    progress.max = state.total;
    progress.value = state.processed;
  }
  analyze.disabled = !videoId || running;
  $("analyze-label").textContent = running ? "Analyzing…" : hasResults ? "Analyze again" : "Analyze comments";
  $("analyze-icon").setAttribute("href", hasResults ? "#icon-refresh" : "#icon-arrow");
  $("results").hidden = $("distribution").hidden = !hasResults;
  $("skipped-filter").hidden = !summary.skipped;
  if (!summary.skipped && selectedFilter() === "skipped") resetFilter();
  if (hasResults) {
    renderDistribution(summary);
    $("metadata").textContent = Math.round(state.latencyMs) + " ms API time · " + summary.skipped + " skipped · Model " + state.modelVersion;
  }
  renderRows();
}

async function loadTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  tabId = tab?.id;
  videoId = watchVideoId(tab?.url);
  const key = "analysis:" + tabId + ":" + videoId;
  if (key !== stateKey) {
    resetFilter();
    $("feedback").textContent = "";
    commentList.scrollTop = 0;
  }
  stateKey = key;
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

filter.onchange = () => {
  $("feedback").textContent = "";
  commentList.scrollTop = 0;
  renderRows();
};
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
