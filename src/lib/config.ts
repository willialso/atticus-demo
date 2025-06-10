const API_BASE_URL = 'https://atticus-demo.onrender.com';
const WS_BASE_URL = API_BASE_URL.replace('https://', 'wss://');

export const config = {
  API_BASE_URL,
  WS_BASE_URL,
  ENDPOINTS: {
    SANDBOX: {
      UPDATE_ACCOUNT: `${API_BASE_URL}/sandbox/update-account`,
      EXECUTE_TRADE: `${API_BASE_URL}/sandbox/trades/execute`,
    },
    WS: {
      MARKET_DATA: `${WS_BASE_URL}/ws`,
    },
  },
}; 