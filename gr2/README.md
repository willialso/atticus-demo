# Golden Retriever 2.0 – Screen-Aware RAG for BTC Options Demo

## Overview

Golden Retriever 2.0 is a sophisticated screen-aware RAG (Retrieval-Augmented Generation) system specifically designed for your BTC Options trading platform. It provides context-aware answers by reading the current UI state and delivering high-fidelity responses about Bitcoin options trading.

## Features

✅ **Screen-Aware Answers** - Reads the UI state you already expose in your frontend  
✅ **High-Fidelity Pipeline** - Jargon → Context → Question augmentation → Retrieval → Answer  
✅ **Built-in Fallback** - Steers users back when they wander outside the v1 scope  
✅ **Zero Backend Disruptions** - Completely separate from existing code  
✅ **Real-Time Integration** - Works with your existing FastAPI backend  

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │───▶│  Screen State   │───▶│   GR2 Pipeline  │
│                 │    │                 │    │                 │
│ • BTC Price     │    │ • current_btc   │    │ 1. Jargon ID    │
│ • Selected Opt  │    │ • selected_type │    │ 2. Context ID   │
│ • Strike Price  │    │ • selected_strike│   │ 3. Question Aug │
│ • Active Tab    │    │ • visible_strikes│   │ 4. Doc Retrieval│
└─────────────────┘    └─────────────────┘    │ 5. Answer Gen   │
                                              └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  Knowledge Base │
                                              │                 │
                                              │ • Delta         │
                                              │ • Gamma         │
                                              │ • Theta         │
                                              │ • Vega          │
                                              │ • Strike Selection│
                                              └─────────────────┘
```

## Quick Start

### 1. Installation

The dependencies are already installed:
```bash
pip install dspy-ai>=2.6.27
```

### 2. API Usage

**Endpoint:** `POST /gr2/chat`

**Request:**
```json
{
  "message": "What does Delta mean?",
  "screen_state": {
    "current_btc_price": 105000.0,
    "selected_option_type": "call",
    "selected_strike": 105000.0,
    "selected_expiry": 240,
    "visible_strikes": [104000, 104500, 105000, 105500, 106000],
    "active_tab": "options_chain"
  }
}
```

**Response:**
```json
{
  "answer": "Based on your question about 'What does Delta mean?' and the current context (Selected option type: call; Selected strike: $105,000; Current BTC price: $105,000; Active tab: options_chain), here's what you need to know:\n\nDelta shows how much the option price is expected to move for a $1 move in BTC. For calls, delta ranges from 0 to 1. For puts, delta ranges from -1 to 0. ATM options have delta around 0.5 for calls and -0.5 for puts.",
  "sources": ["Delta", "Theta", "Option Types"],
  "confidence": 1.0,
  "jargon_terms": ["delta"],
  "context_used": "Selected option type: call; Selected strike: $105,000; Current BTC price: $105,000; Active tab: options_chain"
}
```

### 3. Frontend Integration

```javascript
// Using the provided frontend integration
const gr2Client = new GoldenRetriever2Client();

async function askQuestion(question) {
  const screenState = {
    currentPrice: window.currentBTCPrice || 105000.0,
    selectedOptionType: window.selectedOptionType || null,
    selectedStrike: window.selectedStrike || null,
    selectedExpiry: window.selectedExpiry || 240,
    visibleStrikes: window.visibleStrikes || [],
    activeTab: window.activeTab || "options_chain"
  };
  
  const response = await gr2Client.askGR2(question, screenState);
  displayResponse(response);
}
```

## Knowledge Base

The system includes a comprehensive knowledge base covering:

- **Greeks**: Delta, Gamma, Theta, Vega, Rho
- **Strike Selection**: ATM, ITM, OTM concepts
- **Option Types**: Calls vs Puts
- **Risk Management**: Position sizing, portfolio management
- **Premium Calculation**: Black-Scholes, intrinsic vs time value
- **Expiry Times**: 2-Hour, 4-Hour, 8-Hour, 12-Hour strategies

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gr2/chat` | POST | Main chat endpoint with screen context |
| `/gr2/health` | GET | Health check for GR2 service |
| `/gr2/knowledge-base` | GET | Get current knowledge base (debug) |
| `/gr2/test` | POST | Test GR2 functionality |

## Configuration

### Screen State Schema

```python
SCREEN_SCHEMA = {
    "current_btc_price": float,
    "selected_option_type": str,        # "call" | "put" | None
    "selected_strike": float | None,
    "selected_expiry": int,             # minutes
    "visible_strikes": list[float],     # strikes rendered in chain
    "active_tab": str,                  # "options_chain", "portfolio", etc.
}
```

### Confidence Thresholds

```python
CONFIDENCE_THRESHOLD = 0.25  # Minimum confidence for valid response
MIN_RETRIEVED_DOCS = 1       # Minimum documents required
```

## Fallback Behavior

When the system has low confidence or no relevant documents:

1. **Returns fallback message** with suggested questions
2. **Logs the miss** for later knowledge base expansion
3. **Maintains user experience** without breaking the flow

Example fallback:
```
I'm still a v1 demo and can answer only BTC-options questions about what's on screen. 
Try asking about:
• What does Delta mean here?
• Why is this strike ATM?
• How does Theta affect my position?
• What's the difference between calls and puts?
• How do I choose the right strike price?
```

## Testing

Run the comprehensive test suite:

```bash
python test_gr2_integration.py
```

This tests:
- ✅ Core GR2 functionality
- ✅ API integration
- ✅ FastAPI router inclusion
- ✅ Knowledge base content

## Example Questions

The system handles questions like:

- "What does Delta mean here?"
- "Why is this strike ATM?"
- "How does Theta affect my position?"
- "What's the difference between calls and puts?"
- "How do I choose the right strike price?"
- "What's the risk of selling naked calls?"
- "How does implied volatility affect my option?"

## Integration with Existing Code

Golden Retriever 2.0 is designed to be completely non-disruptive:

- **Separate package** (`gr2/`) with no dependencies on existing code
- **Optional integration** - fails gracefully if not available
- **Same FastAPI app** - just adds new routes
- **Existing endpoints unchanged** - all current functionality preserved

## Deployment

The system is ready for deployment:

1. **Dependencies**: Already in `requirements.txt`
2. **Router**: Automatically included in FastAPI app
3. **Health checks**: Available at `/gr2/health`
4. **Error handling**: Graceful fallbacks throughout

## Future Enhancements

Potential improvements for v2:

- **Expanded knowledge base** with more trading strategies
- **Real-time market data integration** for dynamic answers
- **User-specific learning** based on trading patterns
- **Multi-language support** for international users
- **Advanced NLP** for more natural question understanding

## Support

For issues or questions:

1. Check the health endpoint: `GET /gr2/health`
2. Review logs for error messages
3. Test with the provided test suite
4. Verify screen state format matches schema

---

**Golden Retriever 2.0** - Making Bitcoin options trading accessible and educational! 🚀 