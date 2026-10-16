import fs from "fs";
import path from "path";

export type Lead = {
  id: string;
  name: string;
  phone: string;
  preferredTime: string;
  note: string;
  createdAt: string;
};

export type Handoff = {
  id: string;
  name: string;
  phone: string;
  note: string;
  createdAt: string;
  status: "waiting";
};

const dataDir = path.join(process.cwd(), "data");

function readRows<T>(file: string): T[] {
  const full = path.join(dataDir, file);
  if (!fs.existsSync(full)) return [];
  const parsed = JSON.parse(fs.readFileSync(full, "utf8")) as T[];
  return Array.isArray(parsed) ? parsed : [];
}

function writeRows<T>(file: string, rows: T[]) {
  fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(path.join(dataDir, file), JSON.stringify(rows, null, 2));
}

export function listLeads(): Lead[] {
  return readRows<Lead>("leads.json");
}

export function listHandoffs(): Handoff[] {
  return readRows<Handoff>("handoffs.json");
}

export function addLead(input: Omit<Lead, "id" | "createdAt">): Lead {
  const lead: Lead = {
    ...input,
    id: `lead_${Date.now()}`,
    createdAt: new Date().toISOString(),
  };
  writeRows("leads.json", [...listLeads(), lead]);
  return lead;
}

export function addHandoff(input: Omit<Handoff, "id" | "createdAt" | "status">): Handoff {
  const handoff: Handoff = {
    ...input,
    id: `handoff_${Date.now()}`,
    createdAt: new Date().toISOString(),
    status: "waiting",
  };
  writeRows("handoffs.json", [...listHandoffs(), handoff]);
  return handoff;
}
