import { MessageSquare, Plus } from 'lucide-react';

export function DebateFloor({ marketId: _marketId }: { marketId?: string | null }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-blue-400" />
          Debate Floor
        </h3>
        <button className="ios-btn-gold">
          <Plus className="w-4 h-4 mr-2" />
          Initiate Debate
        </button>
      </div>

      <div className="ios-card-sm p-8 text-center">
        <MessageSquare className="w-12 h-12 text-surface-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">AI-Powered Debates</h3>
        <p className="text-surface-400 text-sm">
          Debate resolution outcomes with AI assistance and community voting
        </p>
      </div>
    </div>
  );
}
