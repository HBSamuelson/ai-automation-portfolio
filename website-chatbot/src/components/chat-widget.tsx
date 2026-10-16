"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type Source = { title: string; heading: string };

type Message = {
  role: "assistant" | "user";
  text: string;
  sources?: Source[];
};

type ChatResponse = {
  reply: string;
  sources: Source[];
  suggestLead: boolean;
  handoffSuggested: boolean;
  engine: string;
  error?: string;
};

const GREETING: Message = {
  role: "assistant",
  text: "Hi, I'm Bright. I answer from BrightSmile's pages: hours, fees, insurance, and booking. I can't give medical advice.",
};

export function ChatWidget({ mode = "launcher" }: { mode?: "launcher" | "panel" }) {
  const [open, setOpen] = useState(mode === "panel");
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [engine, setEngine] = useState("mock");
  const [leadOpen, setLeadOpen] = useState(false);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [formError, setFormError] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight });
  }, [messages, loading, leadOpen, handoffOpen]);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || loading) return;
    setError("");
    setMessages((current) => [...current, { role: "user", text }]);
    setDraft("");
    setLoading(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const body = (await response.json()) as ChatResponse;
      if (!response.ok) {
        setError(body.error || "The desk line didn't go through. Call (303) 555-0140.");
        return;
      }
      setEngine(body.engine);
      setMessages((current) => [
        ...current,
        { role: "assistant", text: body.reply, sources: body.sources },
      ]);
      if (body.suggestLead) setLeadOpen(true);
      if (body.handoffSuggested) setHandoffOpen(true);
    } catch {
      setError("The desk line didn't go through. Call (303) 555-0140.");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(draft);
  }

  async function submitCapture(
    url: string,
    payload: Record<string, string>,
    success: string,
  ) {
    setFormError("");
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = (await response.json()) as { error?: string };
    if (!response.ok) {
      setFormError(body.error || "That didn't save. Try again.");
      return;
    }
    setLeadOpen(false);
    setHandoffOpen(false);
    setMessages((current) => [...current, { role: "assistant", text: success }]);
  }

  const panel = (
    <section className="flex h-full min-h-[520px] flex-col overflow-hidden rounded-3xl bg-card text-card-foreground shadow-xl ring-1 ring-foreground/10">
      <header className="flex items-start justify-between gap-3 bg-primary px-4 py-3 text-primary-foreground">
        <div>
          <p className="font-display text-lg leading-tight">Bright</p>
          <p className="text-xs text-primary-foreground/80">
            {engine === "openai" ? "Grounded in clinic pages via OpenAI" : "Answering from clinic pages"}
          </p>
        </div>
        {mode === "launcher" ? (
          <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(false)}>
            Close
          </Button>
        ) : null}
      </header>
      <div ref={threadRef} className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {messages.map((message, index) => (
          <div key={index} className={message.role === "user" ? "ml-8" : "mr-6"}>
            <p
              className={
                message.role === "user"
                  ? "rounded-2xl bg-secondary px-3 py-2 text-sm"
                  : "rounded-2xl bg-background px-3 py-2 text-sm"
              }
            >
              {message.text}
            </p>
            {message.sources && message.sources.length > 0 ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {message.sources.map((source) => (
                  <Badge key={`${source.title}-${source.heading}`} variant="outline">
                    {source.title}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {loading ? <p className="text-sm text-muted-foreground">Bright is checking the clinic pages...</p> : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {leadOpen ? (
          <CaptureForm
            title="Book a visit"
            timeLabel="Preferred time"
            showTime
            error={formError}
            onSubmit={(fields) =>
              submitCapture(
                "/api/leads",
                fields,
                `Thanks, ${fields.name}. The front desk has ${fields.preferredTime} on the sheet and will confirm by phone.`,
              )
            }
          />
        ) : null}
        {handoffOpen && !leadOpen ? (
          <CaptureForm
            title="Talk to a person"
            timeLabel=""
            showTime={false}
            error={formError}
            onSubmit={(fields) =>
              submitCapture(
                "/api/handoff",
                { name: fields.name, phone: fields.phone, note: fields.note },
                `Thanks, ${fields.name}. A person at the front desk will call you. You can also call (303) 555-0140.`,
              )
            }
          />
        ) : null}
      </div>
      <div className="border-t border-border px-3 py-3">
        <div className="mb-2 flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => { setLeadOpen(true); setHandoffOpen(false); setFormError(""); }}>
            Book a visit
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => { setHandoffOpen(true); setLeadOpen(false); setFormError(""); }}>
            Talk to a person
          </Button>
        </div>
        <form onSubmit={onSubmit} className="flex gap-2">
          <Label htmlFor="bright-question" className="sr-only">Question</Label>
          <Input
            id="bright-question"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Hours, fees, insurance..."
            className="h-10"
          />
          <Button type="submit" disabled={loading || !draft.trim()}>
            Send
          </Button>
        </form>
      </div>
    </section>
  );

  if (mode === "panel") {
    return <div className="h-screen bg-transparent p-0">{panel}</div>;
  }

  return (
    <div className="fixed right-3 bottom-3 z-40 w-[min(400px,calc(100vw-1.5rem))] sm:right-5 sm:bottom-5">
      {open ? panel : (
        <Button type="button" size="lg" className="h-12 rounded-full px-5 shadow-lg" onClick={() => setOpen(true)}>
          Chat with Bright
        </Button>
      )}
    </div>
  );
}

function CaptureForm({
  title,
  showTime,
  error,
  onSubmit,
}: {
  title: string;
  timeLabel: string;
  showTime: boolean;
  error: string;
  onSubmit: (fields: { name: string; phone: string; preferredTime: string; note: string }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [preferredTime, setPreferredTime] = useState("");
  const [note, setNote] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    try {
      await onSubmit({ name, phone, preferredTime, note });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="rounded-2xl bg-accent/60 p-3">
      <p className="mb-2 text-sm font-medium">{title}</p>
      <div className="grid gap-2">
        <Label htmlFor={`${title}-name`}>Name</Label>
        <Input id={`${title}-name`} value={name} onChange={(event) => setName(event.target.value)} required />
        <Label htmlFor={`${title}-phone`}>Phone</Label>
        <Input id={`${title}-phone`} value={phone} onChange={(event) => setPhone(event.target.value)} required />
        {showTime ? (
          <>
            <Label htmlFor={`${title}-time`}>Preferred time</Label>
            <Input id={`${title}-time`} value={preferredTime} onChange={(event) => setPreferredTime(event.target.value)} placeholder="Thursday after 3" required />
          </>
        ) : (
          <>
            <Label htmlFor={`${title}-note`}>What should we call you about?</Label>
            <Textarea id={`${title}-note`} value={note} onChange={(event) => setNote(event.target.value)} required />
          </>
        )}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" disabled={pending}>{pending ? "Saving..." : "Send to the front desk"}</Button>
      </div>
    </form>
  );
}
