export const SENTIMENTS = ["negative", "neutral", "positive"];

export function batches(items, size) {
  const result = [];
  for (let index = 0; index < items.length; index += size) {
    result.push(items.slice(index, index + size));
  }
  return result;
}

export function mergeBatch(comments, response) {
  const results = new Map(response.results.map((row) => [row.id, row]));
  if (response.results.length !== comments.length || results.size !== comments.length) {
    throw new Error("The API returned an incomplete batch.");
  }
  return comments.map(({ id, text }) => {
    const result = results.get(id);
    if (!result) throw new Error("The API returned an unknown comment ID.");
    return { ...result, text };
  });
}

export function summarize(rows) {
  const counts = Object.fromEntries(SENTIMENTS.map((label) => [label, 0]));
  for (const row of rows) {
    if (row.status === "ok" && SENTIMENTS.includes(row.sentiment)) counts[row.sentiment]++;
  }
  const analyzed = Object.values(counts).reduce((sum, count) => sum + count, 0);
  const percentages = Object.fromEntries(
    SENTIMENTS.map((label) => [label, analyzed ? 100 * counts[label] / analyzed : 0]),
  );
  return { counts, percentages, analyzed, skipped: rows.length - analyzed };
}
