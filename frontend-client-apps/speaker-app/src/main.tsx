import React from 'react';
import ReactDOM from 'react-dom/client';
import { SpeakerApp } from './components/SpeakerApp';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <SpeakerApp />
  </React.StrictMode>
);
