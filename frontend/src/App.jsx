import { Menu, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import Brand from "./components/Brand";
import Composer from "./components/Composer";
import Message from "./components/Message";
import SettingsPanel from "./components/SettingsPanel";
import Sidebar from "./components/Sidebar";
import Welcome from "./components/Welcome";
import { analyzeDocument, askKnowledgeBase, checkHealth } from "./lib/api";

const id = () => crypto.randomUUID();

export default function App() {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState(null);
  const [language, setLanguage] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [online, setOnline] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [topK, setTopK] = useState(30);
  const [showSources, setShowSources] = useState(true);
  const [voiceLanguage, setVoiceLanguage] = useState("english");
  const endRef = useRef(null);

  useEffect(() => { checkHealth().then(setOnline); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  function reset() {
    if (busy) return;
    setMessages([]); setDraft(""); setFile(null); setLanguage("auto"); setSidebarOpen(false);
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const question = draft.trim();
    const activeFile = file;
    if (!question && !activeFile) return;
    const loadingId = id();
    setMessages((current) => [...current,
      { id: id(), role: "user", label: "You", text: question || "Summarize this legal document.", fileName: activeFile?.name },
      { id: loadingId, role: "assistant", label: activeFile ? (question ? "Reviewing the document" : "Preparing document summary") : "Searching legal sources", loading: true },
    ]);
    setBusy(true);

    try {
      if (activeFile) {
        const result = await analyzeDocument(activeFile, question, language);
        const analysis = result.analysis || {};
        const reply = analysis.mode === "document_question_answer"
          ? { id: id(), role: "assistant", label: "Document answer", text: analysis.answer || "No answer was returned." }
          : { id: id(), role: "assistant", label: "Document summary", summary: analysis.summary || analysis };
        setMessages((current) => [...current.filter((item) => item.id !== loadingId), reply]);
      } else {
        const result = await askKnowledgeBase(question, language, topK);
        setMessages((current) => [...current.filter((item) => item.id !== loadingId), { id: id(), role: "assistant", label: "Legal assistant", text: result.answer || "No answer was returned.", sources: result.sources || [] }]);
      }
      setDraft(""); setFile(null);
    } catch (error) {
      setMessages((current) => [...current.filter((item) => item.id !== loadingId), { id: id(), role: "error", label: "Request could not be completed", text: error instanceof Error ? error.message : "An unexpected error occurred." }]);
    } finally { setBusy(false); }
  }

  return <div className="flex h-dvh overflow-hidden bg-[#f7f8f6] text-slate-900">
    <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} onReset={reset} onSettings={() => { setSidebarOpen(false); setSettingsOpen(true); }} />
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur-lg sm:px-6">
        <div className="flex items-center gap-3 lg:hidden"><button onClick={() => setSidebarOpen(true)} className="icon-button" aria-label="Open navigation"><Menu size={20} /></button><Brand compact /></div>
        <div className="hidden lg:block" />
        <div className="flex items-center gap-3"><span className="flex items-center gap-2 text-xs text-slate-500"><span className={`size-2 rounded-full ${online === null ? "bg-amber-400" : online ? "bg-emerald-500" : "bg-red-500"}`} />{online === null ? "Checking" : online ? "Service ready" : "Service unavailable"}</span><button onClick={reset} className="icon-button" aria-label="New conversation" title="New conversation"><RotateCcw size={17} /></button></div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto"><div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-10">{messages.length === 0 ? <Welcome /> : <div className="space-y-8">{messages.map((message) => <Message key={message.id} message={message} showSources={showSources} />)}<div ref={endRef} /></div>}</div></main>
      <Composer disabled={busy} draft={draft} setDraft={setDraft} file={file} setFile={setFile} language={language} setLanguage={setLanguage} voiceLanguage={voiceLanguage} onSubmit={submit} />
    </div>
    <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} language={language} setLanguage={setLanguage} voiceLanguage={voiceLanguage} setVoiceLanguage={setVoiceLanguage} topK={topK} setTopK={setTopK} showSources={showSources} setShowSources={setShowSources} />
  </div>;
}
