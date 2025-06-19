// src/hooks/useWebSocket.ts
// Price-only WebSocket hook - no chat, no ping, just price updates

import { useState, useEffect, useRef, useCallback } from 'react';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';

interface PriceUpdate {
  type: 'price_update';
  data: {
    price: number;
  };
}

interface WebSocketOptions {
  url?: string;
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  onPriceUpdate?: (price: number) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  status: WebSocketStatus;
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
    onPriceUpdate,
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
      
      // Try to parse as JSON first
      try {
        const payload = JSON.parse(message);
        
        // Handle price updates
        if (payload.type === "price_update") {
          console.log('💰 Price update received:', payload);
          if (onPriceUpdate) {
            onPriceUpdate(payload.data.price);
          }
          return;
        }
        
      } catch (jsonError) {
        // Handle legacy text format for backward compatibility
        if (message === 'ping') {
          console.log('🏓 Received legacy ping from server, sending pong');
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send('pong');
          }
          return;
        }
        
        if (message === 'pong') {
          console.log('🏓 Received pong response');
          return;
        }
        
        // Handle legacy chat responses (plain text)
        if (typeof message === 'string' && !message.startsWith('Echo:') && !message.startsWith('pong')) {
          // This is likely a chat response
          if (onPriceUpdate) {
            onPriceUpdate(parseFloat(message));
          }
        }
        
        onPriceUpdate?.(parseFloat(message));
      }
    } catch (error) {
      console.error('❌ Failed to parse WebSocket message:', error);
    }
  }, [onPriceUpdate]);

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
    connect,
    disconnect,
    lastError,
    reconnectAttempts
  };
} 