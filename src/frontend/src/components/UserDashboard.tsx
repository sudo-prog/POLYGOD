import { useState } from 'react';
import { User, TrendingUp, DollarSign, Activity, Power, RefreshCw } from 'lucide-react';

export function UserDashboard() {
  const [agentStatus, setAgentStatus] = useState<'running' | 'stopped'>('running');
  const [isLoading, setIsLoading] = useState(false);
  const [lastAction, setLastAction] = useState<string>('');

  const handleKill = async () => {
    if (
      !confirm(
        'Are you sure you want to KILL the POLYGOD agent? All active processes will be terminated.'
      )
    )
      return;
    setIsLoading(true);
    try {
      const response = await fetch('/api/agent/kill', { method: 'POST' });
      const data = await response.json();
      if (response.ok) {
        setAgentStatus('stopped');
        setLastAction(`Agent killed at ${new Date().toLocaleTimeString()}`);
      } else {
        alert(`Failed: ${data.detail}`);
      }
    } catch (err) {
      alert('Failed to kill agent - check backend connection');
    }
    setIsLoading(false);
  };

  const handleRestart = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/agent/restart', { method: 'POST' });
      const data = await response.json();
      if (response.ok) {
        setAgentStatus('running');
        setLastAction(`Agent restarted at ${new Date().toLocaleTimeString()}`);
      } else {
        alert(`Failed: ${data.detail}`);
      }
    } catch (err) {
      alert('Failed to restart agent - check backend connection');
    }
    setIsLoading(false);
  };

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="ios-card p-6 text-center">
        <User className="w-16 h-16 text-primary-400 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-white mb-2">Welcome to POLYGOD</h1>
        <p className="text-surface-400">Your AI-powered trading intelligence dashboard</p>
      </div>

      {/* Kill/Restart Control Panel */}
      <div className="ios-card p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Agent Control</h2>
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div
              className={`w-3 h-3 rounded-full ${
                agentStatus === 'running' ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
              }`}
            ></div>
            <span className="font-medium text-white">POLYGOD Agent</span>
            <span
              className={`text-sm px-2 py-1 rounded-lg ${
                agentStatus === 'running'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-red-500/20 text-red-400'
              }`}
            >
              {agentStatus === 'running' ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleKill}
              disabled={isLoading || agentStatus === 'stopped'}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 rounded-lg text-red-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Power className="w-4 h-4" />
              <span>KILL</span>
            </button>
            <button
              onClick={handleRestart}
              disabled={isLoading || agentStatus === 'running'}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/50 rounded-lg text-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              <span>RESTART</span>
            </button>
          </div>
        </div>
        {lastAction && <div className="mt-4 text-sm text-surface-400">{lastAction}</div>}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="ios-card-sm p-4">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-emerald-400" />
            <div>
              <div className="text-lg font-bold text-white">$12,450</div>
              <div className="text-sm text-surface-400">Total P&L</div>
            </div>
          </div>
        </div>
        <div className="ios-card-sm p-4">
          <div className="flex items-center gap-3">
            <DollarSign className="w-8 h-8 text-primary-400" />
            <div>
              <div className="text-lg font-bold text-white">$8,320</div>
              <div className="text-sm text-surface-400">Active Positions</div>
            </div>
          </div>
        </div>
        <div className="ios-card-sm p-4">
          <div className="flex items-center gap-3">
            <Activity className="w-8 h-8 text-purple-400" />
            <div>
              <div className="text-lg font-bold text-white">24</div>
              <div className="text-sm text-surface-400">Markets Tracked</div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="ios-card p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Recent Activity</h2>
        <div className="space-y-3">
          <div className="flex items-center gap-4 p-3 bg-surface-800/50 rounded-lg">
            <div className="w-2 h-2 bg-emerald-400 rounded-full"></div>
            <div className="flex-1">
              <div className="font-medium text-white">Position opened in "Trump 2024"</div>
              <div className="text-sm text-surface-400">2 hours ago</div>
            </div>
            <div className="text-right">
              <div className="font-medium text-emerald-400">+$245</div>
              <div className="text-sm text-surface-400">+12.5%</div>
            </div>
          </div>
          <div className="flex items-center gap-4 p-3 bg-surface-800/50 rounded-lg">
            <div className="w-2 h-2 bg-red-400 rounded-full"></div>
            <div className="flex-1">
              <div className="font-medium text-white">Position closed in "Bitcoin ETF"</div>
              <div className="text-sm text-surface-400">5 hours ago</div>
            </div>
            <div className="text-right">
              <div className="font-medium text-red-400">-$89</div>
              <div className="text-sm text-surface-400">-3.2%</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
