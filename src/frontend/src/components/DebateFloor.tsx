import { useState } from 'react';
import { MessageSquare, Plus } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Message {
  agent: string;
  content: string;
}

export function DebateFloor({ marketId }: { marketId?: string | null }) {
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [verdict, setVerdict] = useState<string | null>(null);

  const initiateDebate = async () => {
    if (!marketId) return;
    setIsLoading(true);
    setMessages([]);
    setVerdict(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/debate/${marketId}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agents: {
            statistics_expert: true,
            generalist_expert: true,
            devils_advocate: true,
            crypto_macro_analyst: true,
            time_decay_analyst: true,
            top_traders_analyst: true,
          },
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start debate');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              setIsLoading(false);
              return;
            }
            try {
              const msg = JSON.parse(data);
              if (msg.type === 'verdict') {
                setVerdict(msg.content);
              } else if (msg.type === 'message') {
                setMessages((prev) => [...prev, { agent: msg.agent, content: msg.content }]);
              } else if (msg.type === 'error') {
                console.error('Debate error:', msg.content);
                setIsLoading(false);
                return;
              }
            } catch {
              console.warn('Failed to parse SSE data:', data);
            }
          }
        }
      }
    } catch (error) {
      console.error('Debate failed:', error);
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-blue-400" />
          Debate Floor
        </h3>
        <button
          onClick={initiateDebate}
          disabled={isLoading || !marketId}
          className="ios-btn-gold disabled:opacity-50"
        >
          <Plus className="w-4 h-4 mr-2" />
          {isLoading ? 'Debating...' : 'Initiate Debate'}
        </button>
      </div>

      <div className="ios-card-sm p-4">
        {messages.length === 0 && !isLoading && !verdict && (
          <div className="text-center py-8">
            <MessageSquare className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">AI-Powered Debates</h3>
            <p className="text-surface-400 text-sm">
              Debate resolution outcomes with AI assistance and community voting
            </p>
          </div>
        )}

        {isLoading && (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400 mx-auto mb-4"></div>
            <p className="text-surface-400">AI agents are debating...</p>
          </div>
        )}

        <div className="space-y-4">
          {messages.map((msg, idx) => (
            <div key={idx} className="border-l-4 border-blue-400 pl-4">
              <div className="font-semibold text-blue-400">{msg.agent}</div>
              <div className="text-white mt-1">{msg.content}</div>
            </div>
          ))}
        </div>

        {verdict && (
          <div className="mt-6 p-4 bg-blue-500/10 border border-blue-400/30 rounded-lg">
            <h4 className="font-semibold text-blue-400 mb-2">Verdict</h4>
            <p className="text-white">{verdict}</p>
          </div>
        )}
      </div>
    </div>
  );
}
