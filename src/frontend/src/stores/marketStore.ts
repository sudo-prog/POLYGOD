import { create } from 'zustand';

export interface Market {
  id: string;
  slug: string;
  title: string;
  description?: string | null;
  volume_24h: number;
  volume_7d: number;
  liquidity: number;
  yes_percentage?: number;
  yes_price?: number;
  outcomes?: Array<{ price: number }>;
  is_active: boolean;
  end_date?: string | null;
  image_url?: string | null;
  last_updated?: string | null;
}

export type Timeframe = '24H' | '7D' | '1M' | 'ALL';
export type ShareType = 'Yes' | 'No';

export interface RAGGodData {
  paper_pnl: number;
  paper_stats: {
    total_pnl: number;
    current_capital: number;
    return_pct: number;
    open_positions: number;
    total_trades: number;
    win_rate: number;
    recent_pnls: number[];
  };
  mode: number;
  mode_name: string;
  whale_alert: string;
  timestamp: string;
}

export interface RAGGodState {
  isConnected: boolean;
  data: RAGGodData | null;
  lastAlert: string | null;
  reconnectAttempts: number;
}

interface MarketStore {
  selectedMarket: Market | null;
  selectedTimeframe: Timeframe;
  selectedShareType: ShareType;
  searchQuery: string;
  ragGodState: RAGGodState;
  setSelectedMarket: (market: Market | null) => void;
  setSelectedTimeframe: (timeframe: Timeframe) => void;
  setSelectedShareType: (shareType: ShareType) => void;
  setSearchQuery: (query: string) => void;
  setRagGodState: (state: Partial<RAGGodState>) => void;
  resetRagGodState: () => void;
  updatePolyGod: (data: Partial<RAGGodData>) => void;
}

const initialRagGodState: RAGGodState = {
  isConnected: false,
  data: null,
  lastAlert: null,
  reconnectAttempts: 0,
};

export const useMarketStore = create<MarketStore>((set) => ({
  selectedMarket: null,
  selectedTimeframe: '24H',
  selectedShareType: 'Yes',
  searchQuery: '',
  ragGodState: initialRagGodState,
  setSelectedMarket: (market) => set({ selectedMarket: market }),
  setSelectedTimeframe: (timeframe) => set({ selectedTimeframe: timeframe }),
  setSelectedShareType: (shareType) => set({ selectedShareType: shareType }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setRagGodState: (state) =>
    set((prev) => ({
      ragGodState: { ...prev.ragGodState, ...state },
    })),
  resetRagGodState: () => set({ ragGodState: initialRagGodState }),
  updatePolyGod: (data) =>
    set((state) => ({
      ragGodState: {
        ...state.ragGodState,
        data: { ...state.ragGodState.data, ...data } as RAGGodData,
      },
    })),
}));
