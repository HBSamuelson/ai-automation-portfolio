import { SiteHeader } from "@/components/site-header";
import { answerFromKnowledge } from "@/lib/answer";
import { loadChunks } from "@/lib/knowledge";
import { QUESTIONS } from "@/lib/questions";

export const dynamic = "force-dynamic";

export default function ReportPage() {
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
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-4 py-10">
        <p className="text-sm text-primary">20-question check</p>
        <h1 className="text-4xl font-medium">How Bright handled clinic questions</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          {passed} of {rows.length} passed against the 12 clinic pages. This run uses the mock answerer, so it works with no API key.
        </p>
        <div className="mt-6 overflow-x-auto rounded-2xl bg-card">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-xs tracking-wide text-muted-foreground uppercase">
              <tr>
                <th className="px-3 py-3">Result</th>
                <th className="px-3 py-3">Question</th>
                <th className="px-3 py-3">Reply</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.item.id} className="border-t border-border align-top">
                  <td className="px-3 py-3 font-medium">{row.passed ? "Pass" : "Fail"}</td>
                  <td className="px-3 py-3">{row.item.question}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.answer.reply}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
