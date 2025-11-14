import React from 'react';
import { ConnectionState } from '../websocket/WebSocketClient';

interface ConnectionStatusProps {
  connectionState: ConnectionState;
  reconnectAttempt?: number;
  maxReconnectAttempts?: number;
  onRetry?: () => void;
}

export function ConnectionStatus({
  connectionState,
  reconnectAttempt = 0,
  maxReconnectAttempts = 5,
  onRetry
}: ConnectionStatusProps) {
  const getStatusColor = (): string => {
    switch (connectionState) {
      case 'connected':
        return '#4caf50'; // Green
      case 'connecting':
      case 'reconnecting':
        return '#ff9800'; // Orange
      case 'disconnected':
        return '#ffc107'; // Yellow
      case 'failed':
        return '#f44336'; // Red
      default:
        return '#9e9e9e'; // Gray
    }
  };

  const getStatusText = (): string => {
    switch (connectionState) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'reconnecting':
        return `Reconnecting (${reconnectAttempt}/${maxReconnectAttempts})...`;
      case 'disconnected':
        return 'Disconnected';
      case 'failed':
        return 'Connection Failed';
      default:
        return 'Unknown';
    }
  };

  const showRetryButton = connectionState === 'failed' && onRetry;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '8px 16px',
        backgroundColor: '#f5f5f5',
        borderRadius: '4px',
        border: `2px solid ${getStatusColor()}`
      }}
      role='status'
      aria-live='polite'
    >
      <div
        style={{
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          backgroundColor: getStatusColor(),
          flexShrink: 0
        }}
        aria-hidden='true'
      />
      <span
        style={{
          fontSize: '14px',
          fontWeight: 500,
          color: '#333'
        }}
      >
        {getStatusText()}
      </span>
      {showRetryButton && (
        <button
          onClick={onRetry}
          style={{
            marginLeft: 'auto',
            padding: '6px 12px',
            fontSize: '14px',
            fontWeight: 500,
            color: '#fff',
            backgroundColor: '#2196f3',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#1976d2';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#2196f3';
          }}
          aria-label='Retry connection'
        >
          Retry Now
        </button>
      )}
    </div>
  );
}
