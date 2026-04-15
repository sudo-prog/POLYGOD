/**
 * ThinkingWindow — POLYGOD's Internal Monologue Panel
 *
 * A real-time window into the AI's thought process: web searches, code scans,
 * patches applied, decisions made. Connects via SSE to /api/agent/stream.
 *
 * Design: industrial terminal aesthetic — dark, dense, monospaced.
 * Green for success, amber for warnings, red for errors, cyan for searches.
 * Feels like watching a supercomputer think in real time.
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

type ThoughtType =
  | 'thinking'
  | 'search'
  | 'search_result'
  | 'code_scan'
  | 'patch'
  | 'patch_applied'
  | 'patch_failed'
  | 'decision'
  | 'error'
  | 'info'
  | 'warning';

interface Thought {
  id: string;
  timestamp: string;
  type: ThoughtType;
  agent: string;
  message: string;
  detail?: string;
  meta?: Record<string, unknown>;
}

type FilterType = ThoughtType | 'all';

// ── Config ────────────────────────────────────────────────────────────────────

const TYPE_CONFIG: Record<ThoughtType, { icon: string; color: string; bg: string; label: string }> =
  {
    thinking: { icon: '⟳', color: '#a8b8ff', bg: 'rgba(168,184,255,0.06)', label: 'Thinking' },
    search: { icon: '⌕', color: '#38d9ff', bg: 'rgba(56,217,255,0.06)', label: 'Search' },
    search_result: { icon: '◈', color: '#22d3ee', bg: 'rgba(34,211,238,0.06)', label: 'Result' },
    code_scan: { icon: '⚡', color: '#fbbf24', bg: 'rgba(251,191,36,0.06)', label: 'Scan' },
    patch: { icon: '⊕', color: '#c084fc', bg: 'rgba(192,132,252,0.06)', label: 'Patch' },
    patch_applied: { icon: '✓', color: '#4ade80', bg: 'rgba(74,222,128,0.08)', label: 'Applied' },
    patch_failed: { icon: '✗', color: '#f87171', bg: 'rgba(248,113,113,0.08)', label: 'Failed' },
    decision: { icon: '◆', color: '#fb923c', bg: 'rgba(251,146,60,0.06)', label: 'Decision' },
    error: { icon: '⊘', color: '#ef4444', bg: 'rgba(239,68,68,0.08)', label: 'Error' },
    info: { icon: '·', color: '#6b7280', bg: 'transparent', label: 'Info' },
    warning: { icon: '△', color: '#f59e0b', bg: 'rgba(245,158,11,0.06)', label: 'Warning' },
  };

const FILTER_GROUPS: { label: string; types: FilterType[] }[] = [
  { label: 'All', types: ['all'] },
  { label: 'Thinking', types: ['thinking', 'decision'] },
  { label: 'Search', types: ['search', 'search_result'] },
  { label: 'Code', types: ['code_scan', 'patch', 'patch_applied', 'patch_failed'] },
  { label: 'Errors', types: ['error', 'warning'] },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '--:--:--';
  }
}

function useLocalStorage<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored ? JSON.parse(stored) : initial;
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        localStorage.setItem(key, JSON.stringify(v));
      } catch {}
    },
    [key]
  );
  return [value, set];
}

// ── Self-Heal Submit Panel ────────────────────────────────────────────────────

function SelfHealPanel({ apiKey }: { apiKey: string }) {
  const [errorText, setErrorText] = useState('');
  const [filePath, setFilePath] = useState('');
  const [autoFix, setAutoFix] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string>('');

  const submit = async () => {
    if (!errorText.trim()) return;
    setLoading(true);
    setResult('');
    try {
      const resp = await fetch('/api/agent/self-heal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({
          error_text: errorText,
          file_path: filePath || null,
          auto_fix: autoFix,
        }),
      });
      const data = await resp.json();
      setResult(JSON.stringify(data, null, 2));
      setErrorText('');
    } catch (e) {
      setResult(String(e));
    } finally {
      setLoading(false);
    }
  };

  const scan = async () => {
    setLoading(true);
    setResult('Scanning... watch Thinking Window for results');
    try {
      await fetch('/api/agent/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ path: 'src/backend' }),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '12px', borderTop: '1px solid #1f2937' }}>
      <div
        style={{
          fontSize: '10px',
          color: '#6b7280',
          letterSpacing: '0.1em',
          marginBottom: '8px',
          textTransform: 'uppercase',
        }}
      >
        Self-Heal Console
      </div>
      <textarea
        value={errorText}
        onChange={(e) => setErrorText(e.target.value)}
        placeholder="Paste error/traceback here..."
        style={{
          width: '100%',
          height: '80px',
          background: '#0a0f1a',
          border: '1px solid #1f2937',
          color: '#e2e8f0',
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          fontSize: '11px',
          padding: '8px',
          borderRadius: '4px',
          resize: 'vertical',
          outline: 'none',
          boxSizing: 'border-box',
        }}
      />
      <div style={{ display: 'flex', gap: '6px', marginTop: '6px', alignItems: 'center' }}>
        <input
          value={filePath}
          onChange={(e) => setFilePath(e.target.value)}
          placeholder="file path (optional)"
          style={{
            flex: 1,
            background: '#0a0f1a',
            border: '1px solid #1f2937',
            color: '#9ca3af',
            fontSize: '11px',
            padding: '4px 8px',
            borderRadius: '4px',
            outline: 'none',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        />
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '11px',
            color: '#6b7280',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          <input type="checkbox" checked={autoFix} onChange={(e) => setAutoFix(e.target.checked)} />
          Auto-fix
        </label>
        <button
          onClick={submit}
          disabled={loading || !errorText.trim()}
          style={{
            background: loading ? '#1f2937' : '#7c3aed',
            color: '#e2e8f0',
            border: 'none',
            borderRadius: '4px',
            padding: '4px 12px',
            fontSize: '11px',
            cursor: loading ? 'not-allowed' : 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {loading ? '⟳' : 'Heal'}
        </button>
        <button
          onClick={scan}
          disabled={loading}
          style={{
            background: '#0a0f1a',
            color: '#fbbf24',
            border: '1px solid #fbbf24',
            borderRadius: '4px',
            padding: '4px 10px',
            fontSize: '11px',
            cursor: loading ? 'not-allowed' : 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Scan
        </button>
      </div>
      {result && (
        <pre
          style={{
            marginTop: '8px',
            padding: '8px',
            background: '#0a0f1a',
            border: '1px solid #1f2937',
            borderRadius: '4px',
            fontSize: '10px',
            color: '#4ade80',
            overflowX: 'auto',
            maxHeight: '120px',
            overflowY: 'auto',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {result}
        </pre>
      )}
    </div>
  );
}

// ── Thought Row ───────────────────────────────────────────────────────────────

function ThoughtRow({
  thought,
  expanded,
  onToggle,
}: {
  thought: Thought;
  expanded: boolean;
  onToggle: () => void;
}) {
  const cfg = TYPE_CONFIG[thought.type] ?? TYPE_CONFIG.info;
  const hasDetail = !!thought.detail;

  return (
    <div
      style={{
        background: expanded ? cfg.bg : 'transparent',
        borderLeft: `2px solid ${expanded ? cfg.color : 'transparent'}`,
        transition: 'all 0.15s ease',
        cursor: hasDetail ? 'pointer' : 'default',
      }}
      onClick={hasDetail ? onToggle : undefined}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          padding: '3px 10px',
          fontSize: '11px',
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        }}
      >
        {/* Timestamp */}
        <span style={{ color: '#374151', flexShrink: 0, fontSize: '10px' }}>
          {formatTime(thought.timestamp)}
        </span>
        {/* Type icon */}
        <span style={{ color: cfg.color, flexShrink: 0, width: '14px', textAlign: 'center' }}>
          {cfg.icon}
        </span>
        {/* Agent badge */}
        <span
          style={{
            color: '#4b5563',
            fontSize: '9px',
            flexShrink: 0,
            background: '#111827',
            padding: '1px 4px',
            borderRadius: '2px',
            letterSpacing: '0.05em',
          }}
        >
          {thought.agent}
        </span>
        {/* Message */}
        <span
          style={{
            color: cfg.color,
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {thought.message}
        </span>
        {/* Expand indicator */}
        {hasDetail && (
          <span style={{ color: '#374151', flexShrink: 0, fontSize: '9px' }}>
            {expanded ? '▲' : '▼'}
          </span>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && thought.detail && (
        <pre
          style={{
            margin: '0 10px 6px 34px',
            padding: '8px',
            background: '#050a12',
            border: '1px solid #1f2937',
            borderRadius: '4px',
            fontSize: '10px',
            color: '#94a3b8',
            overflowX: 'auto',
            maxHeight: '300px',
            overflowY: 'auto',
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {thought.detail}
        </pre>
      )}
    </div>
  );
}

// ── Stats bar ────────────────────────────────────────────────────────────────

function StatsBar({ thoughts }: { thoughts: Thought[] }) {
  const counts = useMemo(() => {
    const c: Partial<Record<ThoughtType, number>> = {};
    thoughts.forEach((t) => {
      c[t.type] = (c[t.type] ?? 0) + 1;
    });
    return c;
  }, [thoughts]);

  const stats = [
    { key: 'search' as ThoughtType, label: 'Searches' },
    { key: 'patch_applied' as ThoughtType, label: 'Patches' },
    { key: 'error' as ThoughtType, label: 'Errors' },
    { key: 'code_scan' as ThoughtType, label: 'Issues' },
  ];

  return (
    <div
      style={{
        display: 'flex',
        gap: '16px',
        padding: '6px 10px',
        borderBottom: '1px solid #111827',
      }}
    >
      {stats.map(({ key, label }) => {
        const cfg = TYPE_CONFIG[key];
        const count = counts[key] ?? 0;
        return (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ color: cfg.color, fontSize: '11px' }}>{cfg.icon}</span>
            <span
              style={{
                color: count > 0 ? cfg.color : '#374151',
                fontSize: '11px',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {count}
            </span>
            <span style={{ color: '#374151', fontSize: '9px' }}>{label}</span>
          </div>
        );
      })}
      <div style={{ marginLeft: 'auto', fontSize: '9px', color: '#374151' }}>
        {thoughts.length} events
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface ThinkingWindowProps {
  /** The X-API-Key header value for authenticated requests */
  apiKey?: string;
  /** Initial panel height in px */
  defaultHeight?: number;
}

export default function ThinkingWindow({
  apiKey = import.meta.env.VITE_INTERNAL_API_KEY ?? '',
  defaultHeight = 420,
}: ThinkingWindowProps) {
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [connected, setConnected] = useState(false);
  const [filter, setFilter] = useLocalStorage<FilterType>('polygod_thought_filter', 'all');
  const [autoScroll, setAutoScroll] = useLocalStorage('polygod_thought_autoscroll', true);
  const [showHeal, setShowHeal] = useLocalStorage('polygod_show_heal', false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState('');
  const [height, setHeight] = useLocalStorage('polygod_window_height', defaultHeight);

  const listRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);
  const dragging = useRef(false);
  const dragStartY = useRef(0);
  const dragStartH = useRef(0);

  // ── SSE connection ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (!apiKey) return;

    const connect = () => {
      const url = `/api/agent/stream?X-API-Key=${encodeURIComponent(apiKey)}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => setConnected(true);

      es.onmessage = (event) => {
        if (event.data === '[DONE]') return;
        try {
          const thought: Thought = JSON.parse(event.data);
          setThoughts((prev) => {
            const next = [...prev, thought];
            return next.length > 500 ? next.slice(-500) : next;
          });
        } catch {}
      };

      es.onerror = () => {
        setConnected(false);
        es.close();
        // Reconnect after 3s
        setTimeout(connect, 3000);
      };
    };

    connect();
    return () => {
      esRef.current?.close();
      setConnected(false);
    };
  }, [apiKey]);

  // ── Auto-scroll ────────────────────────────────────────────────────────────

  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [thoughts, autoScroll]);

  // ── Drag-to-resize ─────────────────────────────────────────────────────────

  const onDragStart = (e: React.MouseEvent) => {
    dragging.current = true;
    dragStartY.current = e.clientY;
    dragStartH.current = height;
    e.preventDefault();
  };

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const delta = dragStartY.current - e.clientY; // drag up = taller
      setHeight(Math.max(200, Math.min(900, dragStartH.current + delta)));
    };
    const onUp = () => {
      dragging.current = false;
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [setHeight]);

  // ── Filtering ──────────────────────────────────────────────────────────────

  const filteredThoughts = useMemo(() => {
    let list = thoughts;

    if (filter !== 'all') {
      const group = FILTER_GROUPS.find((g) => g.types.includes(filter));
      const types = group?.types.filter((t) => t !== 'all') ?? [filter];
      list = list.filter((t) => types.includes(t.type as FilterType));
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (t) =>
          t.message.toLowerCase().includes(q) ||
          t.agent.toLowerCase().includes(q) ||
          t.detail?.toLowerCase().includes(q)
      );
    }

    return list;
  }, [thoughts, filter, search]);

  // ── Helpers ────────────────────────────────────────────────────────────────

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const clearThoughts = async () => {
    try {
      await fetch('/api/agent/thoughts', {
        method: 'DELETE',
        headers: { 'X-API-Key': apiKey },
      });
    } catch {}
    setThoughts([]);
    setExpanded(new Set());
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: `${height}px`,
        background: '#080d16',
        borderTop: '1px solid #0f172a',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
        zIndex: 900,
        boxShadow: '0 -8px 32px rgba(0,0,0,0.6)',
        userSelect: dragging.current ? 'none' : 'auto',
      }}
    >
      {/* Drag handle */}
      <div
        onMouseDown={onDragStart}
        style={{
          height: '6px',
          cursor: 'ns-resize',
          background: 'linear-gradient(to bottom, #0f172a, #080d16)',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ width: '40px', height: '2px', background: '#1f2937', borderRadius: '1px' }} />
      </div>

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '0 10px',
          height: '36px',
          borderBottom: '1px solid #0f172a',
          flexShrink: 0,
        }}
      >
        {/* Title + status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '9px',
              letterSpacing: '0.15em',
              color: '#6b7280',
              textTransform: 'uppercase',
            }}
          >
            POLYGOD Thinking
          </span>
          <div
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: connected ? '#4ade80' : '#ef4444',
              boxShadow: connected ? '0 0 6px #4ade80' : 'none',
              animation: connected ? 'pulse 2s infinite' : 'none',
            }}
          />
          <span style={{ fontSize: '9px', color: connected ? '#4ade80' : '#ef4444' }}>
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>

        {/* Filter pills */}
        <div style={{ display: 'flex', gap: '4px' }}>
          {FILTER_GROUPS.map((group) => {
            const isActive = group.types.includes(filter);
            return (
              <button
                key={group.label}
                onClick={() => setFilter(group.types[0])}
                style={{
                  background: isActive ? '#1e293b' : 'transparent',
                  color: isActive ? '#e2e8f0' : '#4b5563',
                  border: isActive ? '1px solid #334155' : '1px solid transparent',
                  borderRadius: '3px',
                  padding: '2px 7px',
                  fontSize: '9px',
                  cursor: 'pointer',
                  letterSpacing: '0.05em',
                }}
              >
                {group.label}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="filter..."
          style={{
            background: '#0a0f1a',
            border: '1px solid #1f2937',
            color: '#9ca3af',
            fontSize: '10px',
            padding: '2px 8px',
            borderRadius: '3px',
            outline: 'none',
            width: '120px',
            fontFamily: 'inherit',
          }}
        />

        {/* Controls */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              style={{ accentColor: '#7c3aed' }}
            />
            <span style={{ fontSize: '9px', color: '#6b7280' }}>Auto-scroll</span>
          </label>

          <button
            onClick={() => setShowHeal(!showHeal)}
            style={{
              background: showHeal ? '#7c3aed' : '#0a0f1a',
              color: showHeal ? '#e2e8f0' : '#7c3aed',
              border: '1px solid #7c3aed',
              borderRadius: '3px',
              padding: '2px 8px',
              fontSize: '9px',
              cursor: 'pointer',
            }}
          >
            ⚕ Self-Heal
          </button>

          <button
            onClick={clearThoughts}
            style={{
              background: 'transparent',
              color: '#4b5563',
              border: '1px solid #1f2937',
              borderRadius: '3px',
              padding: '2px 8px',
              fontSize: '9px',
              cursor: 'pointer',
            }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* Stats */}
      <StatsBar thoughts={thoughts} />

      {/* Thought list */}
      <div
        ref={listRef}
        onScroll={() => {
          if (!listRef.current) return;
          const { scrollTop, scrollHeight, clientHeight } = listRef.current;
          if (scrollTop + clientHeight < scrollHeight - 40) setAutoScroll(false);
        }}
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          paddingBottom: '4px',
        }}
      >
        {filteredThoughts.length === 0 ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#1f2937',
              fontSize: '12px',
              fontFamily: 'inherit',
            }}
          >
            {connected ? 'Waiting for thoughts...' : 'Connecting to POLYGOD...'}
          </div>
        ) : (
          filteredThoughts.map((thought) => (
            <ThoughtRow
              key={thought.id}
              thought={thought}
              expanded={expanded.has(thought.id)}
              onToggle={() => toggleExpand(thought.id)}
            />
          ))
        )}
      </div>

      {/* Self-heal panel (collapsible) */}
      {showHeal && <SelfHealPanel apiKey={apiKey} />}

      {/* Pulse animation */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
