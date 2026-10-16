import assert from "node:assert/strict";
import test from "node:test";

import { answerFromKnowledge } from "../src/lib/answer";
import { loadChunks } from "../src/lib/knowledge";
import { normalizePhone } from "../src/lib/phone";
import { QUESTIONS } from "../src/lib/questions";

const chunks = loadChunks();

test("knowledge base is 12 markdown pages", () => {
  const sources = new Set(chunks.map((chunk) => chunk.source));
  assert.equal(sources.size, 12);
  assert.ok(chunks.length >= 12);
});

for (const item of QUESTIONS) {
  test(item.id, () => {
    const answer = answerFromKnowledge(item.question, chunks);
    assert.match(answer.reply, item.expect);
    assert.equal(answer.refused, Boolean(item.refused));
    if (item.suggestLead) assert.equal(answer.suggestLead, true);
    if (item.handoff) assert.equal(answer.handoffSuggested, true);
    if (item.low) assert.equal(answer.lowConfidence, true);
  });
}

test("phone numbers normalize", () => {
  assert.equal(normalizePhone("(303) 555-0140"), "(303) 555-0140");
  assert.equal(normalizePhone("1-720-555-0199"), "(720) 555-0199");
  assert.equal(normalizePhone("555"), null);
});
