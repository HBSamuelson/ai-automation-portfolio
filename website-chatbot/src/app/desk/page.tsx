import Link from "next/link";

import { SiteHeader } from "@/components/site-header";
import { listHandoffs, listLeads } from "@/lib/store";

export const dynamic = "force-dynamic";

export default function DeskPage() {
  const leads = listLeads();
  const handoffs = listHandoffs();
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-4 py-10">
        <p className="text-sm text-primary">Front desk sheet</p>
        <h1 className="text-4xl font-medium">Requests from Bright</h1>
        <p className="mt-2 max-w-xl text-muted-foreground">
          Visit requests and human handoffs land here. This stand-in sheet is the Google Sheet a live gig would write to.
        </p>
        <section className="mt-8">
          <h2 className="text-2xl font-medium">Visit requests</h2>
          {leads.length === 0 ? (
            <p className="mt-3 rounded-2xl bg-card p-4 text-sm">
              No visits requested yet. <Link href="/" className="underline">Ask Bright to book one</Link>.
            </p>
          ) : (
            <div className="mt-3 overflow-x-auto rounded-2xl bg-card">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs tracking-wide text-muted-foreground uppercase">
                  <tr>
                    <th className="px-3 py-3">When</th>
                    <th className="px-3 py-3">Name</th>
                    <th className="px-3 py-3">Phone</th>
                    <th className="px-3 py-3">Preferred time</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.map((lead) => (
                    <tr key={lead.id} className="border-t border-border">
                      <td className="px-3 py-3">{lead.createdAt.slice(0, 16).replace("T", " ")}</td>
                      <td className="px-3 py-3">{lead.name}</td>
                      <td className="px-3 py-3">{lead.phone}</td>
                      <td className="px-3 py-3">{lead.preferredTime}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="mt-10">
          <h2 className="text-2xl font-medium">Waiting for a person</h2>
          {handoffs.length === 0 ? (
            <p className="mt-3 rounded-2xl bg-card p-4 text-sm">No handoffs yet.</p>
          ) : (
            <ul className="mt-3 grid gap-3">
              {handoffs.map((handoff) => (
                <li key={handoff.id} className="rounded-2xl bg-card p-4 text-sm">
                  <p className="font-medium">{handoff.name} · {handoff.phone}</p>
                  <p className="mt-1 text-muted-foreground">{handoff.note}</p>
                  <p className="mt-1 text-xs tracking-wide uppercase">{handoff.status}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
