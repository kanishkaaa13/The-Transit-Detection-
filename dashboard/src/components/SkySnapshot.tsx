import { useState, useEffect } from 'react';
import { Star, Telescope } from 'lucide-react';
import { fetchStarChartImage, resolveStarCoords } from '@/services/astronomyApi';

interface SkySnapshotProps {
  ticId: string;
}

type SnapshotStatus = 'idle' | 'loading' | 'loaded' | 'error';

/**
 * SkySnapshot
 * Renders a small AstronomyAPI star-chart thumbnail for the given TIC star.
 * – Loading: animated skeleton
 * – Loaded: real image with attribution
 * – Error / no credentials: graceful placeholder icon, never throws
 */
export function SkySnapshot({ ticId }: SkySnapshotProps) {
  const [status, setStatus] = useState<SnapshotStatus>('idle');
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!ticId) return;

    let cancelled = false;
    setStatus('loading');
    setImageUrl(null);

    (async () => {
      // 1. Get RA/Dec from the catalog
      const coords = await resolveStarCoords(ticId);
      if (cancelled) return;

      if (!coords) {
        setStatus('error');
        return;
      }

      // 2. Fetch chart image via proxy
      const url = await fetchStarChartImage(ticId, coords.ra, coords.dec);
      if (cancelled) return;

      if (url) {
        setImageUrl(url);
        setStatus('loaded');
      } else {
        setStatus('error');
      }
    })();

    return () => { cancelled = true; };
  }, [ticId]);

  return (
    <div className="space-y-2 pt-3 border-t border-slate-800/40 animate-in fade-in duration-300">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <Star className="h-3.5 w-3.5 text-indigo-400" />
          Sky Snapshot
        </h4>
        {status === 'loading' && (
          <span className="text-[9px] text-indigo-400 animate-pulse font-mono">Generating…</span>
        )}
        {status === 'loaded' && (
          <span className="text-[9px] text-slate-600 font-mono">AstronomyAPI</span>
        )}
      </div>

      {/* Content area */}
      {status === 'idle' || status === 'loading' ? (
        /* Skeleton */
        <div className="w-full h-44 rounded-lg bg-slate-900/60 border border-slate-800/60 overflow-hidden relative">
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/0 via-indigo-950/20 to-slate-900/0 animate-[shimmer_1.8s_infinite] bg-[length:200%_100%]" />
          <div className="flex flex-col items-center justify-center h-full gap-2 opacity-30">
            <Star className="h-7 w-7 text-indigo-400" />
            <span className="text-[10px] text-slate-500">Loading star chart…</span>
          </div>
        </div>
      ) : status === 'loaded' && imageUrl ? (
        /* Real image */
        <div className="relative rounded-lg overflow-hidden border border-indigo-500/20 shadow-[0_0_20px_rgba(99,102,241,0.08)]">
          <img
            src={imageUrl}
            alt={`Star chart for TIC ${ticId}`}
            className="w-full h-auto object-cover block"
            style={{ maxHeight: '200px', objectPosition: 'center' }}
          />
          {/* Overlay gradient at bottom for attribution */}
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-[#020617]/90 to-transparent px-2.5 py-1.5">
            <p className="text-[9px] text-slate-500 font-mono">
              TIC {ticId} · RA/Dec centered · AstronomyAPI Star Chart
            </p>
          </div>
        </div>
      ) : (
        /* Fallback */
        <div className="w-full h-36 rounded-lg bg-slate-900/40 border border-slate-800/40 flex flex-col items-center justify-center gap-2 text-center px-4">
          <Telescope className="h-8 w-8 text-slate-700" />
          <p className="text-[10px] text-slate-600 leading-relaxed">
            Sky snapshot unavailable.
            <br />
            Set <code className="text-slate-500">ASTRONOMY_API_ID</code> &amp; <code className="text-slate-500">ASTRONOMY_API_SECRET</code> in <code className="text-slate-500">.env</code>.
          </p>
        </div>
      )}
    </div>
  );
}
