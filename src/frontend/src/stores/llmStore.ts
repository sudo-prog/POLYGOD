import { create } from 'zustand'

export interface Provider {
    id: number
    name: string
    base_url: string | null
    models: string[]
    status: string
    uptime_24h: string
    avg_speed: number | null
    tokens_today: number
}

export interface AgentConfig {
    id: number
    agent_name: string
    provider_id: number | null
    model_name: string | null
    overrides: Record<string, unknown>
}

export interface UsageLog {
    id: number
    timestamp: string | null
    provider: string
    tokens_used: number | null
    latency_ms: number | null
    agent_name: string | null
    market_id: string | null
}

export interface HeatmapEntry {
    provider: string
    date: string
    tokens: number
}

interface LLMStore {
    selectedProvider: Provider | null
    selectedAgent: AgentConfig | null
    setSelectedProvider: (provider: Provider | null) => void
    setSelectedAgent: (agent: AgentConfig | null) => void
}

export const useLLMStore = create<LLMStore>((set) => ({
    selectedProvider: null,
    selectedAgent: null,
    setSelectedProvider: (provider) => set({ selectedProvider: provider }),
    setSelectedAgent: (agent) => set({ selectedAgent: agent }),
}))