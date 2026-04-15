import { useState, useRef, useEffect, useCallback } from 'react';
import DiffViewer from './DiffViewer';

const STORAGE_KEY = 'polygod_agent_messages';
const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

function usePersistedMessages(initial: Message[]) {
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return initial;
      const { messages: stored, savedAt } = JSON.parse(raw);
      if (Date.now() - savedAt > TTL_MS) {
        localStorage.removeItem(STORAGE_KEY);
        return initial;
      }
      // Re-hydrate Date objects
      return stored.map((m: Message) => ({
        ...m,
        timestamp: new Date(m.timestamp),
      }));
    } catch {
      return initial;
    }
  });

  const setAndPersist = useCallback((updater: Message[] | ((prev: Message[]) => Message[])) => {
    setMessages((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ messages: next, savedAt: Date.now() }));
      } catch {}
      return next;
    });
  }, []);

  return [messages, setAndPersist] as const;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  patches?: PatchAction[];
  shells?: ShellAction[];
}

interface PatchAction {
  file: string;
  description: string;
  old_code: string;
  new_code: string;
  applied?: boolean;
}

interface ShellAction {
  command: string;
  description: string;
  output?: string;
}

const API_KEY = import.meta.env.VITE_INTERNAL_API_KEY || '';
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function extractPatches(text: string): PatchAction[] {
  const patches: PatchAction[] = [];
  const regex = /```json\s*(\{[^`]*"type":\s*"patch"[^`]*\})\s*```/gs;
  let match;
  while ((match = regex.exec(text)) !== null) {
    try {
      const obj = JSON.parse(match[1]);
      if (obj.type === 'patch') patches.push(obj);
    } catch {}
  }
  return patches;
}

function extractShells(text: string): ShellAction[] {
  const shells: ShellAction[] = [];
  const regex = /```json\s*(\{[^`]*"type":\s*"shell"[^`]*\})\s*```/gs;
  let match;
  while ((match = regex.exec(text)) !== null) {
    try {
      const obj = JSON.parse(match[1]);
      if (obj.type === 'shell') shells.push(obj);
    } catch {}
  }
  return shells;
}

// Strip action JSON blocks from display text
function cleanContent(text: string): string {
  return text
    .replace(/```json\s*\{[^`]*"type":\s*"patch"[^`]*\}\s*```/gs, '')
    .replace(/```json\s*\{[^`]*"type":\s*"shell"[^`]*\}\s*```/gs, '')
    .replace(/```json\s*\{[^`]*"type":\s*"memory"[^`]*\}\s*```/gs, '')
    .trim();
}

export default function AgentWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = usePersistedMessages([
    {
      id: 'init',
      role: 'assistant',
      content:
        'POLYGOD Agent online. I have full codebase context + memory of past fixes. Ask me anything — paste errors, describe issues, or ask for architecture advice.',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [memoryActive, setMemoryActive] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    fetch(`${API_BASE}/api/agent/context`, {
      headers: { 'X-API-Key': API_KEY },
    })
      .then((r) => r.json())
      .then((d) => setMemoryActive(d.memory_available))
      .catch(() => {});
  }, []);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput('');

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    const assistantId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);

    const allMsgs = [...messages.filter((m) => m.id !== 'init'), userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const payload = { messages: allMsgs, include_codebase: true };

    // Try SSE first, fall back to WebSocket
    const useSse = async () => {
      const res = await fetch(`${API_BASE}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const lines = decoder.decode(value, { stream: true }).split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6).trim());
            if (event.type === 'chunk') {
              accumulated += event.content;
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, content: accumulated } : m))
              );
            } else if (event.type === 'done') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: event.full,
                        patches: extractPatches(event.full),
                        shells: extractShells(event.full),
                      }
                    : m
                )
              );
            }
          } catch {}
        }
      }
    };

    const useWs = () =>
      new Promise<void>((resolve, reject) => {
        const wsUrl = API_BASE.replace(/^http/, 'ws') + '/api/agent/ws';
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => ws.send(JSON.stringify(payload));
        ws.onmessage = (e) => {
          try {
            const event = JSON.parse(e.data);
            if (event.type === 'done') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: event.full,
                        patches: event.patches || [],
                        shells: event.shells || [],
                      }
                    : m
                )
              );
              ws.close();
              resolve();
            } else if (event.type === 'error') {
              reject(new Error(event.content));
            }
          } catch {}
        };
        ws.onerror = () => reject(new Error('WebSocket error'));
        ws.ontimeout = () => reject(new Error('WebSocket timeout'));
      });

    try {
      await useSse();
    } catch (sseErr) {
      console.warn('SSE failed, falling back to WebSocket:', sseErr);
      try {
        await useWs();
      } catch (wsErr: any) {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: `Error: ${wsErr.message}` } : m))
        );
      }
    } finally {
      setStreaming(false);
    }
  }, [input, messages, streaming]);

  const applyPatch = useCallback(async (msgId: string, patch: PatchAction, idx: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/agent/fix`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY,
        },
        body: JSON.stringify(patch),
      });
      if (!res.ok) throw new Error(await res.text());
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== msgId || !m.patches) return m;
          const newPatches = [...m.patches];
          newPatches[idx] = { ...newPatches[idx], applied: true };
          return { ...m, patches: newPatches };
        })
      );
    } catch (err: any) {
      alert(`Patch failed: ${err.message}`);
    }
  }, []);

  const runShell = useCallback(async (msgId: string, shell: ShellAction, idx: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/agent/shell`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
        body: JSON.stringify(shell),
      });
      const data = await res.json();
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== msgId || !m.shells) return m;
          const s = [...m.shells];
          s[idx] = { ...s[idx], output: data.output || data.detail };
          return { ...m, shells: s };
        })
      );
    } catch (err: any) {
      alert(`Shell failed: ${err.message}`);
    }
  }, []);

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          width: '52px',
          height: '52px',
          borderRadius: '50%',
          background: 'var(--color-background-primary)',
          border: '1.5px solid var(--color-border-primary)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 2px 12px rgba(0,0,0,0.12)',
          zIndex: 9998,
          fontSize: '20px',
          transition: 'transform 0.15s',
        }}
        title="Open POLYGOD Agent"
        aria-label="Open AI Agent"
      >
        {open ? '✕' : '⚡'}
        {memoryActive && (
          <span
            style={{
              position: 'absolute',
              top: '4px',
              right: '4px',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#1D9E75',
              border: '1.5px solid var(--color-background-primary)',
            }}
            title="Memory active"
          />
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          style={{
            position: 'fixed',
            bottom: '88px',
            right: '24px',
            width: '420px',
            maxWidth: 'calc(100vw - 48px)',
            height: '600px',
            maxHeight: 'calc(100vh - 120px)',
            background: 'var(--color-background-primary)',
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: '12px',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 9999,
            overflow: 'hidden',
          }}
          role="dialog"
          aria-label="POLYGOD AI Agent"
        >
          {/* Header */}
          <div
            style={{
              padding: '12px 16px',
              borderBottom: '0.5px solid var(--color-border-tertiary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'var(--color-background-secondary)',
              flexShrink: 0,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '16px' }}>⚡</span>
              <div>
                <p
                  style={{
                    margin: 0,
                    fontSize: '14px',
                    fontWeight: 500,
                    color: 'var(--color-text-primary)',
                  }}
                >
                  POLYGOD Agent
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: '11px',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  {memoryActive ? 'Memory active · ' : ''}
                  {streaming ? 'thinking...' : 'Codebase context loaded'}
                </p>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                onClick={() => {
                  localStorage.removeItem(STORAGE_KEY);
                  setMessages([
                    {
                      id: 'init',
                      role: 'assistant',
                      content: 'POLYGOD Agent online. History cleared.',
                      timestamp: new Date(),
                    },
                  ]);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-tertiary)',
                  fontSize: '11px',
                  padding: '4px 8px',
                }}
                title="Clear history"
              >
                Clear
              </button>
              <button
                onClick={() => setOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-secondary)',
                  fontSize: '16px',
                  padding: '4px',
                }}
              >
                ✕
              </button>
            </div>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '12px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            {messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  gap: '4px',
                }}
              >
                <div
                  style={{
                    maxWidth: '88%',
                    padding: '8px 12px',
                    borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                    background:
                      msg.role === 'user'
                        ? 'var(--color-background-info)'
                        : 'var(--color-background-secondary)',
                    border: '0.5px solid var(--color-border-tertiary)',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    color: 'var(--color-text-primary)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {cleanContent(msg.content)}
                  {streaming &&
                    msg.role === 'assistant' &&
                    msg.id === messages[messages.length - 1].id && (
                      <span
                        style={{
                          display: 'inline-block',
                          width: '6px',
                          height: '12px',
                          background: 'var(--color-text-secondary)',
                          marginLeft: '2px',
                          animation: 'blink 1s step-end infinite',
                        }}
                      />
                    )}
                </div>

                {/* Patch action cards */}
                {msg.patches?.map((patch, idx) => (
                  <div
                    key={idx}
                    style={{
                      maxWidth: '96%',
                      width: '100%',
                      background: 'var(--color-background-secondary)',
                      border: '0.5px solid var(--color-border-success)',
                      borderRadius: '8px',
                      padding: '10px 12px',
                      fontSize: '12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <p style={{ margin: 0, fontWeight: 500, color: 'var(--color-text-primary)' }}>
                        {patch.description}
                      </p>
                      {patch.applied ? (
                        <span style={{ color: '#1D9E75', fontSize: '12px' }}>✓ Applied</span>
                      ) : (
                        <button
                          onClick={() => applyPatch(msg.id, patch, idx)}
                          style={{
                            fontSize: '12px',
                            padding: '4px 12px',
                            borderRadius: '6px',
                            border: '0.5px solid var(--color-border-success)',
                            background: 'var(--color-background-primary)',
                            cursor: 'pointer',
                            color: 'var(--color-text-success)',
                          }}
                        >
                          Apply fix
                        </button>
                      )}
                    </div>
                    <DiffViewer
                      oldCode={patch.old_code}
                      newCode={patch.new_code}
                      filename={patch.file}
                    />
                  </div>
                ))}

                {/* Shell action cards */}
                {msg.shells?.map((shell, idx) => (
                  <div
                    key={idx}
                    style={{
                      maxWidth: '88%',
                      background: 'var(--color-background-secondary)',
                      border: '0.5px solid var(--color-border-tertiary)',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      fontSize: '12px',
                    }}
                  >
                    <p
                      style={{
                        margin: '0 0 4px',
                        fontWeight: 500,
                        color: 'var(--color-text-primary)',
                      }}
                    >
                      {shell.description}
                    </p>
                    <code
                      style={{
                        display: 'block',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '11px',
                        color: 'var(--color-text-secondary)',
                        marginBottom: '6px',
                      }}
                    >
                      $ {shell.command}
                    </code>
                    {shell.output ? (
                      <pre
                        style={{
                          margin: 0,
                          fontSize: '11px',
                          fontFamily: 'var(--font-mono)',
                          background: 'var(--color-background-tertiary)',
                          padding: '6px',
                          borderRadius: '4px',
                          overflowX: 'auto',
                          maxHeight: '120px',
                          color: 'var(--color-text-primary)',
                        }}
                      >
                        {shell.output}
                      </pre>
                    ) : (
                      <button
                        onClick={() => runShell(msg.id, shell, idx)}
                        style={{
                          fontSize: '12px',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          border: '0.5px solid var(--color-border-secondary)',
                          background: 'var(--color-background-primary)',
                          cursor: 'pointer',
                          color: 'var(--color-text-primary)',
                        }}
                      >
                        Run
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Quick prompts */}
          {messages.length <= 1 && (
            <div
              style={{
                padding: '0 16px 8px',
                display: 'flex',
                gap: '6px',
                flexWrap: 'wrap',
                flexShrink: 0,
              }}
            >
              {[
                'Find all security issues',
                'Why is the scheduler not running?',
                'Audit the debate endpoint',
                'Show me N+1 queries',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  style={{
                    fontSize: '11px',
                    padding: '4px 8px',
                    borderRadius: '6px',
                    border: '0.5px solid var(--color-border-tertiary)',
                    background: 'var(--color-background-secondary)',
                    cursor: 'pointer',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}

          {/* Input area */}
          <div
            style={{
              padding: '12px 16px',
              borderTop: '0.5px solid var(--color-border-tertiary)',
              display: 'flex',
              gap: '8px',
              alignItems: 'flex-end',
              flexShrink: 0,
              background: 'var(--color-background-secondary)',
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask about code, paste errors, request fixes..."
              disabled={streaming}
              rows={1}
              style={{
                flex: 1,
                resize: 'none',
                fontSize: '13px',
                padding: '8px 10px',
                borderRadius: '8px',
                border: '0.5px solid var(--color-border-secondary)',
                background: 'var(--color-background-primary)',
                color: 'var(--color-text-primary)',
                outline: 'none',
                lineHeight: '1.5',
                maxHeight: '96px',
                overflowY: 'auto',
              }}
            />
            <button
              onClick={sendMessage}
              disabled={streaming || !input.trim()}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                border: '0.5px solid var(--color-border-secondary)',
                background: streaming
                  ? 'var(--color-background-secondary)'
                  : 'var(--color-background-primary)',
                cursor: streaming ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px',
                flexShrink: 0,
                color: 'var(--color-text-primary)',
                opacity: streaming || !input.trim() ? 0.4 : 1,
              }}
            >
              ↑
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </>
  );
}
