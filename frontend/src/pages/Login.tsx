import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

function getPasswordStrength(password: string): { label: string; color: string; width: string } {
  if (password.length === 0) return { label: '', color: '', width: '0%' };
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (score <= 1) return { label: 'Słabe', color: 'var(--red)', width: '25%' };
  if (score <= 2) return { label: 'Średnie', color: 'var(--yellow)', width: '50%' };
  if (score <= 3) return { label: 'Dobre', color: 'var(--accent)', width: '75%' };
  return { label: 'Silne', color: 'var(--green)', width: '100%' };
}

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState('');
  const { login, register } = useAuthStore();
  const navigate = useNavigate();

  const strength = isRegister ? getPasswordStrength(password) : { label: '', color: '', width: '0%' };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (isRegister) {
      if (password.length < 8) {
        setError('Hasło musi mieć co najmniej 8 znaków');
        return;
      }
      if (!/[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
        setError('Hasło musi zawierać co najmniej jedną cyfrę lub znak specjalny');
        return;
      }
      if (password !== confirmPassword) {
        setError('Hasła nie są identyczne');
        return;
      }
    }

    try {
      if (isRegister) {
        await register(email, password, displayName || undefined);
      } else {
        await login(email, password);
      }
      navigate('/');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string | { msg: string }[] } } })?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join(', '));
      } else {
        setError(detail || 'Wystąpił błąd. Spróbuj ponownie.');
      }
    }
  };

  const switchMode = () => {
    setIsRegister(!isRegister);
    setError('');
    setPassword('');
    setConfirmPassword('');
    setDisplayName('');
  };

  const inputClass = "bg-[var(--bg)] border border-[var(--gray)] rounded px-4 py-2 text-[var(--fg)] focus:border-[var(--accent)] outline-none";

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-[var(--bg2)] p-4 sm:p-8 rounded-xl border border-[var(--gray)] w-full max-w-md mx-4 sm:mx-auto">
        <h1 className="text-2xl font-bold text-[var(--accent)] mb-6 text-center">
          InvestmentAdvisor
        </h1>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className={inputClass}
          />
          {isRegister && (
            <input
              type="text"
              placeholder="Nazwa wyświetlana (opcjonalnie)"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={50}
              className={inputClass}
            />
          )}
          <div className="flex flex-col gap-1">
            <input
              type="password"
              placeholder="Hasło"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className={inputClass}
            />
            {isRegister && password.length > 0 && (
              <div className="flex flex-col gap-1">
                <div className="h-1 rounded bg-[var(--gray)] overflow-hidden">
                  <div
                    className="h-full rounded transition-all duration-300"
                    style={{ width: strength.width, backgroundColor: strength.color }}
                  />
                </div>
                <span className="text-xs" style={{ color: strength.color }}>{strength.label}</span>
              </div>
            )}
            {isRegister && (
              <p className="text-xs text-[var(--overlay)]">
                Min. 8 znaków, co najmniej jedna cyfra lub znak specjalny
              </p>
            )}
          </div>
          {isRegister && (
            <input
              type="password"
              placeholder="Powtórz hasło"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className={inputClass}
            />
          )}
          {error && <p className="text-[var(--red)] text-sm">{error}</p>}
          <button
            type="submit"
            className="bg-[var(--accent)] text-[var(--bg)] py-2 rounded font-semibold hover:opacity-90 transition-opacity"
          >
            {isRegister ? 'Zarejestruj się' : 'Zaloguj się'}
          </button>
        </form>
        <p className="text-center text-sm text-[var(--overlay)] mt-4">
          {isRegister ? 'Masz już konto?' : 'Nie masz konta?'}{' '}
          <button
            onClick={switchMode}
            className="text-[var(--accent)] hover:underline bg-transparent border-none cursor-pointer"
          >
            {isRegister ? 'Zaloguj się' : 'Zarejestruj się'}
          </button>
        </p>
      </div>
    </div>
  );
}
