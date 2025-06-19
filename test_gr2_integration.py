#!/usr/bin/env python3
# test_gr2_integration.py
# Test script for Golden Retriever 2.0 integration

import sys
import os
import json
import asyncio
from typing import Dict, Any

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_gr2_core():
    """Test the core GR2 functionality."""
    print("🧪 Testing Golden Retriever 2.0 Core Functionality...")
    
    try:
        from gr2.screen_rag import GR2
        from gr2.config import BTC_OPTIONS_KB
        
        print(f"✅ GR2 imported successfully")
        print(f"✅ Knowledge base loaded with {len(BTC_OPTIONS_KB)} documents")
        
        # Test with sample screen state
        test_screen_state = {
            "current_btc_price": 105000.0,
            "selected_option_type": "call",
            "selected_strike": 105000.0,
            "selected_expiry": 240,  # 4 hours
            "visible_strikes": [104000, 104500, 105000, 105500, 106000],
            "active_tab": "options_chain"
        }
        
        # Test questions
        test_questions = [
            "What does Delta mean?",
            "Why is this strike ATM?",
            "How does Theta affect my position?",
            "What's the difference between calls and puts?",
            "How do I choose the right strike price?"
        ]
        
        for question in test_questions:
            print(f"\n📝 Testing: {question}")
            result = GR2(question, test_screen_state)
            print(f"   Answer: {result.answer[:100]}...")
            print(f"   Confidence: {result.confidence:.2f}")
            print(f"   Sources: {result.retrieved_docs_titles}")
            print(f"   Jargon terms: {result.jargon_terms}")
        
        print("\n✅ Core GR2 functionality test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Core GR2 test failed: {e}")
        return False

def test_gr2_api():
    """Test the GR2 API integration."""
    print("\n🧪 Testing Golden Retriever 2.0 API Integration...")
    
    try:
        from backend.api_gr2 import router, ChatRequest, ChatResponse
        
        print("✅ GR2 API router imported successfully")
        
        # Test the request/response models
        test_request = ChatRequest(
            message="What does Delta mean?",
            screen_state={
                "current_btc_price": 105000.0,
                "selected_option_type": "call",
                "selected_strike": 105000.0,
                "selected_expiry": 240,
                "visible_strikes": [104000, 104500, 105000, 105500, 106000],
                "active_tab": "options_chain"
            }
        )
        
        print("✅ ChatRequest model test passed")
        
        # Test response model
        test_response = ChatResponse(
            answer="Test answer",
            sources=["Delta", "Greeks"],
            confidence=0.8,
            jargon_terms=["delta"],
            context_used="Test context"
        )
        
        print("✅ ChatResponse model test passed")
        print("✅ GR2 API integration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ GR2 API test failed: {e}")
        return False

def test_fastapi_integration():
    """Test FastAPI integration."""
    print("\n🧪 Testing FastAPI Integration...")
    
    try:
        from backend.api import app
        
        # Check if GR2 router is included
        routes = [route.path for route in app.routes]
        gr2_routes = [route for route in routes if route.startswith('/gr2')]
        
        if gr2_routes:
            print(f"✅ GR2 routes found: {gr2_routes}")
            print("✅ FastAPI integration test passed!")
            return True
        else:
            print("❌ No GR2 routes found in FastAPI app")
            return False
            
    except Exception as e:
        print(f"❌ FastAPI integration test failed: {e}")
        return False

def test_knowledge_base():
    """Test the knowledge base content."""
    print("\n🧪 Testing Knowledge Base...")
    
    try:
        from gr2.config import BTC_OPTIONS_KB
        
        print(f"✅ Knowledge base contains {len(BTC_OPTIONS_KB)} documents")
        
        # Check for key topics
        key_topics = ["delta", "gamma", "theta", "vega", "strike", "premium"]
        found_topics = []
        
        for doc in BTC_OPTIONS_KB:
            if any(topic in doc["title"].lower() for topic in key_topics):
                found_topics.append(doc["title"])
        
        print(f"✅ Found key topics: {found_topics}")
        
        if len(found_topics) >= 4:
            print("✅ Knowledge base test passed!")
            return True
        else:
            print("❌ Knowledge base missing key topics")
            return False
            
    except Exception as e:
        print(f"❌ Knowledge base test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Golden Retriever 2.0 Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_gr2_core,
        test_gr2_api,
        test_fastapi_integration,
        test_knowledge_base
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Golden Retriever 2.0 is ready to use.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 