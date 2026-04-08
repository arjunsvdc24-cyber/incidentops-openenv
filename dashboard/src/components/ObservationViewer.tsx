import { useState } from 'react';
import type { Observation } from '../api/types';

interface ObservationViewerProps {
  observation: Observation | null;
}

export function ObservationViewer({ observation }: ObservationViewerProps) {
  const [expanded, setExpanded] = useState(true);

  if (!observation) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-text-secondary">
        <svg className="w-16 h-16 mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span className="text-sm">No observation yet</span>
        <span className="text-xs text-text-secondary/60">Execute an action to see results</span>
      </div>
    );
  }

  const jsonString = JSON.stringify(observation, null, 2);

  const highlightedJson = jsonString
    .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
    .replace(/: "([^"]*)"(,?)$/gm, ': <span class="json-string">"$1"</span>$2')
    .replace(/: (-?\d+\.?\d*)(,?)$/gm, ': <span class="json-number">$1</span>$2')
    .replace(/: (true|false)(,?)$/gm, ': <span class="json-boolean">$1</span>$2')
    .replace(/: (null)(,?)$/gm, ': <span class="json-null">$1</span>$2');

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-secondary">Observation</span>
          {observation.done && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-success/20 text-success">
              Done
            </span>
          )}
          {observation.terminated && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-danger/20 text-danger">
              Terminated
            </span>
          )}
          {observation.truncated && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-warning/20 text-warning">
              Truncated
            </span>
          )}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          <svg
            className={`w-5 h-5 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {expanded && (
        <div className="relative">
          <pre className="json-viewer bg-surface border border-border rounded-lg p-4 overflow-auto max-h-[500px] text-text-primary">
            <code dangerouslySetInnerHTML={{ __html: highlightedJson }} />
          </pre>
          <button
            onClick={() => navigator.clipboard.writeText(jsonString)}
            className="absolute top-2 right-2 p-2 rounded bg-surface-border hover:bg-border transition-colors text-text-secondary hover:text-text-primary"
            title="Copy to clipboard"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
        </div>
      )}

      {/* Status Message */}
      {observation.message && (
        <div
          className={`p-3 rounded-lg text-sm ${
            observation.error
              ? 'bg-danger/10 border border-danger/30 text-danger'
              : observation.warning
              ? 'bg-warning/10 border border-warning/30 text-warning'
              : 'bg-surface border border-border text-text-primary'
          }`}
        >
          {observation.message}
        </div>
      )}
    </div>
  );
}
