import { useEffect, useRef, useState } from 'react';
import { searchPlaces } from '../api/geo';

/** Text input with debounced place suggestions. Calls onSelect({lat, lng, label}). */
export default function PlaceSearch({ placeholder, value, onSelect }) {
  const [text, setText] = useState(value || '');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState('');
  const box = useRef(null);
  const typed = useRef(false);

  useEffect(() => {
    setText(value || '');
  }, [value]);

  useEffect(() => {
    if (!typed.current || text.trim().length < 3) {
      setResults([]);
      return undefined;
    }
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setStatus('Searching…');
      try {
        const rows = await searchPlaces(text.trim(), { signal: ctrl.signal });
        setResults(rows);
        setStatus(rows.length ? '' : 'No places found.');
      } catch (err) {
        if (err.name !== 'AbortError') setStatus('Search failed.');
      }
    }, 400);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [text]);

  useEffect(() => {
    const close = (e) => {
      if (box.current && !box.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  return (
    <div className="place-search" ref={box}>
      <input
        value={text}
        placeholder={placeholder}
        onChange={(e) => {
          typed.current = true;
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            if (results[0]) {
              onSelect(results[0]);
              setOpen(false);
            }
          }
        }}
      />
      {open && (results.length > 0 || status) && (
        <ul className="suggestions">
          {status && <li className="muted">{status}</li>}
          {results.map((r) => (
            <li key={`${r.lat},${r.lng}`}>
              <button
                type="button"
                onClick={() => {
                  typed.current = false;
                  onSelect(r);
                  setOpen(false);
                }}
              >
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
