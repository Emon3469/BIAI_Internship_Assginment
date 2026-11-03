"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bell, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, CircleHelp,
  ClipboardList, Download, Filter, LayoutGrid, MessageSquareText, MoreHorizontal,
  PanelLeftClose, Plus, Search, SlidersHorizontal, Sparkles, Target, UsersRound,
  X, Zap
} from "lucide-react";

type Lead = {
  lead_id: string; company: string; industry: string; contact_name: string;
  contact_role: string; contact_email: string; contact_phone: string; source: string;
  stage: string; deal_value_bdt: number; last_contact: string | null;
  next_follow_up: string | null; notes: string; is_overdue: boolean; days_overdue: number;
  suggested_action: string; risk_level: string;
};

const fallbackLeads: Lead[] = [
  { lead_id: "L15", company: "Gulshan Dental Chain", industry: "Healthcare", contact_name: "Dr. Arif Hossain", contact_role: "Director", contact_email: "arif@gulshandental.example", contact_phone: "01633200115", source: "Event", stage: "Contacted", deal_value_bdt: 0, last_contact: "2026-10-12", next_follow_up: "2026-10-19", notes: "Interested in patient reminder automation. No response since 12 Oct.", is_overdue: true, days_overdue: 13, suggested_action: "OVERDUE (13 days): Follow up on initial conversation.", risk_level: "high" },
  { lead_id: "L10", company: "Oriental Bank Branch Ops", industry: "Banking", contact_name: "Mizanur Rahman", contact_role: "Senior Manager, Training", contact_email: "mizan@orientalbank.example", contact_phone: "01944200110", source: "LinkedIn", stage: "Meeting", deal_value_bdt: 500000, last_contact: "2026-10-26", next_follow_up: "2026-10-30", notes: "Meeting done. Wants a written proposal with 3 options.", is_overdue: true, days_overdue: 2, suggested_action: "Send meeting summary and written proposal.", risk_level: "medium" },
  { lead_id: "L22", company: "Khulna Jute Works", industry: "Manufacturing", contact_name: "Monir Hossain", contact_role: "Director", contact_email: "monir@khulnajute.example", contact_phone: "01976200122", source: "Referral", stage: "Invoice sent", deal_value_bdt: 150000, last_contact: "2026-10-17", next_follow_up: "2026-10-24", notes: "Invoice sent 17 Oct. Paid? Not marked. Check bank before chasing.", is_overdue: true, days_overdue: 8, suggested_action: "Check payment status before chasing.", risk_level: "high" },
  { lead_id: "L02", company: "Meghna Pharma Ltd", industry: "Pharma", contact_name: "Dr. Sultana Begum", contact_role: "Head of Operations", contact_email: "sultana@meghna-pharma.example", contact_phone: "01819200102", source: "Referral", stage: "Proposal", deal_value_bdt: 700000, last_contact: "2026-10-27", next_follow_up: "2026-11-04", notes: "Proposal sent. Budget approval next week. Wants Bangla support.", is_overdue: false, days_overdue: 0, suggested_action: "Follow up on proposal.", risk_level: "medium" },
  { lead_id: "L01", company: "Padma Textiles Ltd", industry: "Garments", contact_name: "Rafiq Uddin", contact_role: "HR Director", contact_email: "rafiq@padma-textiles.example", contact_phone: "01711200101", source: "Cold email", stage: "Meeting", deal_value_bdt: 350000, last_contact: "2026-10-24", next_follow_up: "2026-11-03", notes: "Wants a 2-day pilot for merchandising team.", is_overdue: false, days_overdue: 0, suggested_action: "Send meeting summary and written proposal.", risk_level: "medium" }
];
const fallbackEnquiries: Lead[] = [
  { lead_id: "E01", company: "Rafi Ahmed", industry: "WhatsApp · Banglish", contact_name: "Rafi Ahmed", contact_role: "Individual", contact_email: "", contact_phone: "01711000001", source: "WhatsApp", stage: "Sales lead", deal_value_bdt: 0, last_contact: "2026-10-26", next_follow_up: "Within 24 hours", notes: "3-day bootcamp price and payment question.", is_overdue: false, days_overdue: 0, suggested_action: "Contact within 24 hours. Product: 3-day bootcamp.", risk_level: "high" },
  { lead_id: "E08", company: "Anika Chowdhury", industry: "Website · English", contact_name: "Anika Chowdhury", contact_role: "Individual", contact_email: "", contact_phone: "01711000008", source: "Website form", stage: "Support issue", deal_value_bdt: 0, last_contact: "2026-10-26", next_follow_up: "Within 2 hours", notes: "Refund request after paying.", is_overdue: true, days_overdue: 1, suggested_action: "Urgent: refund request. Check records and respond within 2 hours.", risk_level: "high" },
  { lead_id: "E03", company: "Gazipur textile company", industry: "Website · English", contact_name: "Mahmud Hasan", contact_role: "Managing Director", contact_email: "", contact_phone: "01711000003", source: "Website form", stage: "Corporate lead", deal_value_bdt: 0, last_contact: "2026-10-26", next_follow_up: "This week", notes: "AI training for a 40-person team. Asked for a call.", is_overdue: false, days_overdue: 0, suggested_action: "HIGH PRIORITY CORPORATE: Contact within 4 hours.", risk_level: "high" }
];

const api = process.env.NEXT_PUBLIC_API_URL !== undefined
  ? process.env.NEXT_PUBLIC_API_URL
  : (typeof window !== "undefined" && window.location.port === "3000" ? "http://localhost:8000" : "");
const stages = ["New", "Contacted", "Meeting", "Proposal", "Invoice sent", "Paid", "Lost"];

function money(value: number) {
  return value ? `৳${value.toLocaleString("en-BD")}` : "Not agreed";
}

export default function Workspace() {
  const [leads, setLeads] = useState<Lead[]>(fallbackLeads);
  const [selectedId, setSelectedId] = useState("L15");
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("All leads");
  const [task, setTask] = useState<"pipeline" | "enquiries">("pipeline");
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    const endpoint = task === "pipeline" ? "/api/pipeline/leads/active" : "/api/crm/enquiries";
    fetch(`${api}${endpoint}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data: Lead[] | Array<Record<string, unknown>>) => {
        const normalized = task === "pipeline" ? data as Lead[] : (data as Array<Record<string, unknown>>).map((item, index) => ({
          lead_id: `E${String(item.original_id ?? index + 1).padStart(2, "0")}`,
          company: String(item.company_name || item.sender_name || "Unknown sender"),
          industry: `${String(item.channel || "Inbound")} · ${String(item.language || "mixed")}`,
          contact_name: String(item.sender_name || ""),
          contact_role: String(item.sender_role || "Individual"),
          contact_email: "",
          contact_phone: String(item.phone || ""),
          source: String(item.channel || ""),
          stage: String(item.category || "General inquiry"),
          deal_value_bdt: 0,
          last_contact: String(item.received_at || "").slice(0, 10) || null,
          next_follow_up: item.needs_follow_up ? "Needs follow-up" : "No follow-up",
          notes: String(item.message || ""),
          is_overdue: false,
          days_overdue: 0,
          suggested_action: String(item.suggested_action || ""),
          risk_level: String(item.priority || "low")
        }));
        if (normalized.length) { setLeads(normalized); setSelectedId(normalized[0].lead_id); }
      })
      .catch(() => setLeads(task === "pipeline" ? fallbackLeads : fallbackEnquiries));
  }, [task]);

  const selected = leads.find((lead) => lead.lead_id === selectedId) ?? leads[0];
  const visibleLeads = useMemo(() => leads.filter((lead) => {
    const matchesQuery = [lead.company, lead.contact_name, lead.industry, lead.lead_id].join(" ").toLowerCase().includes(query.toLowerCase());
    const matchesFilter = activeFilter === "All leads" || (activeFilter === "Needs attention" && lead.is_overdue) || lead.stage === activeFilter;
    return matchesQuery && matchesFilter;
  }), [activeFilter, leads, query]);

  return (
    <main className="flex min-h-screen bg-[#f7f8fc]">
      <aside className="flex w-[58px] shrink-0 flex-col items-center justify-between bg-[#15164e] py-4 text-white">
        <div className="flex flex-col items-center gap-5">
          <div className="grid h-8 w-8 place-items-center rounded-full border border-white/40 text-[11px] font-bold">◉</div>
          <div className="flex flex-col gap-3">
            {[LayoutGrid, UsersRound, ClipboardList, Target, MessageSquareText].map((Icon, index) => (
              <button key={index} aria-label={`Navigation ${index + 1}`} className={`grid h-8 w-8 place-items-center rounded-md transition ${index === 1 ? "bg-[#6563d9] shadow-lg shadow-indigo-950/30" : "text-indigo-100/70 hover:bg-white/10"}`}><Icon size={15} strokeWidth={1.8} /></button>
            ))}
          </div>
        </div>
        <div className="flex flex-col items-center gap-3">
          <button className="relative grid h-8 w-8 place-items-center rounded-md bg-white/10 text-[#ffd0b5]"><Bell size={15} /><span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-[#ff916c]" /></button>
          <div className="grid h-8 w-8 place-items-center rounded-full bg-[#f2b68e] text-[10px] font-bold text-[#3d2742]">JD</div>
        </div>
      </aside>

      <section className="min-w-0 flex-1">
        <header className="flex h-[72px] items-center justify-between border-b hairline bg-white px-8">
          <div className="flex items-center gap-6">
            <button className="text-[#9b9fb5]"><PanelLeftClose size={18} /></button>
            <div className="flex items-center gap-3 text-xs">
              <Step number="1" label="Source data" done />
              <span className="h-px w-8 bg-[#aeb0d7]" />
              <Step number="2" label="Clean & classify" done />
              <span className="h-px w-8 bg-[#aeb0d7]" />
              <Step number="3" label="Work your list" active />
              <span className="h-px w-8 bg-[#d6d8e4]" />
              <Step number="4" label="Export" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className={`rounded-full px-3 py-1.5 text-xs font-bold ${task === "pipeline" ? "bg-[#e6e5ff] text-[#4441aa]" : "text-[#777b95]"}`} onClick={() => setTask("pipeline")}>Corporate pipeline</button>
            <button className={`rounded-full px-3 py-1.5 text-xs font-bold ${task === "enquiries" ? "bg-[#e6e5ff] text-[#4441aa]" : "text-[#777b95]"}`} onClick={() => setTask("enquiries")}>Enquiries</button>
            <button className="grid h-9 w-9 place-items-center rounded-lg border hairline text-[#70748e] hover:bg-[#f8f8fd]"><CircleHelp size={16} /></button>
          </div>
        </header>

        <div className="flex items-center justify-between border-b hairline bg-white px-8 py-4">
          <div>
            <p className="mb-1 text-[10px] font-bold uppercase tracking-[.2em] text-[#7d82a0]">BIAI CRM / {task === "pipeline" ? "Corporate leads" : "Inbound enquiries"}</p>
            <h1 className="text-[17px] font-bold text-[#1b1d44]">Triage and refine your list</h1>
          </div>
          <button className="flex items-center gap-2 rounded-lg bg-[#15164e] px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-indigo-950/15"><Download size={14} /> Export workspace</button>
        </div>

        <div className="grid min-h-[calc(100vh-137px)] grid-cols-[minmax(380px,46%)_1fr]">
          <section className="border-r hairline bg-[#fbfbfe] p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-[13px] font-bold text-[#27294d]">{task === "pipeline" ? "Lead details" : "Enquiry details"}</h2>
              <div className="flex items-center gap-1">
                <button className="grid h-7 w-7 place-items-center rounded border hairline text-[#9a9db1]"><ChevronLeft size={14} /></button>
                <span className="px-2 text-[10px] font-bold text-[#6e728d]">{Math.max(1, leads.findIndex((lead) => lead.lead_id === selectedId) + 1)} of {leads.length}</span>
                <button className="grid h-7 w-7 place-items-center rounded border hairline text-[#5558a9]"><ChevronRight size={14} /></button>
              </div>
            </div>

            <div className="rounded-xl border hairline bg-white p-2 shadow-soft">
              <div className="flex h-[150px] items-center justify-center overflow-hidden rounded-lg bg-[#1a1b58]">
                <div className="relative h-full w-full overflow-hidden bg-[radial-gradient(circle_at_22%_25%,#8d8ceb_0,transparent_29%),linear-gradient(135deg,#171852,#4749a8)]">
                  <div className="absolute -right-12 -top-16 h-52 w-52 rounded-full border-[25px] border-white/10" />
                  <div className="absolute bottom-4 left-6 text-white/90"><p className="text-[10px] font-bold uppercase tracking-[.18em]">Next best action</p><p className="mt-1 text-xl font-bold">{selected?.is_overdue ? `${selected.days_overdue} days overdue` : "Stay on track"}</p></div>
                </div>
              </div>
              <div className="flex items-center justify-between px-1 pb-1 pt-3">
                <div className="flex items-center gap-1 rounded-full bg-[#f1f1ff] p-0.5 text-[10px] font-bold"><span className="rounded-full bg-[#6563d9] px-3 py-1.5 text-white">Live view</span><span className="px-2 text-[#777a97]">Data view</span></div>
                <button className="text-[#8f93a8]"><MoreHorizontal size={17} /></button>
              </div>
            </div>

            <div className="mt-3 rounded-xl border hairline bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-[10px] font-bold text-[#4c4fa8]"><Sparkles size={13} /> BIAI intelligence</div>
              <p className="mt-2 text-[11px] leading-5 text-[#6d7189]">{selected?.suggested_action || "Review the next action before contacting this lead."}</p>
              <div className="mt-3 grid grid-cols-4 divide-x text-center">
                <Stat label="Stage" value={selected?.stage ?? "—"} />
                <Stat label="Value" value={money(selected?.deal_value_bdt ?? 0)} />
                <Stat label="Risk" value={selected?.risk_level ?? "—"} />
                <Stat label="Confidence" value={selected?.is_overdue ? "High" : "Good"} />
              </div>
            </div>

            <div className="mt-3 rounded-xl border hairline bg-white shadow-sm">
              <div className="flex border-b hairline px-4 pt-3 text-[11px] font-bold"><span className="border-b-2 border-[#5756ba] pb-3 text-[#4748a8]">Details</span><span className="ml-5 pb-3 text-[#9497aa]">Activity</span><span className="ml-5 pb-3 text-[#9497aa]">Notes</span></div>
              <div className="grid grid-cols-2 gap-3 p-4">
                <Field label="Company" value={selected?.company} /><Field label="Industry" value={selected?.industry} />
                <Field label="Contact" value={selected?.contact_name || "Needs enrichment"} /><Field label="Role" value={selected?.contact_role || "Not provided"} />
                <Field label="Last contact" value={selected?.last_contact || "No contact yet"} /><Field label="Next follow-up" value={selected?.next_follow_up || "Needs scheduling"} />
              </div>
            </div>
          </section>

          <section className="min-w-0 bg-white p-5">
            <div className="mb-4 flex items-center gap-3">
              <div className="relative min-w-0 flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9598ad]" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company, contact or lead ID" className="h-10 w-full rounded-lg border hairline bg-white pl-9 pr-9 text-xs outline-none ring-[#c6c7f5] focus:ring-2" />{query && <button onClick={() => setQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9295a9]"><X size={14} /></button>}</div>
              <button onClick={() => setShowFilters((value) => !value)} className={`flex h-10 items-center gap-2 rounded-lg border px-3 text-xs font-bold ${showFilters ? "border-[#aaa9e8] bg-[#f0f0ff] text-[#4d4db1]" : "hairline text-[#686c87]"}`}><SlidersHorizontal size={14} /> Filters</button>
              <button className="grid h-10 w-10 place-items-center rounded-lg border hairline text-[#777b93]"><ChevronsRight size={15} /></button>
            </div>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <FilterChip label="All leads" active={activeFilter === "All leads"} onClick={() => setActiveFilter("All leads")} />
              <FilterChip label="Needs attention" active={activeFilter === "Needs attention"} onClick={() => setActiveFilter("Needs attention")} />
              <FilterChip label="Proposal" active={activeFilter === "Proposal"} onClick={() => setActiveFilter("Proposal")} />
              <FilterChip label="Meeting" active={activeFilter === "Meeting"} onClick={() => setActiveFilter("Meeting")} />
              {showFilters && <span className="rounded-full bg-[#f2f2ff] px-3 py-1.5 text-[10px] font-bold text-[#5657ad]">Reference date · 01 Nov 2026</span>}
              <button onClick={() => setActiveFilter("All leads")} className="ml-auto text-[10px] font-bold text-[#4f50aa]">Clear all</button>
            </div>
            <div className="mb-3 flex items-center justify-between text-[10px] text-[#82859b]"><span>Showing <b className="text-[#383b61]">{visibleLeads.length}</b> of {leads.length} leads</span><button className="flex items-center gap-1 font-bold text-[#676a85]"><Plus size={13} /> Add lead</button></div>
            <div className="scrollbar max-h-[calc(100vh-280px)] overflow-y-auto rounded-xl border hairline">
              {visibleLeads.map((lead, index) => <LeadRow key={lead.lead_id} lead={lead} selected={lead.lead_id === selectedId} onClick={() => setSelectedId(lead.lead_id)} delay={index * 45} />)}
              {!visibleLeads.length && <div className="p-12 text-center text-sm text-[#7c8098]">No leads match this view.</div>}
            </div>
            <div className="mt-4 flex items-center justify-between text-[10px] text-[#8b8ea2]"><span>Data synced from Task 2 pipeline</span><span className="flex items-center gap-1 text-[#5759b0]"><Zap size={12} /> Live analysis</span></div>
          </section>
        </div>
      </section>
    </main>
  );
}

function Step({ number, label, done, active }: { number: string; label: string; done?: boolean; active?: boolean }) {
  return <div className={`flex items-center gap-2 whitespace-nowrap ${active ? "font-bold text-[#1f2146]" : "text-[#8b8ea3]"}`}><span className={`grid h-5 w-5 place-items-center rounded-full border text-[9px] ${done ? "border-[#a2a3e6] bg-[#d8d9ff] text-[#4b4daf]" : active ? "border-[#4c4db0] bg-[#7574d4] text-white" : "border-[#d1d3df] bg-white"}`}>{done ? "✓" : number}</span><span className="hidden xl:inline">{label}</span></div>;
}
function Stat({ label, value }: { label: string; value: string }) { return <div className="px-2"><p className="text-[9px] text-[#9497aa]">{label}</p><p className="mt-1 truncate text-[11px] font-bold text-[#393b62]">{value}</p></div>; }
function Field({ label, value }: { label: string; value?: string | null }) { return <div className="rounded-md border hairline bg-[#fbfbfd] px-3 py-2"><p className="text-[9px] text-[#9a9daf]">{label}</p><p className="mt-1 truncate text-[11px] font-bold text-[#444762]">{value || "—"}</p></div>; }
function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) { return <button onClick={onClick} className={`rounded-full border px-3 py-1.5 text-[10px] font-bold transition ${active ? "border-[#bab9ef] bg-[#e8e8ff] text-[#4d4ead]" : "hairline bg-white text-[#72758d] hover:border-[#c5c6e7]"}`}>{label}{active && label !== "All leads" ? " ×" : ""}</button>; }
function LeadRow({ lead, selected, onClick, delay }: { lead: Lead; selected: boolean; onClick: () => void; delay: number }) {
  return <button onClick={onClick} style={{ animationDelay: `${delay}ms` }} className={`animate-lift block w-full border-b hairline p-3 text-left transition last:border-0 ${selected ? "bg-[#f0f0ff] ring-1 ring-inset ring-[#a7a7e7]" : "bg-white hover:bg-[#fafaff]"}`}>
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="flex items-center gap-2"><span className="text-[11px] font-bold text-[#303254]">{lead.lead_id} · {lead.company}</span>{lead.is_overdue && <span className="rounded-full bg-[#ffe8dd] px-1.5 py-0.5 text-[8px] font-bold text-[#b65b38]">OVERDUE</span>}</div><p className="mt-1 text-[10px] text-[#777b91]">{lead.industry} · {lead.contact_name || "Contact missing"}</p></div><span className="text-[10px] font-bold text-[#4e50ad]">{money(lead.deal_value_bdt)}</span></div>
    <div className="mt-2 flex items-center justify-between"><span className={`rounded px-2 py-1 text-[9px] font-bold ${lead.stage === "Proposal" ? "bg-[#e8e8ff] text-[#5657b1]" : lead.stage === "Meeting" ? "bg-[#e4f3f1] text-[#398176]" : lead.stage === "Invoice sent" ? "bg-[#fff1d9] text-[#a46f27]" : "bg-[#f1f2f7] text-[#72758b]"}`}>{lead.stage}</span><span className="max-w-[65%] truncate text-[9px] text-[#84879c]">{lead.notes}</span></div>
  </button>;
}
