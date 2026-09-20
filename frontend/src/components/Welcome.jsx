import { Scale } from "lucide-react";
import { useEffect, useState } from "react";

const phrases = [
  "Ask about Indian law",
  "Understand a legal document",
  "Find the relevant provision",
  "Ask in English or Malayalam",
];

export default function Welcome() {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [visibleText, setVisibleText] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const phrase = phrases[phraseIndex];
    const complete = visibleText === phrase;
    const empty = visibleText === "";
    const delay = complete && !deleting ? 1500 : deleting ? 35 : 65;

    const timer = window.setTimeout(() => {
      if (complete && !deleting) {
        setDeleting(true);
        return;
      }

      if (empty && deleting) {
        setDeleting(false);
        setPhraseIndex((current) => (current + 1) % phrases.length);
        return;
      }

      setVisibleText(
        deleting
          ? phrase.slice(0, visibleText.length - 1)
          : phrase.slice(0, visibleText.length + 1),
      );
    }, delay);

    return () => window.clearTimeout(timer);
  }, [deleting, phraseIndex, visibleText]);

  return <section className="mx-auto flex min-h-[64vh] max-w-3xl flex-col items-center justify-center px-2 py-12 text-center">
    <div className="grid size-14 place-items-center rounded-2xl border border-emerald-900/10 bg-emerald-50 text-emerald-800 shadow-sm"><Scale size={27} strokeWidth={1.7} /></div>
    <h1 className="mt-7 min-h-[3.5rem] text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-5xl" aria-live="polite">
      {visibleText}<span className="typing-cursor" aria-hidden="true" />
    </h1>
    <p className="mt-4 text-sm text-slate-500">Type a question or attach a PDF below.</p>
  </section>;
}
