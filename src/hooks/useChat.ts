// src/hooks/useChat.ts
// Simple HTTP chat hook - separate from price WebSocket

import { useState, useCallback } from 'react';

export type ChatStatus = 'idle' | 'loading' | 'online' | 'error' | 'fallback';

interface ChatMessage {
  id: string;
  question: string;
  answer?: string;
  confidence?: number;
  isError?: boolean;
  source: 'http' | 'websocket';
  timestamp: number;
}

interface UseChatReturn {
  messages: ChatMessage[];
  status: ChatStatus;
  sendMessage: (message: string, screenState?: any) => Promise<void>;
  clearMessages: () => void;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>('idle');

  // Get API base URL
  const getApiBaseUrl = () => {
    try {
      return (import.meta as any).env?.VITE_API_URL || 'https://atticus-demo.onrender.com';
    } catch {
      return 'https://atticus-demo.onrender.com';
    }
  };

  const sendMessage = useCallback(async (message: string, screenState: any = {}) => {
    const messageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    // Add user message immediately
    const userMessage: ChatMessage = {
      id: messageId,
      question: message,
      source: 'http',
      timestamp: Date.now()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setStatus('loading');

    try {
      const apiUrl = getApiBaseUrl();
      const response = await fetch(`${apiUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          screen_state: screenState,
          user_id: 'default'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const chatResponse = await response.json();
      
      // Update the message with the response
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { 
              ...msg, 
              answer: chatResponse.data.answer, 
              confidence: chatResponse.data.confidence,
              isError: chatResponse.data.error ? true : false
            }
          : msg
      ));
      
      // Update status based on response
      if (chatResponse.data.error || chatResponse.data.confidence === 0) {
        setStatus('fallback');
      } else {
        setStatus('online');
      }
      
    } catch (error) {
      console.error('❌ Chat request failed:', error);
      
      // Update the message with error
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { 
              ...msg, 
              answer: "Sorry, I'm having trouble connecting right now. Please try again.",
              isError: true
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

  return {
    messages,
    status,
    sendMessage,
    clearMessages
  };
} 