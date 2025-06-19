# 🚀 Lovable Integration Guide - Bitcoin Options Trading Platform

## 📋 **Complete Integration Information for Lovable**

### **Base Configuration**
- **Platform Name**: Atticus Bitcoin Options Trading Platform
- **Version**: 2.2
- **Backend URL**: `https://atticus-demo.onrender.com`
- **WebSocket URL**: `wss://atticus-demo.onrender.com/ws`
- **Environment**: Production (Render deployment)
- **Auto-Deploy**: ✅ Enabled (pushes from GitHub automatically)

---

## 🔗 **API Endpoints**

### **Core Health & Status**
- **Health Check**: `GET /health`
- **API Documentation**: `GET /docs` (Swagger UI)
- **ReDoc Documentation**: `GET /redoc`

### **Golden Retriever 2.0 (AI Assistant)**
- **Health Check**: `GET /gr2/health`
- **Chat Endpoint**: `POST /gr2/chat`
- **Knowledge Base**: `GET /gr2/knowledge-base`
- **KB Growth Stats**: `GET /gr2/kb-growth`
- **Test Endpoint**: `POST /gr2/test`
- **Cache Stats**: `GET /gr2/cache-stats`
- **Clear Cache**: `POST /gr2/clear-cache`
- **Available Analogies**: `GET /gr2/analogies`

### **Market Data**
- **Current BTC Price**: `GET /market/price`
- **Option Chains**: `GET /market/option-chains`
- **Option Chains (with expiry)**: `GET /market/option-chains?expiry_minutes=240`

### **Trading & Portfolio**
- **Execute Trade**: `POST /trades/execute`
- **Create User**: `POST /users/create`
- **Get Portfolio**: `GET /users/{user_id}/portfolio`
- **Close Position**: `POST /positions/close`

### **Pricing Engine**
- **Black-Scholes Calculator**: `POST /blackscholes/calculate`

### **Sandbox (Demo Mode)**
- **Update Account**: `POST /sandbox/update-account`
- **Execute Sandbox Trade**: `POST /sandbox/trades/execute`

### **Real-time Data**
- **WebSocket Connection**: `wss://atticus-demo.onrender.com/ws`

---

## 🤖 **Golden Retriever 2.0 Integration**

### **Request Format (Lovable Compatible)**
```json
{
  "message": "What is a Bitcoin call option?",
  "context": {
    "screen_state": {
      "current_btc_price": 104800.30,
      "selected_option_type": "call",
      "selected_strike": 105000.0,
      "selected_expiry": 240,
      "visible_strikes": [104000, 104500, 105000, 105500, 106000],
      "active_tab": "options_chain"
    }
  },
  "user_id": "user_123"
}
```

### **Response Format**
```json
{
  "answer": "A Bitcoin call option gives you the right to buy BTC at a specific price...",
  "sources": ["options_basics", "btc_trading_guide"],
  "confidence": 0.92,
  "jargon_terms": ["call option", "strike price"],
  "context_used": "Screen context used for personalized response"
}
```

### **Screen State Schema**
```json
{
  "current_btc_price": 104800.30,
  "selected_option_type": "call|put|",
  "selected_strike": 105000.0,
  "selected_expiry": 240,
  "visible_strikes": [104000, 104500, 105000, 105500, 106000],
  "active_tab": "options_chain|portfolio|trading|education"
}
```

---

## 🔧 **CORS Configuration**

### **Allowed Origins**
```javascript
[
  "https://preview--turbo-options-platform.lovable.app",
  "https://turbo-options-platform.lovable.app",
  "https://preview--atticus-option-flow.lovable.app",
  "https://atticus-option-flow.lovable.app",
  "https://atticus-demo.onrender.com",
  "https://atticustrade.com",
  "http://localhost:3000",
  "http://localhost:3001",
  "http://localhost:5173",
  "http://localhost:8080",
  "http://localhost:8000"
]
```

### **Allowed Methods**
- GET, POST, PUT, DELETE, OPTIONS, PATCH

### **Allowed Headers**
- Content-Type, Authorization, X-User-ID, X-Requested-With, Accept, Origin, Access-Control-Request-Method, Access-Control-Request-Headers

---

## 📊 **Platform Features**

### **Contract Specifications**
- **Standard Contract Size**: 0.1 BTC
- **Available Expiries**: 2HR, 4HR, 8HR, 12HR
- **Strike Ranges**: Dynamic based on current BTC price
- **Option Types**: Call and Put options

### **Pricing Engine**
- **Model**: Black-Scholes with volatility smile/skew
- **Volatility Range**: 15% - 300%
- **Risk-Free Rate**: 5% annual
- **Real-time Updates**: Via WebSocket from OKX exchange

### **Risk Management**
- **Max Single User Exposure**: 10.0 BTC
- **Max Platform Net Delta**: 100.0 BTC
- **Margin Requirement**: 1.5x multiplier

---

## 🔌 **WebSocket Integration**

### **Connection URL**
```
wss://atticus-demo.onrender.com/ws
```

### **Message Types**
- **Price Updates**: Real-time BTC price and volume
- **Option Chain Updates**: Live option pricing
- **Portfolio Updates**: User position changes
- **Trade Confirmations**: Order execution status

### **Connection Parameters**
- **Ping Interval**: 20 seconds
- **Ping Timeout**: 20 seconds
- **Max Message Size**: 1MB

---

## 🛠 **Lovable Setup Instructions**

### **1. Configure API Base URL**
```javascript
const API_BASE_URL = 'https://atticus-demo.onrender.com';
const WS_URL = 'wss://atticus-demo.onrender.com/ws';
```

### **2. Test Golden Retriever 2.0**
```javascript
// Health check
const healthResponse = await fetch(`${API_BASE_URL}/gr2/health`);
const health = await healthResponse.json();

// Test chat
const chatResponse = await fetch(`${API_BASE_URL}/gr2/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What is delta?",
    context: {
      screen_state: {
        current_btc_price: 104800.30,
        selected_option_type: "call",
        selected_strike: 105000.0,
        selected_expiry: 240,
        visible_strikes: [104000, 104500, 105000, 105500, 106000],
        active_tab: "options_chain"
      }
    }
  })
});
```

### **3. Handle Real-time Data**
```javascript
const ws = new WebSocket(WS_URL);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle price updates, option chains, etc.
};

ws.onopen = () => {
  console.log('Connected to real-time data feed');
};
```

---

## 🔒 **Security & Authentication**

### **Current Status**
- **Authentication**: None required (demo mode)
- **CORS**: Fully configured for Lovable domains
- **Rate Limiting**: Not implemented (demo mode)

### **Production Considerations**
- Add API key authentication
- Implement rate limiting
- Add request validation
- Enable HTTPS only

---

## 📈 **Monitoring & Health**

### **Health Check Response**
```json
{
  "status": "healthy",
  "timestamp": "2024-06-19T13:44:10.666Z",
  "version": "2.2",
  "services": {
    "data_feed": "operational",
    "pricing_engine": "operational",
    "golden_retriever": "operational",
    "websocket": "operational"
  }
}
```

### **Golden Retriever 2.0 Health**
```json
{
  "service": "Golden Retriever 2.0",
  "status": "operational",
  "version": "2.0.0",
  "available": true
}
```

---

## 🚨 **Error Handling**

### **Common Error Responses**
- **404**: Endpoint not found
- **422**: Validation error (check request format)
- **500**: Server error (check logs)
- **503**: Service unavailable

### **Fallback Responses**
- Golden Retriever 2.0 provides fallback answers when confidence is low
- WebSocket automatically reconnects on disconnection
- Price feed falls back to alternative exchanges

---

## 📞 **Support & Troubleshooting**

### **Quick Tests**
1. **Health Check**: `curl https://atticus-demo.onrender.com/health`
2. **GR2 Health**: `curl https://atticus-demo.onrender.com/gr2/health`
3. **Market Price**: `curl https://atticus-demo.onrender.com/market/price`

### **Common Issues**
- **CORS Errors**: Check allowed origins in config
- **WebSocket Connection**: Verify URL and ping settings
- **GR2 Unavailable**: Check if Golden Retriever 2.0 is loaded

### **Logs & Debugging**
- Backend logs available in Render dashboard
- Golden Retriever 2.0 logs include confidence scores and sources
- WebSocket connection status logged

---

## 🎯 **Integration Checklist**

- [ ] **Base URL configured**: `https://atticus-demo.onrender.com`
- [ ] **CORS origins added**: All Lovable domains included
- [ ] **Golden Retriever 2.0 tested**: Health check passes
- [ ] **WebSocket connection**: Real-time data flowing
- [ ] **Screen state mapping**: Context properly formatted
- [ ] **Error handling**: Fallback responses implemented
- [ ] **Authentication**: None required (demo mode)
- [ ] **Rate limiting**: Not implemented (demo mode)

---

## 📝 **Notes**

- **Demo Mode**: Platform runs in demo mode with synthetic accounts
- **Real Data**: Uses real BTC price from OKX exchange
- **Auto-Deploy**: Changes pushed to GitHub automatically deploy to Render
- **No Code Required**: Lovable already has frontend code in `src/` directory
- **WebSocket**: Stable connections with automatic reconnection
- **Golden Retriever 2.0**: Screen-aware AI assistant with knowledge base

**Ready for production integration! 🚀** 