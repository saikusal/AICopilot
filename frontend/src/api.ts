export type CopilotResponse = {
  session_id: string;
  transcript: string;
  question?: string | null;
  question_type?: string | null;
  answer?: string | null;
  should_pause: boolean;
  message?: string | null;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function sendAudioChunk(
  sessionId: string,
  blob: Blob,
  mode = "normal",
  force = false
): Promise<CopilotResponse> {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("mode", mode);
  form.append("force", String(force));
  form.append("audio", blob, "chunk.webm");

  const response = await fetch(`${API_BASE}/api/audio-chunk`, {
    method: "POST",
    body: form
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function sendText(
  sessionId: string,
  text: string,
  mode = "normal",
  force = true
): Promise<CopilotResponse> {
  const response = await fetch(`${API_BASE}/api/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, text, mode, force })
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/session/${sessionId}/reset`, { method: "POST" });
}

export type KnowledgeItem = {
  id: string;
  title: string;
  source_type: string;
  preview: string;
};

export async function addKnowledge(title: string, text: string, sourceType = "profile"): Promise<{ chunks: number }> {
  const response = await fetch(`${API_BASE}/api/knowledge/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text, source_type: sourceType })
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function listKnowledge(): Promise<KnowledgeItem[]> {
  const response = await fetch(`${API_BASE}/api/knowledge`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const data = await response.json();
  return data.items || [];
}
