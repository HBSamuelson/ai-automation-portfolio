import { ChatWidget } from "@/components/chat-widget";
import { SiteHeader } from "@/components/site-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const visits = [
  { name: "New patient exam", detail: "$189, x-rays included when we don't already have films." },
  { name: "Adult cleaning", detail: "$129. Plan on about an hour." },
  { name: "Child cleaning", detail: "$99 under age 14. We see children from age 3." },
  { name: "Whitening trays", detail: "$399 take-home. No in-office whitening." },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-4 py-10 pb-28">
        <p className="text-sm tracking-wide text-primary uppercase">Capitol Hill, Denver</p>
        <h1 className="mt-2 max-w-xl text-5xl leading-tight font-medium">Care that fits between a school run and a late meeting.</h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          BrightSmile is at 2200 East Colfax Avenue. Ask Bright about hours, fees, and insurance. The assistant stays on our pages and hands you to the front desk when it should.
        </p>
        <div className="mt-8 flex flex-wrap gap-6 text-sm">
          <p><span className="block text-muted-foreground">Weekdays</span> Mon–Thu 8–5, Fri 8–2</p>
          <p><span className="block text-muted-foreground">Saturday</span> 9–1, closed Sunday</p>
          <p><span className="block text-muted-foreground">Parking</span> Free lot off Emerson Street</p>
        </div>
        <section id="visits" className="mt-12">
          <h2 className="text-3xl font-medium">Common visits</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {visits.map((visit) => (
              <Card key={visit.name}>
                <CardHeader>
                  <CardTitle>{visit.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p>{visit.detail}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
        <section className="mt-12 grid gap-6 md:grid-cols-2">
          <div>
            <h2 className="text-3xl font-medium">Insurance</h2>
            <p className="mt-3 text-muted-foreground">
              We accept Delta Dental, Cigna, Aetna, and MetLife. We do not accept Medicaid. A coordinator confirms your portion before treatment.
            </p>
          </div>
          <div>
            <h2 className="text-3xl font-medium">A real person</h2>
            <p className="mt-3 text-muted-foreground">
              Call (303) 555-0140, or use Talk to a person in the chat. Bright will not diagnose a tooth or recommend medication.
            </p>
          </div>
        </section>
      </main>
      <ChatWidget />
    </div>
  );
}
