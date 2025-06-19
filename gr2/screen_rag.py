# gr2/screen_rag.py
# Golden Retriever 2.0 - Screen-Aware RAG Pipeline

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from gr2.config import BTC_OPTIONS_KB, CONFIDENCE_THRESHOLD, MIN_RETRIEVED_DOCS
from gr2.post_processor import clean_response, extract_jargon_terms, add_analogy_prompt
from gr2.loop_guard import loop_guard

logger = logging.getLogger(__name__)

@dataclass
class RAGResult:
    answer: str
    confidence: float
    retrieved_docs: List[Dict]
    retrieved_docs_titles: List[str]
    jargon_terms: List[str]
    context_used: str

class GoldenRetrieverRAG:
    """Core Golden Retriever RAG implementation with screen awareness."""
    
    def __init__(self, knowledge_base: List[Dict] = None):
        self.knowledge_base = knowledge_base or BTC_OPTIONS_KB
        self._setup_models()
        
    def _setup_models(self):
        """Initialize models for the Golden Retriever pipeline."""
        # Simplified implementation without external LLM dependencies
        self.identify_jargon = self._identify_jargon_simple
        self.identify_context = self._identify_context_simple
        self.augment_question = self._augment_question_simple
        self.generate_answer = self._generate_answer_simple

    def _load_analogies(self):
        """Load analogies from JSON file."""
        try:
            with open('gr2/analogies.json', 'r') as f:
                self.analogies = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load analogies: {e}")
            self.analogies = {}

    def _identify_jargon_simple(self, question: str) -> List[str]:
        """Simple jargon identification based on keywords."""
        btc_options_terms = [
            "delta", "gamma", "theta", "vega", "rho", "greeks",
            "strike", "premium", "expiry", "call", "put", "option",
            "itm", "atm", "otm", "moneyness", "intrinsic", "time value",
            "implied volatility", "black scholes", "hedge", "position"
        ]
        
        question_lower = question.lower()
        found_terms = [term for term in btc_options_terms if term in question_lower]
        return found_terms

    def _identify_context_simple(self, question: str, screen_state: Dict) -> str:
        """Simple context identification from screen state."""
        context_parts = []
        
        if screen_state.get("selected_option_type"):
            context_parts.append(f"Selected option type: {screen_state['selected_option_type']}")
        
        if screen_state.get("selected_strike"):
            context_parts.append(f"Selected strike: ${screen_state['selected_strike']:,.0f}")
        
        if screen_state.get("current_btc_price"):
            context_parts.append(f"Current BTC price: ${screen_state['current_btc_price']:,.0f}")
        
        if screen_state.get("active_tab"):
            context_parts.append(f"Active tab: {screen_state['active_tab']}")
        
        return "; ".join(context_parts) if context_parts else "No specific context available"

    def _augment_question_simple(self, question: str, jargon_terms: List[str], context: str) -> str:
        """Simple question augmentation with analogy requests."""
        augmented = question
        
        # Add analogy request for jargon terms
        if jargon_terms:
            augmented += " When you define an options term, add a plain-English analogy (e.g., 'A put is like paying for return insurance on a gadget: if it breaks (price drops) you get your money back.')"
        
        if jargon_terms:
            augmented += f" [Terms: {', '.join(jargon_terms)}]"
        
        if context:
            augmented += f" [Context: {context}]"
        
        return augmented

    def _generate_answer_simple(self, question: str, screen_state: Dict, retrieved_docs: List[Dict]) -> str:
        """Generate answer based on retrieved documents and screen context."""
        if not retrieved_docs:
            return "I don't have enough information to answer that question about Bitcoin options."
        
        # Combine relevant document content
        doc_content = "\n\n".join([f"{doc['title']}: {doc['content']}" for doc in retrieved_docs])
        
        # Create context-aware answer
        context_info = self._identify_context_simple(question, screen_state)
        
        # Find the most relevant document
        primary_doc = retrieved_docs[0]
        
        answer = f"Based on your question about '{question}' and the current context ({context_info}), here's what you need to know:\n\n"
        answer += f"{primary_doc['content']}"
        
        if len(retrieved_docs) > 1:
            answer += f"\n\nAdditional information: {retrieved_docs[1]['title']}"
        
        return answer

    def _retrieve_relevant_docs(self, question: str, screen_state: Dict) -> List[Dict]:
        """Retrieve relevant documents from knowledge base."""
        try:
            # Simple keyword-based retrieval for v1
            question_lower = question.lower()
            relevant_docs = []
            
            for doc in self.knowledge_base:
                # Check if question contains keywords from doc title or content
                title_lower = doc["title"].lower()
                content_lower = doc["content"].lower()
                
                # Score based on keyword matches
                score = 0
                if any(word in question_lower for word in title_lower.split()):
                    score += 2
                if any(word in question_lower for word in content_lower.split()):
                    score += 1
                
                # Screen state relevance
                if screen_state.get("selected_option_type"):
                    if screen_state["selected_option_type"] in content_lower:
                        score += 1
                
                if score > 0:
                    relevant_docs.append((doc, score))
            
            # Sort by score and return top docs
            relevant_docs.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, score in relevant_docs[:3]]
            
        except Exception as e:
            logger.error(f"Error in document retrieval: {e}")
            return []

    def _calculate_confidence(self, retrieved_docs: List[Dict], question: str) -> float:
        """Calculate confidence score for the response."""
        try:
            if not retrieved_docs:
                return 0.0
            
            # Simple confidence based on number and relevance of docs
            base_confidence = min(len(retrieved_docs) / 3.0, 1.0)
            
            # Boost confidence if question contains specific BTC options terms
            btc_options_terms = ["delta", "gamma", "theta", "vega", "strike", "premium", "expiry", "call", "put", "option"]
            question_lower = question.lower()
            term_matches = sum(1 for term in btc_options_terms if term in question_lower)
            term_boost = min(term_matches * 0.1, 0.3)
            
            return min(base_confidence + term_boost, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.0

    def __call__(self, question: str, screen_state: Dict) -> RAGResult:
        """Main Golden Retriever pipeline execution."""
        try:
            # Step 1: Identify jargon terms
            jargon_terms = self.identify_jargon(question)
            
            # Step 2: Identify relevant context from screen state
            context_used = self.identify_context(question, screen_state)
            
            # Step 3: Retrieve relevant documents
            retrieved_docs = self._retrieve_relevant_docs(question, screen_state)
            
            # Step 4: Augment question with jargon definitions and context
            augmented_question = self.augment_question(question, jargon_terms, context_used)
            
            # Step 5: Generate answer
            answer = self.generate_answer(augmented_question, screen_state, retrieved_docs)
            
            # Step 6: Calculate confidence
            confidence = self._calculate_confidence(retrieved_docs, question)
            
            # Step 7: Check if we should fallback
            if confidence < CONFIDENCE_THRESHOLD or len(retrieved_docs) < MIN_RETRIEVED_DOCS:
                return self._fallback_result(question)
            
            return RAGResult(
                answer=answer,
                confidence=confidence,
                retrieved_docs=retrieved_docs,
                retrieved_docs_titles=[doc["title"] for doc in retrieved_docs],
                jargon_terms=jargon_terms,
                context_used=context_used
            )
            
        except Exception as e:
            logger.error(f"Error in Golden Retriever pipeline: {e}")
            return self._fallback_result(question)

    def _get_jargon_definition(self, term: str) -> str:
        """Get definition for a jargon term."""
        term_lower = term.lower()
        for doc in self.knowledge_base:
            if term_lower in doc["title"].lower():
                return doc["content"]
        return f"Term '{term}' not found in knowledge base."

    def _fallback_result(self, question: str) -> RAGResult:
        """Generate fallback response when confidence is low."""
        fallback_answer = (
            "I'm still a v1 demo and can answer only BTC-options questions about what's on screen. "
            "Try asking about:\n"
            "• What does Delta mean here?\n"
            "• Why is this strike ATM?\n"
            "• How does Theta affect my position?\n"
            "• What's the difference between calls and puts?\n"
            "• How do I choose the right strike price?"
        )
        
        return RAGResult(
            answer=fallback_answer,
            confidence=0.0,
            retrieved_docs=[],
            retrieved_docs_titles=[],
            jargon_terms=[],
            context_used=""
        )

    def fallback(self, question: str) -> str:
        """Simple fallback method for external use."""
        return self._fallback_result(question).answer

# Global instance
GR2 = GoldenRetrieverRAG() 