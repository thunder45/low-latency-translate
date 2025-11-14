/**
 * Accessibility utilities for ARIA labels and screen reader support
 */

export interface AriaButtonProps {
  label: string;
  pressed?: boolean;
  disabled?: boolean;
  describedBy?: string;
}

export function getAriaButtonProps(props: AriaButtonProps): Record<string, string | boolean> {
  const ariaProps: Record<string, string | boolean> = {
    'aria-label': props.label,
    role: 'button'
  };

  if (props.pressed !== undefined) {
    ariaProps['aria-pressed'] = props.pressed;
  }

  if (props.disabled) {
    ariaProps['aria-disabled'] = true;
  }

  if (props.describedBy) {
    ariaProps['aria-describedby'] = props.describedBy;
  }

  return ariaProps;
}

export interface AriaInputProps {
  label: string;
  required?: boolean;
  invalid?: boolean;
  describedBy?: string;
  errorMessage?: string;
}

export function getAriaInputProps(props: AriaInputProps): Record<string, string | boolean> {
  const ariaProps: Record<string, string | boolean> = {
    'aria-label': props.label
  };

  if (props.required) {
    ariaProps['aria-required'] = true;
  }

  if (props.invalid) {
    ariaProps['aria-invalid'] = true;
  }

  if (props.describedBy) {
    ariaProps['aria-describedby'] = props.describedBy;
  }

  return ariaProps;
}

export function announceToScreenReader(message: string): void {
  const announcement = document.createElement('div');
  announcement.setAttribute('role', 'status');
  announcement.setAttribute('aria-live', 'polite');
  announcement.setAttribute('aria-atomic', 'true');
  announcement.className = 'sr-only';
  announcement.textContent = message;
  
  document.body.appendChild(announcement);
  
  setTimeout(() => {
    document.body.removeChild(announcement);
  }, 1000);
}

export function createAriaLiveRegion(id: string, politeness: 'polite' | 'assertive' = 'polite'): HTMLDivElement {
  const region = document.createElement('div');
  region.id = id;
  region.setAttribute('role', 'status');
  region.setAttribute('aria-live', politeness);
  region.setAttribute('aria-atomic', 'true');
  region.className = 'sr-only';
  return region;
}
