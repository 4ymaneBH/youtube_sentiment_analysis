export const API_URL = "http://127.0.0.1:7860";
export const BATCH_SIZE = 50;
export const MAX_COMMENTS = 250;
export const MAX_LENGTH = 5000;

export function watchVideoId(rawUrl) {
  if (!rawUrl) return null;
  const url = new URL(rawUrl);
  return url.origin === "https://www.youtube.com" && url.pathname === "/watch"
    ? url.searchParams.get("v")
    : null;
}
