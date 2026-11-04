import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const live = process.argv.includes("--live");
const output = resolve(process.env.E2E_OUTPUT || "tmp/e2e");
await mkdir(output, { recursive: true });
const profile = await mkdtemp(resolve(output, "profile-"));
const python = process.env.PYTHON_EXE || (process.platform === "win32"
  ? resolve(".venv/Scripts/python.exe") : resolve(".venv/bin/python"));
const api = spawn(python, ["-m", "uvicorn", "app_api:app", "--port", "7860"], {
  stdio: "inherit", windowsHide: true,
  env: { ...process.env, OPENBLAS_NUM_THREADS: "2", OMP_NUM_THREADS: "2" },
});
let serverError;
api.on("error", (error) => { serverError = error; });
const apiUrl = "http://127.0.0.1:7860";
const videoUrl = "https://www.youtube.com/watch?v=" + (live ? "jNQXAC9IVRw" : "fixture-video");

let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (serverError) throw serverError;
    if (api.exitCode !== null) throw new Error("Uvicorn exited before startup");
    ready = await fetch(apiUrl + "/health", { signal: AbortSignal.timeout(750) })
      .then((r) => r.ok).catch(() => false);
    if (ready) break;
    await delay(500);
  }
  assert.ok(ready, "local API is ready");
  const extensionPath = resolve("chrome-extension");
  browser = await chromium.launchPersistentContext(profile, {
    channel: "chromium", headless: true,
    args: ["--disable-extensions-except=" + extensionPath, "--load-extension=" + extensionPath],
  });
  await browser.tracing.start({ screenshots: true, snapshots: true });
  const worker = browser.serviceWorkers()[0] || await browser.waitForEvent("serviceworker");
  const extensionOrigin = new URL(worker.url()).origin.replace(/^null$/, worker.url().split("/").slice(0, 3).join("/"));
  const video = await browser.newPage();
  if (!live) {
    await video.route("https://www.youtube.com/watch?*", (route) => route.fulfill({
      contentType: "text/html",
      body: `<!doctype html><meta charset="utf-8"><main>
        <ytd-comment-view-model><span id="content-text">I love this excellent tutorial!</span></ytd-comment-view-model>
        <ytd-comment-view-model><span id="content-text">This is awful and frustrating.</span></ytd-comment-view-model>
        <ytd-comment-view-model><span id="content-text">The video is 12 minutes long.</span></ytd-comment-view-model>
        <ytd-comment-view-model><span id="content-text">&lt;img src=x onerror=alert(1)&gt;</span></ytd-comment-view-model>
        <ytd-comment-view-model><span id="content-text">https://example.com</span></ytd-comment-view-model>
        <ytd-comment-view-model hidden><span id="content-text">Hidden comment.</span></ytd-comment-view-model>
      </main>`,
    }));
  }
  await video.goto(videoUrl, { waitUntil: "domcontentloaded" });
  if (live) {
    for (let attempt = 0; attempt < 12; attempt++) {
      await video.mouse.wheel(0, 800);
      if (await video.locator("ytd-comment-view-model #content-text, ytd-comment-renderer #content-text").first().isVisible()) break;
      await delay(850);
    }
    await video.locator("ytd-comment-view-model #content-text, ytd-comment-renderer #content-text")
      .first().waitFor({ state: "visible", timeout: 15000 });
  } else {
    await video.evaluate(() => {
      const row = document.createElement("ytd-comment-view-model");
      const body = document.createElement("span");
      body.id = "content-text";
      body.textContent = "A comment loaded after navigation.";
      row.append(body);
      document.querySelector("main").append(row);
    });
  }
  const target = await worker.evaluate(async (url) => {
    const tabs = await chrome.tabs.query({});
    const tab = tabs.find((item) => item.url === url);
    return tab ? { id: tab.id, url: tab.url } : null;
  }, videoUrl);
  assert.ok(target, "extension can identify the test video tab");

  async function checkNativePopup(name) {
    // A popup opened as a tab cannot catch Chrome's intrinsic popup sizing.
    // Toolbar popups are not exposed as Playwright pages, so inspect via CDP.
    await video.bringToFront();
    const client = await browser.browser().newBrowserCDPSession();
    let popupTarget;
    try {
      const previousTargets = new Set((await client.send("Target.getTargets")).targetInfos.map((item) => item.targetId));
      await worker.evaluate(() => chrome.action.openPopup());
      const { targetInfos } = await client.send("Target.getTargets");
      popupTarget = targetInfos.find((item) => item.url === extensionOrigin + "/popup.html" && item.type === "page"
        && !previousTargets.has(item.targetId));
      assert.ok(popupTarget, "native toolbar popup opened");
      const { sessionId } = await client.send("Target.attachToTarget", { targetId: popupTarget.targetId });
      let nextId = 0;
      async function send(method, params = {}) {
        const id = ++nextId;
        return new Promise((resolve, reject) => {
          const timer = setTimeout(() => finish(new Error("Popup CDP timeout: " + method)), 10000);
          function finish(error, result) {
            clearTimeout(timer);
            client.off("Target.receivedMessageFromTarget", receive);
            if (error) reject(error); else resolve(result);
          }
          function receive(event) {
            if (event.sessionId !== sessionId) return;
            const message = JSON.parse(event.message);
            if (message.id === id) finish(message.error ? new Error(message.error.message) : null, message.result);
          }
          client.on("Target.receivedMessageFromTarget", receive);
          client.send("Target.sendMessageToTarget", { sessionId, message: JSON.stringify({ id, method, params }) })
            .catch(finish);
        });
      }
      const { result, exceptionDetails } = await send("Runtime.evaluate", {
        expression: `(async () => {
          await document.fonts.ready;
          while (document.getElementById("status").textContent === "Checking the current tab…") {
            await new Promise(requestAnimationFrame);
          }
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          const root = document.documentElement;
          const controls = [...document.querySelectorAll(".toolbar, h1, #theme, #analyze, #spectrum-art, #distribution, #filter, .actions")]
            .filter((element) => element.getClientRects().length)
            .map((element) => {
              const rect = element.getBoundingClientRect();
              return { name: element.id || element.className || element.tagName, left: rect.left, right: rect.right, bottom: rect.bottom };
            });
          return { width: innerWidth, height: innerHeight, rootWidth: root.getBoundingClientRect().width,
            scrollHeight: root.scrollHeight, clientHeight: root.clientHeight,
            scrollWidth: root.scrollWidth, clientWidth: root.clientWidth,
            fontFamily: getComputedStyle(document.body).fontFamily, controls };
        })()`,
        awaitPromise: true, returnByValue: true,
      });
      assert.ok(!exceptionDetails, "popup layout can be measured");
      const layout = result.value;
      await writeFile(resolve(output, "native-" + name + ".json"), JSON.stringify(layout, null, 2));
      const screenshot = await send("Page.captureScreenshot");
      await writeFile(resolve(output, "native-" + name + ".png"), Buffer.from(screenshot.data, "base64"));
      const expectedWidth = name === "idle" ? 408 : Math.min(408, layout.clientWidth);
      assert.equal(layout.rootWidth, expectedWidth, "toolbar popup uses the available content width: " + name);
      assert.ok(layout.scrollWidth <= layout.clientWidth,
        `${name}: content width ${layout.scrollWidth}px exceeds viewport ${layout.clientWidth}px`);
      assert.match(layout.fontFamily, /system-ui/, "body retains the extension's font stack");
      for (const control of layout.controls) {
        assert.ok(control.left >= 0 && control.right <= layout.clientWidth,
          name + ": " + control.name + " fits across the popup");
      }
      const footer = await send("Runtime.evaluate", {
        expression: `(async () => {
          const button = document.getElementById("results").hidden
            ? document.getElementById("analyze") : document.getElementById("export");
          // Native popup resize is asynchronous after switching views.
          const deadline = performance.now() + 2000;
          do {
            button.scrollIntoView({ block: "center", behavior: "instant" });
            await new Promise(requestAnimationFrame);
            const rect = button.getBoundingClientRect();
            if (rect.top >= 0 && rect.bottom <= innerHeight) break;
          } while (performance.now() < deadline);
          const { top, bottom } = button.getBoundingClientRect();
          return { top, bottom, height: innerHeight, scrollY };
        })()`, awaitPromise: true, returnByValue: true,
      });
      const { top, bottom, height } = footer.result.value;
      assert.ok(top >= 0 && bottom <= height,
        `${name}: bottom actions must fit after scrolling (${JSON.stringify(footer.result.value)})`);
    } finally {
      if (popupTarget) await client.send("Target.closeTarget", { targetId: popupTarget.targetId });
      await client.detach();
    }
  }

  await checkNativePopup("idle");

  async function openPopup() {
    const popup = await browser.newPage();
    await popup.setViewportSize({ width: 420, height: 660 });
    // Opening the popup document as a tab lets Playwright inspect it. Route its
    // active-tab lookup to the video while using the actual extension APIs.
    await popup.addInitScript((tab) => {
      if (location.protocol === "chrome-extension:") chrome.tabs.query = async () => [tab];
    }, target);
    await popup.goto(extensionOrigin + "/popup.html");
    return popup;
  }

  const popup = await openPopup();
  await popup.getByRole("button", { name: "Analyze comments" }).waitFor();
  await popup.evaluate(async () => { await document.fonts.ready; });
  await popup.locator("body").screenshot({ path: resolve(output, "popup-idle.png") });
  await popup.getByRole("button", { name: "Analyze comments" }).click();
  await popup.getByRole("heading", { name: "Sentiment", exact: true }).waitFor({ timeout: 45000 });
  if (!live) {
    assert.equal(await popup.locator("#comments li").count(), 6);
    assert.equal(await popup.locator("#comments img").count(), 0);
    assert.ok((await popup.locator("#metadata").textContent()).includes("1 skipped"));
  }
  await popup.locator("body").screenshot({ path: resolve(output, "popup-light.png") });
  const positiveFilter = popup.getByRole("radio", { name: "Positive", exact: true });
  await positiveFilter.check();
  await positiveFilter.press("ArrowRight");
  assert.ok(await popup.getByRole("radio", { name: "Neutral", exact: true }).isChecked());
  await popup.getByRole("radio", { name: "Neutral", exact: true }).press("ArrowLeft");
  assert.ok(await positiveFilter.isChecked());
  assert.ok(await popup.locator("#comments .badge.positive").count());
  const [download] = await Promise.all([
    popup.waitForEvent("download"), popup.getByRole("button", { name: "Export JSON" }).click(),
  ]);
  assert.match(download.suggestedFilename(), /^youtube-sentiment-.*\.json$/);
  const exported = JSON.parse(await readFile(await download.path(), "utf8"));
  assert.ok(exported.comments.length);
  assert.ok(exported.comments.every((row) => row.sentiment === "positive"));
  await popup.bringToFront();
  await popup.getByRole("button", { name: "Copy results" }).click();
  await popup.getByText("Copied the filtered results.").waitFor();
  await popup.locator("#theme").click();
  assert.equal(await popup.locator("html").getAttribute("data-theme"), "dark");
  await popup.locator("body").screenshot({ path: resolve(output, "popup-dark.png") });
  const count = await popup.locator("#count").textContent();
  await popup.close();
  await checkNativePopup("dark-results");
  const reopened = await openPopup();
  await reopened.getByRole("heading", { name: "Sentiment", exact: true }).waitFor();
  assert.equal(await reopened.locator("#count").textContent(), count);
  assert.equal(await reopened.locator("html").getAttribute("data-theme"), "dark");

  if (!live) {
    const nextUrl = "https://www.youtube.com/watch?v=other-fixture";
    await video.goto(nextUrl);
    target.url = nextUrl;
    const newVideoPopup = await openPopup();
    await newVideoPopup.getByRole("button", { name: "Analyze comments" }).waitFor();
    assert.equal(await newVideoPopup.locator("#count").textContent(), "");
    api.kill();
    for (let attempt = 0; attempt < 20 && api.exitCode === null && api.signalCode === null; attempt++) {
      await delay(100);
    }
    // Also exercise the unavailable-API state when a local server is already running.
    await browser.setOffline(true);
    await newVideoPopup.getByRole("button", { name: "Analyze comments" }).click();
    await newVideoPopup.getByText("Could not reach the sentiment API", { exact: false }).waitFor();
    await newVideoPopup.close();
    await reopened.close();
    await checkNativePopup("error");
  }
  console.log("Passed extension browser flow against " + (live ? "a live YouTube video" : "a fixture video"));
} finally {
  try {
    if (browser) {
      await browser.tracing.stop({ path: resolve(output, "trace.zip") });
      await browser.close();
    }
  } finally {
    if (api.exitCode === null && api.signalCode === null) api.kill();
  }
}
