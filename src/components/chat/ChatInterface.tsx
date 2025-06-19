import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, AlertCircle, Wifi, WifiOff, Radio } from 'lucide-react';
import { useChat, ChatStatus } from '../../hooks/useChat';
import { StatusBanner } from '../StatusBanner';

interface ChatInterfaceProps {
  onClose: () => void;
  currentPrice?: number;
  selectedStrike?: number;
  selectedExpiry?: number;
  selectedOptionType?: 'call' | 'put';
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ 
  onClose,
  currentPrice,
  selectedStrike,
  selectedExpiry,
  selectedOptionType
}) => {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Use our enhanced chat hook with WebSocket integration
  const { 
    messages, 
    status, 
    sendMessage, 
    clearMessages, 
    retryConnection,
    websocketStatus,
    lastWebSocketError
  } = useChat();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Add welcome message when component mounts
    if (messages.length === 0) {
      const welcomeMessage = {
        id: 'welcome',
        message: '',
        answer: 'Hello! I\'m Golden Retriever 2.0, your Bitcoin options trading assistant. I can help you with options strategies, Greeks, risk management, and more. What would you like to know?',
        timestamp: new Date(),
        confidence: 1.0,
        source: 'http' as const
      };
      // We'll add this through the chat system
      sendMessage('', {
        current_page: 'options_trading',
        user_position: selectedOptionType ? `long_${selectedOptionType}` : undefined,
        market_data: {
          btc_price: currentPrice || 104740.00,
          volatility: 0.45
        },
        selected_strike: selectedStrike,
        selected_expiry: selectedExpiry,
        selected_option_type: selectedOptionType
      });
    }
  }, []);

  const handleSendMessage = async () => {
    if (!inputText.trim() || status === 'loading') return;

    // Prepare screen context based on current state
    const screenState = {
      current_page: 'options_trading',
      user_position: selectedOptionType ? `long_${selectedOptionType}` : undefined,
      market_data: {
        btc_price: currentPrice || 104740.00,
        volatility: 0.45
      },
      selected_strike: selectedStrike,
      selected_expiry: selectedExpiry,
      selected_option_type: selectedOptionType
    };

    await sendMessage(inputText, screenState);
    setInputText('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'online':
      case 'websocket_connected':
        return <Wifi className="w-4 h-4 text-green-500" />;
      case 'loading':
        return <Loader2 className="w-4 h-4 text-yellow-500 animate-spin" />;
      case 'websocket_disconnected':
        return <Radio className="w-4 h-4 text-orange-500" />;
      case 'fallback':
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <WifiOff className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'online':
        return 'Connected to Golden Retriever 2.0';
      case 'websocket_connected':
        return 'Connected (Real-time updates available)';
      case 'websocket_disconnected':
        return 'Connected (Real-time updates unavailable)';
      case 'loading':
        return 'Connecting...';
      case 'fallback':
        return 'Limited Mode';
      case 'error':
        return 'Connection Error';
      default:
        return 'Disconnected';
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'online':
      case 'websocket_connected':
        return 'text-green-600';
      case 'websocket_disconnected':
        return 'text-orange-600';
      case 'loading':
        return 'text-yellow-600';
      case 'fallback':
      case 'error':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center space-x-2">
            <h2 className="text-lg font-semibold">Golden Retriever 2.0</h2>
            <div className="flex items-center space-x-1">
              {getStatusIcon()}
              <span className={`text-sm ${getStatusColor()}`}>{getStatusText()}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        {/* Status Banner */}
        <StatusBanner status={status} onRetry={retryConnection} />

        {/* WebSocket Status (if disconnected) */}
        {websocketStatus === 'disconnected' && lastWebSocketError && (
          <div className="bg-orange-50 border-l-4 border-orange-400 p-3 mx-4 mt-2">
            <div className="flex items-center">
              <Radio className="w-4 h-4 text-orange-500 mr-2" />
              <span className="text-sm text-orange-700">
                Real-time updates unavailable: {lastWebSocketError}
              </span>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.message ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  message.message
                    ? 'bg-blue-500 text-white'
                    : message.isError
                    ? 'bg-red-100 text-red-800'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                <div className="text-sm">
                  {message.message || message.answer}
                </div>
                
                {/* Show confidence and source for assistant messages */}
                {!message.message && !message.isError && (
                  <div className="mt-2 text-xs opacity-75">
                    <div>Confidence: {(message.confidence || 0) * 100}%</div>
                    {message.source && (
                      <div>Source: {message.source === 'websocket' ? 'Real-time' : 'HTTP API'}</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {status === 'loading' && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-lg p-3">
                <div className="flex items-center space-x-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t">
          <div className="flex space-x-2">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about Bitcoin options, strategies, Greeks, risk management..."
              className="flex-1 border rounded-lg p-2 resize-none"
              rows={2}
              disabled={status === 'loading'}
            />
            <button
              onClick={handleSendMessage}
              disabled={!inputText.trim() || status === 'loading'}
              className="bg-blue-500 text-white rounded-lg p-2 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          
          {/* Context Info */}
          <div className="mt-2 text-xs text-gray-500">
            {currentPrice && `BTC: $${currentPrice.toLocaleString()}`}
            {selectedStrike && ` | Strike: $${selectedStrike.toLocaleString()}`}
            {selectedOptionType && ` | Type: ${selectedOptionType.toUpperCase()}`}
          </div>
        </div>
      </div>
    </div>
  );
}; 