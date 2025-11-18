/**
 * Unit tests for LoginForm component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginForm } from '../LoginForm';

// Mock services
vi.mock('../../../../shared/services/CognitoAuthService', () => ({
  CognitoAuthService: vi.fn().mockImplementation(() => ({
    login: vi.fn(),
  })),
  AuthError: class AuthError extends Error {
    constructor(message: string, public userMessage: string, public code?: string) {
      super(message);
      this.name = 'AuthError';
    }
  },
}));

vi.mock('../../../../shared/services/TokenStorage', () => ({
  TokenStorage: vi.fn().mockImplementation(() => ({
    storeTokens: vi.fn(),
  })),
}));

vi.mock('../../../../shared/utils/config', () => ({
  getConfig: vi.fn(() => ({
    cognito: {
      userPoolId: 'test-pool',
      clientId: 'test-client',
    },
    awsRegion: 'us-east-1',
    encryptionKey: 'test-encryption-key-32-chars-min',
  })),
}));

describe('LoginForm', () => {
  const mockOnLoginSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render login form with username and password fields', () => {
    // Act
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);

    // Assert
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument();
  });

  it('should render title and subtitle', () => {
    // Act
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);

    // Assert
    expect(screen.getByText('Speaker Login')).toBeInTheDocument();
    expect(screen.getByText('Sign in to start broadcasting')).toBeInTheDocument();
  });

  it('should update username input value', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i) as HTMLInputElement;

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });

    // Assert
    expect(usernameInput.value).toBe('testuser');
  });

  it('should update password input value', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement;

    // Act
    fireEvent.change(passwordInput, { target: { value: 'testpassword' } });

    // Assert
    expect(passwordInput.value).toBe('testpassword');
  });

  it('should have password input type', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement;

    // Assert
    expect(passwordInput.type).toBe('password');
  });

  it('should disable login button when username is empty', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Assert
    expect(loginButton).toBeDisabled();
  });

  it('should disable login button when password is empty', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });

    // Assert
    expect(loginButton).toBeDisabled();
  });

  it('should enable login button when both fields are filled', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'testpassword' } });

    // Assert
    expect(loginButton).not.toBeDisabled();
  });

  it('should show loading state when submitting', async () => {
    // Arrange
    const { CognitoAuthService } = await import('../../../../shared/services/CognitoAuthService');
    const mockLogin = vi.fn().mockImplementation(() => new Promise(() => {})); // Never resolves
    (CognitoAuthService as any).mockImplementation(() => ({
      login: mockLogin,
    }));

    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'testpassword' } });
    fireEvent.click(loginButton);

    // Assert
    await waitFor(() => {
      expect(screen.getByText(/logging in/i)).toBeInTheDocument();
    });
  });

  it('should call onLoginSuccess after successful login', async () => {
    // Arrange
    const { CognitoAuthService } = await import('../../../../shared/services/CognitoAuthService');
    const mockLogin = vi.fn().mockResolvedValue({
      accessToken: 'mock-access',
      idToken: 'mock-id',
      refreshToken: 'mock-refresh',
      expiresIn: 3600,
    });
    (CognitoAuthService as any).mockImplementation(() => ({
      login: mockLogin,
    }));

    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'testpassword' } });
    fireEvent.click(loginButton);

    // Assert
    await waitFor(() => {
      expect(mockOnLoginSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it('should display error message on login failure', async () => {
    // Arrange
    const { CognitoAuthService, AuthError } = await import('../../../../shared/services/CognitoAuthService');
    const mockLogin = vi.fn().mockRejectedValue(
      new AuthError('Auth failed', 'Invalid username or password', 'INVALID_CREDENTIALS')
    );
    (CognitoAuthService as any).mockImplementation(() => ({
      login: mockLogin,
    }));

    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });
    fireEvent.click(loginButton);

    // Assert
    await waitFor(() => {
      expect(screen.getByText('Invalid username or password')).toBeInTheDocument();
    });
  });

  it('should clear password field after error', async () => {
    // Arrange
    const { CognitoAuthService, AuthError } = await import('../../../../shared/services/CognitoAuthService');
    const mockLogin = vi.fn().mockRejectedValue(
      new AuthError('Auth failed', 'Invalid username or password', 'INVALID_CREDENTIALS')
    );
    (CognitoAuthService as any).mockImplementation(() => ({
      login: mockLogin,
    }));

    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement;
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });
    fireEvent.click(loginButton);

    // Assert
    await waitFor(() => {
      expect(passwordInput.value).toBe('');
    });
  });

  it('should have proper accessibility attributes', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);

    // Assert
    expect(usernameInput).toHaveAttribute('aria-label', 'Username');
    expect(usernameInput).toHaveAttribute('aria-required', 'true');
    expect(passwordInput).toHaveAttribute('aria-label', 'Password');
    expect(passwordInput).toHaveAttribute('aria-required', 'true');
  });

  it('should have autocomplete attributes', () => {
    // Arrange
    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);

    // Assert
    expect(usernameInput).toHaveAttribute('autocomplete', 'username');
    expect(passwordInput).toHaveAttribute('autocomplete', 'current-password');
  });

  it('should display error with role="alert"', async () => {
    // Arrange
    const { CognitoAuthService, AuthError } = await import('../../../../shared/services/CognitoAuthService');
    const mockLogin = vi.fn().mockRejectedValue(
      new AuthError('Auth failed', 'Invalid username or password', 'INVALID_CREDENTIALS')
    );
    (CognitoAuthService as any).mockImplementation(() => ({
      login: mockLogin,
    }));

    render(<LoginForm onLoginSuccess={mockOnLoginSuccess} />);
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /log in/i });

    // Act
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });
    fireEvent.click(loginButton);

    // Assert
    await waitFor(() => {
      const errorElement = screen.getByRole('alert');
      expect(errorElement).toBeInTheDocument();
      expect(errorElement).toHaveAttribute('aria-live', 'polite');
    });
  });
});
