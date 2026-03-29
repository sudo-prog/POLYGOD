import { create } from 'zustand';

interface RAGGodData {
  [key: string]: unknown;
}

interface RAGGodState {
  data: RAGGodData | null;
  updateRAGGod: (data: RAGGodData) => void;
}

export const useStore = create<RAGGodState>((set) => ({
  data: null,
  updateRAGGod: (data) => set({ data }),
}));
