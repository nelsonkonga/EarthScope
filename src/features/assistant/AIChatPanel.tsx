import { useEffect, useRef, useState } from "react";
import { fr } from "../../config/strings.fr";
import type { CatalogIndex } from "../../domain/actions";
import { useWorkspace } from "../../state/workspaceStore";
import { ChatMessageView } from "./ChatMessage";
import { useAssistantConversation } from "./useAssistantConversation";

const STORAGE_KEY = "earthscope.assistantSession";

export function AIChatPanel({ catalog }: { catalog: CatalogIndex }) {
  const sessionId = useWorkspace((state) => state.assistantSessionId);
  const setSessionId = useWorkspace((state) => state.setAssistantSessionId);
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const conversation = useAssistantConversation({
    storageKey: STORAGE_KEY,
    sessionId,
    setSessionId,
    context: () => {
      const state = useWorkspace.getState();
      return {
        selectedZoneId: state.selectedZoneId,
        activeVariableIds: state.activeVariableIds,
        primaryVariableId: state.primaryVariableId,
        selectedDate: state.selectedDate,
      };
    },
    onReply: (message) => ({ ...message, actionResults: useWorkspace.getState().applyAssistant(message.actions ?? [], catalog) }),
  });
  const { pending, failedText, expired } = conversation;

  // A question handed over by the landing page assistant (/app?ask=…) is asked once, here.
  const handedOver = useRef<string | null>(new URLSearchParams(window.location.search).get("ask"));
  useEffect(() => {
    const question = handedOver.current?.trim();
    if (!conversation.ready || !question || catalog.zones.length === 0 || catalog.variables.length === 0) return;
    handedOver.current = null;
    window.history.replaceState(null, "", window.location.pathname);
    void conversation.send(question);
  }, [conversation, catalog.zones.length, catalog.variables.length]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [conversation.messages.length, pending]);

  async function send(text: string) {
    if (await conversation.send(text)) setDraft("");
  }

  const prompts = conversation.suggestedPrompts.length ? conversation.suggestedPrompts : fr.fallbackPrompts;
  const messages = conversation.messages;

  return (
    <div className="panel-body chat-panel">
      <h2>{fr.assistant}</h2>
      {expired && <p className="hint">{fr.expired}</p>}
      <div className="thread" aria-live="polite">
        {messages.length === 0 && <p>{fr.assistantEmpty}</p>}
        {messages.map((message) => (
          <ChatMessageView key={message.id} message={message} catalog={catalog} />
        ))}
        {pending && <p className="hint">{fr.assistantWorking}</p>}
        <div ref={endRef} />
      </div>
      {messages.length === 0 && (
        <div className="prompts">
          {prompts.map((prompt) => (
            <button key={prompt} type="button" className="prompt" onClick={() => void send(prompt)} disabled={pending || !sessionId}>
              {prompt}
            </button>
          ))}
        </div>
      )}
      {failedText && (
        <p className="hint">
          {fr.assistantFailed}{" "}
          <button type="button" className="text-btn" onClick={() => void send(failedText)}>
            {fr.retry}
          </button>
        </p>
      )}
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          const text = draft.trim();
          if (text) void send(text);
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={fr.assistantPlaceholder}
          aria-label={fr.assistantPlaceholder}
          disabled={pending || !sessionId}
          maxLength={2000}
        />
        <button type="submit" disabled={pending || !sessionId || draft.trim().length === 0}>
          {fr.send}
        </button>
      </form>
    </div>
  );
}
