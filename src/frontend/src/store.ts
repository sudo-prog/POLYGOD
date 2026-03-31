import { create } from 'zustand';

interface PolyGodData {
  paper_pnl: number;
  mode: number;
  whale_alert: string;
}

interface PolyGodState {
  data: PolyGodData | null;
  updatePolyGod: (data: PolyGodData) => void;
}

export const useStore = create<PolyGodState>((set) => ({
  data: null,
  updatePolyGod: (data) => set({ data }),
}));
