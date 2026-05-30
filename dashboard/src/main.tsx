import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Umami web analytics (cookieless) — injected only when VITE_UMAMI_* are set
// (configured in dashboard/.env.production; unset in local dev so dev traffic
// isn't tracked). Loaded at runtime to keep the analytics host out of the
// public repo. Umami auto-tracks SPA route changes via the History API.
const umamiSrc = import.meta.env.VITE_UMAMI_SRC as string | undefined;
const umamiWebsiteId = import.meta.env.VITE_UMAMI_WEBSITE_ID as string | undefined;
if (umamiSrc && umamiWebsiteId) {
  const tag = document.createElement('script');
  tag.defer = true;
  tag.src = umamiSrc;
  tag.setAttribute('data-website-id', umamiWebsiteId);
  document.head.appendChild(tag);
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
