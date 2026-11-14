import { rejectionLabel, selectionSummary, type CatalogIndex } from "../../domain/actions";
import { fr } from "../../config/strings.fr";
import type { ChatMessage as Message } from "../../domain/types";

export function ChatMessageView({ message, catalog }: { message: Message; catalog: CatalogIndex }) {
  const summary = message.role === "assistant" && message.actionResults ? selectionSummary(message.actionResults, catalog) : null;
  const rejected = message.actionResults?.filter((result) => result.status === "rejected") ?? [];
  return (
    <article className={message.role === "user" ? "bubble user" : "bubble"}>
      <p>{message.text}</p>
      {summary && <p className="selection-line">{summary}</p>}
      {rejected.map((result, index) => (
        <p key={`${result.reason}-${index}`} className="hint">
          {fr.ignored(rejectionLabel[result.reason ?? "invalid"] ?? result.reason ?? "action invalide")}
        </p>
      ))}
    </article>
  );
}
