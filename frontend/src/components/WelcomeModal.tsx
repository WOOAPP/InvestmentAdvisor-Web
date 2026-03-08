import { useState, useEffect } from 'react';

interface WelcomeModalProps {
  onClose: () => void;
  introButtonRef: React.RefObject<HTMLButtonElement | null>;
}

export default function WelcomeModal({ onClose, introButtonRef }: WelcomeModalProps) {
  const [step, setStep] = useState(0);

  // Step 2: highlight the Intro button above the overlay
  useEffect(() => {
    if (step !== 1 || !introButtonRef.current) return;
    const btn = introButtonRef.current;
    btn.style.zIndex = '200';
    btn.style.position = 'relative';
    btn.style.boxShadow = '0 0 0 4px var(--accent), 0 0 20px 4px rgba(137,180,250,0.4)';
    btn.style.animation = 'none';

    return () => {
      btn.style.zIndex = '';
      btn.style.position = '';
      btn.style.boxShadow = '';
      btn.style.animation = '';
    };
  }, [step, introButtonRef]);

  return (
    <div className="fixed inset-0 z-[160] flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-3 sm:p-4">
      <div
        className="bg-[var(--bg2)] border border-[var(--gray)] rounded-2xl shadow-2xl w-full sm:w-[520px] max-h-[85vh] sm:max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {step === 0 && (
          <>
            {/* Header with logo */}
            <div className="flex flex-col items-center pt-6 sm:pt-8 pb-3 sm:pb-4 px-5 sm:px-6">
              <img src="/logo.png" alt="IAdvisor" className="h-20 sm:h-32 mb-3 sm:mb-4" />
              <h2 className="text-lg sm:text-2xl font-bold text-[var(--fg)] text-center">
                Witaj w IAdvisor
              </h2>
            </div>

            {/* Story */}
            <div className="px-5 sm:px-8 pb-4 sm:pb-6 text-[13px] sm:text-[15px] leading-relaxed text-[var(--fg)]/85 space-y-3 sm:space-y-4">
              <p>
                Monitorowanie rynków finansowych to wyścig z czasem. Przeszukiwanie dziesiątek
                źródeł, analizowanie wykresów, śledzenie wiadomości makroekonomicznych — a najlepsze
                okazje i tak potrafią umknąć, bo nikt nie jest w stanie obserwować rynku 24 godziny
                na dobę.
              </p>
              <p>
                Właśnie dlatego powstał <span className="text-[var(--accent)] font-semibold">IAdvisor</span>.
                Platforma, która zbiera wszystkie kluczowe dane w jednym miejscu, dostosowuje je do
                Twoich instrumentów i wspiera Cię systemem <span className="text-[var(--accent)]">multiagentowym AI</span> — tak,
                abyś mógł podejmować trafne decyzje szybciej i pewniej.
              </p>
              <p className="text-[var(--overlay)] text-xs italic">
                Rynki nie czekają — ale teraz Ty masz przewagę.
              </p>
            </div>

            {/* CTA */}
            <div className="px-5 sm:px-8 pb-6 sm:pb-8 flex justify-center">
              <button
                onClick={() => setStep(1)}
                className="w-full sm:w-auto px-8 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm hover:opacity-90 transition-opacity"
              >
                Dalej
              </button>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <div className="flex flex-col items-center pt-6 sm:pt-8 pb-3 sm:pb-4 px-5 sm:px-6">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-[var(--accent)]/15 flex items-center justify-center mb-3 sm:mb-4">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="sm:w-7 sm:h-7">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>
              <h2 className="text-lg sm:text-2xl font-bold text-[var(--fg)] text-center">
                Poznaj aplikację
              </h2>
            </div>

            <div className="px-5 sm:px-8 pb-4 sm:pb-6 text-[13px] sm:text-[15px] leading-relaxed text-[var(--fg)]/85 space-y-3 sm:space-y-4">
              <p>
                Przygotowaliśmy dla Ciebie interaktywny przewodnik, który krok po kroku
                przeprowadzi Cię przez wszystkie najważniejsze funkcje —
                od konfiguracji kluczy API, przez analizy rynkowe, po czat z AI.
              </p>
              <p>
                Kliknij przycisk{' '}
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-[var(--accent)]/15 text-[var(--accent)] border border-[var(--accent)]/30">
                  Intro
                </span>{' '}
                w pasku nawigacji, aby uruchomić przewodnik w dowolnym momencie.
              </p>
            </div>

            <div className="px-5 sm:px-8 pb-6 sm:pb-8 flex flex-col-reverse sm:flex-row justify-center gap-2 sm:gap-3">
              <button
                onClick={onClose}
                className="w-full sm:w-auto px-6 py-2.5 rounded-lg bg-[var(--gray)] text-[var(--fg)] font-semibold text-sm hover:opacity-90 transition-opacity"
              >
                Pomiń
              </button>
              <button
                onClick={() => {
                  onClose();
                  setTimeout(() => introButtonRef.current?.click(), 300);
                }}
                className="w-full sm:w-auto px-6 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm hover:opacity-90 transition-opacity"
              >
                Uruchom przewodnik
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
