async function responseError(response) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
    return JSON.stringify(payload.detail ?? payload);
  } catch { return `The server returned HTTP ${response.status}.`; }
}

async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await responseError(response));
  return response.json();
}

export function askKnowledgeBase(question, outputLanguage, topK = 30, conversationHistory = []) {
  return request("/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, top_k: topK, output_language: outputLanguage, conversation_history: conversationHistory }) });
}

export function analyzeDocument(file, question, outputLanguage) {
  const data = new FormData();
  data.append("file", file);
  if (question) data.append("question", question);
  data.append("output_language", outputLanguage);
  return request("/analyze-document", { method: "POST", body: data });
}

export async function checkHealth() {
  try { return (await fetch("/api/health", { cache: "no-store" })).ok; }
  catch { return false; }
}
