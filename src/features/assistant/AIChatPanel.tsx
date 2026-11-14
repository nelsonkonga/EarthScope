import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { createAssistantSession, fetchAssistantSession, postAssistantMessage } from "../../api/resources";
import { fr } from "../../config/strings.fr";
import type { CatalogIndex } from "../../domain/actions";
import type { ChatMessage, ChatSession } from "../../domain/types";
import { useWorkspace } from "../../state/workspaceStore";
import { ChatMessageView } from "./ChatMessage";

const STORAGE_KEY = "earthscope.assistantSession";

export function AIChatPanel({ catalog }: { catalog: CatalogIndex }) {
  const queryClient = useQueryClient();
  const sessionId = useWorkspace((state) => state.assistantSessionId);
  const setSessionId = useWorkspace((state) => state.setAssistantSessionId);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [failedText, setFailedText] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) setSessionId(stored);
  }, [setSessionId]);

  const session = useQuery({
    queryKey: ["assistant", sessionId],
    enabled: Boolean(sessionId),
    queryFn: async ({ signal }) => {
      try {
        return await fetchAssistantSession(sessionId as string, signal);
      } catch (error) {
        setExpired(true);
        sessionStorage.removeItem(STORAGE_KEY);
        setSessionId(null);
        throw error;
      }
    },
    retry: false,
  });

  useEffect(() => {
    if (sessionId) return;
    const controller = new AbortController();
    void createAssistantSession(controller.signal)
      .then((created) => {
        sessionStorage.setItem(STORAGE_KEY, created.id);
        setSessionId(created.id);
        queryClient.setQueryData(["assistant", created.id], created);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [queryClient, sessionId, setSessionId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [session.data?.messages.length, pending]);

  async function send(text: string) {
    const id = useWorkspace.getState().assistantSessionId;
    if (!id || pending) return;
    setPending(true);
    setFailedText(null);
    const state = useWorkspace.getState();
    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      text,
      createdAt: new Date().toISOString(),
    };
    queryClient.setQueryData<ChatSession>(["assistant", id], (current) =>
      current ? { ...current, messages: [...current.messages, userMessage] } : current,
    );
    try {
      const message = await postAssistantMessage(id, text, {
        selectedZoneId: state.selectedZoneId,
        activeVariableIds: state.activeVariableIds,
        primaryVariableId: state.primaryVariableId,
        selectedDate: state.selectedDate,
      });
      const results = useWorkspace.getState().applyAssistant(message.actions ?? [], catalog);
      const stored = { ...message, actionResults: results };
      queryClient.setQueryData<ChatSession>(["assistant", id], (current) =>
        current ? { ...current, messages: [...current.messages, stored] } : current,
      );
      setDraft("");
    } catch {
      setFailedText(text);
    } finally {
      setPending(false);
    }
  }

  const prompts = session.data?.suggestedPrompts?.length ? session.data.suggestedPrompts : fr.fallbackPrompts;
  const messages = session.data?.messages ?? [];

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
