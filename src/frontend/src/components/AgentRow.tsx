import { Bot, Settings, ChevronRight } from 'lucide-react';
import type { AgentConfig, Provider } from '../stores/llmStore';

interface AgentRowProps {
  agent: AgentConfig;
  providers: Provider[];
}

export default function AgentRow({ agent, providers }: AgentRowProps) {
  const assignedProvider = providers.find((p) => p.id === agent.provider_id);

  return (
    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-900/40 border border-white/5 hover:border-white/10 transition-colors group">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <div className="p-2 rounded-lg bg-primary-600/20 shrink-0">
          <Bot className="w-4 h-4 text-primary-400" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">{agent.agent_name}</p>
          <div className="flex items-center gap-2 text-xs text-surface-400">
            <span className="truncate">
              {assignedProvider?.name || 'No provider'} · {agent.model_name || 'default model'}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {agent.overrides && Object.keys(agent.overrides).length > 0 && (
          <span className="text-[10px] px-2 py-0.5 bg-amber-500/10 text-amber-400 rounded-md">
            {Object.keys(agent.overrides).length} overrides
          </span>
        )}
        <button className="p-1.5 rounded-lg bg-surface-800/60 hover:bg-surface-700/60 text-surface-400 hover:text-white transition-colors opacity-0 group-hover:opacity-100">
          <Settings className="w-3.5 h-3.5" />
        </button>
        <ChevronRight className="w-4 h-4 text-surface-600 group-hover:text-surface-400 transition-colors" />
      </div>
    </div>
  );
}
