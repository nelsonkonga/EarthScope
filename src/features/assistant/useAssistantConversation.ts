import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { createAssistantSession, fetchAssistantSession, postAssistantMessage } from "../../api/resources";
import type { ChatMessage, ChatSession } from "../../domain/types";

export type AssistantContext = Parameters<typeof postAssistantMessage>[2];

function readStored(key: string) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string | null) {
  try {
    if (value) sessionStorage.setItem(key, value);
    else sessionStorage.removeItem(key);
  } catch {
    /* storage blocked: the conversation lasts for this page only */
  }
}

/**
 * One conversation with the backend assistant (/api/v1/assistant). The workspace panel and the
 * landing page drawer both use it, so there is a single assistant with a single behaviour:
 * the backend chooses the answer, this hook only keeps the thread and the session.
 */
export function useAssistantConversation(options: {
  storageKey: string;
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  context: () => AssistantContext;
  /** Runs on every reply before it is stored, e.g. to apply the globe actions. */
  onReply?: (message: ChatMessage) => ChatMessage;
}) {
  const { storageKey, sessionId, setSessionId } = options;
  const queryClient = useQueryClient();
  const latest = useRef(options);
  latest.current = options;
  const [pending, setPending] = useState(false);
  const [failedText, setFailedText] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const stored = readStored(storageKey);
    if (stored && !sessionId) setSessionId(stored);
    // Restore once per mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  const session = useQuery({
    queryKey: ["assistant", sessionId],
    enabled: Boolean(sessionId),
    queryFn: async ({ signal }) => {
      try {
        return await fetchAssistantSession(sessionId as string, signal);
      } catch (error) {
        setExpired(true);
        writeStored(storageKey, null);
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
        setUnavailable(false);
        writeStored(storageKey, created.id);
        setSessionId(created.id);
        queryClient.setQueryData(["assistant", created.id], created);
      })
      .catch(() => {
        if (!controller.signal.aborted) setUnavailable(true);
      });
    return () => controller.abort();
  }, [attempt, queryClient, sessionId, setSessionId, storageKey]);

  const send = useCallback(
    async (text: string) => {
      const id = latest.current.sessionId;
      if (!id || pending) return false;
      setPending(true);
      setFailedText(null);
      const userMessage: ChatMessage = { id: `local-${Date.now()}`, role: "user", text, createdAt: new Date().toISOString() };
      queryClient.setQueryData<ChatSession>(["assistant", id], (current) =>
        current ? { ...current, messages: [...current.messages, userMessage] } : current,
      );
      try {
        const message = await postAssistantMessage(id, text, latest.current.context());
        const stored = latest.current.onReply ? latest.current.onReply(message) : message;
        queryClient.setQueryData<ChatSession>(["assistant", id], (current) =>
          current ? { ...current, messages: [...current.messages, stored] } : current,
        );
        return true;
      } catch {
        queryClient.setQueryData<ChatSession>(["assistant", id], (current) =>
          current ? { ...current, messages: current.messages.filter((item) => item.id !== userMessage.id) } : current,
        );
        setFailedText(text);
        return false;
      } finally {
        setPending(false);
      }
    },
    [pending, queryClient],
  );

  return {
    sessionId,
    ready: Boolean(sessionId && session.data),
    messages: session.data?.messages ?? [],
    suggestedPrompts: session.data?.suggestedPrompts ?? [],
    pending,
    failedText,
    expired,
    unavailable,
    send,
    reconnect: () => {
      setUnavailable(false);
      setAttempt((value) => value + 1);
    },
  };
}
