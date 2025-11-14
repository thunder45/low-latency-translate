/**
 * Browser support check result
 */
export interface BrowserSupportResult {
  supported: boolean;
  missingFeatures: string[];
}

/**
 * Browser support utility class
 * Checks for required browser features
 */
export class BrowserSupport {
  /**
   * Check WebSocket support
   * @returns True if WebSocket is supported
   */
  static checkWebSocketSupport(): boolean {
    return 'WebSocket' in window;
  }

  /**
   * Check Web Audio API support
   * @returns True if Web Audio API is supported
   */
  static checkWebAudioSupport(): boolean {
    return 'AudioContext' in window || 'webkitAudioContext' in window;
  }

  /**
   * Check MediaDevices API support (for microphone access)
   * @returns True if MediaDevices API is supported
   */
  static checkMediaDevicesSupport(): boolean {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  /**
   * Check localStorage support
   * @returns True if localStorage is supported and accessible
   */
  static checkLocalStorageSupport(): boolean {
    try {
      const testKey = '__storage_test__';
      localStorage.setItem(testKey, 'test');
      localStorage.removeItem(testKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Check all required features
   * @returns Support result with missing features list
   */
  static checkAllRequirements(): BrowserSupportResult {
    const missingFeatures: string[] = [];

    if (!this.checkWebSocketSupport()) {
      missingFeatures.push('WebSocket');
    }

    if (!this.checkWebAudioSupport()) {
      missingFeatures.push('Web Audio API');
    }

    if (!this.checkMediaDevicesSupport()) {
      missingFeatures.push('MediaDevices API (microphone access)');
    }

    if (!this.checkLocalStorageSupport()) {
      missingFeatures.push('localStorage');
    }

    return {
      supported: missingFeatures.length === 0,
      missingFeatures,
    };
  }

  /**
   * Get browser information
   * @returns Browser name and version
   */
  static getBrowserInfo(): { name: string; version: string } {
    const userAgent = navigator.userAgent;
    let name = 'Unknown';
    let version = 'Unknown';

    // Chrome
    if (userAgent.indexOf('Chrome') > -1 && userAgent.indexOf('Edg') === -1) {
      name = 'Chrome';
      const match = userAgent.match(/Chrome\/(\d+)/);
      if (match) version = match[1];
    }
    // Edge
    else if (userAgent.indexOf('Edg') > -1) {
      name = 'Edge';
      const match = userAgent.match(/Edg\/(\d+)/);
      if (match) version = match[1];
    }
    // Firefox
    else if (userAgent.indexOf('Firefox') > -1) {
      name = 'Firefox';
      const match = userAgent.match(/Firefox\/(\d+)/);
      if (match) version = match[1];
    }
    // Safari
    else if (userAgent.indexOf('Safari') > -1 && userAgent.indexOf('Chrome') === -1) {
      name = 'Safari';
      const match = userAgent.match(/Version\/(\d+)/);
      if (match) version = match[1];
    }

    return { name, version };
  }

  /**
   * Check if browser meets minimum version requirements
   * @returns True if browser meets requirements
   */
  static meetsMinimumVersion(): boolean {
    const { name, version } = this.getBrowserInfo();
    const versionNumber = parseInt(version, 10);

    // Minimum version requirements
    const minimumVersions: Record<string, number> = {
      Chrome: 90,
      Edge: 90,
      Firefox: 88,
      Safari: 14,
    };

    const minimumVersion = minimumVersions[name];
    if (!minimumVersion) {
      // Unknown browser, assume it's not supported
      return false;
    }

    return versionNumber >= minimumVersion;
  }

  /**
   * Get recommended browsers list
   * @returns Array of recommended browser strings
   */
  static getRecommendedBrowsers(): string[] {
    return [
      'Chrome 90 or later',
      'Firefox 88 or later',
      'Safari 14 or later',
      'Edge 90 or later',
    ];
  }

  /**
   * Get upgrade message for current browser
   * @returns Upgrade message or null if browser is supported
   */
  static getUpgradeMessage(): string | null {
    const { name, version } = this.getBrowserInfo();
    
    if (!this.meetsMinimumVersion()) {
      return `Your browser (${name} ${version}) is not supported. Please upgrade to one of the following: ${this.getRecommendedBrowsers().join(', ')}`;
    }

    const result = this.checkAllRequirements();
    if (!result.supported) {
      return `Your browser is missing required features: ${result.missingFeatures.join(', ')}. Please use a modern browser: ${this.getRecommendedBrowsers().join(', ')}`;
    }

    return null;
  }
}
