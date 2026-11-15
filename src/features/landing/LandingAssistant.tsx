import { useEffect, useRef, useState } from "react";
import { createAssistantSession, postAssistantMessage } from "../../api/resources";
import { navigate } from "../../app/router";
import type { ChatMessage } from "../../domain/types";
import type { Dictionary, Locale } from "../../i18n";
import { LandingIcon } from "./LandingIcons";

type Entry = ChatMessage & { question?: string };

export function LandingAssistant({ t, locale, onClose, onAbout }: { t: Dictionary; locale: Locale; onClose: () => void; onAbout: () => void }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, pending, failed]);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const created = await createAssistantSession();
    setSessionId(created.id);
    return created.id;
  }

  async function send(text: string) {
    if (pending) return;
    setPending(true);
    setFailed(null);
    setMessages((current) => [...current, { id: `local-${Date.now()}`, role: "user", text, createdAt: new Date().toISOString() }]);
    setDraft("");
    try {
      const id = await ensureSession();
      const message = await postAssistantMessage(id, text, {
        selectedZoneId: null,
        activeVariableIds: [],
        primaryVariableId: null,
        selectedDate: null,
        locale,
      });
      setMessages((current) => [...current, { ...message, question: text }]);
    } catch {
      setMessages((current) => current.slice(0, -1));
      setFailed(text);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="ts-drawer ts-assistant" role="dialog" aria-modal="true" aria-labelledby="ts-assistant-title">
      <header className="ts-drawer-head">
        <div>
          <h2 id="ts-assistant-title">{t.assistant.title}</h2>
          <p className="ts-muted">{t.assistant.subtitle}</p>
        </div>
        <button type="button" className="ts-icon-btn" onClick={onClose} aria-label={t.assistant.close}>
          <LandingIcon name="close" />
        </button>
      </header>
      <div className="ts-thread" aria-live="polite">
        <article className="ts-bubble">
          <p>{t.assistant.welcome}</p>
        </article>
        {messages.length === 0 && (
          <div className="ts-examples">
            <p className="ts-label">{t.assistant.examplesLabel}</p>
            {t.assistant.examples.map((example) => (
              <button key={example} type="button" className="ts-example" onClick={() => void send(example)} disabled={pending}>
                {example}
                <LandingIcon name="arrow" size={16} />
              </button>
            ))}
          </div>
        )}
        {messages.map((message) => (
          <article key={message.id} className={message.role === "user" ? "ts-bubble is-user" : "ts-bubble"}>
            {message.text.split(/\n{2,}/).map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
            {message.role === "assistant" && (
              <footer className="ts-bubble-foot">
                <span>{message.source === "gemini" ? t.assistant.gemini : t.assistant.rules}</span>
                {message.actions && message.actions.length > 0 && message.question && (
                  <button type="button" className="ts-link" onClick={() => navigate(`/app?ask=${encodeURIComponent(message.question ?? "")}`)}>
                    {t.assistant.openGlobe}
                  </button>
                )}
              </footer>
            )}
          </article>
        ))}
        {pending && (
          <p className="ts-working" role="status">
            <span className="ts-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {t.assistant.working}
          </p>
        )}
        {failed && (
          <div className="ts-bubble is-error" role="alert">
            <p>{t.assistant.failed}</p>
            <div className="ts-row">
              <button type="button" className="ts-link" onClick={() => void send(failed)}>
                {t.assistant.retry}
              </button>
              <button type="button" className="ts-link" onClick={onAbout}>
                {t.assistant.openAbout}
              </button>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form
        className="ts-composer"
        onSubmit={(event) => {
          event.preventDefault();
          const text = draft.trim();
          if (text) void send(text);
        }}
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t.assistant.placeholder}
          aria-label={t.assistant.placeholder}
          maxLength={2000}
          disabled={pending}
        />
        <button type="submit" className="ts-send" disabled={pending || draft.trim().length === 0} aria-label={t.assistant.send}>
          <LandingIcon name="send" size={18} />
        </button>
      </form>
    </div>
  );
}
