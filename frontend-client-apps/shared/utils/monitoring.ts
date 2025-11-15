/**
 * AWS CloudWatch RUM integration for real user monitoring
 */

export interface RUMConfig {
  applicationId: string;
  applicationVersion: string;
  region: string;
  identityPoolId: string;
  endpoint?: string;
  telemetries?: string[];
  allowCookies?: boolean;
  enableXRay?: boolean;
}

export interface CustomMetric {
  name: string;
  value: number;
  unit?: string;
  metadata?: Record<string, string | number>;
}

class RUMClient {
  private config: RUMConfig | null = null;
  private initialized: boolean = false;
  private rum: any = null;

  /**
   * Initialize CloudWatch RUM
   */
  async initialize(config: RUMConfig): Promise<void> {
    if (this.initialized) {
      console.warn('RUM already initialized');
      return;
    }

    this.config = config;

    try {
      // Dynamically import AWS RUM Web Client (optional dependency)
      const { AwsRum } = await import('aws-rum-web' as any);

      this.rum = new AwsRum(
        config.applicationId,
        config.applicationVersion,
        config.region,
        {
          sessionSampleRate: 1,
          identityPoolId: config.identityPoolId,
          endpoint: config.endpoint,
          telemetries: config.telemetries || ['performance', 'errors', 'http'],
          allowCookies: config.allowCookies !== false,
          enableXRay: config.enableXRay !== false
        }
      );

      this.initialized = true;
      console.log('CloudWatch RUM initialized');
    } catch (error) {
      console.error('Failed to initialize CloudWatch RUM:', error);
    }
  }

  /**
   * Record a custom metric
   */
  recordCustomMetric(metric: CustomMetric): void {
    if (!this.initialized || !this.rum) {
      console.warn('RUM not initialized, metric not recorded:', metric.name);
      return;
    }

    try {
      this.rum.recordEvent(metric.name, {
        value: metric.value,
        unit: metric.unit || 'None',
        ...metric.metadata
      });
    } catch (error) {
      console.error('Failed to record custom metric:', error);
    }
  }

  /**
   * Record an error
   */
  recordError(error: Error, metadata?: Record<string, any>): void {
    if (!this.initialized || !this.rum) {
      console.warn('RUM not initialized, error not recorded');
      return;
    }

    try {
      this.rum.recordError(error, metadata);
    } catch (err) {
      console.error('Failed to record error:', err);
    }
  }

  /**
   * Record a page view
   */
  recordPageView(pageName: string): void {
    if (!this.initialized || !this.rum) {
      console.warn('RUM not initialized, page view not recorded');
      return;
    }

    try {
      this.rum.recordPageView(pageName);
    } catch (error) {
      console.error('Failed to record page view:', error);
    }
  }

  /**
   * Add session attributes
   */
  addSessionAttributes(attributes: Record<string, string | number>): void {
    if (!this.initialized || !this.rum) {
      console.warn('RUM not initialized, attributes not added');
      return;
    }

    try {
      Object.entries(attributes).forEach(([key, value]) => {
        this.rum.addSessionAttribute(key, value);
      });
    } catch (error) {
      console.error('Failed to add session attributes:', error);
    }
  }
}

// Singleton instance
export const rumClient = new RUMClient();

/**
 * Performance monitoring utility
 */
export class PerformanceMonitor {
  /**
   * Record page load metrics
   */
  static recordPageLoad(): void {
    if (typeof window === 'undefined' || !window.performance) {
      return;
    }

    try {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      
      if (navigation) {
        rumClient.recordCustomMetric({
          name: 'PageLoadTime',
          value: navigation.loadEventEnd - navigation.fetchStart,
          unit: 'Milliseconds',
          metadata: {
            domContentLoaded: navigation.domContentLoadedEventEnd - navigation.fetchStart,
            domInteractive: navigation.domInteractive - navigation.fetchStart
          }
        });
      }
    } catch (error) {
      console.error('Failed to record page load metrics:', error);
    }
  }

  /**
   * Record audio latency
   */
  static recordAudioLatency(latencyMs: number, stage: string): void {
    rumClient.recordCustomMetric({
      name: 'AudioLatency',
      value: latencyMs,
      unit: 'Milliseconds',
      metadata: {
        stage
      }
    });
  }

  /**
   * Record session creation time
   */
  static recordSessionCreation(durationMs: number, success: boolean): void {
    rumClient.recordCustomMetric({
      name: 'SessionCreationTime',
      value: durationMs,
      unit: 'Milliseconds',
      metadata: {
        success: success ? 'true' : 'false'
      }
    });
  }

  /**
   * Record listener join time
   */
  static recordListenerJoin(durationMs: number, success: boolean): void {
    rumClient.recordCustomMetric({
      name: 'ListenerJoinTime',
      value: durationMs,
      unit: 'Milliseconds',
      metadata: {
        success: success ? 'true' : 'false'
      }
    });
  }

  /**
   * Record control response time
   */
  static recordControlResponse(action: string, durationMs: number): void {
    rumClient.recordCustomMetric({
      name: 'ControlResponseTime',
      value: durationMs,
      unit: 'Milliseconds',
      metadata: {
        action
      }
    });
  }

  /**
   * Record language switch duration
   */
  static recordLanguageSwitch(durationMs: number, success: boolean): void {
    rumClient.recordCustomMetric({
      name: 'LanguageSwitchTime',
      value: durationMs,
      unit: 'Milliseconds',
      metadata: {
        success: success ? 'true' : 'false'
      }
    });
  }

  /**
   * Record WebSocket connection metrics
   */
  static recordConnectionMetric(metric: 'connect' | 'disconnect' | 'reconnect', durationMs?: number): void {
    rumClient.recordCustomMetric({
      name: `WebSocket${metric.charAt(0).toUpperCase() + metric.slice(1)}`,
      value: durationMs || 0,
      unit: durationMs ? 'Milliseconds' : 'Count',
      metadata: {
        metric
      }
    });
  }
}
