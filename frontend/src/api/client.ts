import type {
  AnswerResponse,
  AuthResponse,
  Citation,
  DocumentDetail,
  DocumentPreview,
  DocumentSummary,
  ServerConversation,
  StructuredAnswer,
  UserProfile,
  UploadStatusResponse,
  ProviderStatus,
} from '../types/rag';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const ACCESS_TOKEN_KEY = 'rag_access_token';
const REFRESH_TOKEN_KEY = 'rag_refresh_token';

export function getStoredAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens(response: AuthResponse) {
  localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchWithAuth(path, init);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(formatApiError(error, response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function fetchWithAuth(path: string, init?: RequestInit, retry = true): Promise<Response> {
  const headers = new Headers(init?.headers);
  const accessToken = getStoredAccessToken();
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (response.status !== 401 || !retry || path === '/api/auth/refresh') {
    return response;
  }

  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    return response;
  }

  try {
    const refreshed = await refreshSession(refreshToken);
    storeTokens(refreshed);
    return fetchWithAuth(path, init, false);
  } catch {
    clearTokens();
    return response;
  }
}

export async function registerUser(name: string, email: string, password: string): Promise<AuthResponse> {
  const response = await request<AuthResponse>('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  });
  storeTokens(response);
  return response;
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  const response = await request<AuthResponse>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  storeTokens(response);
  return response;
}

export function refreshSession(refreshToken: string): Promise<AuthResponse> {
  return request<AuthResponse>('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function logoutUser(): Promise<void> {
  const refreshToken = getStoredRefreshToken();
  if (refreshToken) {
    await request<void>('/api/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => undefined);
  }
  clearTokens();
}

export function getProfile(): Promise<UserProfile> {
  return request<UserProfile>('/api/auth/me');
}

export function requestPasswordReset(email: string): Promise<{ message: string }> {
  return request<{ message: string }>('/api/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(resetToken: string, newPassword: string): Promise<void> {
  return request<void>('/api/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reset_token: resetToken, new_password: newPassword }),
  });
}

export function listDocuments(): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>('/api/documents');
}

export function getDocument(documentId: string): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/api/documents/${documentId}`);
}

export function getDocumentPreview(documentId: string): Promise<DocumentPreview> {
  return request<DocumentPreview>(`/api/documents/${documentId}/preview`).then((preview) => ({
    ...preview,
    file_url: toApiUrl(preview.file_url),
  }));
}

export function getDocumentFileUrl(documentId: string): string {
  return withAccessToken(`${API_BASE_URL}/api/documents/${documentId}/file`);
}

function toApiUrl(pathOrUrl: string): string {
  const url = /^https?:\/\//i.test(pathOrUrl)
    ? pathOrUrl
    : `${API_BASE_URL}${pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`}`;
  return withAccessToken(url);
}

function withAccessToken(url: string): string {
  const accessToken = getStoredAccessToken();
  if (!accessToken) {
    return url;
  }
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}access_token=${encodeURIComponent(accessToken)}`;
}

function formatApiError(error: unknown, status: number): string {
  if (isValidationError(error)) {
    return error.detail
      .map((item) => {
        const field = item.loc[item.loc.length - 1];
        return `${capitalize(String(field))}: ${cleanValidationMessage(item.msg)}`;
      })
      .join(' ');
  }

  if (isDetailError(error)) {
    return typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail);
  }

  return `Request failed with ${status}`;
}

function isValidationError(
  error: unknown,
): error is { detail: Array<{ loc: Array<string | number>; msg: string }> } {
  return (
    typeof error === 'object' &&
    error !== null &&
    Array.isArray((error as { detail?: unknown }).detail)
  );
}

function isDetailError(error: unknown): error is { detail: unknown } {
  return typeof error === 'object' && error !== null && 'detail' in error;
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ');
}

function cleanValidationMessage(message: string) {
  return message.replace(/^Value error,\s*/i, '');
}

export function uploadDocument(file: File): Promise<UploadStatusResponse> {
  const body = new FormData();
  body.append('file', file);
  return request<UploadStatusResponse>('/api/documents', {
    method: 'POST',
    body,
  });
}

export function deleteDocument(documentId: string): Promise<void> {
  return request<void>(`/api/documents/${documentId}`, {
    method: 'DELETE',
  });
}

export function reindexDocument(documentId: string): Promise<UploadStatusResponse> {
  return request<UploadStatusResponse>(`/api/documents/${documentId}/reindex`, {
    method: 'POST',
  });
}

export function renameConversation(sessionId: string, title: string): Promise<{ id: string; title: string }> {
  return request<{ id: string; title: string }>(`/api/conversations/${sessionId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title }),
  });
}

export function listConversations(): Promise<ServerConversation[]> {
  return request<ServerConversation[]>('/api/conversations');
}

export function deleteConversation(sessionId: string): Promise<void> {
  return request<void>(`/api/conversations/${sessionId}`, {
    method: 'DELETE',
  });
}

export function askQuestion(question: string, sessionId = 'default'): Promise<AnswerResponse> {
  return request<AnswerResponse>('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question, session_id: sessionId }),
  });
}

export async function streamQuestion(
  question: string,
  sessionId: string,
  handlers: {
    onSources: (citations: Citation[]) => void;
    onStructured?: (response: StructuredAnswer) => void;
    onDelta: (text: string) => void;
    onDone: () => void;
  },
): Promise<void> {
  const response = await fetchWithAuth('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question, session_id: sessionId, limit: 4 }),
  });

  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => null);
    throw new Error(formatApiError(error, response.status));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.trim()) {
        continue;
      }

      const payload = JSON.parse(line) as { event: string; data: unknown };
      if (payload.event === 'sources') {
        handlers.onSources(payload.data as Citation[]);
      }
      if (payload.event === 'structured') {
        handlers.onStructured?.(payload.data as StructuredAnswer);
      }
      if (payload.event === 'delta') {
        handlers.onDelta(String(payload.data));
      }
      if (payload.event === 'done') {
        handlers.onDone();
      }
    }
  }
}

export function listProviders(): Promise<ProviderStatus[]> {
  return request<ProviderStatus[]>('/api/settings/providers');
}

export function saveProvider(provider: string, apiKey: string): Promise<ProviderStatus> {
  return request<ProviderStatus>('/api/settings/providers', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
}

export function deleteProvider(provider: string): Promise<void> {
  return request<void>(`/api/settings/providers/${encodeURIComponent(provider)}`, {
    method: 'DELETE',
  });
}
