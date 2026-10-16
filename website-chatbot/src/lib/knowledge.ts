import fs from "fs";
import path from "path";

export type Chunk = {
  id: string;
  title: string;
  heading: string;
  text: string;
  source: string;
};

const STOP = new Set([
  "the", "and", "for", "you", "your", "our", "are", "was", "with", "this", "that",
  "from", "have", "has", "can", "about", "what", "when", "where", "how", "does",
  "do", "is", "a", "an", "of", "to", "in", "on", "or", "it", "we", "at", "be",
  "if", "my", "me", "i", "much", "please", "not", "dental", "take",
]);

export function tokenize(value: string): string[] {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((token) => token.length > 1 && !STOP.has(token));
}

export function chunkMarkdown(source: string, markdown: string): Chunk[] {
  const title = markdown.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? source;
  const sections = markdown.split(/^##\s+/m).slice(1);
  if (sections.length === 0) {
    return [{
      id: source,
      title,
      heading: title,
      text: markdown.replace(/^#\s+.+$/m, "").trim(),
      source,
    }];
  }
  return sections.map((section, index) => {
    const [headingLine, ...rest] = section.split("\n");
    const heading = headingLine.trim();
    const body = rest.join("\n").trim();
    return {
      id: `${source}#${index}`,
      title,
      heading,
      text: `${heading}. ${body}`,
      source,
    };
  });
}

export function loadChunks(directory = path.join(process.cwd(), "content", "kb")): Chunk[] {
  return fs
    .readdirSync(directory)
    .filter((name) => name.endsWith(".md"))
    .sort()
    .flatMap((name) => chunkMarkdown(name, fs.readFileSync(path.join(directory, name), "utf8")));
}

export type ScoredChunk = { chunk: Chunk; score: number };

export function retrieve(chunks: Chunk[], query: string, k = 4): ScoredChunk[] {
  const queryTokens = tokenize(query);
  const docs = chunks.map((chunk) => tokenize(`${chunk.title} ${chunk.text}`));
  const docCount = docs.length || 1;
  const docFrequency = new Map<string, number>();
  for (const doc of docs) {
    for (const token of new Set(doc)) {
      docFrequency.set(token, (docFrequency.get(token) ?? 0) + 1);
    }
  }
  const averageLength = docs.reduce((sum, doc) => sum + doc.length, 0) / docCount;
  const k1 = 1.2;
  const b = 0.75;
  const scored = docs.map((doc, index) => {
    const termFrequency = new Map<string, number>();
    for (const token of doc) termFrequency.set(token, (termFrequency.get(token) ?? 0) + 1);
    let score = 0;
    for (const token of queryTokens) {
      const frequency = termFrequency.get(token) ?? 0;
      if (!frequency) continue;
      const documentsWithTerm = docFrequency.get(token) ?? 0;
      const idf = Math.log(1 + (docCount - documentsWithTerm + 0.5) / (documentsWithTerm + 0.5));
      const lengthNorm = 1 - b + (b * doc.length) / (averageLength || 1);
      score += (idf * (frequency * (k1 + 1))) / (frequency + k1 * lengthNorm);
    }
    return { chunk: chunks[index], score };
  });
  return scored
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k);
}
