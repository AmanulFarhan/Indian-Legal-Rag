import { ArrowUp, FileText, Mic, MicOff, Paperclip, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export default function Composer({
  disabled,
  draft,
  setDraft,
  file,
  setFile,
  language,
  setLanguage,
  voiceLanguage,
  onSubmit,
}) {
  const inputRef = useRef(null);
  const fileRef = useRef(null);
  const recognitionRef = useRef(null);
  const initialDraftRef = useRef("");
  const finalTranscriptRef = useRef("");

  const [dragging, setDragging] = useState(false);
  const [listening, setListening] = useState(false);
  const [voicePreview, setVoicePreview] = useState("");
  const [voiceError, setVoiceError] = useState("");

  const SpeechRecognition = typeof window === "undefined"
    ? null
    : window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceSupported = Boolean(SpeechRecognition);

  useEffect(() => {
    const input = inputRef.current;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 168)}px`;
  }, [draft]);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.onend = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.abort();
        recognitionRef.current = null;
      }
    };
  }, []);

  function chooseFile(candidate) {
    if (!candidate) return;
    if (candidate.type !== "application/pdf" && !candidate.name.toLowerCase().endsWith(".pdf")) {
      window.alert("Please choose a PDF document.");
      return;
    }
    if (candidate.size > 50 * 1024 * 1024) {
      window.alert("The PDF must be smaller than 50 MB.");
      return;
    }
    setFile(candidate);
  }

  function toggleVoiceInput() {
    setVoiceError("");

    if (!voiceSupported) {
      setVoiceError("Voice input is not supported by this browser.");
      return;
    }

    if (recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = voiceLanguage === "malayalam" ? "ml-IN" : "en-IN";
    recognition.continuous = false;
    recognition.interimResults = true;

    initialDraftRef.current = draft.trim();
    finalTranscriptRef.current = "";

    recognition.onstart = () => {
      setListening(true);
      setVoicePreview("");
    };

    recognition.onresult = (event) => {
      let interimText = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0].transcript;

        if (event.results[index].isFinal) {
          finalTranscriptRef.current += `${transcript} `;
        } else {
          interimText += transcript;
        }
      }

      setVoicePreview(interimText);
    };

    recognition.onerror = (event) => {
      const messages = {
        "not-allowed": "Microphone permission was denied.",
        "no-speech": "No speech was detected. Please try again.",
        network: "Speech recognition is temporarily unavailable.",
        aborted: "Voice input was cancelled.",
      };

      setVoiceError(messages[event.error] || "Voice recognition could not be completed.");
    };

    recognition.onend = () => {
      const transcript = finalTranscriptRef.current.trim();

      if (transcript) {
        const previous = initialDraftRef.current;
        setDraft(previous ? `${previous} ${transcript}` : transcript);
      }

      setListening(false);
      setVoicePreview("");
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setVoiceError("Voice recognition could not be started.");
    }
  }

  return <div className="border-t border-slate-200/80 bg-[#f7f8f6]/95 px-4 pb-3 pt-3 backdrop-blur-lg">
    <div className="mx-auto max-w-4xl">
      {file && <div className="mb-2 flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm"><span className="grid size-8 place-items-center rounded-lg bg-red-50 text-red-700"><FileText size={16} /></span><span className="min-w-0 flex-1"><strong className="block truncate text-xs text-slate-800">{file.name}</strong><small className="text-[11px] text-slate-400">{(file.size / 1024 / 1024).toFixed(2)} MB · PDF document</small></span><button type="button" onClick={() => setFile(null)} className="icon-button" aria-label="Remove document"><X size={17} /></button></div>}

      <form onSubmit={onSubmit} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0]); }} className={`rounded-2xl border bg-white p-3 shadow-[0_12px_35px_rgba(15,23,42,0.09)] transition ${dragging ? "border-emerald-700 ring-4 ring-emerald-700/10" : "border-slate-300 focus-within:border-emerald-700/50 focus-within:ring-4 focus-within:ring-emerald-700/5"}`}>
        <label htmlFor="legal-question" className="sr-only">Ask a legal question</label>
        <textarea ref={inputRef} id="legal-question" value={draft} disabled={disabled || listening} rows={1} maxLength={4000} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form.requestSubmit(); } }} placeholder="Ask a legal question or attach a PDF…" className="max-h-42 min-h-8 w-full resize-none bg-transparent px-1 text-[15px] leading-6 text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60" />

        {listening && <p className="mt-1 text-xs text-emerald-700" aria-live="polite">{voicePreview || "Listening…"}</p>}
        {voiceError && <p className="mt-1 text-xs text-red-700" role="alert">{voiceError}</p>}

        <div className="mt-2 flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-1.5">
            <input ref={fileRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={(event) => chooseFile(event.target.files?.[0])} />
            <button type="button" disabled={disabled} onClick={() => fileRef.current.click()} className="control-button"><Paperclip size={16} /><span className="hidden sm:inline">Attach PDF</span></button>
            <button type="button" onClick={toggleVoiceInput} disabled={disabled || !voiceSupported} aria-label={listening ? "Stop voice input" : "Start voice input"} aria-pressed={listening} title={voiceSupported ? "Speak your legal question" : "Voice input is not supported by this browser"} className={listening ? "control-button bg-red-50 text-red-700" : "control-button"}>{listening ? <MicOff size={16} /> : <Mic size={16} />}<span className="hidden sm:inline">{listening ? "Stop" : "Voice"}</span></button>
            <div className="h-5 w-px bg-slate-200" />
            <label className="flex items-center gap-2 text-xs text-slate-400"><span className="hidden sm:inline">Response</span><select value={language} disabled={disabled} onChange={(event) => setLanguage(event.target.value)} className="rounded-lg border-0 bg-slate-50 px-2 py-1.5 text-xs font-semibold text-slate-700 outline-none ring-1 ring-slate-200"><option value="auto">Auto</option><option value="english">English</option><option value="malayalam">Malayalam</option></select></label>
          </div>
          <button type="submit" disabled={disabled || listening || (!draft.trim() && !file)} className="grid size-9 shrink-0 place-items-center rounded-xl bg-emerald-800 text-white transition hover:bg-emerald-900 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400" aria-label="Send message"><ArrowUp size={18} strokeWidth={2.2} /></button>
        </div>
      </form>

      <p className="mt-2 text-center text-[10px] leading-4 text-slate-400">General legal information only. Verify important matters with a qualified legal professional.</p>
    </div>
  </div>;
}
