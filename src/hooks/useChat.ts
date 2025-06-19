// hooks/useChat.ts
// Enhanced chat hook with WebSocket integration and status management

import { useState, useCallback, useEffect } from 'react';
import { chatWithRetry } from '../utils/fetchWithRetry';
import { useWebSocket, WebSocketStatus } from './useWebSocket';

export type ChatStatus = 'idle' | 'loading' | 'online' | 'fallback' | 'error' | 'websocket_connected' | 'websocket_disconnected';

export interface ChatMessage {
  id: string;
  message: string;
  answer: string;
  timestamp: Date;
  confidence?: number;
  isError?: boolean;
  source?: 'websocket' | 'http';
}

export interface UseChatReturn {
  messages: ChatMessage[];
  status: ChatStatus;
  sendMessage: (message: string, screenState: any) => Promise<void>;
  clearMessages: () => void;
  retryConnection: () => Promise<void>;
  websocketStatus: WebSocketStatus;
  lastWebSocketError: string | null;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>('idle');

  // WebSocket integration
  const {
    status: websocketStatus,
    sendMessage: sendWebSocketMessage,
    connect: connectWebSocket,
    disconnect: disconnectWebSocket,
    lastError: lastWebSocketError
  } = useWebSocket({
    url: 'wss://atticus-demo.onrender.com/ws',
    maxReconnectAttempts: 3,
    reconnectInterval: 2000,
    maxReconnectInterval: 10000,
    onMessage: (wsMessage) => {
      // Handle WebSocket messages (real-time updates)
      if (wsMessage.type === 'price_update' || wsMessage.type === 'market_data') {
        console.log('📊 Real-time market data received:', wsMessage.data);
        // You can update UI with real-time data here
      }
    },
    onConnect: () => {
      console.log('✅ WebSocket connected for real-time updates');
      setStatus('websocket_connected');
    },
    onDisconnect: () => {
      console.log('🔌 WebSocket disconnected');
      setStatus('websocket_disconnected');
    },
    onError: (error) => {
      console.error('❌ WebSocket error:', error);
      setStatus('error');
    }
  });

  const sendMessage = useCallback(async (message: string, screenState: any) => {
    const messageId = Date.now().toString();
    const timestamp = new Date();

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: messageId,
      message,
      answer: '',
      timestamp,
      source: 'http'
    };

    setMessages(prev => [...prev, userMessage]);
    setStatus('loading');

    try {
      // Use HTTP API for chat (more reliable than WebSocket for chat)
      const result = await chatWithRetry(message, screenState);
      
      // Update the message with the response
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { 
              ...msg, 
              answer: result.answer, 
              confidence: result.confidence,
              isError: result.confidence === 0,
              source: 'http'
            }
          : msg
      ));

      // Update status based on response
      if (result.confidence === 0) {
        setStatus('fallback');
      } else {
        setStatus('online');
      }

    } catch (error) {
      // Handle any unexpected errors
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { 
              ...msg, 
              answer: "⚠️ Unexpected error occurred. Please try again.",
              isError: true,
              source: 'http'
            }
          : msg
      ));
      setStatus('error');
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStatus('idle');
  }, []);

  const retryConnection = useCallback(async () => {
    setStatus('loading');
    
    try {
      // Test HTTP connection with a simple message
      const result = await chatWithRetry("test", {});
      
      if (result.confidence === 0) {
        setStatus('fallback');
      } else {
        setStatus('online');
      }

      // Also try to reconnect WebSocket
      connectWebSocket();
    } catch (error) {
      setStatus('fallback');
    }
  }, [connectWebSocket]);

  // Update status based on WebSocket status
  useEffect(() => {
    if (websocketStatus === 'connected' && status !== 'websocket_connected') {
      setStatus('websocket_connected');
    } else if (websocketStatus === 'disconnected' && status === 'websocket_connected') {
      setStatus('websocket_disconnected');
    } else if (websocketStatus === 'error' && status !== 'error') {
      setStatus('error');
    }
  }, [websocketStatus, status]);

  return {
    messages,
    status,
    sendMessage,
    clearMessages,
    retryConnection,
    websocketStatus,
    lastWebSocketError
  };
} 