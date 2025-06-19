// gr2/frontend_integration.js
// Frontend integration example for Golden Retriever 2.0

/**
 * Golden Retriever 2.0 Frontend Integration
 * This example shows how to integrate GR2 with your existing frontend
 */

class GoldenRetriever2Client {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.endpoint = `${baseUrl}/gr2/chat`;
    }

    /**
     * Ask Golden Retriever 2.0 a question with screen context
     * @param {string} message - User's question
     * @param {Object} screenState - Current UI state
     * @returns {Promise<Object>} Response from GR2
     */
    async askGR2(message, screenState) {
        try {
            const payload = {
                message: message,
                screen_state: {
                    current_btc_price: screenState.currentPrice || 0.0,
                    selected_option_type: screenState.selectedOptionType || null,
                    selected_strike: screenState.selectedStrike || null,
                    selected_expiry: screenState.selectedExpiry || 0,
                    visible_strikes: screenState.visibleStrikes || [],
                    active_tab: screenState.activeTab || "options_chain"
                }
            };

            console.log('Sending to Golden Retriever 2.0:', payload);

            const response = await fetch(this.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Golden Retriever 2.0 response:', data);
            return data;

        } catch (error) {
            console.error('Error calling Golden Retriever 2.0:', error);
            return {
                answer: "Sorry, I'm having trouble connecting to the AI assistant right now.",
                confidence: 0.0,
                sources: []
            };
        }
    }

    /**
     * Check if Golden Retriever 2.0 is available
     * @returns {Promise<boolean>}
     */
    async checkHealth() {
        try {
            const response = await fetch(`${this.baseUrl}/gr2/health`);
            if (response.ok) {
                const data = await response.json();
                return data.available === true;
            }
            return false;
        } catch (error) {
            console.error('Health check failed:', error);
            return false;
        }
    }

    /**
     * Test Golden Retriever 2.0 functionality
     * @returns {Promise<Object>}
     */
    async testGR2() {
        try {
            const testScreenState = {
                currentPrice: 105000.0,
                selectedOptionType: "call",
                selectedStrike: 105000.0,
                selectedExpiry: 240,
                visibleStrikes: [104000, 104500, 105000, 105500, 106000],
                activeTab: "options_chain"
            };

            return await this.askGR2("What does Delta mean?", testScreenState);
        } catch (error) {
            console.error('GR2 test failed:', error);
            return { error: error.message };
        }
    }
}

// Example usage with your existing frontend
async function integrateWithExistingFrontend() {
    const gr2Client = new GoldenRetriever2Client();
    
    // Check if GR2 is available
    const isAvailable = await gr2Client.checkHealth();
    if (!isAvailable) {
        console.warn('Golden Retriever 2.0 is not available');
        return;
    }

    // Example: Get current screen state from your existing UI
    function getCurrentScreenState() {
        // This should be implemented based on your existing frontend
        // Example implementation:
        return {
            currentPrice: window.currentBTCPrice || 105000.0,
            selectedOptionType: window.selectedOptionType || null,
            selectedStrike: window.selectedStrike || null,
            selectedExpiry: window.selectedExpiry || 240,
            visibleStrikes: window.visibleStrikes || [],
            activeTab: window.activeTab || "options_chain"
        };
    }

    // Example: Handle user questions
    async function handleUserQuestion(question) {
        const screenState = getCurrentScreenState();
        const response = await gr2Client.askGR2(question, screenState);
        
        // Display the response in your UI
        displayGR2Response(response);
    }

    // Example: Display GR2 response
    function displayGR2Response(response) {
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'bot-message gr2-response';
            messageDiv.innerHTML = `
                <div class="gr2-answer">${response.answer}</div>
                ${response.sources && response.sources.length > 0 ? 
                    `<div class="gr2-sources">Sources: ${response.sources.join(', ')}</div>` : ''}
                ${response.confidence !== undefined ? 
                    `<div class="gr2-confidence">Confidence: ${(response.confidence * 100).toFixed(1)}%</div>` : ''}
            `;
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    }

    // Example: Add quick question buttons
    function addQuickQuestions() {
        const quickQuestions = [
            "What does Delta mean?",
            "Why is this strike ATM?",
            "How does Theta affect my position?",
            "What's the difference between calls and puts?",
            "How do I choose the right strike price?"
        ];

        const container = document.getElementById('quickQuestions');
        if (container) {
            quickQuestions.forEach(question => {
                const button = document.createElement('button');
                button.className = 'quick-question';
                button.textContent = question;
                button.onclick = () => handleUserQuestion(question);
                container.appendChild(button);
            });
        }
    }

    // Initialize the integration
    addQuickQuestions();
    
    // Example: Test GR2 functionality
    const testResult = await gr2Client.testGR2();
    console.log('GR2 test result:', testResult);
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GoldenRetriever2Client;
} else if (typeof window !== 'undefined') {
    window.GoldenRetriever2Client = GoldenRetriever2Client;
    window.integrateWithExistingFrontend = integrateWithExistingFrontend;
} 