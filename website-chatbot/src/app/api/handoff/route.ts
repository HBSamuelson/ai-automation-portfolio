import { NextResponse } from "next/server";

import { normalizePhone } from "@/lib/phone";
import { addHandoff, listHandoffs } from "@/lib/store";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({ handoffs: listHandoffs() });
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const name = typeof body?.name === "string" ? body.name.trim() : "";
  const phone = typeof body?.phone === "string" ? normalizePhone(body.phone) : null;
  const note = typeof body?.note === "string" ? body.note.trim() : "";
  if (name.length < 2) {
    return NextResponse.json({ error: "Add a name so a person can ask for you." }, { status: 400 });
  }
  if (!phone) {
    return NextResponse.json({ error: "Enter a 10-digit phone number." }, { status: 400 });
  }
  if (note.length < 3) {
    return NextResponse.json({ error: "Add a short note about what you need." }, { status: 400 });
  }
  const handoff = addHandoff({ name, phone, note });
  return NextResponse.json({ handoff });
}
