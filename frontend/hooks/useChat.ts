// hooks/useChat.ts
// Enhanced chat hook with status management and fallback mode

import { useState, useCallback } from 'react';
import { chatWithRetry } from '../utils/fetchWithRetry';

export type ChatStatus = 'idle' | 'loading' | 'online' | 'fallback' | 'error';

export interface ChatMessage {
  id: string;
  message: string;
  answer: string;
  timestamp: Date;
  confidence?: number;
  isError?: boolean;
}

export interface UseChatReturn {
  messages: ChatMessage[];
  status: ChatStatus;
  sendMessage: (message: string, screenState: any) => Promise<void>;
  clearMessages: () => void;
  retryConnection: () => Promise<void>;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>('idle');

  const sendMessage = useCallback(async (message: string, screenState: any) => {
    const messageId = Date.now().toString();
    const timestamp = new Date();

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: messageId,
      message,
      answer: '',
      timestamp,
    };

    setMessages(prev => [...prev, userMessage]);
    setStatus('loading');

    try {
      const result = await chatWithRetry(message, screenState);
      
      // Update the message with the response
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { 
              ...msg, 
              answer: result.answer, 
              confidence: result.confidence,
              isError: result.confidence === 0
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

  const retryConnection = useCallback(async () => {
    setStatus('loading');
    
    try {
      // Test connection with a simple message
      const result = await chatWithRetry("test", {});
      
      if (result.confidence === 0) {
        setStatus('fallback');
      } else {
        setStatus('online');
      }
    } catch (error) {
      setStatus('fallback');
    }
  }, []);

  return {
    messages,
    status,
    sendMessage,
    clearMessages,
    retryConnection,
  };
} 