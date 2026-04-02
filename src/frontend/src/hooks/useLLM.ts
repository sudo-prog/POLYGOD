import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import type { Provider, AgentConfig, UsageLog, HeatmapEntry } from '../stores/llmStore'

// ─── Providers ──────────────────────────────────────────────────────────────

async function fetchProviders(): Promise<Provider[]> {
    const response = await axios.get<Provider[]>('/api/llm/providers')
    return response.data
}

export function useProviders() {
    return useQuery({
        queryKey: ['llm', 'providers'],
        queryFn: fetchProviders,
        staleTime: 1000 * 60 * 2,
        refetchInterval: 1000 * 60 * 2,
    })
}

async function testProviderHealth(providerId: number): Promise<{ status: string; latency_ms: number; error?: string }> {
    const response = await axios.post('/api/llm/providers/test', null, {
        params: { provider_id: providerId },
    })
    return response.data
}

export function useTestProviderHealth() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: testProviderHealth,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['llm', 'providers'] })
        },
    })
}

// ─── Agents ─────────────────────────────────────────────────────────────────

async function fetchAgents(): Promise<AgentConfig[]> {
    const response = await axios.get<AgentConfig[]>('/api/llm/agents')
    return response.data
}

export function useAgents() {
    return useQuery({
        queryKey: ['llm', 'agents'],
        queryFn: fetchAgents,
        staleTime: 1000 * 60 * 5,
    })
}

// ─── Usage Logs ─────────────────────────────────────────────────────────────

async function fetchUsageLogs(params?: { days?: number; limit?: number }): Promise<UsageLog[]> {
    const response = await axios.get<UsageLog[]>('/api/llm/usage', { params })
    return response.data
}

export function useUsageLogs(days: number = 7) {
    return useQuery({
        queryKey: ['llm', 'usage', days],
        queryFn: () => fetchUsageLogs({ days }),
        staleTime: 1000 * 60 * 2,
        refetchInterval: 1000 * 60 * 2,
    })
}

// ─── Heatmap ────────────────────────────────────────────────────────────────

async function fetchHeatmap(days: number = 7): Promise<HeatmapEntry[]> {
    const response = await axios.get<HeatmapEntry[]>('/api/llm/heatmap', { params: { days } })
    return response.data
}

export function useHeatmap(days: number = 7) {
    return useQuery({
        queryKey: ['llm', 'heatmap', days],
        queryFn: () => fetchHeatmap(days),
        staleTime: 1000 * 60 * 5,
    })
}