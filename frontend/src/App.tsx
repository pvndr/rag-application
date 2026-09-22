import { useEffect, useState } from 'react';
import {
  clearTokens,
  deleteDocument,
  deleteConversation,
  getDocument,
  getDocumentPreview,
  getProfile,
  getStoredAccessToken,
  listConversations,
  listDocuments,
  loginUser,
  logoutUser,
  reindexDocument,
  registerUser,
  renameConversation,
  requestPasswordReset,
  resetPassword,
  streamQuestion,
  uploadDocument,
} from './api/client';
import { ApiKeyModal } from './components/ApiKeyModal';
import { AuthScreen } from './components/AuthScreen';
import { ChatWorkspace } from './components/ChatWorkspace';
import { DocumentPanel } from './components/DocumentPanel';
import { DocumentViewer } from './components/DocumentViewer';
import type {
  AuthResponse,
  ChatMessage,
  ChatThread,
  Citation,
  DocumentDetail,
  DocumentPreview,
  DocumentSummary,
  ServerConversation,
  UserProfile,
} from './types/rag';

const initialThread: ChatThread = {
  id: crypto.randomUUID(),
  title: 'New conversation',
  messages: [],
  updatedAt: new Date().toISOString(),
};

export default function App() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [threads, setThreads] = useState<ChatThread[]>([initialThread]);
  const [activeThreadId, setActiveThreadId] = useState(initialThread.id);
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [authMessage, setAuthMessage] = useState<string | null>(null);
  const [documentDetails, setDocumentDetails] = useState<DocumentDetail | null>(null);
  const [documentPreview, setDocumentPreview] = useState<DocumentPreview | null>(null);
  const [inspectedDocumentId, setInspectedDocumentId] = useState<string | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const [isViewingDocument, setIsViewingDocument] = useState(false);
  const [isReindexing, setIsReindexing] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const activeThread = threads.find((thread) => thread.id === activeThreadId) ?? threads[0];

  useEffect(() => {
    if (!getStoredAccessToken()) {
      setIsAuthLoading(false);
      return;
    }
    getProfile()
      .then((profile) => {
        setUser(profile);
      })
      .catch(() => {
        clearTokens();
        setUser(null);
      })
      .finally(() => setIsAuthLoading(false));
  }, []);

  useEffect(() => {
    if (!user) {
      return;
    }
    loadWorkspace();
  }, [user]);

  async function loadWorkspace() {
    setError(null);
    try {
      const [documentList, conversationList] = await Promise.all([
        listDocuments(),
        listConversations(),
      ]);
      setDocuments(documentList);
      const loadedThreads = conversationList.map(mapConversation);
      const nextThreads = loadedThreads.length > 0 ? loadedThreads : [createThread()];
      setThreads(nextThreads);
      setActiveThreadId(nextThreads[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your workspace');
    }
  }

  async function handleAuthResult(action: () => Promise<AuthResponse>) {
    setIsAuthLoading(true);
    setError(null);
    try {
      const response = await action();
      setUser(response.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setIsAuthLoading(false);
    }
  }

  async function handleLogout() {
    await logoutUser();
    setUser(null);
    setDocuments([]);
    const thread = createThread();
    setThreads([thread]);
    setActiveThreadId(thread.id);
    setDocumentPreview(null);
    setDocumentDetails(null);
  }

  async function handleUpload(file: File) {
    setIsUploading(true);
    setError(null);
    try {
      const upload = await uploadDocument(file);
      setDocuments((current) => [upload.document, ...current]);
      updateActiveThread((thread) => ({
        ...thread,
        title:
          thread.messages.length === 0
            ? makeTitle(upload.document.filename.replace(/\.[^.]+$/, ''))
            : thread.title,
        messages: [
          ...thread.messages,
          {
            id: crypto.randomUUID(),
            role: 'user',
            content: `Uploaded ${upload.document.filename}`,
            attachments: [upload.document],
          },
        ],
        updatedAt: new Date().toISOString(),
      }));
      await openDocumentPreview(upload.document.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDelete(documentId: string) {
    setError(null);
    try {
      await deleteDocument(documentId);
      setDocuments((current) => current.filter((document) => document.id !== documentId));
      if (inspectedDocumentId === documentId) {
        setInspectedDocumentId(null);
        setDocumentDetails(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  }

  async function handleInspectDocument(documentId: string) {
    if (inspectedDocumentId === documentId) {
      setInspectedDocumentId(null);
      setDocumentDetails(null);
      return;
    }

    setInspectedDocumentId(documentId);
    setIsInspecting(true);
    setError(null);
    try {
      const detail = await getDocument(documentId);
      setDocumentDetails(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load document metadata');
      setDocumentDetails(null);
    } finally {
      setIsInspecting(false);
    }
  }

  async function handleReindex(documentId: string) {
    setIsReindexing(documentId);
    setError(null);
    try {
      const response = await reindexDocument(documentId);
      setDocuments((current) =>
        current.map((document) => (document.id === documentId ? response.document : document)),
      );
      if (inspectedDocumentId === documentId) {
        const detail = await getDocument(documentId);
        setDocumentDetails(detail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Re-index failed');
    } finally {
      setIsReindexing(null);
    }
  }

  async function handleViewDocument(documentId: string) {
    await openDocumentPreview(documentId);
  }

  async function openDocumentPreview(documentId: string) {
    setIsViewingDocument(true);
    setDocumentPreview(null);
    setError(null);
    try {
      const preview = await getDocumentPreview(documentId);
      setDocumentPreview(preview);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load document preview');
      setIsViewingDocument(false);
    }
  }

  async function handleQuestionSubmit() {
    const prompt = input.trim();
    if (!prompt) {
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: prompt,
    };
    const assistantMessageId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      citations: [],
      isStreaming: true,
    };

    updateActiveThread((thread) => ({
      ...thread,
      title: thread.messages.length === 0 ? makeTitle(prompt) : thread.title,
      messages: [...thread.messages, userMessage, assistantMessage],
      updatedAt: new Date().toISOString(),
    }));
    setInput('');
    setIsAsking(true);
    setError(null);

    try {
      await streamQuestion(prompt, activeThreadId, {
        onSources: (citations: Citation[]) => {
          updateMessage(assistantMessageId, { citations });
        },
        onStructured: (structured) => {
          updateMessage(assistantMessageId, { structured });
        },
        onDelta: (text: string) => {
          appendToMessage(assistantMessageId, text);
        },
        onDone: () => {
          updateMessage(assistantMessageId, { isStreaming: false });
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Question failed');
      updateMessage(assistantMessageId, {
        content: 'I could not complete that request. Check the backend connection and API configuration.',
        isStreaming: false,
      });
    } finally {
      setIsAsking(false);
    }
  }

  function handleNewChat() {
    const thread = createThread();
    setThreads((current) => [thread, ...current]);
    setActiveThreadId(thread.id);
    setIsSidebarOpen(false);
  }

  async function handleRenameThread(threadId: string, title: string) {
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      return;
    }

    setThreads((current) =>
      current.map((thread) =>
        thread.id === threadId
          ? { ...thread, title: cleanTitle, updatedAt: new Date().toISOString() }
          : thread,
      ),
    );

    try {
      await renameConversation(threadId, cleanTitle);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rename failed');
    }
  }

  async function handleDeleteConversation(threadId: string) {
    setError(null);
    try {
      await deleteConversation(threadId);
      setThreads((current) => {
        const remaining = current.filter((thread) => thread.id !== threadId);
        const next = remaining.length > 0 ? remaining : [createThread()];
        if (threadId === activeThreadId) {
          setActiveThreadId(next[0].id);
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete chat failed');
    }
  }

  function handleNameFromContext(threadId: string) {
    const thread = threads.find((candidate) => candidate.id === threadId);
    if (!thread) {
      return;
    }

    const title = makeContextTitle(thread, documents, inspectedDocumentId);
    void handleRenameThread(threadId, title);
  }

  function updateActiveThread(updater: (thread: ChatThread) => ChatThread) {
    setThreads((current) =>
      current.map((thread) => (thread.id === activeThreadId ? updater(thread) : thread)),
    );
  }

  function updateMessage(messageId: string, patch: Partial<ChatMessage>) {
    updateActiveThread((thread) => ({
      ...thread,
      messages: thread.messages.map((message) =>
        message.id === messageId ? { ...message, ...patch } : message,
      ),
      updatedAt: new Date().toISOString(),
    }));
  }

  function appendToMessage(messageId: string, text: string) {
    updateActiveThread((thread) => ({
      ...thread,
      messages: thread.messages.map((message) =>
        message.id === messageId ? { ...message, content: `${message.content}${text}` } : message,
      ),
      updatedAt: new Date().toISOString(),
    }));
  }

  if (isAuthLoading && !user) {
    return <div className="flex h-screen items-center justify-center bg-[#f8f5ee] text-sm text-stone-500">Loading secure workspace...</div>;
  }

  if (!user) {
    return (
      <AuthScreen
        error={error}
        initialResetToken={getResetTokenFromUrl()}
        isLoading={isAuthLoading}
        onForgotPassword={async (email) => {
          try {
            const response = await requestPasswordReset(email);
            setError(null);
            return response.message;
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not send reset email');
            return '';
          }
        }}
        onLogin={(email, password) => void handleAuthResult(() => loginUser(email, password))}
        onRegister={(name, email, password) => void handleAuthResult(() => registerUser(name, email, password))}
        onResetPassword={(token, password) =>
          void resetPassword(token, password)
            .then(() => {
              window.history.replaceState({}, document.title, window.location.pathname);
              setAuthMessage('Your password was reset. You can log in with the new password.');
              setError(null);
            })
            .catch((err: Error) => setError(err.message))
        }
        successMessage={authMessage}
      />
    );
  }

  return (
    <div className="grid h-screen grid-cols-1 overflow-hidden bg-[#f8f5ee] text-stone-900 md:grid-cols-[320px_1fr]">
      <DocumentPanel
        activeThreadId={activeThread.id}
        conversations={threads}
        documents={documents}
        documentDetails={documentDetails}
        inspectedDocumentId={inspectedDocumentId}
        isInspecting={isInspecting}
        isOpen={isSidebarOpen}
        isReindexing={isReindexing}
        isUploading={isUploading}
        user={user}
        onDelete={handleDelete}
        onDeleteConversation={handleDeleteConversation}
        onInspectDocument={handleInspectDocument}
        onNameFromContext={handleNameFromContext}
        onNewChat={handleNewChat}
        onRenameThread={handleRenameThread}
        onReindex={handleReindex}
        onSelectThread={(threadId) => {
          setActiveThreadId(threadId);
          setIsSidebarOpen(false);
        }}
        onUpload={handleUpload}
        onViewDocument={handleViewDocument}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onLogout={handleLogout}
      />
      <ChatWorkspace
        activeTitle={activeThread.title}
        error={error}
        input={input}
        isAsking={isAsking}
        isUploading={isUploading}
        messages={activeThread.messages}
        onInputChange={setInput}
        onSubmit={handleQuestionSubmit}
        onToggleSidebar={() => setIsSidebarOpen((current) => !current)}
        onUpload={handleUpload}
        onViewDocument={handleViewDocument}
      />
      <DocumentViewer
        isLoading={isViewingDocument && !documentPreview}
        preview={documentPreview}
        onClose={() => {
          setIsViewingDocument(false);
          setDocumentPreview(null);
        }}
      />
      <ApiKeyModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
}

function makeTitle(prompt: string) {
  return prompt.length > 42 ? `${prompt.slice(0, 39)}...` : prompt;
}

function createThread(): ChatThread {
  return {
    id: crypto.randomUUID(),
    title: 'New conversation',
    messages: [],
    updatedAt: new Date().toISOString(),
    createdAt: new Date().toISOString(),
  };
}

function mapConversation(conversation: ServerConversation): ChatThread {
  return {
    id: conversation.id,
    title: conversation.title,
    updatedAt: conversation.updated_at,
    createdAt: conversation.created_at,
    messages: conversation.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      structured: message.structured ?? undefined,
    })),
  };
}

function makeContextTitle(
  thread: ChatThread,
  documents: DocumentSummary[],
  inspectedDocumentId: string | null,
) {
  const selectedDocument =
    documents.find((document) => document.id === inspectedDocumentId) ??
    findDocumentFromCitations(thread, documents) ??
    documents[0];
  const latestPrompt = [...thread.messages]
    .reverse()
    .find((message) => message.role === 'user')
    ?.content.trim();

  const documentName = selectedDocument
    ? selectedDocument.filename.replace(/\.[^.]+$/, '')
    : 'Knowledge base';
  const promptPart = latestPrompt ? summarizePrompt(latestPrompt) : 'New question';
  return `${documentName} - ${promptPart}`.slice(0, 80);
}

function findDocumentFromCitations(thread: ChatThread, documents: DocumentSummary[]) {
  const citedDocumentId = [...thread.messages]
    .reverse()
    .flatMap((message) => message.citations ?? [])
    .find((citation) => citation.document_id)?.document_id;
  return documents.find((document) => document.id === citedDocumentId);
}

function summarizePrompt(prompt: string) {
  const cleaned = prompt
    .replace(/[^\w\s-]/g, '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 7)
    .join(' ');
  return cleaned || 'New question';
}

function getResetTokenFromUrl() {
  return new URLSearchParams(window.location.search).get('token');
}
