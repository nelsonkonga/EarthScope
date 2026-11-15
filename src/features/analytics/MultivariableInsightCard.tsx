import { formatNumber } from "../../domain/format";
import type { CorrelationPair } from "../../domain/types";
import { fr } from "../../config/strings.fr";

export function MultivariableInsightCard({ pairs }: { pairs: CorrelationPair[] }) {
  if (pairs.length === 0) return <p className="hint">{fr.noCorrelation}</p>;
  return (
    <div className="insights">
      {pairs.map((pair) => {
        const r = pair.pearsonR;
        const position = r == null ? 50 : ((r + 1) / 2) * 100;
        return (
          <article key={pair.variableIds.join("-")} className="insight">
            <h3>{fr.correlation}</h3>
            <div className="corr-track" aria-hidden="true">
              <span className="corr-mark" style={{ left: `${position}%` }} />
            </div>
            <p>{pair.interpretation}</p>
            {pair.bestLag && (
              <p className="hint">
                Décalage le plus lié : {pair.bestLag.steps > 0 ? "+" : ""}
                {pair.bestLag.steps} {pair.bestLag.unit === "month" ? "mois" : "ans"} (r = {formatNumber(pair.bestLag.pearsonR)},{" "}
                {pair.bestLag.pValue < 0.001 ? "p < 0,001" : `p = ${formatNumber(pair.bestLag.pValue)}`}).
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
