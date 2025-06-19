// components/StatusBanner.tsx
// Status banner for Golden Retriever 2.0 connection status

import React from 'react';
import { ChatStatus } from '../hooks/useChat';

interface StatusBannerProps {
  status: ChatStatus;
  onRetry?: () => void;
}

export const StatusBanner: React.FC<StatusBannerProps> = ({ status, onRetry }) => {
  if (status === 'idle' || status === 'online') {
    return null;
  }

  const getStatusConfig = () => {
    switch (status) {
      case 'loading':
        return {
          color: 'bg-blue-100 border-blue-400 text-blue-800',
          icon: '🔄',
          message: 'Connecting to Golden Retriever 2.0...',
          showRetry: false
        };
      case 'fallback':
        return {
          color: 'bg-yellow-100 border-yellow-400 text-yellow-800',
          icon: '⚠️',
          message: 'Backend unreachable – running limited help mode. Live prices & trades disabled.',
          showRetry: true
        };
      case 'error':
        return {
          color: 'bg-red-100 border-red-400 text-red-800',
          icon: '❌',
          message: 'Connection error. Please check your network and try again.',
          showRetry: true
        };
      default:
        return {
          color: 'bg-gray-100 border-gray-400 text-gray-800',
          icon: 'ℹ️',
          message: 'Unknown status',
          showRetry: false
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className={`border-l-4 p-4 mb-4 ${config.color} rounded-r-lg`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-lg">{config.icon}</span>
          <span className="font-medium">{config.message}</span>
        </div>
        {config.showRetry && onRetry && (
          <button
            onClick={onRetry}
            className="px-3 py-1 text-sm bg-white border border-current rounded hover:bg-gray-50 transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}; 