/**
 * ClinNote AI — Entry Point
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Register service worker for PWA offline support
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/service-worker.js')
      .then((registration) => {
        console.log('[ClinNote] Service Worker registered:', registration.scope);
      })
      .catch((error) => {
        console.warn('[ClinNote] Service Worker registration failed:', error);
      });
  });
}

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Root element not found');

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
