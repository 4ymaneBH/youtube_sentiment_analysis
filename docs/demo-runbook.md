# Demo recording runbook

Target length is about six minutes. Use the final release model and record the visible browser and terminal. For a cloud demonstration, verify the Space is running and build the extension with the Space's HTTPS origin before recording.

| Time | Show on screen | Explain |
|---|---|---|
| 0:00–0:40 | Repository and architecture diagram | How the extension, API, and trained model fit together |
| 0:40–1:30 | Chrome Extensions and **Load unpacked** | Which release folder to select and how to pin the popup |
| 1:30–2:35 | A real YouTube watch page and its loaded comments | Scroll to load comments, open the popup, and run analysis |
| 2:35–3:45 | Distribution, comments, and sentiment filter | How the shares and predicted probabilities are computed |
| 3:45–4:35 | Light/dark switch, clipboard, and JSON export | What the filter applies to and where the exported results go |
| 4:35–5:25 | API health, sample prediction, and popup latency | Which model is deployed and the distinction between inference and request time |
| 5:25–6:05 | Performance report and confusion matrix | The held-out Reddit results and the limits of applying them to YouTube |

Choose a public video with enabled comments and avoid showing private account details. Preview the recording to verify the API response, theme switch, and export are legible.
