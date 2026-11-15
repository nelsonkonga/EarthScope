import { rejectionLabel, selectionSummary, type CatalogIndex } from "../../domain/actions";
import { ui } from "../../config/strings";
import type { ChatMessage as Message } from "../../domain/types";

export function ChatMessageView({ message, catalog }: { message: Message; catalog: CatalogIndex }) {
  const summary = message.role === "assistant" && message.actionResults ? selectionSummary(message.actionResults, catalog) : null;
  const rejected = message.actionResults?.filter((result) => result.status === "rejected") ?? [];
  return (
    <article className={message.role === "user" ? "bubble user" : "bubble"}>
      {message.text.split(/\n{2,}/).map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
      {message.role === "assistant" && message.source === "gemini" && <p className="hint source-line">{ui.writtenByGemini}</p>}
      {summary && <p className="selection-line">{summary}</p>}
      {rejected.map((result, index) => (
        <p key={`${result.reason}-${index}`} className="hint">
          {ui.ignored(rejectionLabel[result.reason ?? "invalid"] ?? result.reason ?? "invalid action")}
        </p>
      ))}
    </article>
  );
}
