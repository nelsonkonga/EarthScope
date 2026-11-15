import { useI18n } from "../../../i18n";
import { BrandMark } from "./BrandMark";
import { Icon } from "./Icon";

export function ClosingSection({ onEnter }: { onEnter: () => void }) {
  const { t } = useI18n();
  return (
    <section className="ts-closing" aria-labelledby="ts-closing-title">
      <div className="ts-shell ts-closing-inner">
        <span className="ts-closing-mark" aria-hidden="true">
          <BrandMark size={40} />
        </span>
        <h2 id="ts-closing-title" className="ts-heading">
          {t.closing.title}
        </h2>
        <p>{t.closing.text}</p>
        <button type="button" className="ts-primary ts-primary-lg" onClick={onEnter}>
          {t.closing.cta}
          <Icon name="arrow" size={18} />
        </button>
      </div>
    </section>
  );
}
