import { Eye, FileText } from 'lucide-react';
import type { Citation } from '../types/rag';

type Props = {
  citations: Citation[];
  onViewDocument?: (documentId: string) => void;
};

export function SourceCards({ citations, onViewDocument }: Props) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {citations.map((citation, index) => (
        <button
          key={`${citation.chunk_id}-${index}`}
          className="rounded border border-stone-200 bg-[#fbfaf7] p-3 text-left hover:border-stone-400 hover:bg-white disabled:cursor-default disabled:hover:border-stone-200 disabled:hover:bg-[#fbfaf7]"
          type="button"
          disabled={!onViewDocument}
          onClick={() => onViewDocument?.(citation.document_id)}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <FileText size={15} className="shrink-0 text-amber-700" aria-hidden="true" />
              <p className="truncate text-xs font-semibold text-stone-900">{citation.filename}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-600">
                {citation.score.toFixed(3)}
              </span>
              {onViewDocument && <Eye size={14} className="text-stone-500" aria-hidden="true" />}
            </div>
          </div>
          <p className="mt-2 line-clamp-3 text-xs leading-5 text-stone-600">{citation.text}</p>
          <p className="mt-2 truncate text-[11px] text-stone-400">{citation.chunk_id}</p>
        </button>
      ))}
    </div>
  );
}
