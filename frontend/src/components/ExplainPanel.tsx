import { useEffect, useId, useState } from 'react';
import { useExplainChromeOptional } from './ExplainContext';

export type ExplainSections = {
  what: string;
  why: string;
  whatAitDoes: string;
};

type Props = {
  lead: string;
  sections: ExplainSections;
  labelledBy?: string;
};

export function ExplainPanel({ lead, sections, labelledBy }: Props) {
  const { hideAll, screenshotMode } = useExplainChromeOptional();
  const [hidden, setHidden] = useState(false);
  const panelId = useId();

  useEffect(() => {
    if (screenshotMode || hideAll) {
      setHidden(true);
      return;
    }
    setHidden(false);
  }, [hideAll, screenshotMode]);

  if (screenshotMode) {
    return null;
  }

  if (hidden) {
    return (
      <div className="explain-panel explain-panel--hidden" data-testid="explain-panel">
        <button
          type="button"
          className="explain-toggle"
          data-testid="explain-toggle"
          onClick={() => setHidden(false)}
        >
          Show explanation
        </button>
      </div>
    );
  }

  return (
    <aside
      className="explain-panel"
      data-testid="explain-panel"
      id={panelId}
      aria-labelledby={labelledBy}
    >
      <div className="explain-panel-header">
        <p className="explain-lead">{lead}</p>
        <button
          type="button"
          className="explain-toggle"
          data-testid="explain-toggle"
          aria-controls={panelId}
          onClick={() => setHidden(true)}
        >
          Hide
        </button>
      </div>
      <dl className="explain-dl" data-testid="explain-body">
        <div>
          <dt>What this is</dt>
          <dd>{sections.what}</dd>
        </div>
        <div>
          <dt>Why it matters</dt>
          <dd>{sections.why}</dd>
        </div>
        <div>
          <dt>What Adversarial Integration Tester does here</dt>
          <dd>{sections.whatAitDoes}</dd>
        </div>
      </dl>
    </aside>
  );
}
