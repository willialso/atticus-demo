// utils/fetchWithRetry.ts
// Resilient fetch wrapper for Golden Retriever 2.0 API calls

// Extend Window interface to include toast
declare global {
  interface Window {
    toast?: {
      error: (message: string) => void;
      warn: (message: string) => void;
      success: (message: string) => void;
    };
  }
}

export interface FetchOptions extends RequestInit {
  retries?: number;
  backoff?: number;
}

export async function fetchWithRetry(
  url: string,
  options: FetchOptions = {},
  retries = 3,
  backoff = 800   // ms
): Promise<any> {
  const { retries: customRetries, backoff: customBackoff, ...fetchOptions } = options;
  const maxRetries = customRetries ?? retries;
  const baseBackoff = customBackoff ?? backoff;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions.headers,
        },
      });

      if (!res.ok) {
        // Distinguish CORS / network / 5xx
        if (res.type === "opaque") throw new Error("cors");
        if (res.status >= 500) throw new Error("server");
        if (res.status === 403) throw new Error("forbidden");
        if (res.status === 404) throw new Error("not_found");
        throw new Error(`server ${res.status}`);
      }
      
      return await res.json();
    } catch (err: any) {
      const isLast = attempt === maxRetries;
      const type = err.message;

      // Surface real CORS/Network errors as suggested
      if (type.startsWith('TypeError') && type.includes('fetch')) {
        console.error('CORS/Network block', err);
        if (isLast) throw new Error("CORS-blocked");
      } else if (type === "cors") {
        if (isLast) throw new Error("CORS-blocked");
      } else if (type.startsWith("server")) {
        if (isLast) throw new Error("Server error");
      } else if (type === "forbidden") {
        if (isLast) throw new Error("Access forbidden");
      } else if (type === "not_found") {
        if (isLast) throw new Error("Endpoint not found");
      } else {
        if (isLast) throw new Error("Network error");
      }
      
      // Exponential back-off
      if (!isLast) {
        await new Promise(r => setTimeout(r, baseBackoff * 2 ** attempt));
      }
    }
  }
  
  throw new Error("Max retries exceeded");
}

// Specialized function for Golden Retriever 2.0 chat
export async function chatWithRetry(
  message: string, 
  screenState: any, 
  baseUrl: string = "https://atticus-demo.onrender.com"
): Promise<{ answer: string; confidence?: number }> {
  try {
    const data = await fetchWithRetry(
      `${baseUrl}/gr2/chat`,
      {
        method: "POST",
        body: JSON.stringify({ 
          message, 
          screen_state: screenState 
        }),
        retries: 3,
        backoff: 500
      }
    );
    
    return {
      answer: data.answer || "No response received",
      confidence: data.confidence
    };
  } catch (e: any) {
    // Return fallback response based on error type
    if (e.message === "CORS-blocked") {
      // Show toast notification for CORS error
      if (typeof window !== 'undefined' && window.toast) {
        window.toast.error("Browser blocked the request (CORS). Please refresh the page and try again.");
      }
      return {
        answer: "⚠️ Browser blocked the request (CORS). Please refresh the page and try again.",
        confidence: 0
      };
    }
    if (e.message === "Server error") {
      // Show toast notification for server error
      if (typeof window !== 'undefined' && window.toast) {
        window.toast.warn("Server error – retrying...");
      }
      return {
        answer: "⚠️ Server temporary error; retrying soon. Please try again in a moment.",
        confidence: 0
      };
    }
    if (e.message === "Access forbidden") {
      return {
        answer: "⚠️ Access denied. Please check your connection and try again.",
        confidence: 0
      };
    }
    
    // Show toast notification for network error
    if (typeof window !== 'undefined' && window.toast) {
      window.toast.error("Network problem – working offline.");
    }
    
    return {
      answer: "⚠️ Network issue. Working in offline help-only mode. Please check your connection.",
      confidence: 0
    };
  }
}

// Health check for Golden Retriever 2.0
export async function checkGr2Health(baseUrl: string = "https://atticus-demo.onrender.com"): Promise<boolean> {
  try {
    const data = await fetchWithRetry(
      `${baseUrl}/gr2/health`,
      {
        method: "GET",
        retries: 1,
        backoff: 500
      }
    );
    
    return data?.available === true;
  } catch (error) {
    console.warn('Golden Retriever 2.0 health check failed:', error);
    return false;
  }
}

// Get knowledge base growth statistics
export async function getKbGrowthStats(baseUrl: string = "https://atticus-demo.onrender.com"): Promise<any> {
  try {
    const data = await fetchWithRetry(
      `${baseUrl}/gr2/kb-growth`,
      {
        method: "GET",
        retries: 2,
        backoff: 1000
      }
    );
    
    return data;
  } catch (error) {
    console.warn('Failed to get KB growth stats:', error);
    return null;
  }
} 