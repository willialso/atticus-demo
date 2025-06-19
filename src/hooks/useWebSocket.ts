// src/hooks/useWebSocket.ts
// Robust WebSocket hook with proper connection state management

import { useState, useEffect, useRef, useCallback } from 'react';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';

interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp?: number;
}

interface WebSocketOptions {
  url?: string;
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  status: WebSocketStatus;
  sendMessage: (message: WebSocketMessage) => void;
  connect: () => void;
  disconnect: () => void;
  lastError: string | null;
  reconnectAttempts: number;
}

export function useWebSocket(options: WebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = 'wss://atticus-demo.onrender.com/ws',
    maxReconnectAttempts = 5,
    reconnectInterval = 1000,
    maxReconnectInterval = 30000,
    onMessage,
    onConnect,
    onDisconnect,
    onError
  } = options;

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
      const message: WebSocketMessage = JSON.parse(event.data);
      console.log('📨 WebSocket message received:', message);
      onMessage?.(message);
    } catch (error) {
      console.error('❌ Failed to parse WebSocket message:', error);
    }
  }, [onMessage]);

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
      console.log(`🔌 Connecting to WebSocket: ${url}`);
      cleanup();
      
      isConnectingRef.current = true;
      setStatus('connecting');
      setLastError(null);

      wsRef.current = new WebSocket(url);
      
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
  }, [url, cleanup, handleOpen, handleClose, handleError, handleMessage]);

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
      console.warn('⚠️ Cannot send message: WebSocket not connected');
      setLastError('WebSocket not connected');
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();

    return () => {
      shouldReconnectRef.current = false;
      cleanup();
    };
  }, [connect, cleanup]);

  return {
    status,
    sendMessage,
    connect,
    disconnect,
    lastError,
    reconnectAttempts
  };
} 