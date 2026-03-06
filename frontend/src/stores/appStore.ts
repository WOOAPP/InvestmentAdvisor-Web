import { create } from 'zustand';

interface AppState {
  statusMsg: string;
  setStatusMsg: (msg: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  statusMsg: '',
  setStatusMsg: (msg) => set({ statusMsg: msg }),
}));
