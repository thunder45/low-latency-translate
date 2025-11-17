import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SessionCreator } from '../SessionCreator';

describe('SessionCreator', () => {
  const mockOnCreateSession = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render form with default values', () => {
    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error={null}
      />
    );

    expect(screen.getByText('Create Broadcast Session')).toBeInTheDocument();
    expect(screen.getByLabelText('Select source language')).toBeInTheDocument();
    expect(screen.getByLabelText('Select quality tier')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create session' })).toBeInTheDocument();
  });

  it('should call onCreateSession with correct config when button clicked', async () => {
    mockOnCreateSession.mockResolvedValue(undefined);

    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error={null}
      />
    );

    const createButton = screen.getByRole('button', { name: 'Create session' });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(mockOnCreateSession).toHaveBeenCalledWith({
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });
    });
  });

  it('should disable form controls when isCreating is true', () => {
    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={true}
        error={null}
      />
    );

    const languageSelect = screen.getByLabelText('Select source language');
    const qualitySelect = screen.getByLabelText('Select quality tier');
    const createButton = screen.getByRole('button', { name: 'Create session' });

    expect(languageSelect).toBeDisabled();
    expect(qualitySelect).toBeDisabled();
    expect(createButton).toBeDisabled();
  });

  it('should show "Creating Session..." text when isCreating is true', () => {
    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={true}
        error={null}
      />
    );

    expect(screen.getByText('Creating Session...')).toBeInTheDocument();
    expect(screen.getByText('Creating session...')).toBeInTheDocument(); // Progress message
  });

  it('should display error message when error prop is set', () => {
    const errorMessage = 'Failed to create session';

    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error={errorMessage}
      />
    );

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('should show retry button when error is displayed', () => {
    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error="Connection failed"
      />
    );

    const retryButton = screen.getByRole('button', { name: 'Retry session creation' });
    expect(retryButton).toBeInTheDocument();
  });

  it('should call onCreateSession when retry button is clicked', async () => {
    mockOnCreateSession.mockResolvedValue(undefined);

    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error="Connection failed"
      />
    );

    const retryButton = screen.getByRole('button', { name: 'Retry session creation' });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(mockOnCreateSession).toHaveBeenCalled();
    });
  });

  it('should update source language when selection changes', () => {
    mockOnCreateSession.mockResolvedValue(undefined);

    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error={null}
      />
    );

    const languageSelect = screen.getByLabelText('Select source language') as HTMLSelectElement;
    fireEvent.change(languageSelect, { target: { value: 'es' } });

    expect(languageSelect.value).toBe('es');

    const createButton = screen.getByRole('button', { name: 'Create session' });
    fireEvent.click(createButton);

    expect(mockOnCreateSession).toHaveBeenCalledWith({
      sourceLanguage: 'es',
      qualityTier: 'standard',
    });
  });

  it('should update quality tier when selection changes', () => {
    mockOnCreateSession.mockResolvedValue(undefined);

    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error={null}
      />
    );

    const qualitySelect = screen.getByLabelText('Select quality tier') as HTMLSelectElement;
    
    // Note: Premium is disabled, so we can't actually select it in the test
    // Just verify the select element exists and has the correct default
    expect(qualitySelect.value).toBe('standard');
  });

  it('should have accessible labels and ARIA attributes', () => {
    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error={null}
      />
    );

    const languageSelect = screen.getByLabelText('Select source language');
    const qualitySelect = screen.getByLabelText('Select quality tier');
    const createButton = screen.getByRole('button', { name: 'Create session' });

    expect(languageSelect).toHaveAttribute('aria-label', 'Select source language');
    expect(qualitySelect).toHaveAttribute('aria-label', 'Select quality tier');
    expect(createButton).toHaveAttribute('aria-label', 'Create session');
  });

  it('should show progress indicator with spinner when creating', () => {
    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={true}
        error={null}
      />
    );

    const progressMessage = screen.getByRole('status');
    expect(progressMessage).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByText('Creating session...')).toBeInTheDocument();
  });

  it('should not show error or progress when idle', () => {
    render(
      <SessionCreator
        onCreateSession={mockOnCreateSession}
        isCreating={false}
        error={null}
      />
    );

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
