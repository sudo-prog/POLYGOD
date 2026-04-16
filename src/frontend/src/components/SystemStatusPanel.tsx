import { useState, useEffect, useCallback } from 'react';

interface SystemCheck {
  name: string;
  status: 'ok' | 'error';
  detail: string;
  error: string;
  checked_at: string;
}

interface SystemsHealthResponse {
  all_ok: boolean;
  polygod_mode: number;
  checks: Record<string, SystemCheck>;
  boot_time: string | null;
}

interface StatusDotProps {
  check: SystemCheck;
}

function StatusDot({ check }: StatusDotProps) {
  const [showPopup, setShowPopup] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);

  const isOk = check.status === 'ok';

  const handleDoubleClick = async () => {
    if (!isOk) {
      setAnalyzing(true);
      setAnalysisResult(null);
      try {
        const resp = await fetch('/api/agent/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': import.meta.env.VITE_INTERNAL_API_KEY || '',
          },
          body: JSON.stringify({
            message: `SYSTEM ERROR in component "${check.name}": ${check.error}.
            Diagnose the root cause and provide the exact fix.
            Reference the relevant file from the POLYGOD architecture.
            Be concise — max 3 sentences + code fix.`,
          }),
        });
        const data = await resp.json();
        setAnalysisResult(data.response || data.content || 'Analysis failed');
      } catch (e) {
        setAnalysisResult(`Request failed: ${e}`);
      } finally {
        setAnalyzing(false);
      }
    }
  };

  const handleRightClick = (e: React.MouseEvent) => {
    e.preventDefault();
    const errorText = `[${check.name}] ${check.error || check.detail}`;
    navigator.clipboard.writeText(errorText).catch(() => {});
  };

  return (
    <div className="relative flex items-center gap-2 py-1.5 px-2 rounded hover:bg-white/5 group">
      {/* Status dot */}
      <button
        onClick={() => !isOk && setShowPopup(!showPopup)}
        onDoubleClick={handleDoubleClick}
        onContextMenu={handleRightClick}
        className="relative flex-shrink-0"
        title={
          isOk ? check.detail : `Click: details | Double-click: AI fix | Right-click: copy error`
        }
      >
        {/* Outer ring */}
        <div
          className={`w-3 h-3 rounded-full border-2 transition-all duration-500 ${
            isOk
              ? 'border-emerald-400 bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
              : 'border-red-400 bg-red-400 shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse'
          }`}
        />
        {/* Pulse ring for errors */}
        {!isOk && (
          <div className="absolute inset-0 rounded-full border-2 border-red-400 animate-ping opacity-50" />
        )}
      </button>

      {/* Label */}
      <span className={`text-xs font-medium ${isOk ? 'text-gray-300' : 'text-red-300'}`}>
        {check.name}
      </span>

      {/* Detail (always visible for ok, hidden for errors until clicked) */}
      {isOk && check.detail && (
        <span className="text-xs text-gray-500 ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
          {check.detail}
        </span>
      )}

      {/* Error popup */}
      {!isOk && showPopup && (
        <div className="absolute left-6 top-0 z-50 w-80 bg-gray-900 border border-red-500/50 rounded-lg p-3 shadow-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-red-400 text-xs font-bold uppercase tracking-wide">
              ⚠ {check.name}
            </span>
            <button
              onClick={() => setShowPopup(false)}
              className="text-gray-500 hover:text-white text-xs"
            >
              ✕
            </button>
          </div>

          <p className="text-gray-300 text-xs mb-3 font-mono bg-gray-800 rounded p-2">
            {check.error || 'Unknown error'}
          </p>

          <div className="flex gap-2">
            <button
              onClick={handleDoubleClick}
              disabled={analyzing}
              className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs py-1.5 px-2 rounded transition-colors"
            >
              {analyzing ? '🤖 Analysing...' : '🤖 AI Fix'}
            </button>
            <button
              onClick={handleRightClick}
              className="bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs py-1.5 px-2 rounded transition-colors"
            >
              📋 Copy
            </button>
          </div>

          {analysisResult && (
            <div className="mt-3 p-2 bg-blue-900/30 border border-blue-500/30 rounded text-xs text-blue-200 max-h-48 overflow-y-auto">
              <span className="font-bold text-blue-400 block mb-1">🤖 AI Analysis:</span>
              <pre className="whitespace-pre-wrap font-mono text-xs">{analysisResult}</pre>
            </div>
          )}

          <p className="text-gray-600 text-xs mt-2">
            Checked: {new Date(check.checked_at).toLocaleTimeString()}
          </p>
        </div>
      )}
    </div>
  );
}

export function SystemStatusPanel() {
  const [health, setHealth] = useState<SystemsHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      const resp = await fetch('/api/health/systems');
      if (resp.ok) {
        const data: SystemsHealthResponse = await resp.json();
        setHealth(data);
      }
    } catch (e) {
      console.error('Health check failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    // Refresh every 30 seconds
    const interval = setInterval(fetchHealth, 30_000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const modeLabels: Record<number, { label: string; color: string }> = {
    0: { label: 'OBSERVE', color: 'text-gray-400' },
    1: { label: 'PAPER', color: 'text-yellow-400' },
    2: { label: 'LOW', color: 'text-orange-400' },
    3: { label: 'BEAST', color: 'text-red-400' },
  };

  const currentMode = health?.polygod_mode ?? 0;
  const modeInfo = modeLabels[currentMode] || modeLabels[0];

  if (loading) {
    return (
      <div className="bg-gray-900/80 border border-gray-700 rounded-lg p-4">
        <div className="flex items-center gap-2 text-gray-500 text-sm">
          <div className="w-2 h-2 rounded-full bg-gray-500 animate-pulse" />
          Running system checks...
        </div>
      </div>
    );
  }

  const checks = health?.checks ? Object.values(health.checks) : [];
  const failedCount = checks.filter((c) => c.status === 'error').length;

  return (
    <div className="bg-gray-900/80 border border-gray-700 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          {/* Master status indicator */}
          <div
            className={`w-3 h-3 rounded-full border-2 ${
              health?.all_ok
                ? 'border-emerald-400 bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.6)]'
                : 'border-red-400 bg-red-400 shadow-[0_0_10px_rgba(239,68,68,0.6)] animate-pulse'
            }`}
          />
          <span className="text-sm font-semibold text-white">System Status</span>
          {failedCount > 0 && (
            <span className="text-xs bg-red-900/60 text-red-300 px-2 py-0.5 rounded-full">
              {failedCount} error{failedCount > 1 ? 's' : ''}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Mode badge */}
          <span className={`text-xs font-mono font-bold ${modeInfo.color}`}>
            MODE {currentMode}: {modeInfo.label}
          </span>
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${
              collapsed ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Check list */}
      {!collapsed && (
        <div className="border-t border-gray-700/50 px-2 pb-2 pt-1">
          {checks.length === 0 ? (
            <p className="text-gray-500 text-xs px-2 py-2">No checks available</p>
          ) : (
            checks.map((check) => <StatusDot key={check.name} check={check} />)
          )}

          {/* Refresh button */}
          <button
            onClick={fetchHealth}
            className="w-full mt-2 text-xs text-gray-600 hover:text-gray-400 py-1 flex items-center justify-center gap-1 transition-colors"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Refresh checks
          </button>
        </div>
      )}
    </div>
  );
}
