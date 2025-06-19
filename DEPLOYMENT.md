# BTC Options Platform - Deployment Guide

## 🚀 Render Deployment

### Prerequisites
- GitHub repository with the code pushed
- Render account (free tier available)

### Deployment Steps

1. **Connect to Render**
   - Go to [render.com](https://render.com)
   - Sign up/Login with your GitHub account
   - Click "New +" → "Web Service"

2. **Connect Repository**
   - Select your GitHub repository: `willialso/atticus-demo`
   - Render will auto-detect it's a Python FastAPI app

3. **Configure Service**
   - **Name**: `btc-options-platform-backend`
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.api:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Starter` (free tier)

4. **Environment Variables** (Optional)
   - `PYTHON_VERSION`: `3.11.0`
   - `PORT`: `8000` (auto-set by Render)

5. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy automatically
   - Your app will be available at: `https://your-app-name.onrender.com`

### Health Check
- Endpoint: `/health`
- Golden Retriever 2.0: `/gr2/health`

## 🔗 Lovable Integration

### What Lovable Needs to Connect

Lovable requires the following information to connect to your deployed backend:

#### 1. **Base URL**
```
https://your-app-name.onrender.com
```

#### 2. **API Endpoints**
- **Health Check**: `GET /health`
- **Golden Retriever 2.0 Chat**: `POST /gr2/chat`
- **Golden Retriever 2.0 Health**: `GET /gr2/health`
- **Knowledge Base**: `GET /gr2/knowledge-base`

#### 3. **Authentication**
- Currently: No authentication required (demo mode)
- Production: Add API key authentication

#### 4. **Request Format for Golden Retriever 2.0**
```json
{
  "question": "What is a Bitcoin call option?",
  "screen_context": {
    "current_page": "options_trading",
    "user_position": "long_call",
    "market_data": {
      "btc_price": 104800.30,
      "volatility": 0.45
    }
  }
}
```

#### 5. **Response Format**
```json
{
  "answer": "A Bitcoin call option gives you the right to buy BTC at a specific price...",
  "confidence": 0.92,
  "sources": ["options_basics", "btc_trading_guide"],
  "jargon_identified": ["call option", "strike price"],
  "context_used": true
}
```

### Lovable Configuration Steps

1. **In Lovable Dashboard**
   - Go to Integrations → Custom API
   - Enter your Render URL
   - Test connection with `/health` endpoint

2. **Configure Golden Retriever 2.0**
   - Set chat endpoint: `/gr2/chat`
   - Configure screen context mapping
   - Set up response parsing

3. **Test Integration**
   - Send test questions through Lovable
   - Verify screen-aware responses
   - Check confidence scoring

## 🔧 Local Development

### Run Locally
```bash
# Activate virtual environment
source myenv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend
python -m uvicorn backend.api:app --reload --port 8000
```

### Test Golden Retriever 2.0
```bash
# Health check
curl http://localhost:8000/gr2/health

# Chat with screen context
curl -X POST http://localhost:8000/gr2/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is delta hedging?",
    "screen_context": {
      "current_page": "portfolio",
      "user_position": "long_call"
    }
  }'
```

## 📊 Monitoring

### Render Dashboard
- View logs in real-time
- Monitor performance metrics
- Set up alerts for downtime

### Health Endpoints
- `/health` - Basic service health
- `/gr2/health` - Golden Retriever 2.0 status
- `/gr2/knowledge-base` - Knowledge base status

## 🔒 Security Considerations

### For Production
1. **Add Authentication**
   ```python
   # In backend/api.py
   from fastapi import HTTPException, Depends
   from fastapi.security import HTTPBearer
   
   security = HTTPBearer()
   
   async def verify_token(token: str = Depends(security)):
       # Implement token validation
       pass
   ```

2. **Environment Variables**
   - Store sensitive data in Render environment variables
   - Never commit API keys to Git

3. **Rate Limiting**
   - Implement rate limiting for API endpoints
   - Protect against abuse

## 🚨 Troubleshooting

### Common Issues

1. **Build Failures**
   - Check `requirements.txt` for version conflicts
   - Verify Python version compatibility

2. **Runtime Errors**
   - Check Render logs for detailed error messages
   - Verify all dependencies are installed

3. **Connection Issues**
   - Ensure Render service is running
   - Check firewall/network settings

### Support
- Render Documentation: [docs.render.com](https://docs.render.com)
- FastAPI Documentation: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- Golden Retriever 2.0: Custom implementation for BTC options

---

**Ready for Production! 🎉**

Your BTC Options Platform with Golden Retriever 2.0 is now deployed and ready for Lovable integration. 