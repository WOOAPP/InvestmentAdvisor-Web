import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState('');
  const { login, register } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
      navigate('/');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Wystapil blad');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-[var(--bg2)] p-4 sm:p-8 rounded-xl border border-[var(--gray)] w-full max-w-md mx-3 sm:mx-0">
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
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-4 py-2 text-[var(--fg)] focus:border-[var(--accent)] outline-none"
          />
          <input
            type="password"
            placeholder="Haslo"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-4 py-2 text-[var(--fg)] focus:border-[var(--accent)] outline-none"
          />
          {error && <p className="text-[var(--red)] text-sm">{error}</p>}
          <button
            type="submit"
            className="bg-[var(--accent)] text-[var(--bg)] py-2 rounded font-semibold hover:opacity-90 transition-opacity"
          >
            {isRegister ? 'Zarejestruj' : 'Zaloguj'}
          </button>
        </form>
        <p className="text-center text-sm text-[var(--overlay)] mt-4">
          {isRegister ? 'Masz juz konto?' : 'Nie masz konta?'}{' '}
          <button
            onClick={() => setIsRegister(!isRegister)}
            className="text-[var(--accent)] hover:underline bg-transparent border-none cursor-pointer"
          >
            {isRegister ? 'Zaloguj sie' : 'Zarejestruj sie'}
          </button>
        </p>
      </div>
    </div>
  );
}
