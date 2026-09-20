import { Scale } from "lucide-react";

export default function Brand({ compact = false }) {
  return <div className="flex min-w-0 items-center gap-3">
    <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-emerald-800 text-white shadow-sm"><Scale size={21} strokeWidth={1.8} /></div>
    {!compact && <div className="min-w-0 leading-tight"><p className="truncate text-[15px] font-semibold tracking-[-0.01em] text-slate-900">Nyaya</p><p className="truncate text-xs text-slate-500">Indian Legal Assistant</p></div>}
  </div>;
}
