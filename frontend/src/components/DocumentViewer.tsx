import { ExternalLink, FileText, X } from 'lucide-react';
import type { DocumentPreview } from '../types/rag';

type Props = {
  preview: DocumentPreview | null;
  isLoading: boolean;
  onClose: () => void;
};

export function DocumentViewer({ preview, isLoading, onClose }: Props) {
  if (!preview && !isLoading) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-40 bg-stone-950/30 p-3 backdrop-blur-sm md:p-6">
      <section className="mx-auto flex h-full max-w-6xl flex-col overflow-hidden rounded border border-stone-200 bg-[#fbfaf7] shadow-2xl">
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-stone-200 px-4">
          <div className="flex min-w-0 items-center gap-2">
            <FileText size={17} className="shrink-0 text-amber-700" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-stone-950">
                {preview?.filename ?? 'Loading document...'}
              </p>
              <p className="text-xs text-stone-500">
                {preview ? `Uploaded document preview - ${preview.content_type}` : 'Preparing preview'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {preview && (
              <a
                className="inline-flex h-9 w-9 items-center justify-center rounded text-stone-600 hover:bg-stone-100"
                href={preview.file_url}
                target="_blank"
                rel="noreferrer"
                title="Open original file"
              >
                <ExternalLink size={16} aria-hidden="true" />
              </a>
            )}
            <button
              className="inline-flex h-9 w-9 items-center justify-center rounded text-stone-600 hover:bg-stone-100"
              type="button"
              title="Close viewer"
              onClick={onClose}
            >
              <X size={17} aria-hidden="true" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 bg-white">
          {isLoading && (
            <div className="flex h-full items-center justify-center text-sm text-stone-500">
              Loading preview...
            </div>
          )}
          {!isLoading && preview?.render_mode === 'pdf' && (
            <iframe
              className="h-full w-full border-0"
              src={preview.file_url}
              title={`Preview of ${preview.filename}`}
            />
          )}
          {!isLoading && preview?.render_mode === 'text' && (
            <div className="h-full overflow-y-auto p-5">
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-stone-800">
                {preview.text}
              </pre>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
