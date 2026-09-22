import { useEffect, useState } from 'react';
import { Check, ExternalLink, Eye, EyeOff, KeyRound, Lock, ShieldCheck, Trash2, X } from 'lucide-react';
import { deleteProvider, listProviders, saveProvider } from '../api/client';
import type { ProviderStatus } from '../types/rag';

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function ApiKeyModal({ isOpen, onClose }: Props) {
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [geminiKeyInput, setGeminiKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadProviders();
      setGeminiKeyInput('');
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  }, [isOpen]);

  async function loadProviders() {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await listProviders();
      setProviders(data);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to load provider settings.');
    } finally {
      setIsLoading(false);
    }
  }

  const geminiStatus = providers.find((p) => p.provider === 'gemini');

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!geminiKeyInput.trim()) {
      setErrorMessage('Please enter an API key.');
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const updated = await saveProvider('gemini', geminiKeyInput.trim());
      setGeminiKeyInput('');
      setShowKey(false);
      setSuccessMessage('Gemini API key successfully saved and encrypted.');
      setProviders((prev) =>
        prev.map((p) => (p.provider === 'gemini' ? updated : p))
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to save API key.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to remove your custom Gemini API key?')) {
      return;
    }

    setIsDeleting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deleteProvider('gemini');
      setSuccessMessage('Custom API key removed. Reverted to default.');
      await loadProviders();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to remove API key.');
    } finally {
      setIsDeleting(false);
    }
  }

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/40 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-hidden rounded-lg border border-stone-200 bg-[#fbfaf7] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-200 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-stone-950 text-white">
              <KeyRound size={16} aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-stone-950">LLM Provider Settings</h2>
              <p className="text-xs text-stone-500">Configure your personal API keys</p>
            </div>
          </div>
          <button
            type="button"
            className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
            onClick={onClose}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Security Notice */}
          <div className="flex items-start gap-2.5 rounded-md border border-stone-200 bg-white p-3 text-xs text-stone-600">
            <Lock size={15} className="mt-0.5 shrink-0 text-stone-500" aria-hidden="true" />
            <p>
              Your API keys are encrypted at rest using server-side encryption. They are never returned in plaintext, logged, or shared with other users.
            </p>
          </div>

          {/* Feedback messages */}
          {errorMessage && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              {errorMessage}
            </div>
          )}
          {successMessage && (
            <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
              <Check size={14} className="shrink-0 text-emerald-600" aria-hidden="true" />
              <span>{successMessage}</span>
            </div>
          )}

          {isLoading ? (
            <div className="py-8 text-center text-xs text-stone-500">Loading settings...</div>
          ) : (
            <div className="space-y-4">
              {/* Gemini Provider Card */}
              <div className="rounded-lg border border-stone-200 bg-white p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-stone-950">Google Gemini</span>
                    <span className="text-[11px] text-stone-400">gemini-2.5-flash</span>
                  </div>
                  <div>
                    {geminiStatus?.is_custom ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                        <ShieldCheck size={12} aria-hidden="true" />
                        Custom Key Active
                      </span>
                    ) : geminiStatus?.has_system_fallback ? (
                      <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                        System Key Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full border border-stone-200 bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-600">
                        Not Configured
                      </span>
                    )}
                  </div>
                </div>

                {/* Status description */}
                <div className="mt-2 text-xs text-stone-600">
                  {geminiStatus?.is_custom ? (
                    <div className="flex items-center justify-between pt-1">
                      <p className="font-mono text-stone-700">
                        Key: {geminiStatus.masked_key}
                      </p>
                      <button
                        type="button"
                        disabled={isDeleting}
                        onClick={handleDelete}
                        className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                      >
                        <Trash2 size={13} aria-hidden="true" />
                        {isDeleting ? 'Removing...' : 'Remove Key'}
                      </button>
                    </div>
                  ) : geminiStatus?.has_system_fallback ? (
                    <p className="text-stone-500">
                      Using the shared system default key. Provide your own key below to override it.
                    </p>
                  ) : (
                    <p className="text-amber-700">
                      No Gemini key is available. Add your personal key below to enable chat.
                    </p>
                  )}
                </div>

                {/* Input form */}
                <form onSubmit={handleSave} className="mt-4 space-y-2 border-t border-stone-100 pt-3">
                  <label htmlFor="gemini-key" className="block text-xs font-medium text-stone-700">
                    {geminiStatus?.is_custom ? 'Update API Key' : 'Enter Gemini API Key'}
                  </label>
                  <div className="relative">
                    <input
                      id="gemini-key"
                      type={showKey ? 'text' : 'password'}
                      value={geminiKeyInput}
                      onChange={(e) => setGeminiKeyInput(e.target.value)}
                      placeholder="AIzaSy... or AQ.Ab..."
                      className="w-full rounded border border-stone-300 bg-[#fbfaf7] px-3 py-2 pr-10 text-xs font-mono text-stone-900 placeholder:text-stone-400 focus:border-stone-950 focus:outline-none"
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowKey((prev) => !prev)}
                      className="absolute right-2.5 top-2.5 text-stone-400 hover:text-stone-600"
                      title={showKey ? 'Hide key' : 'Show key'}
                    >
                      {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <a
                      href="https://aistudio.google.com/app/apikey"
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-stone-500 hover:text-stone-800"
                    >
                      Get key from Google AI Studio
                      <ExternalLink size={11} aria-hidden="true" />
                    </a>

                    <button
                      type="submit"
                      disabled={isSaving || !geminiKeyInput.trim()}
                      className="rounded bg-stone-950 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-800 disabled:opacity-50"
                    >
                      {isSaving ? 'Saving...' : geminiStatus?.is_custom ? 'Update Key' : 'Save Key'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-stone-200 bg-stone-50 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-stone-300 bg-white px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
