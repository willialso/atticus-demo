import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AutoHedgeModal from '../src/components/AutoHedgeModal';

// Mock fetch
global.fetch = jest.fn();

describe('AutoHedgeModal', () => {
    const mockOnClose = jest.fn();
    const mockOnHedgeExecuted = jest.fn();
    const mockHedgeAnalysis = {
        status: 'pending',
        options_needed: [{
            type: 'call',
            strike: 50000,
            expiry_hours: 1,
            quantity: 1,
            action: 'buy'
        }]
    };

    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders correctly when open', () => {
        render(
            <AutoHedgeModal
                isOpen={true}
                onClose={mockOnClose}
                onHedgeExecuted={mockOnHedgeExecuted}
            />
        );

        expect(screen.getByText('Auto-Hedge Strategy')).toBeInTheDocument();
    });

    it('does not render when closed', () => {
        render(
            <AutoHedgeModal
                isOpen={false}
                onClose={mockOnClose}
                onHedgeExecuted={mockOnHedgeExecuted}
            />
        );

        expect(screen.queryByText('Auto-Hedge Strategy')).not.toBeInTheDocument();
    });

    it('displays hedge analysis results when available', () => {
        render(
            <AutoHedgeModal
                isOpen={true}
                onClose={mockOnClose}
                onHedgeExecuted={mockOnHedgeExecuted}
            />
        );

        // Set hedge analysis
        const modal = screen.getByRole('dialog');
        const hedgeAnalysis = {
            status: 'pending',
            options_needed: [{
                type: 'call',
                strike: 50000,
                expiry_hours: 1,
                quantity: 1,
                action: 'buy'
            }]
        };

        // Trigger state update
        fireEvent.change(modal, { target: { value: JSON.stringify(hedgeAnalysis) } });

        expect(screen.getByText('Hedge Analysis Results')).toBeInTheDocument();
        expect(screen.getByText('CALL')).toBeInTheDocument();
        expect(screen.getByText('$50000')).toBeInTheDocument();
        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('BUY')).toBeInTheDocument();
    });

    it('executes hedge trade when button is clicked', async () => {
        const mockResponse = {
            success: true,
            position: {
                symbol: 'BTC-CALL',
                size: 1,
                side: 'buy',
                strike: 50000
            },
            portfolio_summary: {
                total_positions: 1,
                total_exposure: 50000,
                unrealized_pnl: 0
            },
            risk_analysis: {
                delta: 0.5,
                gamma: 0.1,
                vega: 0.2,
                theta: -0.3
            }
        };

        (global.fetch as jest.Mock).mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve(mockResponse)
        });

        render(
            <AutoHedgeModal
                isOpen={true}
                onClose={mockOnClose}
                onHedgeExecuted={mockOnHedgeExecuted}
            />
        );

        // Set hedge analysis
        const modal = screen.getByRole('dialog');
        const hedgeAnalysis = {
            status: 'pending',
            options_needed: [{
                type: 'call',
                strike: 50000,
                expiry_hours: 1,
                quantity: 1,
                action: 'buy'
            }]
        };

        // Trigger state update
        fireEvent.change(modal, { target: { value: JSON.stringify(hedgeAnalysis) } });

        // Click execute button
        const executeButton = screen.getByText('Execute Hedge on Atticus Platform');
        fireEvent.click(executeButton);

        // Verify API call
        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith('/api/sandbox/trades/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: 'sandbox_user',
                    option_type: 'call',
                    strike: 50000,
                    expiry_minutes: 60,
                    quantity: 1,
                    side: 'buy'
                })
            });
        });

        // Verify callback
        expect(mockOnHedgeExecuted).toHaveBeenCalledWith(mockResponse);
    });

    it('handles API error correctly', async () => {
        const errorMessage = 'Failed to execute hedge trade';
        (global.fetch as jest.Mock).mockResolvedValueOnce({
            ok: false,
            json: () => Promise.resolve({ detail: errorMessage })
        });

        render(
            <AutoHedgeModal
                isOpen={true}
                onClose={mockOnClose}
                onHedgeExecuted={mockOnHedgeExecuted}
            />
        );

        // Set hedge analysis
        const modal = screen.getByRole('dialog');
        const hedgeAnalysis = {
            status: 'pending',
            options_needed: [{
                type: 'call',
                strike: 50000,
                expiry_hours: 1,
                quantity: 1,
                action: 'buy'
            }]
        };

        // Trigger state update
        fireEvent.change(modal, { target: { value: JSON.stringify(hedgeAnalysis) } });

        // Click execute button
        const executeButton = screen.getByText('Execute Hedge on Atticus Platform');
        fireEvent.click(executeButton);

        // Verify error message is displayed
        await waitFor(() => {
            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });

        // Verify callback was not called
        expect(mockOnHedgeExecuted).not.toHaveBeenCalled();
    });
}); 