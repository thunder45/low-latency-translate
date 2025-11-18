import React from 'react';
import ReactDOM from 'react-dom/client';
import { SpeakerApp } from './components/SpeakerApp';
import { TokenStorage } from '../../shared/services/TokenStorage';
import { getConfig } from '../../shared/utils/config';
import './index.css';

/**
 * Initialize TokenStorage singleton before app renders
 * This ensures encryption key is derived once and cached
 */
async function initializeApp() {
  try {
    const config = getConfig();
    const tokenStorage = TokenStorage.getInstance();
    await tokenStorage.initialize(config.encryptionKey);
    console.log('[App] TokenStorage initialized');
  } catch (error) {
    console.error('[App] Failed to initialize TokenStorage:', error);
    // Still render app, components will handle initialization if needed
  }
}

// Initialize before rendering
initializeApp().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <SpeakerApp />
    </React.StrictMode>
  );
}).catch(error => {
  console.error('[App] Initialization failed:', error);
  // Render error state or fallback
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <div style={{ padding: '20px', color: 'red' }}>
        <h1>Initialization Error</h1>
        <p>Failed to initialize application. Please refresh the page.</p>
      </div>
    </React.StrictMode>
  );
});
