import { Plus, Settings, X } from "lucide-react";
import Brand from "./Brand";

export default function Sidebar({ open, onClose, onReset, onSettings }) {
  return <>
    {open && <button className="fixed inset-0 z-30 bg-slate-950/25 lg:hidden" onClick={onClose} aria-label="Close navigation" />}
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-[284px] flex-col border-r border-slate-200 bg-[#f0f3f0] p-4 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex items-center justify-between px-1"><Brand /><button onClick={onClose} className="icon-button lg:hidden" aria-label="Close navigation"><X size={18} /></button></div>
      <button onClick={onReset} className="mt-7 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-800 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"><Plus size={17} /> New conversation</button>
      <div className="mt-auto border-t border-slate-200 pt-3">
        <button onClick={onSettings} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-white hover:text-slate-900"><Settings size={18} />Settings</button>
      </div>
    </aside>
  </>;
}
