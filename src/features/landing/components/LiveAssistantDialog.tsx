import { navigateTerraSense } from '../TerraSenseRoutes';
import { useAssistantConversation } from '../../assistant/useAssistantConversation';
import { useWorkspace } from '../../../state/workspaceStore';
import { useLandingLanguage } from '../context/LandingContext';
import { AssistantDialog, type AssistantController } from './AssistantDialog';

const STORAGE_KEY = 'earthscope.assistantSession';

/**
 * Adapter between the landing dialog and the application's existing assistant
 * (useAssistantConversation, /api/v1/assistant). It reuses the workspace session, so a
 * conversation started here continues in /app. Mounted only while the dialog is open,
 * so visiting the landing page never opens a session on its own.
 */
export function LiveAssistantDialog({ onClose }: { onClose: () => void }) {
  const { t, language } = useLandingLanguage();
  const sessionId = useWorkspace((state) => state.assistantSessionId);
  const setSessionId = useWorkspace((state) => state.setAssistantSessionId);
  const conversation = useAssistantConversation({
    storageKey: STORAGE_KEY,
    sessionId,
    setSessionId,
    context: () => ({ selectedZoneId: null, activeVariableIds: [], primaryVariableId: null, selectedDate: null, locale: language }),
  });

  const messages = conversation.messages.map((message, index) => {
    const question = message.role === 'assistant'
      ? [...conversation.messages.slice(0, index)].reverse().find((item) => item.role === 'user')?.text
      : undefined;
    return {
      id: message.id,
      role: message.role,
      content: message.text,
      sources: message.role === 'assistant' ? [message.source === 'gemini' ? t.assistant.sourceGemini : t.assistant.sourceRules] : undefined,
      action: message.role === 'assistant' && message.actions?.length && question
        ? { label: t.assistant.openInWorkspace, onSelect: () => navigateTerraSense(`/app?ask=${encodeURIComponent(question)}`) }
        : undefined,
    };
  });

  const controller: AssistantController = {
    messages,
    isLoading: conversation.pending || (!conversation.ready && !conversation.unavailable),
    error: conversation.unavailable ? t.assistant.unavailable : conversation.failedText ? t.assistant.error : null,
    sendMessage: async (text) => {
      await conversation.send(text);
    },
    retry: conversation.unavailable ? conversation.reconnect : conversation.failedText ? () => void conversation.send(conversation.failedText as string) : undefined,
  };

  return <AssistantDialog open onClose={onClose} controller={controller} />;
}
