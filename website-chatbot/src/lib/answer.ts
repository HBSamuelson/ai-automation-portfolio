import { type Chunk, retrieve, tokenize } from "./knowledge";

export type Source = { title: string; heading: string };

export type Answer = {
  reply: string;
  sources: Source[];
  suggestLead: boolean;
  refused: boolean;
  handoffSuggested: boolean;
  lowConfidence: boolean;
};

const MEDICAL =
  /\b(diagnos\w*|prescription|antibiotic|cancer|tumor|dosage|medication|infected|infection|should i take|abscess)\b/i;
const BOOKING = /\b(book|appointment|schedule|come in|set up a visit)\b/i;
const HUMAN = /\b(human|real person|front desk|talk to a person|talk to someone|speak to a person)\b/i;

const REFUSAL =
  "I can't help with medical advice, a diagnosis, or medication. BrightSmile can see you for a dental concern. Call (303) 555-0140 or ask me to book a visit. If this is an emergency you can't wait on, call the office or 911.";
const UNKNOWN =
  "I don't have that in BrightSmile's pages. I can take your name and number and have the front desk call you.";
const HANDOFF =
  "I can hand this to a person at the front desk. Leave your name, phone, and what you need, and someone will call you back.";
const BOOKING_LINE = "I can take your name, phone, and a preferred time for a visit.";

function sentencesOf(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 24);
}

function overlap(queryTokens: string[], sentence: string): number {
  const tokens = new Set(tokenize(sentence));
  return queryTokens.filter((token) => tokens.has(token)).length;
}

export function answerFromKnowledge(query: string, chunks: Chunk[]): Answer {
  const suggestLead = BOOKING.test(query);
  const wantsHuman = HUMAN.test(query);
  if (MEDICAL.test(query)) {
    return {
      reply: REFUSAL,
      sources: [],
      suggestLead: true,
      refused: true,
      handoffSuggested: true,
      lowConfidence: false,
    };
  }
  if (wantsHuman && !suggestLead) {
    return {
      reply: HANDOFF,
      sources: [],
      suggestLead: false,
      refused: false,
      handoffSuggested: true,
      lowConfidence: false,
    };
  }

  const queryTokens = tokenize(query);
  const hits = retrieve(chunks, query, 8);
  const ranked = hits.flatMap(({ chunk }) =>
    sentencesOf(chunk.text).map((sentence) => ({
      sentence,
      score: overlap(queryTokens, sentence),
      chunk,
    })),
  );
  ranked.sort((a, b) => b.score - a.score || a.sentence.length - b.sentence.length);
  const best = ranked[0];
  if (!best || best.score < 1) {
    return {
      reply: suggestLead ? `${UNKNOWN} ${BOOKING_LINE}` : UNKNOWN,
      sources: [],
      suggestLead,
      refused: false,
      handoffSuggested: true,
      lowConfidence: true,
    };
  }

  const chosen = ranked.filter((item) => item.chunk.id === best.chunk.id && item.score > 0).slice(0, 2);
  const cleaned = chosen.map((item) => item.sentence).join(" ").replace(/\s+/g, " ").trim();
  const sources = [{ title: best.chunk.title, heading: best.chunk.heading }];
  return {
    reply: suggestLead ? `${cleaned} ${BOOKING_LINE}` : cleaned,
    sources,
    suggestLead,
    refused: false,
    handoffSuggested: false,
    lowConfidence: false,
  };
}
