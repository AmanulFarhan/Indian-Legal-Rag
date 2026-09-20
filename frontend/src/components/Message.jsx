import { AlertCircle, FileText, Scale, UserRound } from "lucide-react";
import Markdown from "react-markdown";
import Sources from "./Sources";
import Summary from "./Summary";

function Loader() {
  return <div className="flex h-7 items-center gap-1.5" aria-label="Preparing response"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></div>;
}

function cleanVisibleAnswer(text = "") {
  return text
    .replace(/\s*\[(?:S\d+)(?:,\s*S\d+)*\]/g, "")
    .replace(/[ \t]+([.,;:])/g, "$1")
    .replace(/ {2,}/g, " ");
}

function sourcesUsed(text = "", sources = []) {
  const sourceNumbers = new Set(
    [...text.matchAll(/S(\d+)/g)].map((match) => Number(match[1])),
  );

  if (!sourceNumbers.size) return sources.slice(0, 5);

  return [...sourceNumbers]
    .map((number) => sources[number - 1])
    .filter(Boolean);
}

export default function Message({ message, showSources = true }) {
  const user = message.role === "user";
  const error = message.role === "error";
  const Icon = user ? UserRound : error ? AlertCircle : Scale;
  return <article className="message-enter grid grid-cols-[36px_minmax(0,1fr)] gap-3.5">
    <div className={`grid size-9 place-items-center rounded-xl ${user ? "bg-slate-800" : error ? "bg-red-700" : "bg-emerald-800"} text-white`}><Icon size={17} /></div>
    <div className="min-w-0 pt-1">
      <p className="mb-2 text-xs font-semibold text-slate-700">{message.label}</p>
      {message.loading ? <Loader /> : message.summary ? <Summary data={message.summary} /> : <div className={user ? "inline-block max-w-full rounded-2xl rounded-tl-md bg-slate-200/75 px-4 py-3" : error ? "rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-800" : "prose-legal"}><Markdown>{cleanVisibleAnswer(message.text)}</Markdown></div>}
      {message.fileName && <div className="mt-2 inline-flex max-w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500"><FileText size={14} className="shrink-0 text-red-700" /><span className="truncate">{message.fileName}</span></div>}
      {showSources && <Sources sources={sourcesUsed(message.text, message.sources)} />}
    </div>
  </article>;
}
