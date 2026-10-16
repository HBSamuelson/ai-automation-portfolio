import { NextResponse } from "next/server";

import { normalizePhone } from "@/lib/phone";
import { addLead, listLeads } from "@/lib/store";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({ leads: listLeads() });
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const name = typeof body?.name === "string" ? body.name.trim() : "";
  const phone = typeof body?.phone === "string" ? normalizePhone(body.phone) : null;
  const preferredTime = typeof body?.preferredTime === "string" ? body.preferredTime.trim() : "";
  const note = typeof body?.note === "string" ? body.note.trim() : "";
  if (name.length < 2) {
    return NextResponse.json({ error: "Add a name so the desk knows who to call." }, { status: 400 });
  }
  if (!phone) {
    return NextResponse.json({ error: "Enter a 10-digit phone number." }, { status: 400 });
  }
  if (preferredTime.length < 2) {
    return NextResponse.json({ error: "Add a preferred day or time." }, { status: 400 });
  }
  const lead = addLead({ name, phone, preferredTime, note });
  return NextResponse.json({ lead });
}
