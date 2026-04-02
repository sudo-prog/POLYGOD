import { useState } from 'react'
import { Brain, Zap, Activity, Cpu, Bot, BarChart3 } from 'lucide-react'
import { useLLMStore, type Provider } from '../stores/llmStore'
import { useProviders, useAgents, useUsageLogs, useHeatmap } from '../hooks/useLLM'
import LLMProviderCard from './LLMProviderCard'
import AgentRow from './AgentRow'

function GlassCard({ title, value, icon, accent }: { title: string; value: string | number; icon: React.ReactNode; accent: string }) {
    return (
        <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-white/10 p-4">
            <div className="flex items-center gap-2 mb-2">
                <div className={`p-1.5 rounded-lg bg-surface-800/60 ${accent}`}>{icon}</div>
                <span className="text-[10px] uppercase tracking-wider text-surface-400">{title}</span>
            </div>
            <p className="text-xl font-bold text-white">{value}</p>
        </div>
    )
}

export default function LLMHub() {
    const { selectedProvider, setSelectedProvider } = useLLMStore()
    const { data: providers = [], isLoading: providersLoading } = useProviders()
    const { data: agents = [], isLoading: agentsLoading } = useAgents()
    const { data: usageLogs = [] } = useUsageLogs()
    const { data: heatmap = [] } = useHeatmap()

    const [activeSection, setActiveSection] = useState<'providers' | 'agents' | 'usage'>('providers')

    // Compute global usage stats
    const totalTokensToday = providers.reduce((sum, p) => sum + (p.tokens_today || 0), 0)
    const activeProviders = providers.filter(p => p.status === '✅').length
    const avgLatency = providers
        .filter(p => p.avg_speed)
        .reduce((sum, p, _, arr) => sum + (p.avg_speed || 0) / arr.length, 0)

    return (
        <div className="p-4 lg:p-6 space-y-6 text-white">
            {/* Global Usage Dashboard */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <GlassCard
                    title="Tokens Today"
                    value={totalTokensToday.toLocaleString()}
                    icon={<Zap className="w-4 h-4 text-emerald-400" />}
                    accent="text-emerald-400"
                />
                <GlassCard
                    title="Active Providers"
                    value={`${activeProviders}/${providers.length}`}
                    icon={<Activity className="w-4 h-4 text-blue-400" />}
                    accent="text-blue-400"
                />
                <GlassCard
                    title="Agents Running"
                    value={agents.length}
                    icon={<Bot className="w-4 h-4 text-purple-400" />}
                    accent="text-purple-400"
                />
                <GlassCard
                    title="Avg Latency"
                    value={avgLatency > 0 ? `${Math.round(avgLatency)}ms` : '—'}
                    icon={<Cpu className="w-4 h-4 text-amber-400" />}
                    accent="text-amber-400"
                />
            </div>

            {/* Section Tabs */}
            <div className="flex items-center gap-1 bg-surface-900/50 backdrop-blur-sm rounded-xl p-1 w-fit">
                <button
                    onClick={() => setActiveSection('providers')}
                    className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-colors ${activeSection === 'providers'
                            ? 'bg-primary-600/30 text-white'
                            : 'text-surface-300 hover:text-white'
                        }`}
                >
                    <Brain className="w-4 h-4" />
                    Providers
                </button>
                <button
                    onClick={() => setActiveSection('agents')}
                    className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-colors ${activeSection === 'agents'
                            ? 'bg-primary-600/30 text-white'
                            : 'text-surface-300 hover:text-white'
                        }`}
                >
                    <Bot className="w-4 h-4" />
                    Agents
                </button>
                <button
                    onClick={() => setActiveSection('usage')}
                    className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-colors ${activeSection === 'usage'
                            ? 'bg-primary-600/30 text-white'
                            : 'text-surface-300 hover:text-white'
                        }`}
                >
                    <BarChart3 className="w-4 h-4" />
                    Usage
                </button>
            </div>

            {/* Providers Grid */}
            {activeSection === 'providers' && (
                <div>
                    <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                        <Brain className="w-5 h-5 text-primary-400" />
                        LLM Providers
                    </h2>
                    {providersLoading ? (
                        <div className="text-center py-12 text-surface-400">Loading providers...</div>
                    ) : providers.length === 0 ? (
                        <div className="text-center py-12 text-surface-400">
                            <Brain className="w-12 h-12 mx-auto mb-3 opacity-30" />
                            <p>No providers configured yet</p>
                            <p className="text-xs mt-1">Add your first LLM provider to get started</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            {providers.map(p => (
                                <LLMProviderCard
                                    key={p.id}
                                    provider={p}
                                    isSelected={selectedProvider?.id === p.id}
                                    onSelect={setSelectedProvider}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Agents Management */}
            {activeSection === 'agents' && (
                <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl border border-white/10 p-6">
                    <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                        <Bot className="w-5 h-5 text-purple-400" />
                        AI Debate Floor Agents
                    </h2>
                    {agentsLoading ? (
                        <div className="text-center py-8 text-surface-400">Loading agents...</div>
                    ) : agents.length === 0 ? (
                        <div className="text-center py-8 text-surface-400">
                            <Bot className="w-10 h-10 mx-auto mb-3 opacity-30" />
                            <p>No agents configured yet</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {agents.map(a => (
                                <AgentRow key={a.id} agent={a} providers={providers} />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Usage Logs */}
            {activeSection === 'usage' && (
                <div className="space-y-6">
                    {/* Heatmap */}
                    <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl border border-white/10 p-6">
                        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <BarChart3 className="w-5 h-5 text-amber-400" />
                            Usage Heatmap (7 days)
                        </h2>
                        {heatmap.length === 0 ? (
                            <div className="text-center py-8 text-surface-400">No usage data yet</div>
                        ) : (
                            <div className="overflow-x-auto">
                                <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${Math.min(heatmap.length, 28)}, minmax(28px, 1fr))` }}>
                                    {heatmap.slice(-28).map((entry, i) => {
                                        const intensity = Math.min(1, entry.tokens / 50000)
                                        return (
                                            <div
                                                key={i}
                                                className="rounded aspect-square flex items-center justify-center text-[8px] font-medium"
                                                style={{
                                                    backgroundColor: `rgba(16, 185, 129, ${intensity * 0.6 + 0.05})`,
                                                    color: intensity > 0.3 ? 'white' : 'rgba(255,255,255,0.5)',
                                                }}
                                                title={`${entry.provider}: ${entry.tokens.toLocaleString()} tokens on ${entry.date}`}
                                            >
                                                {entry.tokens > 0 ? Math.round(entry.tokens / 1000) + 'k' : ''}
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Recent Logs Table */}
                    <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl border border-white/10 p-6">
                        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <Activity className="w-5 h-5 text-blue-400" />
                            Recent Usage Logs
                        </h2>
                        {usageLogs.length === 0 ? (
                            <div className="text-center py-8 text-surface-400">No usage logs yet</div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                    <thead>
                                        <tr className="text-surface-400 border-b border-white/5">
                                            <th className="text-left py-2 font-medium">Time</th>
                                            <th className="text-left py-2 font-medium">Provider</th>
                                            <th className="text-left py-2 font-medium">Agent</th>
                                            <th className="text-right py-2 font-medium">Tokens</th>
                                            <th className="text-right py-2 font-medium">Latency</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {usageLogs.slice(0, 50).map(log => (
                                            <tr key={log.id} className="border-b border-white/5 hover:bg-white/5">
                                                <td className="py-2 text-surface-300">
                                                    {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
                                                </td>
                                                <td className="py-2 text-white font-medium">{log.provider}</td>
                                                <td className="py-2 text-surface-300">{log.agent_name || '—'}</td>
                                                <td className="py-2 text-right text-emerald-400 font-mono">
                                                    {log.tokens_used?.toLocaleString() || '—'}
                                                </td>
                                                <td className="py-2 text-right text-surface-300">
                                                    {log.latency_ms ? `${log.latency_ms}ms` : '—'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}