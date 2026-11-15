import { useEffect, useRef, useState } from "react";
import { navigate } from "../../../app/router";
import { useI18n } from "../../../i18n";
import { useAssistantConversation } from "../../assistant/useAssistantConversation";
import { Dialog } from "./Dialog";
import { Icon } from "./Icon";

const STORAGE_KEY = "terrasense.landingAssistantSession";

/**
 * The landing entry to the platform assistant. Same backend, same session handling as the
 * workspace panel (useAssistantConversation); only the presentation differs. Globe actions
 * are not applied here: "See it in the visualisation" asks the same question in /app.
 */
export function AssistantDrawer({ onClose, onAbout }: { onClose: () => void; onAbout: () => void }) {
  const { t, locale } = useI18n();
  const a = t.assistant;
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const conversation = useAssistantConversation({
    storageKey: STORAGE_KEY,
    sessionId,
    setSessionId,
    context: () => ({ selectedZoneId: null, activeVariableIds: [], primaryVariableId: null, selectedDate: null, locale }),
  });
  const { messages, pending, failedText, unavailable, ready } = conversation;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [messages.length, pending, failedText]);

  const send = async (text: string) => {
    if (await conversation.send(text)) setDraft("");
  };

  const questionBefore = (index: number) => {
    for (let i = index - 1; i >= 0; i -= 1) if (messages[i].role === "user") return messages[i].text;
    return null;
  };

  return (
    <Dialog labelledBy="ts-assistant-title" onClose={onClose} initialFocus={inputRef}>
      <header className="ts-panel-head">
        <div>
          <h2 id="ts-assistant-title">{a.title}</h2>
          <p className="ts-panel-sub">{a.subtitle}</p>
        </div>
        <button type="button" className="ts-icon-btn" onClick={onClose} aria-label={a.close}>
          <Icon name="close" />
        </button>
      </header>
      <div className="ts-thread" aria-live="polite" aria-relevant="additions">
        <article className="ts-msg">
          <p className="ts-msg-who">{a.bot}</p>
          <p>{a.welcome}</p>
        </article>
        {conversation.expired && <p className="ts-thread-note">{a.expired}</p>}
        {messages.length === 0 && !unavailable && (
          <div className="ts-suggestions">
            <p className="ts-overline">{a.examplesLabel}</p>
            {a.examples.map((example) => (
              <button key={example} type="button" className="ts-suggestion" onClick={() => void send(example)} disabled={pending || !ready}>
                <span>{example}</span>
                <Icon name="arrow" size={16} />
              </button>
            ))}
          </div>
        )}
        {messages.map((message, index) => {
          const question = message.role === "assistant" ? questionBefore(index) : null;
          return (
            <article key={message.id} className={message.role === "user" ? "ts-msg is-user" : "ts-msg"}>
              <p className="ts-msg-who">{message.role === "user" ? a.you : a.bot}</p>
              {message.text.split(/\n{2,}/).map((paragraph, part) => (
                <p key={part}>{paragraph}</p>
              ))}
              {message.role === "assistant" && (
                <footer className="ts-msg-foot">
                  <span>{message.source === "gemini" ? a.gemini : a.rules}</span>
                  {message.actions && message.actions.length > 0 && question && (
                    <button type="button" className="ts-text-link" onClick={() => navigate(`/app?ask=${encodeURIComponent(question)}`)}>
                      {a.openGlobe}
                      <Icon name="arrow" size={14} />
                    </button>
                  )}
                </footer>
              )}
            </article>
          );
        })}
        {pending && (
          <p className="ts-working" role="status">
            <span className="ts-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {a.working}
          </p>
        )}
        {(failedText || unavailable) && (
          <div className="ts-msg is-error" role="alert">
            <p>{unavailable ? a.unavailable : a.failed}</p>
            <div className="ts-msg-actions">
              {unavailable ? (
                <button type="button" className="ts-text-link" onClick={conversation.reconnect}>
                  {a.reconnect}
                </button>
              ) : (
                failedText && (
                  <button type="button" className="ts-text-link" onClick={() => void send(failedText)}>
                    {a.retry}
                  </button>
                )
              )}
              <button type="button" className="ts-text-link" onClick={onAbout}>
                {a.openAbout}
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
        <label className="ts-sr" htmlFor="ts-composer-input">
          {a.placeholder}
        </label>
        <input
          id="ts-composer-input"
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={a.placeholder}
          maxLength={2000}
          autoComplete="off"
          disabled={pending}
        />
        <button type="submit" className="ts-send" disabled={pending || !ready || draft.trim().length === 0} aria-label={a.send}>
          <Icon name="send" size={18} />
        </button>
      </form>
      <p className="ts-composer-note">{a.disclaimer}</p>
    </Dialog>
  );
}
