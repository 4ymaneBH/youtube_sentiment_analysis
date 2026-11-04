import assert from "node:assert/strict";
import test from "node:test";
import { batches, mergeBatch, summarize } from "../chrome-extension/batches.js";
import { watchVideoId } from "../chrome-extension/config.js";

test("splits 103 comments without losing order", () => {
  const input = Array.from({ length: 103 }, (_, i) => i);
  const groups = batches(input, 50);
  assert.deepEqual(groups.map((batch) => batch.length), [50, 50, 3]);
  assert.deepEqual(groups.flat(), input);
});

test("joins by ID, preserves local text, and excludes skipped rows", () => {
  const text = [{ id: "a", text: "<img onerror='throw 1'>" }, { id: "b", text: "http://example.com" }];
  const results = [{ id: "b", status: "skipped" }, { id: "a", status: "ok", sentiment: "positive" }];
  const merged = mergeBatch(text, { results });
  assert.equal(merged[0].text, text[0].text);
  assert.equal(summarize(merged).percentages.positive, 100);
  assert.equal(summarize(merged).skipped, 1);
  assert.throws(() => mergeBatch(text, { results: [results[0], results[0]] }));
});

test("only YouTube watch pages have a video ID", () => {
  assert.equal(watchVideoId("https://www.youtube.com/watch?v=some-id"), "some-id");
  assert.equal(watchVideoId("https://example.com/watch?v=some-id"), null);
  assert.equal(watchVideoId("https://www.youtube.com/"), null);
});
