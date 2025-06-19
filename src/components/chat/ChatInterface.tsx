import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, AlertCircle, Wifi, WifiOff } from 'lucide-react';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: number;
  error?: boolean;
  errorDetails?: string;
  confidence?: number;
  sources?: string[];
  jargonTerms?: string[];
}

interface ChatInterfaceProps {
  onClose: () => void;
  currentPrice?: number;
  selectedStrike?: number;
  selectedExpiry?: number;
  selectedOptionType?: 'call' | 'put';
}

type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error';

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ 
  onClose,
  currentPrice,
  selectedStrike,
  selectedExpiry,
  selectedOptionType
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Test connection to Golden Retriever 2.0
    testConnection();
  }, []);

  const testConnection = async () => {
    setConnectionStatus('connecting');
    try {
      const response = await fetch('https://atticus-demo.onrender.com/gr2/health');
      if (response.ok) {
        setConnectionStatus('connected');
        // Add welcome message
        setMessages([{
          id: '1',
          text: 'Hello! I\'m Golden Retriever 2.0, your Bitcoin options trading assistant. I can help you with options strategies, Greeks, risk management, and more. What would you like to know?',
          isUser: false,
          timestamp: Date.now(),
          confidence: 1.0,
          sources: ['Welcome'],
          jargonTerms: []
        }]);
      } else {
        setConnectionStatus('error');
      }
    } catch (error) {
      setConnectionStatus('error');
      console.error('Connection test failed:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputText,
      isUser: true,
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);

    try {
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

      const response = await fetch('https://atticus-demo.onrender.com/gr2/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputText,
          screen_state: screenState
        })
      });

      if (response.ok) {
        const data = await response.json();
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: data.answer,
          isUser: false,
          timestamp: Date.now(),
          confidence: data.confidence,
          sources: data.sources,
          jargonTerms: data.jargon_terms
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: 'Sorry, I encountered an error while processing your request. Please try again.',
        isUser: false,
        timestamp: Date.now(),
        error: true,
        errorDetails: error instanceof Error ? error.message : 'Unknown error'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const getStatusIcon = () => {
    switch (connectionStatus) {
      case 'connected':
        return <Wifi className="w-4 h-4 text-green-500" />;
      case 'connecting':
        return <Loader2 className="w-4 h-4 text-yellow-500 animate-spin" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <WifiOff className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'Connected to Golden Retriever 2.0';
      case 'connecting':
        return 'Connecting...';
      case 'error':
        return 'Connection Error';
      default:
        return 'Disconnected';
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
              <span className="text-sm text-gray-600">{getStatusText()}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  message.isUser
                    ? 'bg-blue-500 text-white'
                    : message.error
                    ? 'bg-red-100 text-red-800'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                <div className="text-sm">{message.text}</div>
                
                {/* Show confidence and sources for assistant messages */}
                {!message.isUser && !message.error && (
                  <div className="mt-2 text-xs opacity-75">
                    {message.confidence && (
                      <div>Confidence: {(message.confidence * 100).toFixed(0)}%</div>
                    )}
                    {message.sources && message.sources.length > 0 && (
                      <div>Sources: {message.sources.join(', ')}</div>
                    )}
                    {message.jargonTerms && message.jargonTerms.length > 0 && (
                      <div>Terms: {message.jargonTerms.join(', ')}</div>
                    )}
                  </div>
                )}
                
                {message.error && message.errorDetails && (
                  <div className="mt-1 text-xs opacity-75">
                    Error: {message.errorDetails}
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {isLoading && (
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
              disabled={isLoading || connectionStatus !== 'connected'}
            />
            <button
              onClick={sendMessage}
              disabled={!inputText.trim() || isLoading || connectionStatus !== 'connected'}
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