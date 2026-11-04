(() => {
  const commentSelector = "ytd-comment-view-model, ytd-comment-renderer";
  function collect(limit) {
    const comments = [];
    const seen = new Set();
    for (const node of document.querySelectorAll(commentSelector)) {
      if (!node.getClientRects().length) continue;
      const body = node.querySelector("#content-text");
      const text = body?.innerText?.trim();
      if (!text) continue;
      const permalink = node.querySelector('a[href*="lc="]');
      const threadId = permalink && new URL(permalink.href).searchParams.get("lc");
      const id = threadId || "loaded-" + (comments.length + 1);
      if (seen.has(id)) continue;
      seen.add(id);
      comments.push({ id, text });
      if (comments.length >= limit) break;
    }
    return comments;
  }

  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (sender.id !== chrome.runtime.id || message.type !== "collect-comments") return;
    const url = new URL(location.href);
    const videoId = url.pathname === "/watch" ? url.searchParams.get("v") : null;
    reply({ videoId, comments: videoId ? collect(message.limit) : [] });
  });
})();
