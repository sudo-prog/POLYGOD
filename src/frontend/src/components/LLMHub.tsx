import { Brain, Cpu, Bot, Plus } from 'lucide-react';

function LLMHub() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="ios-card p-6 text-center">
        <Brain className="w-16 h-16 text-primary-400 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-white mb-2">LLM Hub</h1>
        <p className="text-surface-400">AI-powered market analysis and prediction models</p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="ios-card-sm p-4 text-center cursor-pointer hover:bg-surface-800/50 transition-colors">
          <Bot className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
          <h3 className="font-medium text-white mb-1">Run Analysis</h3>
          <p className="text-xs text-surface-400">Get AI market insights</p>
        </div>
        <div className="ios-card-sm p-4 text-center cursor-pointer hover:bg-surface-800/50 transition-colors">
          <Cpu className="w-8 h-8 text-blue-400 mx-auto mb-2" />
          <h3 className="font-medium text-white mb-1">Model Training</h3>
          <p className="text-xs text-surface-400">Train custom models</p>
        </div>
        <div className="ios-card-sm p-4 text-center cursor-pointer hover:bg-surface-800/50 transition-colors">
          <Brain className="w-8 h-8 text-purple-400 mx-auto mb-2" />
          <h3 className="font-medium text-white mb-1">Predictions</h3>
          <p className="text-xs text-surface-400">View AI forecasts</p>
        </div>
      </div>

      {/* Recent Models */}
      <div className="ios-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-white">Active Models</h2>
          <button className="ios-btn-gold">
            <Plus className="w-4 h-4 mr-2" />
            New Model
          </button>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between p-4 bg-surface-800/50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-lg flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-medium text-white">Sentiment Analysis v2.1</h3>
                <p className="text-sm text-surface-400">Processing news articles</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-emerald-400">Active</div>
              <div className="text-xs text-surface-400">94% accuracy</div>
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-surface-800/50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-lg flex items-center justify-center">
                <Cpu className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-medium text-white">Price Prediction Model</h3>
                <p className="text-sm text-surface-400">Training on historical data</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-yellow-400">Training</div>
              <div className="text-xs text-surface-400">87% complete</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LLMHub;
