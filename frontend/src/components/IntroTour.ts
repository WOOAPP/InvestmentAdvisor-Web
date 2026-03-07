import { driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';

export type TourPhase = 'settings-general' | 'settings' | 'dashboard' | 'charts' | 'calendar' | 'portfolio';

const TOUR_PHASE_KEY = 'tour_phase';

const PHASE_ORDER: TourPhase[] = ['settings-general', 'settings', 'dashboard', 'charts', 'calendar', 'portfolio'];
const PHASE_ROUTES: Record<TourPhase, string> = {
  'settings-general': '/settings',
  settings: '/settings',
  dashboard: '/',
  charts: '/charts',
  calendar: '/calendar',
  portfolio: '/portfolio',
};

const isMobile = () => window.innerWidth < 768;

function getPhaseSteps(phase: TourPhase): DriveStep[] {
  const mobile = isMobile();

  switch (phase) {
    case 'settings-general':
      return [
        {
          element: '[data-tour="settings-apikeys"]',
          popover: {
            title: 'Klucze API',
            description: 'Wprowadź klucze API dla dostawców AI (OpenAI, Anthropic lub OpenRouter). Bez klucza aplikacja nie wygeneruje analiz.',
            side: 'bottom',
            align: 'start',
          },
        },
      ];

    case 'settings':
      return [
        {
          element: '[data-tour="settings-instruments"]',
          popover: {
            title: 'Instrumenty',
            description: 'Dodaj instrumenty finansowe które chcesz obserwować. Wyszukaj po symbolu lub nazwie i wybierz z listy.',
            side: 'bottom',
            align: 'start',
          },
        },
        {
          element: '[data-tour="settings-sources"]',
          popover: {
            title: 'Źródła internetowe',
            description: 'Dodaj adresy stron z analizami i wiadomościami — AI wykorzysta ich treść podczas generowania raportów.',
            side: mobile ? 'bottom' : 'left',
            align: 'start',
          },
        },
      ];

    case 'dashboard': {
      const steps: DriveStep[] = [];
      if (mobile) {
        steps.push({
          element: '[data-tour="mobile-instruments"]',
          popover: {
            title: 'Twoje instrumenty',
            description: 'Rozwiń aby zobaczyć aktualne kursy wybranych instrumentów ze sparkline.',
            side: 'bottom',
            align: 'start',
          },
        });
        steps.push({
          element: '[data-tour="mobile-assessment"]',
          popover: {
            title: 'Ocena rynkowa',
            description: 'Wskaźniki ryzyka i okazji inwestycyjnych generowane przez AI. Kliknij aby zobaczyć szczegóły.',
            side: 'bottom',
            align: 'center',
          },
        });
      } else {
        steps.push({
          element: '[data-tour="instruments"]',
          popover: {
            title: 'Twoje instrumenty',
            description: 'Aktualne kursy wybranych instrumentów ze sparkline. Przeciągnij aby zmienić kolejność.',
            side: 'right',
            align: 'start',
          },
        });
        steps.push({
          element: '[data-tour="gauges"]',
          popover: {
            title: 'Ocena rynkowa',
            description: 'Wskaźniki ryzyka i okazji inwestycyjnych generowane przez AI na podstawie bieżących danych.',
            side: 'right',
            align: 'start',
          },
        });
      }
      steps.push({
        element: '[data-tour="run-analysis"]',
        popover: {
          title: 'Uruchom analizę',
          description: 'Główny przycisk — AI pobiera dane rynkowe, wiadomości i treści ze źródeł, a następnie generuje szczegółowy raport.',
          side: 'bottom',
          align: 'start',
        },
      });
      steps.push({
        element: '[data-tour="analysis-area"]',
        popover: {
          title: 'Raport AI',
          description: mobile
            ? 'Tu pojawi się analiza wygenerowana przez AI.'
            : 'Tu pojawi się analiza wygenerowana przez AI. Kliknij dwukrotnie aby rozwinąć na pełny ekran.',
          side: 'top',
          align: 'center',
        },
      });
      if (mobile) {
        steps.push({
          element: '[data-tour="mobile-chat-btn"]',
          popover: {
            title: 'Czat z AI',
            description: 'Otwórz czat z AI. Kontekst obejmuje bieżącą analizę, dane rynkowe i wiadomości.',
            side: 'top',
            align: 'end',
          },
        });
      } else {
        steps.push({
          element: '[data-tour="chat-panel"]',
          popover: {
            title: 'Czat z AI',
            description: 'Zadawaj pytania o rynki. Kontekst czatu obejmuje bieżącą analizę, dane rynkowe i wiadomości.',
            side: 'top',
            align: 'center',
          },
        });
      }
      return steps;
    }

    case 'charts': {
      if (mobile) {
        return [
          {
            element: '[data-tour="charts-mobile-tabs"]',
            popover: {
              title: 'Panele',
              description: 'Przełączaj między listą instrumentów, wykresem i czatem AI. Czat ma szerszy kontekst — dane z 5 interwałów, portfel i kalendarz.',
              side: 'bottom',
              align: 'center',
            },
          },
          {
            element: '[data-tour="charts-chart"]',
            popover: {
              title: 'Wykres',
              description: 'Interaktywny wykres TradingView ze statystykami i profilem instrumentu.',
              side: 'bottom',
              align: 'center',
            },
          },
        ];
      }
      return [
        {
          element: '[data-tour="charts-instruments"]',
          popover: {
            title: 'Wybierz instrument',
            description: 'Kliknij instrument z listy aby zobaczyć szczegółowy wykres z danymi historycznymi.',
            side: 'right',
            align: 'start',
          },
        },
        {
          element: '[data-tour="charts-chart"]',
          popover: {
            title: 'Wykres',
            description: 'Interaktywny wykres TradingView ze statystykami i profilem instrumentu.',
            side: 'left',
            align: 'center',
          },
        },
        {
          element: '[data-tour="charts-chat"]',
          popover: {
            title: 'Czat kontekstowy',
            description: 'Ten czat ma szerszy kontekst — obejmuje dane z 5 interwałów czasowych wybranego instrumentu, portfel i kalendarz.',
            side: 'left',
            align: 'start',
          },
        },
      ];
    }

    case 'calendar':
      return [
        {
          element: '[data-tour="calendar-events"]',
          popover: {
            title: 'Wydarzenia ekonomiczne',
            description: 'Lista nadchodzących wydarzeń makroekonomicznych z wagą wpływu na rynki.',
            side: 'bottom',
            align: 'center',
          },
        },
        {
          element: '[data-tour="calendar-analyze"]',
          popover: {
            title: 'Analiza AI wydarzenia',
            description: 'Kliknij wydarzenie aby je rozwinąć, a następnie użyj przycisku „Analizuj" — AI oceni wpływ na rynki.',
            side: 'top',
            align: 'center',
          },
        },
      ];

    case 'portfolio':
      return [
        {
          element: '[data-tour="portfolio-add"]',
          popover: {
            title: 'Dodaj pozycję',
            description: 'Dodaj instrumenty do portfela — podaj ilość i cenę zakupu. Portfel jest uwzględniany w kontekście czatu.',
            side: 'bottom',
            align: 'start',
          },
        },
        {
          element: '[data-tour="portfolio-table"]',
          popover: {
            title: 'Pozycje',
            description: 'Tabela pozycji z aktualną wyceną i bilansem zysku/straty.',
            side: 'top',
            align: 'center',
          },
        },
        {
          element: '[data-tour="portfolio-forex"]',
          popover: {
            title: 'Kursy walut',
            description: 'Bieżące kursy walut w formie kafelków ze sparkline.',
            side: 'top',
            align: 'center',
          },
        },
      ];
  }
}

function getNextPhase(current: TourPhase): TourPhase | null {
  const idx = PHASE_ORDER.indexOf(current);
  return idx < PHASE_ORDER.length - 1 ? PHASE_ORDER[idx + 1] : null;
}

export function getTourPhase(): TourPhase | null {
  return sessionStorage.getItem(TOUR_PHASE_KEY) as TourPhase | null;
}

export function clearTourPhase() {
  sessionStorage.removeItem(TOUR_PHASE_KEY);
}

export function startTour(navigate: (path: string) => void) {
  sessionStorage.setItem(TOUR_PHASE_KEY, 'settings-general');
  navigate('/settings');
}

export function runTourPhase(phase: TourPhase, navigate: (path: string) => void) {
  const steps = getPhaseSteps(phase);
  if (!steps.length) {
    // Skip to next phase if no steps (shouldn't happen)
    const next = getNextPhase(phase);
    if (next) {
      sessionStorage.setItem(TOUR_PHASE_KEY, next);
      navigate(PHASE_ROUTES[next]);
    } else {
      clearTourPhase();
    }
    return;
  }

  const isLastPhase = !getNextPhase(phase);

  const d = driver({
    steps,
    showProgress: true,
    progressText: '{{current}} / {{total}}',
    nextBtnText: 'Dalej',
    prevBtnText: 'Wstecz',
    doneBtnText: isLastPhase ? 'Gotowe' : 'Dalej →',
    allowClose: true,
    overlayOpacity: 0.6,
    stagePadding: 8,
    stageRadius: 8,
    popoverClass: 'iadvisor-tour',
    smoothScroll: true,
    onCloseClick: () => {
      clearTourPhase();
      d.destroy();
    },
    onDestroyed: () => {
      const currentPhase = getTourPhase();
      if (!currentPhase) return; // user closed tour

      const next = getNextPhase(phase);
      if (next) {
        sessionStorage.setItem(TOUR_PHASE_KEY, next);
        navigate(PHASE_ROUTES[next]);
      } else {
        clearTourPhase();
      }
    },
  });

  d.drive();
}
