import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { Alert, useApi } from './ui';

let gisPromise = null;
function loadGis() {
  if (window.google?.accounts?.id) return Promise.resolve();
  gisPromise ||= new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://accounts.google.com/gsi/client';
    s.async = true;
    s.onload = resolve;
    s.onerror = () => reject(new Error('Google sign-in failed to load'));
    document.head.appendChild(s);
  });
  return gisPromise;
}

/** "Continue with Google". Hidden when the server has no Google client ID configured. */
export default function GoogleButton({ role, text = 'continue_with', onSignedIn }) {
  const { data: meta } = useApi('/meta/');
  const { googleLogin } = useAuth();
  const ref = useRef(null);
  const [error, setError] = useState('');
  const clientId = meta?.google_client_id;
  const cb = useRef();
  cb.current = async (resp) => {
    setError('');
    try {
      onSignedIn(await googleLogin(resp.credential, role));
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    if (!clientId || !ref.current) return;
    let alive = true;
    loadGis().then(() => {
      if (!alive || !ref.current) return;
      window.google.accounts.id.initialize({ client_id: clientId, ux_mode: 'popup', callback: (r) => cb.current(r) });
      window.google.accounts.id.renderButton(ref.current, {
        theme: 'filled_black', size: 'large', shape: 'pill', text, width: Math.min(360, ref.current.offsetWidth || 320),
      });
    }).catch((e) => setError(e.message));
    return () => { alive = false; };
  }, [clientId, text]);

  if (!clientId) return null;
  return (
    <div className="google-signin">
      <div className="divider-or"><span>or</span></div>
      <div ref={ref} className="google-btn-slot" />
      <Alert>{error}</Alert>
    </div>
  );
}
