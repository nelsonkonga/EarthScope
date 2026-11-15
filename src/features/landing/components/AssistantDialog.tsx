import { useEffect, useRef, useState } from 'react';
import { useLandingLanguage } from '../context/LandingContext';
import { AccessibleDialog } from './AccessibleDialog';
import { ArrowUpRight, MessageIcon } from './Icons';

export type AssistantController = {
  messages: Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    sources?: string[];
    action?: { label: string; onSelect: () => void };
  }>;
  isLoading: boolean;
  error?: string | null;
  retry?: () => void;
  sendMessage: (message: string) => Promise<void> | void;
};

/** Presentation only: the conversation, its session and its answers belong to the controller. */
export function AssistantDialog({ open, onClose, controller }: { open: boolean; onClose: () => void; controller: AssistantController }) {
  const { t } = useLandingLanguage();
  const a = t.assistant;
  const [draft, setDraft] = useState('');
  const messageContainer = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    messageContainer.current?.scrollTo({ top: messageContainer.current.scrollHeight, behavior: reduce ? 'auto' : 'smooth' });
  }, [open, controller.messages.length, controller.isLoading, controller.error]);

  async function send(message: string) {
    const value = message.trim();
    if (!value || controller.isLoading) return;
    setDraft('');
    await controller.sendMessage(value);
  }

  return (
    <AccessibleDialog open={open} onClose={onClose} title={a.title} size="wide">
      <div className="ts-assistant">
        <div className="ts-assistant__intro">
          <span className="ts-assistant__avatar" aria-hidden="true"><MessageIcon size={21} /></span>
          <div>
            <p>{a.welcome}</p>
            <span className="ts-assistant__status"><i aria-hidden="true" />{controller.isLoading && !controller.messages.length ? a.connecting : a.status}</span>
          </div>
        </div>

        <div className="ts-assistant__messages" ref={messageContainer} aria-live="polite">
          {controller.messages.length ? controller.messages.map((message) => (
            <article className={`ts-chat-message ts-chat-message--${message.role}`} key={message.id}>
              <div className="ts-chat-message__role">{message.role === 'assistant' ? a.bot : a.you}</div>
              {message.content.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
              {(message.sources?.length || message.action) ? (
                <div className="ts-chat-message__sources">
                  {message.sources?.map((source) => <span key={source}>{source}</span>)}
                  {message.action && <button type="button" className="ts-text-link" onClick={message.action.onSelect}>{message.action.label}<ArrowUpRight size={13} /></button>}
                </div>
              ) : null}
            </article>
          )) : <div className="ts-assistant__empty">{a.empty}</div>}
          {controller.isLoading && controller.messages.length > 0 && <p className="ts-assistant__working" role="status">{a.sending}</p>}
          {controller.error && (
            <div className="ts-assistant__error" role="alert">
              <span>{controller.error}</span>
              {controller.retry && <button type="button" className="ts-text-link" onClick={controller.retry}>{a.retry}</button>}
            </div>
          )}
        </div>

        {!controller.messages.length && (
          <div className="ts-assistant__suggestions">
            {a.suggestions.map((suggestion) => (
              <button type="button" key={suggestion} disabled={controller.isLoading} onClick={() => void send(suggestion)}>{suggestion}<ArrowUpRight size={14} /></button>
            ))}
          </div>
        )}

        <form className="ts-assistant__form" onSubmit={(event) => { event.preventDefault(); void send(draft); }}>
          <label className="ts-sr-only" htmlFor="terra-sense-assistant-input">{a.inputLabel}</label>
          <input id="terra-sense-assistant-input" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={a.placeholder} maxLength={2000} autoComplete="off" disabled={controller.isLoading} />
          <button className="ts-button" type="submit" disabled={controller.isLoading || !draft.trim()}>{controller.isLoading ? a.sending : a.send} <ArrowUpRight size={15} /></button>
        </form>
        <p className="ts-assistant__disclaimer">{a.disclaimer}</p>
      </div>
    </AccessibleDialog>
  );
}
