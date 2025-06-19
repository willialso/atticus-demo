import React, { useState } from 'react';
import { ChatInterface } from './chat/ChatInterface';

export const ChatExample: React.FC = () => {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [currentPrice] = useState(104740.00);
  const [selectedStrike] = useState(105000);
  const [selectedOptionType] = useState<'call' | 'put'>('call');

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">BTC Options Platform</h1>
      
      <div className="mb-4">
        <p className="text-gray-600">
          Current BTC Price: ${currentPrice.toLocaleString()}
        </p>
        <p className="text-gray-600">
          Selected Strike: ${selectedStrike.toLocaleString()} {selectedOptionType.toUpperCase()}
        </p>
      </div>

      <button
        onClick={() => setIsChatOpen(true)}
        className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600"
      >
        Open Golden Retriever 2.0
      </button>

      {isChatOpen && (
        <ChatInterface
          onClose={() => setIsChatOpen(false)}
          currentPrice={currentPrice}
          selectedStrike={selectedStrike}
          selectedOptionType={selectedOptionType}
        />
      )}
    </div>
  );
}; 