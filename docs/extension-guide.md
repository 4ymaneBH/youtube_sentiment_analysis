# Chrome extension guide

Start the local API with `uv run python main.py` and wait for the health endpoint to return `ok`. Load the source folder or the unpacked release ZIP from Chrome's Extensions page. Pin the extension if you want it to stay visible next to the address bar.

On a YouTube watch page, scroll to the comments before opening the popup. The extension scans the comments already displayed by YouTube, including expanded replies. Use **Analyze again** after scrolling further or switching videos.

![Light theme and results](screenshots/popup-light.png)

- **Overview** shows the three sentiment shares, analyzed and skipped counts, model version, and accumulated API round-trip time.
- **Sentiment** filters the comments by predicted class or skipped status. It leaves the overall distribution visible.
- **Copy results** puts the filtered rows in the clipboard as JSON.
- **Export JSON** downloads the same rows with the video ID, model version, and a summary for the current filter.
- **Dark / Light** switches and saves the popup theme.

![Dark theme and positive filter](screenshots/popup-dark.png)

If no comments are shown, scroll to the comment section and try again. Videos with comments disabled cannot be analyzed. If the extension was installed while the video was open, reload the page to attach the content script. If the API is unavailable, check its health endpoint and retry. Partial results remain visible when a later batch fails.

The underlying model was evaluated on labeled Reddit comments. Interpret YouTube scores in the context of language, irony, and the comments you actually loaded.
