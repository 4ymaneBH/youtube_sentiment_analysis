import { batches, mergeBatch } from "./batches.js";
import { API_URL, BATCH_SIZE, MAX_COMMENTS, MAX_LENGTH } from "./config.js";

const jobs = new Map();
const stateKey = (tabId, videoId) => "analysis:" + tabId + ":" + videoId;

async function predictBatch(comments) {
  for (let attempt = 0; attempt < 2; attempt++) {
    let response;
    try {
      response = await fetch(API_URL + "/predict_batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comments }),
        signal: AbortSignal.timeout(12000),
      });
    } catch {
      if (attempt === 0) continue;
      throw new Error("Could not reach the sentiment API. Check the connection and try again.");
    }
    if (response.ok) return response.json();
    if (attempt === 0 && response.status >= 500) continue;
    throw new Error("The sentiment API returned HTTP " + response.status + ".");
  }
}

async function analyze(tabId, videoId, key) {
  const state = { status: "running", total: 0, processed: 0, rows: [], latencyMs: 0 };
  const save = () => chrome.storage.session.set({ [key]: state });
  try {
    await save();
    const page = await chrome.tabs.sendMessage(tabId, {
      type: "collect-comments", limit: MAX_COMMENTS,
    }).catch(() => {
      throw new Error("Reload the YouTube video after installing the extension, then try again.");
    });
    if (page?.videoId !== videoId) {
      throw new Error("The video changed. Open the extension again on the current video.");
    }
    const comments = page.comments.map(({ id, text }) => ({
      id, text: Array.from(text).slice(0, MAX_LENGTH).join(""),
    }));
    state.total = comments.length;
    if (!state.total) {
      state.status = "empty";
      await save();
      return;
    }
    for (const batch of batches(comments, BATCH_SIZE)) {
      const started = performance.now();
      const result = await predictBatch(batch);
      if (state.modelVersion && state.modelVersion !== result.model_version) {
        throw new Error("The API model changed during analysis. Run the analysis again.");
      }
      state.rows.push(...mergeBatch(batch, result));
      state.modelVersion = result.model_version;
      state.latencyMs += performance.now() - started;
      state.processed += batch.length;
      await save();
    }
    state.status = "done";
  } catch (error) {
    state.status = state.rows.length ? "partial" : "error";
    state.error = error.message;
  }
  await save();
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.url !== chrome.runtime.getURL("popup.html")) return;
  const { tabId, videoId, type } = message;
  if (!Number.isInteger(tabId) || !/^[\w-]{1,32}$/.test(videoId)) return;
  const key = stateKey(tabId, videoId);
  if (type === "start") {
    if (!jobs.has(key)) {
      const job = analyze(tabId, videoId, key).finally(() => jobs.delete(key));
      jobs.set(key, job);
    }
    reply({ ok: true });
    return;
  }
  if (type === "state") {
    chrome.storage.session.get(key).then((stored) => {
      const state = stored[key];
      if (state?.status === "running" && !jobs.has(key)) {
        state.status = state.rows.length ? "partial" : "error";
        state.error = "The analysis was interrupted. Run it again to refresh results.";
      }
      reply(state ?? { status: "idle", rows: [] });
    });
    return true;
  }
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const keys = await chrome.storage.session.getKeys();
  await chrome.storage.session.remove(keys.filter((key) => key.startsWith("analysis:" + tabId + ":")));
});
