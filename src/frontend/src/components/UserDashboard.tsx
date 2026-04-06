import { User, TrendingUp, DollarSign, Activity } from 'lucide-react';

export function UserDashboard() {
  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="ios-card p-6 text-center">
        <User className="w-16 h-16 text-primary-400 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-white mb-2">Welcome to POLYGOD</h1>
        <p className="text-surface-400">Your AI-powered trading intelligence dashboard</p>
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
