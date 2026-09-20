import { Database, Eye, Languages, Mic, Settings, X } from "lucide-react";

export default function SettingsPanel({ open, onClose, language, setLanguage, voiceLanguage, setVoiceLanguage, topK, setTopK, showSources, setShowSources }) {
  if (!open) return null;

  return <div className="fixed inset-0 z-50">
    <button className="absolute inset-0 bg-slate-950/25 backdrop-blur-[2px]" onClick={onClose} aria-label="Close settings" />
    <section className="settings-enter absolute inset-y-0 right-0 flex w-full max-w-[390px] flex-col border-l border-slate-200 bg-[#f8faf8] shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="settings-title">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
        <div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-emerald-800"><Settings size={18} /></span><div><h2 id="settings-title" className="text-sm font-semibold text-slate-900">Settings</h2><p className="text-xs text-slate-400">Personalize your workspace</p></div></div>
        <button onClick={onClose} className="icon-button" aria-label="Close settings"><X size={18} /></button>
      </header>

      <div className="space-y-3 overflow-y-auto p-5">
        <label className="setting-card">
          <span className="setting-icon"><Languages size={18} /></span>
          <span className="min-w-0 flex-1"><strong>Response language</strong><small>Choose the default answer language.</small></span>
          <select value={language} onChange={(event) => setLanguage(event.target.value)} className="setting-select"><option value="auto">Auto</option><option value="english">English</option><option value="malayalam">Malayalam</option></select>
        </label>

        <label className="setting-card">
          <span className="setting-icon"><Mic size={18} /></span>
          <span className="min-w-0 flex-1"><strong>Voice input language</strong><small>Select the language you will speak.</small></span>
          <select value={voiceLanguage} onChange={(event) => setVoiceLanguage(event.target.value)} className="setting-select"><option value="english">English</option><option value="malayalam">Malayalam</option></select>
        </label>

        <label className="setting-card">
          <span className="setting-icon"><Database size={18} /></span>
          <span className="min-w-0 flex-1"><strong>Retrieval depth</strong><small>More passages can improve recall but use more input tokens.</small></span>
          <select value={topK} onChange={(event) => setTopK(Number(event.target.value))} className="setting-select"><option value={10}>10</option><option value={20}>20</option><option value={30}>30</option></select>
        </label>

        <div className="setting-card">
          <span className="setting-icon"><Eye size={18} /></span>
          <span className="min-w-0 flex-1"><strong>Show retrieved sources</strong><small>Display supporting passages below answers.</small></span>
          <button type="button" role="switch" aria-checked={showSources} onClick={() => setShowSources((current) => !current)} className={`relative h-6 w-11 shrink-0 rounded-full transition ${showSources ? "bg-emerald-700" : "bg-slate-300"}`}><span className={`absolute top-0.5 size-5 rounded-full bg-white shadow-sm transition ${showSources ? "left-[22px]" : "left-0.5"}`} /></button>
        </div>
      </div>

      <div className="mt-auto border-t border-slate-200 px-5 py-4"><p className="text-[11px] leading-5 text-slate-400">Settings apply to this browser session.</p></div>
    </section>
  </div>;
}
