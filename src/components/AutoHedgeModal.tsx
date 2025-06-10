import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { config } from '../lib/config';

interface AutoHedgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onHedgeExecuted?: (result: any) => void;
}

interface HedgeAnalysis {
  status: 'pending' | 'executed' | 'failed';
  options_needed: Array<{
    type: string;
    strike: number;
    expiry_hours: number;
    quantity: number;
    action: string;
  }>;
  execution_details?: any;
}

const AutoHedgeModal: React.FC<AutoHedgeModalProps> = ({ isOpen, onClose, onHedgeExecuted }) => {
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hedgeAnalysis, setHedgeAnalysis] = useState<HedgeAnalysis | null>(null);

  const executeHedgeOnAtticus = async () => {
    if (!hedgeAnalysis) return;

    try {
      setIsExecuting(true);
      setError(null);
      
      // First, update the sandbox account
      const accountUpdate = {
        account_id: "sandbox_user",
        platform: "sandbox",
        positions: []
      };

      const accountResponse = await fetch(config.ENDPOINTS.SANDBOX.UPDATE_ACCOUNT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(accountUpdate),
      });

      if (!accountResponse.ok) {
        const errorData = await accountResponse.json();
        throw new Error(errorData.detail || 'Failed to update sandbox account');
      }
      
      // Prepare trade request
      const tradeRequest = {
        user_id: "sandbox_user", // Use a consistent sandbox user ID
        option_type: hedgeAnalysis.options_needed[0].type,
        strike: hedgeAnalysis.options_needed[0].strike,
        expiry_minutes: hedgeAnalysis.options_needed[0].expiry_hours * 60,
        quantity: hedgeAnalysis.options_needed[0].quantity,
        side: hedgeAnalysis.options_needed[0].action
      };

      // Execute trade in sandbox
      const response = await fetch(config.ENDPOINTS.SANDBOX.EXECUTE_TRADE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(tradeRequest),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to execute hedge trade');
      }

      const result = await response.json();
      
      // Update local state with new position and portfolio data
      if (result.status === 'success') {
        setHedgeAnalysis({
          ...hedgeAnalysis,
          status: 'executed',
          execution_details: {
            trade_id: result.trade_id,
            position: result.position,
            portfolio_summary: result.portfolio_summary,
            risk_analysis: result.risk_analysis,
            hedging_plan: result.hedging_plan
          }
        });
        
        // Notify parent component of successful execution
        if (onHedgeExecuted) {
          onHedgeExecuted(result);
        }
      } else {
        throw new Error(result.message || 'Trade execution failed');
      }

    } catch (error) {
      console.error('Error executing hedge:', error);
      setError(error.message);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Auto-Hedge Strategy</DialogTitle>
        </DialogHeader>
        
        {error && (
          <div className="bg-red-50 p-3 rounded-lg mb-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {hedgeAnalysis && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Hedge Analysis Results</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-gray-600">Option Type</div>
                      <div className="font-medium">{hedgeAnalysis.options_needed[0].type.toUpperCase()}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Strike Price</div>
                      <div className="font-medium">${hedgeAnalysis.options_needed[0].strike}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Quantity</div>
                      <div className="font-medium">{hedgeAnalysis.options_needed[0].quantity}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Action</div>
                      <div className="font-medium">{hedgeAnalysis.options_needed[0].action.toUpperCase()}</div>
                    </div>
                  </div>
                  
                  <Button 
                    className="w-full bg-green-600 hover:bg-green-700"
                    onClick={executeHedgeOnAtticus}
                    disabled={isExecuting}
                  >
                    {isExecuting ? 'Executing...' : 'Execute Hedge on Atticus Platform'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default AutoHedgeModal; 