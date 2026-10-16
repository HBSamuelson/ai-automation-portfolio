import { NextResponse } from "next/server";

import { respond } from "@/lib/respond";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const message = typeof body?.message === "string" ? body.message.trim() : "";
  if (!message) {
    return NextResponse.json({ error: "Type a question first." }, { status: 400 });
  }
  if (message.length > 1000) {
    return NextResponse.json({ error: "That message is too long. Try a shorter question." }, { status: 400 });
  }
  const reply = await respond(message);
  return NextResponse.json(reply);
}
