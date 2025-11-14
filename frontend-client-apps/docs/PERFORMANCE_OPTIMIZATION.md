# Performance Optimization Guide

## Overview

This document outlines the performance optimization strategies implemented in the frontend client applications and provides guidance for maintaining optimal performance.

## Performance Targets

### Lighthouse Scores
- **Performance**: ≥90%
- **Accessibility**: ≥90%
- **Best Practices**: ≥90%
- **SEO**: ≥90%

### Core Web Vitals
- **LCP (Largest Contentful Paint)**: <2.5s
- **FID (First Input Delay)**: <100ms
- **CLS (Cumulative Layout Shift)**: <0.1
- **TTI (Time to Interactive)**: <3s

### Bundle Size
- **Total (gzipped)**: <500KB per app

## Implemented Optimizations

### 1. Code Splitting

**Manual Chunks** (Vite configuration):
```typescript
manualChunks: {
  'react-vendor': ['react', 'react-dom'],
  'auth-vendor': ['amazon-cognito-identity-js'], // Speaker only
  'state-vendor': ['zustand'],
}
```

**Benefits**:
- Separates vendor code from application code
- Enables better caching (vendor code changes less frequently)
- Reduces initial bundle size

### 2. Build Optimization

**Terser Minification**:
- Removes whitespace and comments
- Mangles variable names
- Removes dead code

**Tree Shaking**:
- Eliminates unused exports
- Reduces bundle size by 20-30%

**Target ES2020**:
- Modern JavaScript features
- Smaller polyfills
- Better browser performance

### 3. Asset Optimization

**Images**:
- Use WebP format with fallbacks
- Lazy load images below the fold
- Implement responsive images with srcset

**Fonts**:
- Use system fonts where possible
- Preload critical fonts
- Use font-display: swap

### 4. Runtime Optimizations

**React Performance**:
```typescript
// Memoization for expensive components
const MemoizedComponent = React.memo(Component);

// useMemo for expensive calculations
const expensiveValue = useMemo(() => computeExpensiveValue(a, b), [a, b]);

// useCallback for stable function references
const handleClick = useCallback(() => {
  doSomething(id);
}, [id]);
```

**Debouncing**:
```typescript
// Volume slider updates
const debouncedVolumeChange = debounce((value) => {
  setVolume(value);
}, 50);
```

**Audio Processing**:
- Process audio in Web Workers (future enhancement)
- Use AudioWorklet for better performance
- Implement efficient buffer management

### 5. Network Optimization

**WebSocket**:
- Binary message format for audio data
- Compression for text messages
- Connection pooling and reuse

**Caching**:
- Service Worker for offline support (future)
- LocalStorage for preferences
- Memory cache for frequently accessed data

### 6. Rendering Optimization

**Virtual Scrolling**:
- Implement for large lists (language selector)
- Render only visible items
- Reduces DOM nodes

**CSS Optimization**:
- Use CSS containment
- Minimize reflows and repaints
- Use transform and opacity for animations

## Performance Monitoring

### Running Audits

**Lighthouse Audit**:
```bash
cd frontend-client-apps
./scripts/performance-audit.sh
```

**Bundle Analysis**:
```bash
cd frontend-client-apps
./scripts/analyze-bundle.sh
```

### Continuous Monitoring

**CloudWatch RUM**:
- Tracks real user metrics
- Monitors Core Web Vitals
- Alerts on performance degradation

**Custom Metrics**:
```typescript
// Track custom performance metrics
PerformanceMonitor.recordCustomMetric('session_creation_time', duration);
PerformanceMonitor.recordAudioLatency(latency);
```

## Performance Checklist

### Before Deployment

- [ ] Run Lighthouse audit on both apps
- [ ] Verify all scores ≥90%
- [ ] Check Core Web Vitals meet targets
- [ ] Analyze bundle sizes (<500KB gzipped)
- [ ] Test on slow 3G network
- [ ] Test on low-end devices
- [ ] Verify no console errors or warnings

### During Development

- [ ] Use React DevTools Profiler
- [ ] Monitor bundle size changes
- [ ] Profile expensive operations
- [ ] Test with Chrome DevTools Performance tab
- [ ] Check for memory leaks

## Common Performance Issues

### Issue: Large Bundle Size

**Symptoms**:
- Bundle >500KB gzipped
- Slow initial load

**Solutions**:
1. Analyze bundle with visualizer
2. Identify large dependencies
3. Use dynamic imports for non-critical code
4. Remove unused dependencies

**Example**:
```typescript
// Before: Import everything
import { LargeLibrary } from 'large-library';

// After: Dynamic import
const LargeLibrary = lazy(() => import('large-library'));
```

### Issue: Slow Component Rendering

**Symptoms**:
- UI feels sluggish
- High CPU usage
- Dropped frames

**Solutions**:
1. Use React.memo for pure components
2. Implement useMemo for expensive calculations
3. Use useCallback for stable function references
4. Avoid inline object/array creation in render

**Example**:
```typescript
// Before: Creates new object on every render
<Component style={{ margin: 10 }} />

// After: Stable reference
const style = { margin: 10 };
<Component style={style} />
```

### Issue: Memory Leaks

**Symptoms**:
- Memory usage grows over time
- Browser becomes unresponsive
- Crashes after extended use

**Solutions**:
1. Clean up event listeners in useEffect
2. Cancel pending requests on unmount
3. Clear intervals and timeouts
4. Dispose of audio contexts

**Example**:
```typescript
useEffect(() => {
  const handler = () => { /* ... */ };
  window.addEventListener('resize', handler);
  
  // Cleanup
  return () => {
    window.removeEventListener('resize', handler);
  };
}, []);
```

### Issue: Poor Audio Performance

**Symptoms**:
- Audio stuttering or dropouts
- High latency
- Crackling sounds

**Solutions**:
1. Increase audio buffer size
2. Use AudioWorklet instead of ScriptProcessorNode
3. Optimize audio processing code
4. Reduce sample rate if acceptable

## Advanced Optimizations

### 1. Service Worker (Future)

```typescript
// Cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('v1').then((cache) => {
      return cache.addAll([
        '/',
        '/index.html',
        '/assets/main.js',
        '/assets/main.css',
      ]);
    })
  );
});
```

### 2. Web Workers for Audio Processing

```typescript
// Offload audio processing to worker
const audioWorker = new Worker('audio-processor.worker.js');
audioWorker.postMessage({ type: 'process', data: audioData });
```

### 3. HTTP/2 Server Push

```yaml
# CloudFront configuration
PushManifest:
  - /assets/main.js
  - /assets/main.css
  - /assets/vendor.js
```

### 4. Preloading Critical Resources

```html
<!-- Preload critical JavaScript -->
<link rel="preload" href="/assets/main.js" as="script">

<!-- Preload critical CSS -->
<link rel="preload" href="/assets/main.css" as="style">

<!-- Preconnect to API Gateway -->
<link rel="preconnect" href="wss://api.example.com">
```

## Performance Budget

### JavaScript Budget
- **Initial Bundle**: <200KB (gzipped)
- **Vendor Chunks**: <250KB (gzipped)
- **Total**: <500KB (gzipped)

### CSS Budget
- **Critical CSS**: <14KB (inline)
- **Total CSS**: <50KB (gzipped)

### Image Budget
- **Hero Images**: <100KB
- **Icons**: <10KB (use SVG)
- **Total Images**: <500KB

### Network Budget
- **Initial Load**: <1MB
- **Subsequent Loads**: <500KB

## Testing Performance

### Local Testing

```bash
# Build production bundle
npm run build

# Serve production build
npx serve -s dist

# Run Lighthouse
lighthouse http://localhost:3000 --view
```

### Network Throttling

```bash
# Chrome DevTools
# 1. Open DevTools (F12)
# 2. Go to Network tab
# 3. Select "Slow 3G" from throttling dropdown
# 4. Test application
```

### Device Emulation

```bash
# Chrome DevTools
# 1. Open DevTools (F12)
# 2. Toggle device toolbar (Ctrl+Shift+M)
# 3. Select device (e.g., iPhone 12, Pixel 5)
# 4. Test application
```

## Monitoring in Production

### CloudWatch RUM Configuration

```typescript
const rumConfig = {
  sessionSampleRate: 1.0,
  guestRoleArn: 'arn:aws:iam::ACCOUNT:role/RUM-Monitor',
  identityPoolId: 'us-east-1:POOL-ID',
  endpoint: 'https://dataplane.rum.us-east-1.amazonaws.com',
  telemetries: ['performance', 'errors', 'http'],
  allowCookies: true,
  enableXRay: true,
};
```

### Custom Dashboards

Create CloudWatch dashboards to monitor:
- Page load times (p50, p95, p99)
- Core Web Vitals
- Error rates
- API latency
- WebSocket connection stability

### Alerts

Set up alerts for:
- LCP >3s (warning), >5s (critical)
- FID >150ms (warning), >300ms (critical)
- CLS >0.15 (warning), >0.25 (critical)
- Error rate >1% (warning), >5% (critical)

## Resources

### Tools
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)
- [WebPageTest](https://www.webpagetest.org/)
- [Chrome DevTools](https://developers.google.com/web/tools/chrome-devtools)
- [React DevTools Profiler](https://reactjs.org/blog/2018/09/10/introducing-the-react-profiler.html)

### Documentation
- [Web Vitals](https://web.dev/vitals/)
- [Vite Performance](https://vitejs.dev/guide/performance.html)
- [React Performance](https://reactjs.org/docs/optimizing-performance.html)
- [MDN Performance](https://developer.mozilla.org/en-US/docs/Web/Performance)

### Best Practices
- [Google Web Fundamentals](https://developers.google.com/web/fundamentals/performance)
- [Smashing Magazine Performance](https://www.smashingmagazine.com/category/performance)
- [Web.dev Performance](https://web.dev/performance/)

## Conclusion

Performance optimization is an ongoing process. Regularly monitor metrics, run audits, and address issues as they arise. The tools and strategies outlined in this guide will help maintain optimal performance for the frontend client applications.
