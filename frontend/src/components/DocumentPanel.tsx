import { Check, Eye, FileSearch, FileText, KeyRound, MessageSquarePlus, Pencil, RefreshCw, Sparkles, Trash2, Upload, X } from 'lucide-react';
import type { ChangeEvent, FormEvent } from 'react';
import { useState } from 'react';
import type { ChatThread, DocumentDetail, DocumentSummary, UserProfile } from '../types/rag';

type Props = {
  activeThreadId: string;
  conversations: ChatThread[];
  documentDetails: DocumentDetail | null;
  documents: DocumentSummary[];
  inspectedDocumentId: string | null;
  isInspecting: boolean;
  isOpen: boolean;
  isReindexing: string | null;
  isUploading: boolean;
  user: UserProfile;
  onDeleteConversation: (threadId: string) => void;
  onDelete: (documentId: string) => void;
  onInspectDocument: (documentId: string) => void;
  onNameFromContext: (threadId: string) => void;
  onNewChat: () => void;
  onRenameThread: (threadId: string, title: string) => void;
  onReindex: (documentId: string) => void;
  onSelectThread: (threadId: string) => void;
  onUpload: (file: File) => void;
  onViewDocument: (documentId: string) => void;
  onOpenSettings: () => void;
  onLogout: () => void;
};

export function DocumentPanel({
  activeThreadId,
  conversations,
  documentDetails,
  documents,
  inspectedDocumentId,
  isInspecting,
  isOpen,
  isReindexing,
  isUploading,
  user,
  onDelete,
  onDeleteConversation,
  onInspectDocument,
  onNameFromContext,
  onNewChat,
  onRenameThread,
  onReindex,
  onSelectThread,
  onUpload,
  onViewDocument,
  onOpenSettings,
  onLogout,
}: Props) {
  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      onUpload(file);
      event.target.value = '';
    }
  }

  return (
    <aside className={`${isOpen ? 'flex' : 'hidden'} min-h-0 flex-col border-r border-stone-200 bg-[#f2eee6] md:flex`}>
      <div className="border-b border-stone-200 p-4">
        <div className="mb-3 rounded border border-stone-200 bg-white p-3">
          <p className="truncate text-sm font-semibold text-stone-950">{user.name}</p>
          <p className="truncate text-xs text-stone-500">{user.email}</p>
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-600">{user.role}</span>
            <div className="flex items-center gap-2">
              <button
                className="inline-flex items-center gap-1 text-xs font-medium text-stone-600 hover:text-stone-950"
                type="button"
                onClick={onOpenSettings}
                title="LLM Provider Settings"
              >
                <KeyRound size={13} aria-hidden="true" />
                API Keys
              </button>
              <span className="text-stone-300">•</span>
              <button className="text-xs font-medium text-stone-600 hover:text-stone-950" type="button" onClick={onLogout}>
                Logout
              </button>
            </div>
          </div>
        </div>
        <button
          className="flex h-10 w-full items-center justify-center gap-2 rounded bg-stone-950 px-3 text-sm font-medium text-white hover:bg-stone-800"
          type="button"
          onClick={onNewChat}
        >
          <MessageSquarePlus size={16} aria-hidden="true" />
          New chat
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <section>
          <h2 className="px-2 text-xs font-semibold uppercase text-stone-500">Chat history</h2>
          <ul className="mt-2 space-y-1">
            {conversations.map((thread) => (
              <li key={thread.id}>
                <ConversationRow
                  isActive={thread.id === activeThreadId}
                  thread={thread}
                  onNameFromContext={onNameFromContext}
                  onDeleteConversation={onDeleteConversation}
                  onRenameThread={onRenameThread}
                  onSelectThread={onSelectThread}
                />
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-6">
          <div className="flex items-center justify-between gap-3 px-2">
            <div>
              <h2 className="text-xs font-semibold uppercase text-stone-500">Document dashboard</h2>
              <p className="mt-1 text-xs text-stone-500">{documents.length} documents indexed</p>
            </div>
            <label className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded border border-stone-300 bg-white text-stone-700 hover:bg-stone-50" title="Upload document">
              <Upload size={17} aria-hidden="true" />
              <input
                accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                className="sr-only"
                type="file"
                onChange={handleFileChange}
                disabled={isUploading}
              />
            </label>
          </div>

          {documents.length === 0 ? (
            <div className="mt-3 rounded border border-dashed border-stone-300 bg-white/60 p-4 text-sm text-stone-500">
              Upload PDF, DOCX, or TXT documents to start asking grounded questions.
            </div>
          ) : (
            <ul className="mt-3 space-y-2">
              {documents.map((document) => (
                <li key={document.id} className="rounded border border-stone-200 bg-white p-3 shadow-sm">
                  <div className="flex items-start gap-3">
                    <FileText className="mt-0.5 shrink-0 text-amber-700" size={18} aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-stone-900" title={document.filename}>
                        {document.filename}
                      </p>
                      <p className="mt-1 text-xs text-stone-500">
                        {document.chunk_count.toLocaleString()} chunks | {formatBytes(document.size_bytes)}
                      </p>
                      <p className="mt-1 text-xs font-medium text-amber-700">{document.status}</p>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-4 gap-1">
                    <button
                      className="inline-flex h-8 items-center justify-center rounded text-stone-600 hover:bg-stone-50"
                      type="button"
                      title="View document"
                      onClick={() => onViewDocument(document.id)}
                    >
                      <Eye size={15} aria-hidden="true" />
                    </button>
                    <button
                      className="inline-flex h-8 items-center justify-center rounded text-stone-600 hover:bg-stone-50"
                      type="button"
                      title="Inspect metadata"
                      onClick={() => onInspectDocument(document.id)}
                    >
                      <FileSearch size={15} aria-hidden="true" />
                    </button>
                    <button
                      className="inline-flex h-8 items-center justify-center rounded text-stone-600 hover:bg-stone-50 disabled:text-stone-300"
                      type="button"
                      title="Re-index document"
                      disabled={isReindexing === document.id}
                      onClick={() => onReindex(document.id)}
                    >
                      <RefreshCw className={isReindexing === document.id ? 'animate-spin' : ''} size={15} aria-hidden="true" />
                    </button>
                    <button
                      className="inline-flex h-8 items-center justify-center rounded text-stone-600 hover:bg-red-50 hover:text-red-600"
                      type="button"
                      title="Delete document"
                      onClick={() => onDelete(document.id)}
                    >
                      <Trash2 size={15} aria-hidden="true" />
                    </button>
                  </div>

                  {inspectedDocumentId === document.id && (
                    <DocumentMetadata detail={documentDetails} isLoading={isInspecting} />
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </aside>
  );
}

function ConversationRow({
  isActive,
  thread,
  onNameFromContext,
  onDeleteConversation,
  onRenameThread,
  onSelectThread,
}: {
  isActive: boolean;
  thread: ChatThread;
  onNameFromContext: (threadId: string) => void;
  onDeleteConversation: (threadId: string) => void;
  onRenameThread: (threadId: string, title: string) => void;
  onSelectThread: (threadId: string) => void;
}) {
  const [isRenaming, setIsRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState(thread.title);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = draftTitle.trim();
    if (title) {
      onRenameThread(thread.id, title);
      setIsRenaming(false);
    }
  }

  if (isRenaming) {
    return (
      <form className="flex items-center gap-1 rounded bg-white p-1 shadow-sm" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded border border-stone-200 px-2 py-1 text-sm outline-none focus:border-stone-500"
          value={draftTitle}
          onChange={(event) => setDraftTitle(event.target.value)}
          autoFocus
        />
        <button className="inline-flex h-7 w-7 items-center justify-center rounded text-stone-600 hover:bg-stone-100" type="submit" title="Save name">
          <Check size={14} aria-hidden="true" />
        </button>
        <button
          className="inline-flex h-7 w-7 items-center justify-center rounded text-stone-600 hover:bg-stone-100"
          type="button"
          title="Cancel rename"
          onClick={() => {
            setDraftTitle(thread.title);
            setIsRenaming(false);
          }}
        >
          <X size={14} aria-hidden="true" />
        </button>
      </form>
    );
  }

  return (
    <div className={`group flex items-center gap-1 rounded ${isActive ? 'bg-white text-stone-950 shadow-sm' : 'text-stone-700 hover:bg-white/70'}`}>
      <button
        className="min-w-0 flex-1 truncate px-3 py-2 text-left text-sm"
        type="button"
        onClick={() => onSelectThread(thread.id)}
        title={thread.title}
      >
        {thread.title}
      </button>
      <button
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded text-stone-500 opacity-100 hover:bg-stone-100 hover:text-amber-700 md:opacity-0 md:group-hover:opacity-100"
        type="button"
        title="Name from selected document and prompt"
        onClick={() => onNameFromContext(thread.id)}
      >
        <Sparkles size={14} aria-hidden="true" />
      </button>
      <button
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded text-stone-500 opacity-100 hover:bg-red-50 hover:text-red-600 md:opacity-0 md:group-hover:opacity-100"
        type="button"
        title="Delete chat"
        onClick={() => onDeleteConversation(thread.id)}
      >
        <Trash2 size={14} aria-hidden="true" />
      </button>
      <button
        className="mr-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded text-stone-500 opacity-100 hover:bg-stone-100 hover:text-stone-900 md:opacity-0 md:group-hover:opacity-100"
        type="button"
        title="Rename chat"
        onClick={() => setIsRenaming(true)}
      >
        <Pencil size={14} aria-hidden="true" />
      </button>
    </div>
  );
}

function DocumentMetadata({
  detail,
  isLoading,
}: {
  detail: DocumentDetail | null;
  isLoading: boolean;
}) {
  if (isLoading) {
    return <div className="mt-3 rounded bg-stone-50 p-3 text-xs text-stone-500">Loading metadata...</div>;
  }
  if (!detail) {
    return null;
  }

  return (
    <div className="mt-3 rounded bg-stone-50 p-3 text-xs text-stone-600">
      <dl className="grid grid-cols-[84px_1fr] gap-x-2 gap-y-1">
        <dt className="text-stone-400">Type</dt>
        <dd className="truncate">{detail.content_type}</dd>
        <dt className="text-stone-400">Created</dt>
        <dd>{new Date(detail.created_at).toLocaleString()}</dd>
        <dt className="text-stone-400">Characters</dt>
        <dd>{detail.characters.toLocaleString()}</dd>
        <dt className="text-stone-400">Source</dt>
        <dd className="truncate" title={detail.file_path}>{detail.file_path}</dd>
      </dl>
    </div>
  );
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
