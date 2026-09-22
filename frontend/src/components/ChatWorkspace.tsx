import {
  Bot,
  Eye,
  FileText,
  HelpCircle,
  ListChecks,
  Loader2,
  PanelLeft,
  Paperclip,
  Send,
  Sparkles,
  User,
} from 'lucide-react';
import type { ChangeEvent, FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage, StructuredAnswer } from '../types/rag';
import { SourceCards } from './SourceCards';

type Props = {
  activeTitle: string;
  error: string | null;
  input: string;
  isAsking: boolean;
  isUploading: boolean;
  messages: ChatMessage[];
  onInputChange: (input: string) => void;
  onSubmit: () => void;
  onToggleSidebar: () => void;
  onUpload: (file: File) => void;
  onViewDocument: (documentId: string) => void;
};

export function ChatWorkspace({
  activeTitle,
  error,
  input,
  isAsking,
  isUploading,
  messages,
  onInputChange,
  onSubmit,
  onToggleSidebar,
  onUpload,
  onViewDocument,
}: Props) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      onUpload(file);
    }
    event.target.value = '';
  }

  return (
    <main className="flex min-h-0 flex-1 flex-col bg-[#f8f5ee]">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-stone-200 bg-[#fbfaf7]/90 px-4 backdrop-blur md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded border border-stone-300 bg-white text-stone-700 md:hidden"
            type="button"
            title="Toggle history"
            onClick={onToggleSidebar}
          >
            <PanelLeft size={18} aria-hidden="true" />
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-stone-950">{activeTitle}</p>
            <p className="text-xs text-stone-500">Grounded answers with source citations</p>
          </div>
        </div>
        <div className="hidden items-center gap-2 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-600 sm:flex">
          <Sparkles size={14} className="text-amber-700" aria-hidden="true" />
          Gemini RAG
        </div>
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-6">
          {error && (
            <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {messages.length === 0 ? (
            <div className="flex min-h-[55vh] items-center justify-center">
              <div className="max-w-xl text-center">
                <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-stone-950 text-white">
                  <Sparkles size={22} aria-hidden="true" />
                </div>
                <h1 className="text-2xl font-semibold text-stone-950">Ask your documents anything</h1>
                <p className="mt-3 text-sm leading-6 text-stone-600">
                  Upload PDF, DOCX, or TXT files, then ask focused questions. Answers stream into the conversation and include the chunks used as evidence.
                </p>
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <MessageBubble key={message.id} message={message} onViewDocument={onViewDocument} />
            ))
          )}
        </div>
      </section>

      <form className="shrink-0 border-t border-stone-200 bg-[#fbfaf7] p-4" onSubmit={handleSubmit}>
        <div className="mx-auto max-w-4xl">
          <div className="flex items-end gap-3 rounded border border-stone-300 bg-white p-2 shadow-sm focus-within:border-stone-500">
            <label
              className="inline-flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded text-stone-600 hover:bg-stone-100 disabled:cursor-not-allowed"
              title="Upload document"
              aria-label="Upload document"
            >
              {isUploading ? (
                <Loader2 size={18} className="animate-spin" aria-hidden="true" />
              ) : (
                <Paperclip size={18} aria-hidden="true" />
              )}
              <input
                className="sr-only"
                type="file"
                accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                disabled={isUploading}
                onChange={handleFileChange}
              />
            </label>
            <textarea
              className="max-h-40 min-h-12 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-6 text-stone-950 outline-none"
              placeholder="Upload a document or ask your knowledge base..."
              rows={2}
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
            />
            <button
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded bg-stone-950 text-white hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-300"
              type="submit"
              title="Send message"
              disabled={isAsking || input.trim().length === 0}
            >
              <Send size={17} aria-hidden="true" />
            </button>
          </div>
        </div>
      </form>
    </main>
  );
}

function MessageBubble({
  message,
  onViewDocument,
}: {
  message: ChatMessage;
  onViewDocument: (documentId: string) => void;
}) {
  const isAssistant = message.role === 'assistant';

  return (
    <article className="grid grid-cols-[32px_1fr] gap-3">
      <div className={`flex h-8 w-8 items-center justify-center rounded-full ${isAssistant ? 'bg-stone-950 text-white' : 'bg-white text-stone-700 ring-1 ring-stone-200'}`}>
        {isAssistant ? <Bot size={17} aria-hidden="true" /> : <User size={17} aria-hidden="true" />}
      </div>
      <div className="min-w-0">
        <div className="mb-1 flex items-center gap-2">
          <p className="text-sm font-semibold text-stone-950">{isAssistant ? 'Assistant' : 'You'}</p>
          {message.isStreaming && <TypingIndicator />}
        </div>
        <div className={`max-w-none text-sm leading-7 ${isAssistant ? 'rounded bg-white p-4 shadow-sm ring-1 ring-stone-200' : 'text-stone-800'}`}>
          {isAssistant ? (
            message.content ? (
              <div className="prose prose-stone max-w-none text-sm leading-7">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
              </div>
            ) : (
              <TypingLine />
            )
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </div>
        {isAssistant && message.structured && <StructuredAnswerPanel response={message.structured} />}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {message.attachments.map((document) => (
              <button
                key={document.id}
                className="flex min-w-0 items-center gap-3 rounded border border-stone-200 bg-white p-3 text-left shadow-sm hover:border-stone-400"
                type="button"
                onClick={() => onViewDocument(document.id)}
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-stone-100 text-stone-700">
                  <FileText size={18} aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-stone-950">
                    {document.filename}
                  </span>
                  <span className="mt-0.5 block text-xs text-stone-500">
                    {document.chunk_count} chunks - {formatBytes(document.size_bytes)}
                  </span>
                </span>
                <Eye size={16} className="shrink-0 text-stone-500" aria-hidden="true" />
              </button>
            ))}
          </div>
        )}
        {isAssistant && message.citations && message.citations.length > 0 && (
          <SourceCards citations={message.citations} onViewDocument={onViewDocument} />
        )}
      </div>
    </article>
  );
}

function StructuredAnswerPanel({ response }: { response: StructuredAnswer }) {
  return (
    <div className="mt-3 space-y-3 rounded border border-stone-200 bg-[#fbfaf7] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-stone-950">Structured response</p>
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${confidenceClass(response.confidence)}`}>
          {response.confidence} confidence
        </span>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase text-stone-500">Summary</p>
        <p className="mt-1 text-sm leading-6 text-stone-700">{response.summary}</p>
      </div>

      {response.key_points.length > 0 && (
        <div>
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-stone-500">
            <ListChecks size={14} aria-hidden="true" />
            Key points
          </p>
          <ul className="mt-2 space-y-1.5">
            {response.key_points.map((point, index) => (
              <li key={`${point}-${index}`} className="text-sm leading-6 text-stone-700">
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      {response.sources.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase text-stone-500">Sources</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {response.sources.map((source, index) => (
              <span
                key={`${source.document}-${source.page ?? 'unknown'}-${index}`}
                className="rounded border border-stone-200 bg-white px-2.5 py-1 text-xs text-stone-700"
              >
                {source.document}
                {source.page ? `, page ${source.page}` : ''}
              </span>
            ))}
          </div>
        </div>
      )}

      {response.follow_up_questions.length > 0 && (
        <div>
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-stone-500">
            <HelpCircle size={14} aria-hidden="true" />
            Follow-up questions
          </p>
          <ul className="mt-2 space-y-1.5">
            {response.follow_up_questions.map((question, index) => (
              <li key={`${question}-${index}`} className="text-sm leading-6 text-stone-700">
                {question}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function confidenceClass(confidence: StructuredAnswer['confidence']) {
  if (confidence === 'High') {
    return 'bg-emerald-50 text-emerald-700';
  }
  if (confidence === 'Medium') {
    return 'bg-amber-50 text-amber-700';
  }
  return 'bg-red-50 text-red-700';
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function TypingIndicator() {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-stone-500">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-stone-400" />
      <span>thinking</span>
    </span>
  );
}

function TypingLine() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="h-2 w-2 animate-bounce rounded-full bg-stone-400 [animation-delay:-0.2s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-stone-400 [animation-delay:-0.1s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-stone-400" />
    </div>
  );
}
