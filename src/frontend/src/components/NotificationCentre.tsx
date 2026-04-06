import { useState, useEffect } from 'react';
import { Bell, X, Zap, TrendingUp, MessageSquare, Clock } from 'lucide-react';

interface Notification {
  id: string;
  type: 'whale' | 'price' | 'news';
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
}

interface NotificationCentreProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NotificationCentre({ isOpen, onClose }: NotificationCentreProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // Load notifications from sessionStorage
  useEffect(() => {
    const saved = sessionStorage.getItem('pg-notifications');
    if (saved) {
      setNotifications(JSON.parse(saved));
    }
  }, []);

  // Save notifications to sessionStorage
  useEffect(() => {
    sessionStorage.setItem('pg-notifications', JSON.stringify(notifications));
  }, [notifications]);

  // Mock notifications for demo
  useEffect(() => {
    if (notifications.length === 0) {
      const mockNotifications: Notification[] = [
        {
          id: '1',
          type: 'whale',
          title: 'Large Buy Order',
          message: '$250,000 YES position opened in "Trump 2024"',
          timestamp: Date.now() - 1000 * 60 * 5,
          read: false,
        },
        {
          id: '2',
          type: 'price',
          title: 'Price Alert',
          message: '"Bitcoin ETF" increased by 8.5% in the last hour',
          timestamp: Date.now() - 1000 * 60 * 15,
          read: false,
        },
        {
          id: '3',
          type: 'news',
          title: 'Breaking News',
          message: 'Major crypto exchange announces new listing',
          timestamp: Date.now() - 1000 * 60 * 30,
          read: true,
        },
      ];
      setNotifications(mockNotifications);
    }
  }, []);

  const formatTimeAgo = (timestamp: number) => {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'whale':
        return <Zap className="w-4 h-4 text-emerald-400" />;
      case 'price':
        return <TrendingUp className="w-4 h-4 text-blue-400" />;
      case 'news':
        return <MessageSquare className="w-4 h-4 text-purple-400" />;
    }
  };

  const dismissNotification = (id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  const markAsRead = (id: string) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-400 bg-surface-900/95 backdrop-blur-xl border-b border-white/10 shadow-lg">
      <div className="max-w-[1920px] mx-auto p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-white">Notifications</h2>
          <button onClick={onClose} className="ios-icon-btn">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3 max-h-96 overflow-y-auto">
          {notifications.length > 0 ? (
            notifications
              .sort((a, b) => b.timestamp - a.timestamp)
              .map((notification) => (
                <div
                  key={notification.id}
                  className={`ios-inner p-4 flex items-start gap-3 ${
                    !notification.read ? 'bg-primary-500/10 border-primary-500/20' : ''
                  }`}
                >
                  <div className="flex-shrink-0 mt-0.5">{getIcon(notification.type)}</div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-white mb-1">{notification.title}</h3>
                    <p className="text-surface-400 text-sm mb-2">{notification.message}</p>
                    <div className="flex items-center gap-1 text-xs text-surface-500">
                      <Clock className="w-3 h-3" />
                      {formatTimeAgo(notification.timestamp)}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    {!notification.read && (
                      <button
                        onClick={() => markAsRead(notification.id)}
                        className="ios-btn text-xs px-2 py-1"
                      >
                        Mark Read
                      </button>
                    )}
                    <button
                      onClick={() => dismissNotification(notification.id)}
                      className="ios-icon-btn w-6 h-6"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))
          ) : (
            <div className="ios-inner p-8 text-center">
              <Bell className="w-12 h-12 text-surface-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-white mb-2">No notifications</h3>
              <p className="text-surface-400">You're all caught up!</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
