import fs from "fs";
import path from "path";

import { answerFromKnowledge } from "../src/lib/answer";
import { loadChunks } from "../src/lib/knowledge";
import { QUESTIONS } from "../src/lib/questions";

const chunks = loadChunks();
const rows = QUESTIONS.map((item) => {
  const answer = answerFromKnowledge(item.question, chunks);
  const passed = item.expect.test(answer.reply)
    && answer.refused === Boolean(item.refused)
    && (!item.suggestLead || answer.suggestLead)
    && (!item.handoff || answer.handoffSuggested)
    && (!item.low || answer.lowConfidence);
  return { item, answer, passed };
});

const passed = rows.filter((row) => row.passed).length;
const lines = [
  "# BrightSmile chatbot test report",
  "",
  `Mock engine, no API key. ${passed} of ${rows.length} questions passed.`,
  "",
  "| Question | Result | Reply |",
  "| --- | --- | --- |",
  ...rows.map((row) => {
    const reply = row.answer.reply.replace(/\|/g, "\\|").replace(/\n/g, " ");
    return `| ${row.item.question} | ${row.passed ? "pass" : "fail"} | ${reply} |`;
  }),
  "",
];

const dir = path.join(process.cwd(), "samples");
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, "test-report.md"), lines.join("\n"));
console.log(`${passed}/${rows.length} passed. Wrote samples/test-report.md`);
if (passed !== rows.length) process.exit(1);
