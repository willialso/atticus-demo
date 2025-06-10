const API_BASE_URL = 'http://localhost:8000';

export const config = {
  API_BASE_URL,
  ENDPOINTS: {
    SANDBOX: {
      UPDATE_ACCOUNT: `${API_BASE_URL}/sandbox/update-account`,
      EXECUTE_TRADE: `${API_BASE_URL}/sandbox/trades/execute`,
    },
  },
}; 