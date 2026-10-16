import { answerFromKnowledge, type Answer } from "./answer";
import { loadChunks } from "./knowledge";

export type ChatReply = Answer & { engine: "mock" | "guardrail" | "openai" };

export async function respond(message: string): Promise<ChatReply> {
  const local = answerFromKnowledge(message, loadChunks());
  if (local.refused) return { ...local, engine: "guardrail" };
  const key = process.env.OPENAI_API_KEY;
  if (!key || local.sources.length === 0) return { ...local, engine: "mock" };
  try {
    const reply = await groundedReply(message, local, key);
    return { ...local, reply, engine: "openai" };
  } catch {
    return { ...local, engine: "mock" };
  }
}

async function groundedReply(message: string, local: Answer, key: string): Promise<string> {
  const notes = local.sources.map((source) => `${source.title} / ${source.heading}`).join(", ");
  const context = local.reply;
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      temperature: 0.2,
      messages: [
        {
          role: "system",
          content:
            "You are Bright, the BrightSmile Dental website assistant. Answer in under 80 words using only the clinic notes. If the notes do not answer the question, say you do not have that in BrightSmile's pages. Never diagnose, prescribe, or promise a medical outcome.",
        },
        {
          role: "user",
          content: `Notes (${notes}): ${context}\n\nVisitor: ${message}`,
        },
      ],
    }),
  });
  if (!response.ok) throw new Error(`OpenAI returned ${response.status}`);
  const body = (await response.json()) as { choices?: { message?: { content?: string } }[] };
  const text = body.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error("OpenAI returned an empty reply");
  return text;
}
