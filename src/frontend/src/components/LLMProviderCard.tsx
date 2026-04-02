import { Activity, Zap, Clock, Cpu, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import type { Provider } from '../stores/llmStore'
import { useTestProviderHealth } from '../hooks/useLLM'

interface LLMProviderCardProps {
    provider: Provider
    isSelected: boolean
    onSelect: (provider: Provider) => void
}

export default function LLMProviderCard({ provider, isSelected, onSelect }: LLMProviderCardProps) {
    const testHealth = useTestProviderHealth()

    const statusIcon = () => {
        switch (provider.status) {
            case '✅':
                return <CheckCircle className="w-4 h-4 text-emerald-400" />
            case '⚠️':
                return <AlertTriangle className="w-4 h-4 text-amber-400" />
            case '🔴':
                return <XCircle className="w-4 h-4 text-red-400" />
            default:
                return <Activity className="w-4 h-4 text-gray-400" />
        }
    }

    const statusColor = () => {
        switch (provider.status) {
            case '✅':
                return 'border-emerald-500/30 hover:border-emerald-500/50'
            case '⚠️':
                return 'border-amber-500/30 hover:border-amber-500/50'
            case '🔴':
                return 'border-red-500/30 hover:border-red-500/50'
            default:
                return 'border-white/10 hover:border-white/20'
        }
    }

    return (
        <div
            onClick={() => onSelect(provider)}
            className={`relative cursor-pointer rounded-2xl p-5 transition-all duration-200 ${isSelected
                    ? 'bg-primary-600/15 border-primary-500/50 ring-1 ring-primary-500/20'
                    : `bg-gray-900/50 backdrop-blur-sm border ${statusColor()}`
                }`}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    {statusIcon()}
                    <h3 className="text-sm font-semibold text-white">{provider.name}</h3>
                </div>
                <button
                    onClick={(e) => {
                        e.stopPropagation()
                        testHealth.mutate(provider.id)
                    }}
                    disabled={testHealth.isPending}
                    className="text-[10px] px-2 py-1 bg-surface-800/60 hover:bg-surface-700/60 text-surface-300 hover:text-white rounded-lg transition-colors flex items-center gap-1"
                >
                    <Zap className="w-3 h-3" />
                    {testHealth.isPending ? 'Testing...' : 'Test'}
                </button>
            </div>

            {/* Models */}
            <div className="mb-3">
                <p className="text-[10px] uppercase tracking-wider text-surface-400 mb-1">Models</p>
                <div className="flex flex-wrap gap-1">
                    {provider.models.length > 0 ? (
                        provider.models.slice(0, 3).map((model) => (
                            <span
                                key={model}
                                className="text-[10px] px-2 py-0.5 bg-surface-800/60 text-surface-300 rounded-md truncate max-w-[120px]"
                            >
                                {model}
                            </span>
                        ))
                    ) : (
                        <span className="text-[10px] text-surface-500 italic">No models configured</span>
                    )}
                    {provider.models.length > 3 && (
                        <span className="text-[10px] text-surface-500">+{provider.models.length - 3}</span>
                    )}
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 pt-3 border-t border-white/5">
                <div className="text-center">
                    <div className="flex items-center justify-center gap-1 mb-0.5">
                        <Clock className="w-3 h-3 text-surface-400" />
                        <span className="text-[10px] uppercase tracking-wider text-surface-400">Uptime</span>
                    </div>
                    <p className="text-xs font-semibold text-white">{provider.uptime_24h}</p>
                </div>
                <div className="text-center">
                    <div className="flex items-center justify-center gap-1 mb-0.5">
                        <Cpu className="w-3 h-3 text-surface-400" />
                        <span className="text-[10px] uppercase tracking-wider text-surface-400">Speed</span>
                    </div>
                    <p className="text-xs font-semibold text-white">
                        {provider.avg_speed ? `${provider.avg_speed}ms` : '—'}
                    </p>
                </div>
                <div className="text-center">
                    <div className="flex items-center justify-center gap-1 mb-0.5">
                        <Zap className="w-3 h-3 text-surface-400" />
                        <span className="text-[10px] uppercase tracking-wider text-surface-400">Today</span>
                    </div>
                    <p className="text-xs font-semibold text-white">
                        {provider.tokens_today.toLocaleString()}
                    </p>
                </div>
            </div>
        </div>
    )
}