import React from 'react';
import { AppError } from '../utils/ErrorHandler';

interface ErrorDisplayProps {
  error: AppError | null;
  onDismiss?: () => void;
  onRetry?: () => void;
  onReconnect?: () => void;
  persistent?: boolean;
}

export function ErrorDisplay({
  error,
  onDismiss,
  onRetry,
  onReconnect,
  persistent = false
}: ErrorDisplayProps) {
  if (!error) {
    return null;
  }

  const getErrorStyle = () => {
    const baseStyle = {
      padding: '16px',
      borderRadius: '4px',
      marginBottom: '16px',
      border: '2px solid',
      backgroundColor: '#fff3e0',
      borderColor: '#ff9800'
    };

    if (error.type === 'NETWORK_ERROR' || error.type === 'WEBSOCKET_ERROR') {
      return {
        ...baseStyle,
        backgroundColor: '#ffebee',
        borderColor: '#f44336'
      };
    }

    return baseStyle;
  };

  const showRetryButton = error.retryable && onRetry;
  const showReconnectButton = error.type === 'WEBSOCKET_ERROR' && onReconnect;
  const showDismissButton = !persistent && onDismiss;

  return (
    <div
      style={getErrorStyle()}
      role='alert'
      aria-live='assertive'
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontSize: '16px',
              fontWeight: 600,
              color: '#d32f2f',
              marginBottom: '8px'
            }}
          >
            Error
          </div>
          <div
            style={{
              fontSize: '14px',
              color: '#333',
              marginBottom: '12px'
            }}
          >
            {error.userMessage || error.message}
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {showRetryButton && (
              <button
                onClick={onRetry}
                style={{
                  padding: '8px 16px',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: '#fff',
                  backgroundColor: '#2196f3',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
                aria-label='Retry action'
              >
                Retry
              </button>
            )}
            {showReconnectButton && (
              <button
                onClick={onReconnect}
                style={{
                  padding: '8px 16px',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: '#fff',
                  backgroundColor: '#4caf50',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
                aria-label='Reconnect'
              >
                Reconnect
              </button>
            )}
            {showDismissButton && (
              <button
                onClick={onDismiss}
                style={{
                  padding: '8px 16px',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: '#666',
                  backgroundColor: '#f5f5f5',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
                aria-label='Dismiss error'
              >
                Dismiss
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
