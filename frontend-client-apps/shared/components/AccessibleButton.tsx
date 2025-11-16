import React, { CSSProperties } from 'react';

interface AccessibleButtonProps {
  onClick: () => void;
  label: string;
  ariaLabel?: string;
  pressed?: boolean;
  ariaPressed?: boolean;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  icon?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export function AccessibleButton({
  onClick,
  label,
  ariaLabel,
  pressed,
  ariaPressed,
  disabled = false,
  variant = 'primary',
  icon,
  children,
  className
}: AccessibleButtonProps) {
  const [isFocused, setIsFocused] = React.useState(false);

  // Use ariaPressed if provided, otherwise fall back to pressed
  const isPressedState = ariaPressed !== undefined ? ariaPressed : pressed;

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
        backgroundColor: isPressedState ? '#1565c0' : '#1976d2',
        boxShadow: isPressedState ? 'inset 0 2px 4px rgba(0,0,0,0.2)' : '0 2px 4px rgba(0,0,0,0.1)'
      },
      secondary: {
        color: '#333',
        backgroundColor: isPressedState ? '#e0e0e0' : '#f5f5f5',
        border: '1px solid #ddd',
        boxShadow: isPressedState ? 'inset 0 2px 4px rgba(0,0,0,0.1)' : 'none'
      },
      danger: {
        color: '#fff',
        backgroundColor: isPressedState ? '#c62828' : '#d32f2f',
        boxShadow: isPressedState ? 'inset 0 2px 4px rgba(0,0,0,0.2)' : '0 2px 4px rgba(0,0,0,0.1)'
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

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel || label}
      aria-pressed={isPressedState !== undefined ? isPressedState : undefined}
      className={className}
      style={{
        ...getButtonStyle(),
        ...(isFocused ? focusStyle : {})
      }}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      onMouseEnter={(e) => {
        if (!disabled && !isPressedState) {
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
        if (!disabled && !isPressedState) {
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
