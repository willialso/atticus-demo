// src/hooks/useWebSocket.ts
// Robust WebSocket hook with proper connection state management

import { useState, useEffect, useRef, useCallback } from 'react';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';

interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp?: number;
}

interface ChatMessage {
  type: 'chat';
  message: string;
  screen_state?: any;
}

interface ChatResponse {
  type: 'chat_response';
  data: {
    answer: string;
    confidence?: number;
    sources?: string[];
    jargon_terms?: string[];
    context_used?: string;
    error?: string;
    timestamp: number;
  };
}

interface WebSocketOptions {
  url?: string;
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  onMessage?: (message: WebSocketMessage) => void;
  onChatResponse?: (response: ChatResponse) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  status: WebSocketStatus;
  sendMessage: (message: WebSocketMessage) => void;
  sendChatMessage: (message: string) => void;
  connect: () => void;
  disconnect: () => void;
  lastError: string | null;
  reconnectAttempts: number;
}

export function useWebSocket(options: WebSocketOptions = {}): UseWebSocketReturn {
  const {
    url,
    maxReconnectAttempts = 5,
    reconnectInterval = 1000,
    maxReconnectInterval = 30000,
    onMessage,
    onChatResponse,
    onConnect,
    onDisconnect,
    onError
  } = options;

  // Option A: Construct WebSocket URL properly
  const getWsBaseUrl = () => {
    if (url) return url;
    // Try to get from environment, fallback to default
    try {
      return (import.meta as any).env?.VITE_WS_URL || 'wss://atticus-demo.onrender.com';
    } catch {
      return 'wss://atticus-demo.onrender.com';
    }
  };
  
  const base = getWsBaseUrl();
  const cleanBase = base.replace(/\/+$/, ''); // strip trailing /
  const wsPath = '/ws';
  const wsUrl = `${cleanBase}${wsPath}`;

  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [lastError, setLastError] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isConnectingRef = useRef(false);
  const shouldReconnectRef = useRef(true);

  // Clean up function
  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  // Calculate reconnect delay with exponential backoff
  const getReconnectDelay = useCallback((attempt: number): number => {
    const delay = Math.min(reconnectInterval * Math.pow(2, attempt), maxReconnectInterval);
    return delay + Math.random() * 1000; // Add jitter
  }, [reconnectInterval, maxReconnectInterval]);

  // Handle connection success
  const handleOpen = useCallback(() => {
    console.log('✅ WebSocket connected successfully');
    setStatus('connected');
    setLastError(null);
    setReconnectAttempts(0);
    reconnectAttemptsRef.current = 0;
    isConnectingRef.current = false;
    onConnect?.();
  }, [onConnect]);

  // Handle connection close
  const handleClose = useCallback((event: CloseEvent) => {
    console.log(`🔌 WebSocket closed: ${event.code} - ${event.reason}`);
    setStatus('disconnected');
    isConnectingRef.current = false;
    
    // Don't reconnect if we manually closed or if we've exceeded max attempts
    if (!shouldReconnectRef.current || reconnectAttemptsRef.current >= maxReconnectAttempts) {
      if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
        setLastError(`Max reconnection attempts (${maxReconnectAttempts}) exceeded`);
        setStatus('error');
      }
      onDisconnect?.();
      return;
    }

    // Attempt to reconnect
    setStatus('reconnecting');
    const delay = getReconnectDelay(reconnectAttemptsRef.current);
    console.log(`🔄 Attempting to reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);
    
    reconnectTimeoutRef.current = setTimeout(() => {
      if (shouldReconnectRef.current) {
        reconnectAttemptsRef.current++;
        setReconnectAttempts(reconnectAttemptsRef.current);
        connect();
      }
    }, delay);
  }, [maxReconnectAttempts, getReconnectDelay, onDisconnect]);

  // Handle connection errors
  const handleError = useCallback((event: Event) => {
    console.error('❌ WebSocket error:', event);
    setLastError('WebSocket connection error');
    setStatus('error');
    isConnectingRef.current = false;
    onError?.(event);
  }, [onError]);

  // Handle incoming messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = event.data;
      console.log('📨 WebSocket message received:', message);
      
      // Handle server-initiated ping (keep-alive)
      if (message === 'ping') {
        console.log('🏓 Received ping from server, sending pong');
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send('pong');
        }
        return;
      }
      
      // Handle simple text responses (chat answers)
      if (typeof message === 'string' && !message.startsWith('Echo:') && !message.startsWith('pong')) {
        // This is likely a chat response
        if (onChatResponse) {
          onChatResponse({
            type: 'chat_response',
            data: {
              answer: message,
              confidence: 1.0,
              sources: [],
              jargon_terms: [],
              context_used: '',
              timestamp: Date.now()
            }
          });
        }
      }
      
      // Handle pong responses
      if (message === 'pong') {
        console.log('🏓 Received pong response');
      }
      
      onMessage?.({ type: 'message', data: message, timestamp: Date.now() });
    } catch (error) {
      console.error('❌ Failed to parse WebSocket message:', error);
    }
  }, [onMessage, onChatResponse]);

  // Connect function
  const connect = useCallback(() => {
    if (isConnectingRef.current || wsRef.current?.readyState === WebSocket.CONNECTING) {
      console.log('⚠️ WebSocket connection already in progress');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('✅ WebSocket already connected');
      return;
    }

    try {
      console.log(`🔌 [WS] connecting to ${wsUrl}`);
      cleanup();
      
      isConnectingRef.current = true;
      setStatus('connecting');
      setLastError(null);

      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = handleOpen;
      wsRef.current.onclose = handleClose;
      wsRef.current.onerror = handleError;
      wsRef.current.onmessage = handleMessage;

    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error);
      setLastError('Failed to create WebSocket connection');
      setStatus('error');
      isConnectingRef.current = false;
    }
  }, [wsUrl, cleanup, handleOpen, handleClose, handleError, handleMessage]);

  // Disconnect function
  const disconnect = useCallback(() => {
    console.log('🔌 Manually disconnecting WebSocket');
    shouldReconnectRef.current = false;
    cleanup();
    setStatus('disconnected');
    setLastError(null);
    setReconnectAttempts(0);
    reconnectAttemptsRef.current = 0;
    isConnectingRef.current = false;
  }, [cleanup]);

  // Send message function
  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        const messageWithTimestamp = {
          ...message,
          timestamp: Date.now()
        };
        wsRef.current.send(JSON.stringify(messageWithTimestamp));
        console.log('📤 WebSocket message sent:', messageWithTimestamp);
      } catch (error) {
        console.error('❌ Failed to send WebSocket message:', error);
        setLastError('Failed to send message');
      }
    } else {
      console.warn('⚠️ WebSocket not connected, cannot send message');
      setLastError('WebSocket not connected');
    }
  }, []);

  // Send chat message using simplified format
  const sendChatMessage = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const chatMessage = `chat:${message}`;
      console.log('📤 Sending chat message:', chatMessage);
      wsRef.current.send(chatMessage);
    } else {
      console.error('❌ WebSocket not connected, cannot send chat message');
      setLastError('WebSocket not connected');
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    
    // Cleanup on unmount
    return () => {
      shouldReconnectRef.current = false;
      cleanup();
    };
  }, [connect, cleanup]);

  return {
    status,
    sendMessage,
    sendChatMessage,
    connect,
    disconnect,
    lastError,
    reconnectAttempts
  };
} 