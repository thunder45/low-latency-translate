import React, { CSSProperties } from 'react';

interface AccessibleButtonProps {
  onClick: () => void;
  label: string;
  ariaLabel?: string;
  pressed?: boolean;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

export function AccessibleButton({
  onClick,
  label,
  ariaLabel,
  pressed,
  disabled = false,
  variant = 'primary',
  icon,
  children
}: AccessibleButtonProps) {
  const getButtonStyle = (): CSSProperties => {
    const baseStyle: CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
      padding: '10px 20px',
      fontSize: '16px',
      fontWeight: 500,
      border: 'none',
      borderRadius: '4px',
      cursor: disabled ? 'not-allowed' : 'pointer',
      transition: 'all 0.2s',
      opacity: disabled ? 0.6 : 1,
      outline: 'none',
      position: 'relative'
    };

    const variants = {
      primary: {
        color: '#fff',
        backgroundColor: pressed ? '#1565c0' : '#1976d2',
        boxShadow: pressed ? 'inset 0 2px 4px rgba(0,0,0,0.2)' : '0 2px 4px rgba(0,0,0,0.1)'
      },
      secondary: {
        color: '#333',
        backgroundColor: pressed ? '#e0e0e0' : '#f5f5f5',
        border: '1px solid #ddd',
        boxShadow: pressed ? 'inset 0 2px 4px rgba(0,0,0,0.1)' : 'none'
      },
      danger: {
        color: '#fff',
        backgroundColor: pressed ? '#c62828' : '#d32f2f',
        boxShadow: pressed ? 'inset 0 2px 4px rgba(0,0,0,0.2)' : '0 2px 4px rgba(0,0,0,0.1)'
      }
    };

    return {
      ...baseStyle,
      ...variants[variant]
    };
  };

  const focusStyle: CSSProperties = {
    outline: '3px solid #2196f3',
    outlineOffset: '2px'
  };

  const [isFocused, setIsFocused] = React.useState(false);

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel || label}
      aria-pressed={pressed !== undefined ? pressed : undefined}
      style={{
        ...getButtonStyle(),
        ...(isFocused ? focusStyle : {})
      }}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      onMouseEnter={(e) => {
        if (!disabled && !pressed) {
          const target = e.currentTarget;
          if (variant === 'primary') {
            target.style.backgroundColor = '#1565c0';
          } else if (variant === 'secondary') {
            target.style.backgroundColor = '#e0e0e0';
          } else if (variant === 'danger') {
            target.style.backgroundColor = '#c62828';
          }
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled && !pressed) {
          const target = e.currentTarget;
          if (variant === 'primary') {
            target.style.backgroundColor = '#1976d2';
          } else if (variant === 'secondary') {
            target.style.backgroundColor = '#f5f5f5';
          } else if (variant === 'danger') {
            target.style.backgroundColor = '#d32f2f';
          }
        }
      }}
    >
      {icon && <span aria-hidden='true'>{icon}</span>}
      {children || label}
    </button>
  );
}
