/**
 * Controls Monitoring Utility
 * 
 * Provides comprehensive monitoring and logging for speaker-listener controls
 * Tracks latency, errors, state changes, and user interactions
 */

export interface ControlMetric {
  name: string;
  value: number;
  unit: string;
  timestamp: number;
  tags?: Record<string, string>;
}

export interface ControlEvent {
  type: 'control_action' | 'state_change' | 'error' | 'performance';
  operation: string;
  success: boolean;
  latency?: number;
  error?: string;
  metadata?: Record<string, any>;
  timestamp: number;
}

/**
 * Controls monitoring service
 */
export class ControlsMonitoring {
  private static instance: ControlsMonitoring;
  private metrics: ControlMetric[] = [];
  private events: ControlEvent[] = [];
  private readonly MAX_STORED_METRICS = 1000;
  private readonly MAX_STORED_EVENTS = 500;

  private constructor() {}

  static getInstance(): ControlsMonitoring {
    if (!ControlsMonitoring.instance) {
      ControlsMonitoring.instance = new ControlsMonitoring();
    }
    return ControlsMonitoring.instance;
  }

  /**
   * Log control operation latency
   */
  logControlLatency(operation: string, startTime: number, metadata?: Record<string, any>): void {
    const latency = Date.now() - startTime;
    
    // Log to console
    console.log(`[Controls] ${operation} latency: ${latency}ms`, metadata);
    
    // Warn if latency exceeds targets
    const target = this.getLatencyTarget(operation);
    if (latency > target) {
      console.warn(`[Controls] ${operation} latency exceeded target: ${latency}ms > ${target}ms`);
    }
    
    // Store metric
    this.recordMetric({
      name: `control.${operation}.latency`,
      value: latency,
      unit: 'ms',
      timestamp: Date.now(),
      tags: {
        operation,
        exceeded_target: (latency > target).toString(),
        ...metadata,
      },
    });
    
    // Store event
    this.recordEvent({
      type: 'performance',
      operation,
      success: latency <= target,
      latency,
      metadata,
      timestamp: Date.now(),
    });
    
    // Send to external monitoring if available
    this.sendToExternalMonitoring({
      name: `control.${operation}.latency`,
      value: latency,
      unit: 'ms',
      timestamp: Date.now(),
    });
  }

  /**
   * Log control action
   */
  logControlAction(
    operation: string,
    success: boolean,
    metadata?: Record<string, any>
  ): void {
    console.log(`[Controls] ${operation}: ${success ? 'success' : 'failed'}`, metadata);
    
    this.recordEvent({
      type: 'control_action',
      operation,
      success,
      metadata,
      timestamp: Date.now(),
    });
    
    // Track success rate
    this.recordMetric({
      name: `control.${operation}.success`,
      value: success ? 1 : 0,
      unit: 'boolean',
      timestamp: Date.now(),
      tags: { operation },
    });
  }

  /**
   * Log state change
   */
  logStateChange(
    stateType: 'speaker' | 'listener',
    oldState: any,
    newState: any,
    metadata?: Record<string, any>
  ): void {
    console.log(`[Controls] ${stateType} state change:`, {
      old: oldState,
      new: newState,
      ...metadata,
    });
    
    this.recordEvent({
      type: 'state_change',
      operation: `${stateType}_state_change`,
      success: true,
      metadata: {
        stateType,
        oldState,
        newState,
        ...metadata,
      },
      timestamp: Date.now(),
    });
  }

  /**
   * Log buffer overflow event
   */
  logBufferOverflow(
    bufferedDuration: number,
    maxDuration: number,
    metadata?: Record<string, any>
  ): void {
    console.warn('[Controls] Buffer overflow:', {
      bufferedDuration,
      maxDuration,
      ...metadata,
    });
    
    this.recordEvent({
      type: 'error',
      operation: 'buffer_overflow',
      success: false,
      metadata: {
        bufferedDuration,
        maxDuration,
        ...metadata,
      },
      timestamp: Date.now(),
    });
    
    this.recordMetric({
      name: 'control.buffer.overflow',
      value: 1,
      unit: 'count',
      timestamp: Date.now(),
      tags: {
        bufferedDuration: bufferedDuration.toString(),
        maxDuration: maxDuration.toString(),
      },
    });
  }

  /**
   * Log state sync failure
   */
  logStateSyncFailure(
    operation: string,
    error: Error,
    retryCount: number,
    metadata?: Record<string, any>
  ): void {
    console.error('[Controls] State sync failure:', {
      operation,
      error: error.message,
      retryCount,
      ...metadata,
    });
    
    this.recordEvent({
      type: 'error',
      operation: 'state_sync_failure',
      success: false,
      error: error.message,
      metadata: {
        operation,
        retryCount,
        ...metadata,
      },
      timestamp: Date.now(),
    });
    
    this.recordMetric({
      name: 'control.state_sync.failure',
      value: 1,
      unit: 'count',
      timestamp: Date.now(),
      tags: {
        operation,
        retryCount: retryCount.toString(),
      },
    });
  }

  /**
   * Log language switch
   */
  logLanguageSwitch(
    fromLanguage: string,
    toLanguage: string,
    duration: number,
    success: boolean,
    metadata?: Record<string, any>
  ): void {
    console.log('[Controls] Language switch:', {
      from: fromLanguage,
      to: toLanguage,
      duration,
      success,
      ...metadata,
    });
    
    this.recordEvent({
      type: 'control_action',
      operation: 'language_switch',
      success,
      latency: duration,
      metadata: {
        fromLanguage,
        toLanguage,
        ...metadata,
      },
      timestamp: Date.now(),
    });
    
    this.recordMetric({
      name: 'control.language_switch.duration',
      value: duration,
      unit: 'ms',
      timestamp: Date.now(),
      tags: {
        fromLanguage,
        toLanguage,
        success: success.toString(),
      },
    });
    
    // Warn if duration exceeds 500ms target
    if (duration > 500) {
      console.warn(`[Controls] Language switch exceeded target: ${duration}ms > 500ms`);
    }
  }

  /**
   * Log preference save/load
   */
  logPreferenceOperation(
    operation: 'save' | 'load',
    preferenceType: string,
    success: boolean,
    duration: number,
    metadata?: Record<string, any>
  ): void {
    console.log(`[Controls] Preference ${operation}:`, {
      type: preferenceType,
      success,
      duration,
      ...metadata,
    });
    
    this.recordEvent({
      type: 'control_action',
      operation: `preference_${operation}`,
      success,
      latency: duration,
      metadata: {
        preferenceType,
        ...metadata,
      },
      timestamp: Date.now(),
    });
    
    this.recordMetric({
      name: `control.preference.${operation}.duration`,
      value: duration,
      unit: 'ms',
      timestamp: Date.now(),
      tags: {
        preferenceType,
        success: success.toString(),
      },
    });
  }

  /**
   * Get metrics summary
   */
  getMetricsSummary(): {
    totalMetrics: number;
    totalEvents: number;
    recentMetrics: ControlMetric[];
    recentEvents: ControlEvent[];
    averageLatencies: Record<string, number>;
    successRates: Record<string, number>;
  } {
    const recentMetrics = this.metrics.slice(-50);
    const recentEvents = this.events.slice(-50);
    
    // Calculate average latencies
    const latencyMetrics = this.metrics.filter(m => m.name.includes('.latency'));
    const averageLatencies: Record<string, number> = {};
    
    const latencyGroups = latencyMetrics.reduce((acc, m) => {
      if (!acc[m.name]) acc[m.name] = [];
      acc[m.name].push(m.value);
      return acc;
    }, {} as Record<string, number[]>);
    
    Object.entries(latencyGroups).forEach(([name, values]) => {
      averageLatencies[name] = values.reduce((a, b) => a + b, 0) / values.length;
    });
    
    // Calculate success rates
    const successMetrics = this.metrics.filter(m => m.name.includes('.success'));
    const successRates: Record<string, number> = {};
    
    const successGroups = successMetrics.reduce((acc, m) => {
      const operation = m.tags?.operation || 'unknown';
      if (!acc[operation]) acc[operation] = [];
      acc[operation].push(m.value);
      return acc;
    }, {} as Record<string, number[]>);
    
    Object.entries(successGroups).forEach(([operation, values]) => {
      const successCount = values.filter(v => v === 1).length;
      successRates[operation] = (successCount / values.length) * 100;
    });
    
    return {
      totalMetrics: this.metrics.length,
      totalEvents: this.events.length,
      recentMetrics,
      recentEvents,
      averageLatencies,
      successRates,
    };
  }

  /**
   * Clear stored metrics and events
   */
  clear(): void {
    this.metrics = [];
    this.events = [];
  }

  /**
   * Get latency target for operation
   */
  private getLatencyTarget(operation: string): number {
    const targets: Record<string, number> = {
      pause: 100,
      resume: 100,
      mute: 50,
      unmute: 50,
      setVolume: 100,
      language_switch: 500,
      preference_load: 1000,
      preference_save: 1000,
    };
    
    return targets[operation] || 100;
  }

  /**
   * Record metric
   */
  private recordMetric(metric: ControlMetric): void {
    this.metrics.push(metric);
    
    // Trim if exceeds max
    if (this.metrics.length > this.MAX_STORED_METRICS) {
      this.metrics = this.metrics.slice(-this.MAX_STORED_METRICS);
    }
  }

  /**
   * Record event
   */
  private recordEvent(event: ControlEvent): void {
    this.events.push(event);
    
    // Trim if exceeds max
    if (this.events.length > this.MAX_STORED_EVENTS) {
      this.events = this.events.slice(-this.MAX_STORED_EVENTS);
    }
  }

  /**
   * Send to external monitoring service
   */
  private sendToExternalMonitoring(metric: ControlMetric): void {
    // Check if external monitoring is available (e.g., CloudWatch, DataDog)
    if (typeof window !== 'undefined' && (window as any).monitoring) {
      try {
        (window as any).monitoring.logMetric(metric);
      } catch (error) {
        console.error('[Controls] Failed to send metric to external monitoring:', error);
      }
    }
  }
}

// Export singleton instance
export const controlsMonitoring = ControlsMonitoring.getInstance();
