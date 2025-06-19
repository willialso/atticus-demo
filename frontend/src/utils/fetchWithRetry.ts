// frontend/src/utils/fetchWithRetry.ts
// Resilient fetch wrapper with exponential backoff and CORS error handling

interface FetchOptions extends RequestInit {
  retries?: number;
  baseDelay?: number;
  maxDelay?: number;
}

interface FetchResponse<T = any> {
  data: T;
  status: number;
  ok: boolean;
}

class FetchError extends Error {
  constructor(
    message: string,
    public status?: number,
    public isCorsError: boolean = false,
    public isNetworkError: boolean = false
  ) {
    super(message);
    this.name = 'FetchError';
  }
}

/**
 * Exponential backoff delay calculation
 */
function calculateDelay(attempt: number, baseDelay: number, maxDelay: number): number {
  const delay = baseDelay * Math.pow(2, attempt);
  return Math.min(delay, maxDelay);
}

/**
 * Detect if an error is a CORS error
 */
function isCorsError(error: any): boolean {
  return (
    error instanceof TypeError &&
    (error.message === 'Failed to fetch' || 
     error.message.includes('CORS') ||
     error.message.includes('cross-origin'))
  );
}

/**
 * Detect if an error is a network error
 */
function isNetworkError(error: any): boolean {
  return (
    error instanceof TypeError &&
    (error.message === 'Network request failed' ||
     error.message === 'Failed to fetch' ||
     error.message.includes('network'))
  );
}

/**
 * Resilient fetch with exponential backoff and CORS error handling
 */
export async function fetchWithRetry<T = any>(
  url: string,
  options: FetchOptions = {}
): Promise<FetchResponse<T>> {
  const {
    retries = 3,
    baseDelay = 1000,
    maxDelay = 10000,
    ...fetchOptions
  } = options;

  let lastError: Error = new Error('Unknown error');

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions.headers,
        },
      });

      if (!response.ok) {
        throw new FetchError(
          `HTTP ${response.status}: ${response.statusText}`,
          response.status
        );
      }

      const data = await response.json();
      
      return {
        data,
        status: response.status,
        ok: response.ok,
      };

    } catch (error: any) {
      lastError = error;

      // Check if it's the last attempt
      if (attempt === retries) {
        break;
      }

      // Determine error type
      const isCors = isCorsError(error);
      const isNetwork = isNetworkError(error);
      const isServerError = error instanceof FetchError && error.status && error.status >= 500;

      // Don't retry CORS errors - they won't be fixed by retrying
      if (isCors) {
        throw new FetchError(
          'CORS error: Browser blocked the request due to cross-origin restrictions',
          undefined,
          true
        );
      }

      // Don't retry client errors (4xx) - they won't be fixed by retrying
      if (error instanceof FetchError && error.status && error.status >= 400 && error.status < 500) {
        throw error;
      }

      // Only retry network errors and server errors
      if (isNetwork || isServerError) {
        const delay = calculateDelay(attempt, baseDelay, maxDelay);
        console.warn(`Fetch attempt ${attempt + 1} failed, retrying in ${delay}ms:`, error.message);
        
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }

      // For other errors, don't retry
      throw error;
    }
  }

  // If we get here, all retries failed
  if (lastError instanceof FetchError) {
    throw lastError;
  }

  throw new FetchError(
    `Request failed after ${retries + 1} attempts: ${lastError?.message || 'Unknown error'}`,
    undefined,
    isCorsError(lastError),
    isNetworkError(lastError)
  );
}

/**
 * Specialized function for Golden Retriever 2.0 chat requests
 */
export async function postChat(body: any, baseUrl: string = ''): Promise<any> {
  try {
    const response = await fetchWithRetry(`${baseUrl}/gr2/chat`, {
      method: 'POST',
      body: JSON.stringify(body),
      retries: 3,
      baseDelay: 500,
    });

    return response.data;
  } catch (error: any) {
    if (error instanceof FetchError) {
      if (error.isCorsError) {
        throw new Error('CORS_ERROR');
      } else if (error.isNetworkError) {
        throw new Error('NETWORK_ERROR');
      } else if (error.status) {
        throw new Error(`HTTP_${error.status}`);
      }
    }
    throw error;
  }
}

/**
 * Health check for Golden Retriever 2.0
 */
export async function checkGr2Health(baseUrl: string = ''): Promise<boolean> {
  try {
    const response = await fetchWithRetry(`${baseUrl}/gr2/health`, {
      method: 'GET',
      retries: 1,
      baseDelay: 500,
    });

    return response.data?.available === true;
  } catch (error) {
    console.warn('Golden Retriever 2.0 health check failed:', error);
    return false;
  }
}

/**
 * Get knowledge base growth statistics
 */
export async function getKbGrowthStats(baseUrl: string = ''): Promise<any> {
  try {
    const response = await fetchWithRetry(`${baseUrl}/gr2/kb-growth`, {
      method: 'GET',
      retries: 2,
      baseDelay: 1000,
    });

    return response.data;
  } catch (error) {
    console.warn('Failed to get KB growth stats:', error);
    return null;
  }
} 