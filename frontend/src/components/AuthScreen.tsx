import { KeyRound, Loader2, ShieldCheck } from 'lucide-react';
import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';

type Props = {
  error: string | null;
  successMessage?: string | null;
  isLoading: boolean;
  initialResetToken?: string | null;
  onForgotPassword: (email: string) => Promise<string>;
  onLogin: (email: string, password: string) => void;
  onRegister: (name: string, email: string, password: string) => void;
  onResetPassword: (token: string, password: string) => void;
};

export function AuthScreen({
  error,
  successMessage,
  isLoading,
  initialResetToken,
  onForgotPassword,
  onLogin,
  onRegister,
  onResetPassword,
}: Props) {
  const [mode, setMode] = useState<'login' | 'register' | 'forgot' | 'reset'>(
    initialResetToken ? 'reset' : 'login',
  );
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [resetToken, setResetToken] = useState(initialResetToken ?? '');
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  // The reset token arrives via the URL query parameter and is held only in
  // state. Once the reset succeeds (signalled by the parent's success
  // message), drop it from state and return to the login form.
  useEffect(() => {
    if (successMessage) {
      setResetToken('');
      setPassword('');
      setMode('login');
    }
  }, [successMessage]);

  const passwordChecks = getPasswordChecks(password);
  const shouldEnforcePasswordPolicy = mode === 'register' || mode === 'reset';
  const canSubmitPassword = shouldEnforcePasswordPolicy
    ? passwordChecks.every((check) => check.isMet)
    : password.length > 0;
  const canSubmit =
    mode === 'forgot'
      ? email.trim().length > 0
      : mode === 'reset'
        ? resetToken.trim().length > 0 && canSubmitPassword
        : canSubmitPassword;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    if (mode === 'register') {
      onRegister(name, email, password);
    } else if (mode === 'forgot') {
      void handleForgotPassword();
    } else if (mode === 'reset') {
      onResetPassword(resetToken, password);
    } else {
      onLogin(email, password);
    }
  }

  async function handleForgotPassword() {
    const message = await onForgotPassword(email);
    setResetMessage(message);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f8f5ee] px-4">
      <section className="grid w-full max-w-5xl overflow-hidden rounded border border-stone-200 bg-white shadow-xl md:grid-cols-[1fr_420px]">
        <div className="hidden bg-stone-950 p-10 text-white md:block">
          <div className="flex h-12 w-12 items-center justify-center rounded bg-white/10">
            <ShieldCheck size={24} aria-hidden="true" />
          </div>
          <h1 className="mt-8 text-3xl font-semibold">Private RAG workspace</h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-stone-300">
            Each account gets its own document library, chat history, and retrieval scope. Access is protected with expiring JWT sessions.
          </p>
        </div>

        <form className="p-6 md:p-8" onSubmit={submit}>
          <div className="flex h-11 w-11 items-center justify-center rounded bg-stone-950 text-white md:hidden">
            <KeyRound size={21} aria-hidden="true" />
          </div>
          <h2 className="mt-5 text-2xl font-semibold text-stone-950">
            {mode === 'register'
              ? 'Create account'
              : mode === 'forgot'
                ? 'Forgot password'
                : mode === 'reset'
                  ? 'Reset password'
                  : 'Welcome back'}
          </h2>
          <p className="mt-2 text-sm text-stone-500">
            {mode === 'register'
              ? 'Register to create a user-specific document library.'
              : mode === 'forgot'
                ? 'Enter your email and we will send a secure reset link.'
              : mode === 'reset'
                ? 'Choose a new password for your account.'
                : 'Sign in to continue to your documents and chats.'}
          </p>

          {error && <div className="mt-5 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
          {successMessage && <div className="mt-5 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{successMessage}</div>}
          {resetMessage && <div className="mt-5 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">{resetMessage}</div>}

          <div className="mt-6 space-y-4">
            {mode === 'register' && (
              <label className="block">
                <span className="text-xs font-medium text-stone-600">Name</span>
                <input className="mt-1 h-10 w-full rounded border border-stone-300 px-3 text-sm outline-none focus:border-stone-600" value={name} onChange={(event) => setName(event.target.value)} />
              </label>
            )}
            {(mode === 'login' || mode === 'register' || mode === 'forgot') && (
              <label className="block">
                <span className="text-xs font-medium text-stone-600">Email</span>
                <input className="mt-1 h-10 w-full rounded border border-stone-300 px-3 text-sm outline-none focus:border-stone-600" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
              </label>
            )}
            {mode !== 'forgot' && (
              <label className="block">
                <span className="text-xs font-medium text-stone-600">{mode === 'reset' ? 'New password' : 'Password'}</span>
                <input
                  className="mt-1 h-10 w-full rounded border border-stone-300 px-3 text-sm outline-none focus:border-stone-600"
                  type="password"
                  minLength={8}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                {shouldEnforcePasswordPolicy ? (
                  <ul className="mt-2 grid gap-1 text-xs text-stone-500 sm:grid-cols-2">
                    {passwordChecks.map((check) => (
                      <li key={check.label} className={password && !check.isMet ? 'text-red-600' : check.isMet ? 'text-emerald-700' : 'text-stone-500'}>
                        {check.label}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="mt-1 block text-xs text-stone-500">Enter your account password.</span>
                )}
              </label>
            )}
          </div>

          <button className="mt-6 inline-flex h-10 w-full items-center justify-center gap-2 rounded bg-stone-950 px-4 text-sm font-medium text-white hover:bg-stone-800 disabled:bg-stone-300" type="submit" disabled={isLoading || !canSubmit}>
            {isLoading && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
            {mode === 'register'
              ? 'Create account'
              : mode === 'forgot'
                ? 'Send reset link'
                : mode === 'reset'
                  ? 'Reset password'
                  : 'Log in'}
          </button>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-sm">
            <button className="text-stone-600 hover:text-stone-950" type="button" onClick={() => setMode(mode === 'register' ? 'login' : 'register')}>
              {mode === 'register' ? 'Already have an account?' : 'Create an account'}
            </button>
            {mode === 'login' && (
              <button className="text-stone-600 hover:text-stone-950" type="button" onClick={() => setMode('forgot')}>
                Forgot password
              </button>
            )}
            {(mode === 'forgot' || mode === 'reset') && (
              <button className="text-stone-600 hover:text-stone-950" type="button" onClick={() => setMode('login')}>
                Back to login
              </button>
            )}
          </div>
        </form>
      </section>
    </main>
  );
}

function getPasswordChecks(password: string) {
  return [
    { label: 'At least 8 characters', isMet: password.length >= 8 },
    { label: 'One uppercase letter', isMet: /[A-Z]/.test(password) },
    { label: 'One lowercase letter', isMet: /[a-z]/.test(password) },
    { label: 'One number', isMet: /\d/.test(password) },
    { label: 'One special character', isMet: /[^A-Za-z0-9]/.test(password) },
  ];
}
