import { ChevronDown, ExternalLink } from "lucide-react";

export default function Sources({ sources }) {
  if (!sources?.length) return null;
  return <details open className="group mt-5 border-t border-slate-200 pt-4">
    <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-semibold text-emerald-800"><ChevronDown size={15} className="transition group-open:rotate-180" />Sources used ({sources.length})</summary>
    <div className="mt-3 grid gap-2 sm:grid-cols-2">{sources.map((source, index) => <div key={`${source.source || source.document}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-500">
      <p className="font-semibold text-slate-700">{source.citation || source.document || source.document_title || source.source || "Legal source"}</p>
      {source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 font-semibold text-emerald-800 hover:underline">Open source <ExternalLink size={12} /></a>}
    </div>)}</div>
  </details>;
}
