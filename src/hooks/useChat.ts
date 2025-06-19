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
  const [pendingMessageId, setPendingMessageId] = useState<string | null>(null);

  // WebSocket integration
  const {
    status: websocketStatus,
    sendChatMessage,
    connect: connectWebSocket,
    disconnect: disconnectWebSocket,
    lastError: lastWebSocketError
  } = useWebSocket({
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
    onChatResponse: (chatResponse) => {
      // Handle chat responses from WebSocket
      console.log('💬 Chat response received:', chatResponse);
      
      if (pendingMessageId) {
        setMessages(prev => prev.map(msg => 
          msg.id === pendingMessageId 
            ? { 
                ...msg, 
                answer: chatResponse.data.answer, 
                confidence: chatResponse.data.confidence,
                isError: chatResponse.data.error ? true : false,
                source: 'websocket'
              }
            : msg
        ));
        
        // Update status based on response
        if (chatResponse.data.error || chatResponse.data.confidence === 0) {
          setStatus('fallback');
        } else {
          setStatus('online');
        }
        
        setPendingMessageId(null);
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

  const sendMessage = useCallback(async (message: string, screenState: any = {}) => {
    if (!message.trim()) return;

    const messageId = Date.now().toString();
    const newMessage: ChatMessage = {
      id: messageId,
      message,
      answer: '',
      timestamp: new Date(),
      source: 'websocket'
    };

    setMessages(prev => [...prev, newMessage]);
    setStatus('loading');

    try {
      // Try WebSocket first
      if (websocketStatus === 'connected') {
        console.log('🚀 Sending via WebSocket');
        setStatus('websocket_connected');
        
        // Send via WebSocket
        sendChatMessage(message, screenState);
        
        // The response will be handled by the WebSocket message handler
        // which will call onChatResponse and update the message
      } else {
        // Fallback to HTTP
        console.log('🔄 Falling back to HTTP');
        setStatus('fallback');
        
        const response = await chatWithRetry(message, screenState);
        
        setMessages(prev => prev.map(msg => 
          msg.id === messageId 
            ? { ...msg, answer: response.answer, confidence: response.confidence, source: 'http' }
            : msg
        ));
        setStatus('online');
      }
    } catch (error) {
      console.error('❌ Chat error:', error);
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { ...msg, answer: 'Sorry, I encountered an error. Please try again.', isError: true }
          : msg
      ));
      setStatus('error');
    }
  }, [websocketStatus, sendChatMessage]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStatus('idle');
    setPendingMessageId(null);
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