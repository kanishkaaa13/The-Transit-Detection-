import { useState, useEffect, useRef } from 'react';
import { 
  ResponsiveContainer, 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis,
  CartesianGrid
} from 'recharts';
import { 
  Compass, 
  Filter, 
  Search, 
  Orbit,
  Star,
  ChevronRight,
  AlertTriangle,
  RotateCcw
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SkySnapshot } from '@/components/SkySnapshot';

interface SkyStar {
  id: string;
  ra: number;
  dec: number;
  classification: 'Exoplanet' | 'Binary Star' | 'Stellar Blend' | 'Starspot';
  confidence: number;
}

interface SkyMapProps {
  onSelectStar: (ticId: string) => void;
}

export function SkyMap({ onSelectStar }: SkyMapProps) {
  const [stars, setStars] = useState<SkyStar[]>([]);
  const [filteredStars, setFilteredStars] = useState<SkyStar[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [starLoadError, setStarLoadError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  
  // Interactive Sky Map enhancements
  const [raDomain, setRaDomain] = useState<[number, number]>([0, 360]);
  const [decDomain, setDecDomain] = useState<[number, number]>([-90, -80]);
  const [scaleBySize, setScaleBySize] = useState<boolean>(false);
  const [selectedPopoverStar, setSelectedPopoverStar] = useState<SkyStar | null>(null);

  // Center coordinate state & zoom level (1 = widest to 6 = narrowest, default 2 for wider initial view)
  const [centerRa, setCenterRa] = useState<number>(0);
  const [centerDec, setCenterDec] = useState<number>(-87);
  const [zoom, setZoom] = useState<number>(2);

  // Mouse drag panning and scroll zoom states & refs
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const startCenter = useRef({ ra: 0, dec: 0 });
  const mapContainerRef = useRef<HTMLDivElement | null>(null);

  // Colors mapping for classifications
  const colors = {
    'Exoplanet': '#10b981', // green
    'Binary Star': '#f97316', // orange
    'Stellar Blend': '#64748b', // gray
    'Starspot': '#0284c7' // blue
  };

  const badgeColors = {
    'Exoplanet': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    'Binary Star': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    'Stellar Blend': 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    'Starspot': 'bg-sky-500/10 text-sky-400 border-sky-500/20'
  };

  // Fetch stars coordinates and classifications on mount
  useEffect(() => {
    setLoading(true);
    setStarLoadError(null);
    fetch('/api/sky-map-stars')
      .then(res => {
        if (!res.ok) throw new Error(`Sky catalog unavailable (HTTP ${res.status})`);
        return res.json();
      })
      .then((data: SkyStar[]) => {
        setStars(data);
        setFilteredStars(data);
      })
      .catch((err: Error) => {
        console.error('SkyMap: star catalog fetch failed:', err);
        setStarLoadError(err.message ?? 'Failed to load the star catalog. Check your connection and reload.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // Filter Target List sidebar only
  useEffect(() => {
    let result = stars;

    if (searchQuery.trim()) {
      result = result.filter(s => s.id.includes(searchQuery.trim()));
    }

    if (typeFilter !== 'all') {
      result = result.filter(s => s.classification === typeFilter);
    }

    setFilteredStars(result);
  }, [searchQuery, typeFilter, stars]);

  // FOV mapping in degrees corresponding to each AstronomyAPI zoom level (1 to 6)
  const zoomLevels: Record<number, { fov: number }> = {
    1: { fov: 40 },
    2: { fov: 20 },
    3: { fov: 10 },
    4: { fov: 5 },
    5: { fov: 2.5 },
    6: { fov: 1.25 }
  };

  // Recalculate X (RA) and Y (Dec) domains of Recharts to align precisely with the AstronomyAPI field boundaries
  useEffect(() => {
    const level = zoomLevels[zoom] || zoomLevels[4];
    const fov = level.fov;

    // Declination (Dec) bounds
    const halfDec = fov / 2;
    let minDec = centerDec - halfDec;
    let maxDec = centerDec + halfDec;
    
    // Clamp to valid Dec bounds (-90 to -80 degrees)
    if (minDec < -90) {
      minDec = -90;
      maxDec = -90 + fov;
    }
    if (maxDec > -80) {
      maxDec = -80;
      minDec = -80 - fov;
    }
    setDecDomain([minDec, maxDec]);

    // Right Ascension (RA) bounds
    // cos(dec) factors in the convergence of RA lines near the celestial pole
    const cosDec = Math.cos((centerDec * Math.PI) / 180);
    const raSpan = Math.min(360, fov / (cosDec > 0.01 ? cosDec : 0.01));
    const halfRa = raSpan / 2;
    let minRa = centerRa - halfRa;
    let maxRa = centerRa + halfRa;

    if (minRa < 0) {
      minRa = 0;
      maxRa = raSpan;
    }
    if (maxRa > 360) {
      maxRa = 360;
      minRa = 360 - raSpan;
    }
    setRaDomain([minRa, maxRa]);
  }, [centerRa, centerDec, zoom]);

  // Ref for smooth-scrolling the sidebar to the selected star
  const selectedItemRef = useRef<HTMLDivElement | null>(null);
  const listContainerRef = useRef<HTMLDivElement | null>(null);

  // Align map center to highlighted search targets or manually navigated stars
  useEffect(() => {
    if (selectedPopoverStar) {
      setCenterRa(selectedPopoverStar.ra);
      setCenterDec(selectedPopoverStar.dec);
      // Smooth-scroll sidebar to the selected item
      if (selectedItemRef.current && listContainerRef.current) {
        selectedItemRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [selectedPopoverStar]);

  // Native mouse wheel listener on mapContainerRef to zoom in/out cleanly and prevent default page scroll
  useEffect(() => {
    const element = mapContainerRef.current;
    if (!element) return;

    const handleNativeWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.deltaY < 0) {
        // scroll up: zoom in
        setZoom(prev => Math.min(6, prev + 1));
      } else {
        // scroll down: zoom out
        setZoom(prev => Math.max(1, prev - 1));
      }
    };

    element.addEventListener('wheel', handleNativeWheel, { passive: false });
    return () => {
      element.removeEventListener('wheel', handleNativeWheel);
    };
  }, [zoom]);

  // Click-drag panning handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
    startCenter.current = { ra: centerRa, dec: centerDec };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const W = rect.width || 1;
    const H = rect.height || 1;

    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;

    const level = zoomLevels[zoom] || zoomLevels[2];
    const fov = level.fov;
    const cosDec = Math.cos((centerDec * Math.PI) / 180);
    const raSpan = Math.min(360, fov / (cosDec > 0.01 ? cosDec : 0.01));

    // RA mapping: drag right shifts map left (reducing RA), drag left shifts map right (increasing RA)
    let newRa = startCenter.current.ra - (dx / W) * raSpan;
    if (newRa < 0) newRa = 0;
    if (newRa > 360) newRa = 360;

    // Dec mapping: drag down shifts map north (increasing Dec), drag up shifts map south (decreasing Dec)
    let newDec = startCenter.current.dec + (dy / H) * fov;
    if (newDec < -90) newDec = -90;
    if (newDec > -80) newDec = -80;

    setCenterRa(newRa);
    setCenterDec(newDec);
  };

  const handleMouseUpOrLeave = () => {
    setIsDragging(false);
  };

  // Popover details navigation click
  const handleInspectNavigate = () => {
    if (selectedPopoverStar) {
      onSelectStar(selectedPopoverStar.id);
    }
  };

  // Custom Dot shape mapping highlight opacity and toggled confidence scale sizes
  const renderCustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    if (cx === undefined || cy === undefined) return null;

    const isHighlighted = searchQuery ? payload.id.includes(searchQuery) : false;
    const isSelected = selectedPopoverStar ? payload.id === selectedPopoverStar.id : false;

    // Radius logic
    let r = 5.5;
    if (scaleBySize) {
      r = payload.confidence * 8.5 + 3; // maps 0.5-1.0 to size 7.25-11.5
    }

    if (isHighlighted || isSelected) {
      r = r + 4.5;
    }

    const fill = colors[payload.classification as 'Exoplanet' | 'Binary Star' | 'Stellar Blend' | 'Starspot'] || '#94a3b8';
    const stroke = isHighlighted ? '#ffffff' : isSelected ? '#a5b4fc' : 'rgba(255, 255, 255, 0.15)';
    const strokeWidth = isHighlighted ? 2.5 : isSelected ? 2.0 : 0.5;
    
    // Dim out non-matched coordinates if filters exist
    let opacity = 1.0;
    if (searchQuery && !isHighlighted) {
      opacity = 0.15;
    } else if (typeFilter !== 'all' && payload.classification !== typeFilter) {
      opacity = 0.15;
    }

    return (
      <circle 
        cx={cx} 
        cy={cy} 
        r={r} 
        fill={fill} 
        stroke={stroke} 
        strokeWidth={strokeWidth}
        opacity={opacity}
        className="transition-all duration-300 hover:scale-150 hover:stroke-white cursor-pointer"
        onClick={() => setSelectedPopoverStar(payload)}
      />
    );
  };

  return (
    <div className="space-y-6">
      {/* ---------------------------------------------------------
          Interactive Map Header & Filter Controls
          --------------------------------------------------------- */}
      <Card className="bg-[#0f172a]/40 border-slate-800 glow-purple backdrop-blur-md">
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
                <Compass className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <h3 className="text-md font-bold text-slate-200">Southern Polar Sky Map</h3>
                <p className="text-xs text-slate-400">Celestial coordinates of targeted dwarf stars. Highlight stars dynamically.</p>
              </div>
            </div>

            {/* Center Position Display */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1.5 text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2.5 py-1 rounded-full font-mono">
                CENTER RA: {centerRa.toFixed(1)}°
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2.5 py-1 rounded-full font-mono">
                CENTER DEC: {centerDec.toFixed(1)}°
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2.5 py-1 rounded-full font-mono">
                ZOOM: {zoom}x
              </span>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
              {/* Highlight Target search bar */}
              <div className="relative flex-1 sm:w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
                <Input
                  type="text"
                  placeholder="Highlight Target (TIC ID)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value.replace(/\D/g, ''))}
                  className="pl-8 bg-[#020617]/50 border-slate-700 text-indigo-100 placeholder:text-slate-500 text-xs h-9"
                />
              </div>

              {/* Classification filter */}
              <div className="relative w-full sm:w-48">
                <Filter className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="w-full h-9 pl-8 pr-3 rounded-md bg-[#020617]/50 border border-slate-700 text-slate-330 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
                >
                  <option value="all">All Classifications</option>
                  <option value="Exoplanet">Exoplanets</option>
                  <option value="Binary Star">Binary Stars</option>
                  <option value="Stellar Blend">Stellar Blends</option>
                  <option value="Starspot">Starspots</option>
                </select>
              </div>
            </div>
          </div>

        </CardContent>
      </Card>

      {/* ---------------------------------------------------------
          Main Sky Map Layout
          --------------------------------------------------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Celestial Scatter Chart (3 cols) */}
        <Card className="lg:col-span-3 bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md min-h-[520px] flex flex-col relative overflow-hidden">
          <CardHeader className="pb-2">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div>
                <CardTitle className="text-md font-semibold text-slate-200 flex items-center gap-2">
                  <Orbit className="h-4.5 w-4.5 text-indigo-400" />
                  Stellar Field Distribution
                </CardTitle>
                <CardDescription className="text-slate-400 text-xs">
                  Declination (Dec) vs. Right Ascension (RA) mapping. Selected stars highlight white.
                </CardDescription>
              </div>

              {/* Point size scale toggle */}
              <div className="flex items-center gap-2 bg-[#020617]/40 px-3 py-1.5 rounded-lg border border-slate-800 text-xs">
                <span className="text-slate-400">Scale by Confidence</span>
                <input 
                  type="checkbox"
                  checked={scaleBySize}
                  onChange={(e) => setScaleBySize(e.target.checked)}
                  className="w-3.5 h-3.5 accent-indigo-500 cursor-pointer rounded"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-between p-6 relative">
            {/* Star catalog load error banner */}
            {starLoadError && (
              <div className="mb-4 flex items-start gap-3 p-3 bg-rose-950/30 border border-rose-500/25 rounded-lg text-xs">
                <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-rose-300 font-semibold">Catalog load failed</p>
                  <p className="text-rose-400/70 mt-0.5">{starLoadError}</p>
                </div>
              </div>
            )}
            {loading ? (
              // Scatter-plot skeleton — dots at varied positions + shimmer overlay
              <div className="h-[400px] w-full mt-2 bg-[#060c1a]/60 rounded-md border border-slate-800/30 relative overflow-hidden">
                {/* Shimmer sweep */}
                <div className="absolute inset-0 skeleton opacity-50" />
                {/* Fake scatter dots — mimic distribution of real chart */}
                {[
                  { x: 18, y: 30 }, { x: 32, y: 62 }, { x: 47, y: 44 },
                  { x: 58, y: 75 }, { x: 71, y: 28 }, { x: 83, y: 55 },
                  { x: 25, y: 85 }, { x: 65, y: 18 }, { x: 42, y: 58 },
                  { x: 78, y: 40 }, { x: 52, y: 90 }, { x: 12, y: 50 },
                  { x: 90, y: 70 }, { x: 36, y: 35 }, { x: 62, y: 82 }
                ].map((pos, i) => (
                  <div
                    key={i}
                    className="absolute rounded-full bg-indigo-400/20 skeleton"
                    style={{
                      left: `${pos.x}%`,
                      top: `${pos.y}%`,
                      width: i % 3 === 0 ? '10px' : '7px',
                      height: i % 3 === 0 ? '10px' : '7px',
                      transform: 'translate(-50%, -50%)',
                      animationDelay: `${i * 0.12}s`,
                    }}
                  />
                ))}
                <div className="absolute inset-0 flex items-center justify-center">
                  <Orbit className="h-8 w-8 text-indigo-500/15 animate-spin" style={{ animationDuration: '5s' }} />
                </div>
              </div>
            ) : (
              <div className="relative w-full flex-1 flex flex-col justify-between select-none">
                
                {/* Floating Inspector Popover (bottom-left) */}
                {selectedPopoverStar && (
                  <div className="absolute bottom-4 left-4 z-30 w-60 bg-[#020617]/95 border border-slate-850 p-3.5 rounded-lg shadow-2xl space-y-2.5 backdrop-blur-md animate-in slide-in-from-bottom-2 duration-300">
                    <div className="flex justify-between items-start">
                      <div className="flex flex-col">
                        <span className="text-[10px] text-slate-500 font-semibold font-mono">SELECTED STAR</span>
                        <strong className="text-sm text-slate-100 font-mono">TIC {selectedPopoverStar.id}</strong>
                      </div>
                      <Badge variant="outline" className={`text-[9px] font-semibold ${badgeColors[selectedPopoverStar.classification]}`}>
                        {selectedPopoverStar.classification}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400 border-t border-slate-900 pt-2">
                      <div>
                        <span className="text-slate-600 block">Confidence</span>
                        <strong className="text-indigo-300 font-bold">{(selectedPopoverStar.confidence * 100).toFixed(1)}%</strong>
                      </div>
                      <div>
                        <span className="text-slate-600 block">Mock Period</span>
                        <strong className="text-slate-300">
                          {((Number(selectedPopoverStar.id) % 15) + 1.25).toFixed(3)} d
                        </strong>
                      </div>
                    </div>
                    <Button 
                      onClick={handleInspectNavigate} 
                      className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-[10px] h-8 shadow-md cursor-pointer"
                    >
                      Inspect Telemetry Detail
                      <ChevronRight className="h-3 w-3 ml-1 shrink-0" />
                    </Button>
                  </div>
                )}

                {/* Recharts Scatter chart viewport with starry background, mouse handlers, and coordinate grid lines */}
                <div
                  ref={mapContainerRef}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUpOrLeave}
                  onMouseLeave={handleMouseUpOrLeave}
                  className="h-[400px] w-full mt-2 relative rounded-md overflow-hidden bg-[#060c1a]/60 border border-slate-800/30"
                  style={{
                    cursor: isDragging ? 'grabbing' : 'grab',
                  }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart
                      margin={{ top: 25, right: 25, bottom: 25, left: 25 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.05)" />
                      <XAxis 
                        type="number" 
                        dataKey="ra" 
                        domain={raDomain}
                        allowDataOverflow={true}
                        stroke="rgba(148, 163, 184, 0.3)"
                        fontSize={9}
                        tickFormatter={(val) => `${val.toFixed(0)}° RA`}
                      />
                      <YAxis 
                        type="number" 
                        dataKey="dec" 
                        domain={decDomain}
                        allowDataOverflow={true}
                        stroke="rgba(148, 163, 184, 0.3)"
                        fontSize={9}
                        tickFormatter={(val) => `${val.toFixed(0)}° Dec`}
                      />
                      <Scatter 
                        name="Stellar Coordinates" 
                        data={stars} 
                        shape={renderCustomDot}
                      />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

          {/* Target list sidebar with scroll shadows */}
          <Card className="bg-[#0f172a]/20 border-slate-850 flex flex-col max-h-[550px]">
            <CardHeader className="pb-3 border-b border-slate-800/40">
              <CardTitle className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Star className="h-3.5 w-3.5 text-indigo-400" />
                Target List ({filteredStars.length})
              </CardTitle>
            </CardHeader>
            {/* Scroll container with shadow overlays */}
            <div className="relative flex-1 overflow-hidden">
              {/* Top shadow — always visible if content overflows */}
              <div className="scroll-shadow-top absolute top-0 left-0 right-0 h-5 z-10 pointer-events-none" />
              <div
                ref={listContainerRef}
                className="overflow-y-auto h-full divide-y divide-slate-900/60 scrollbar"
              >
            {loading ? (
              // Sidebar skeleton placeholders
              <div className="divide-y divide-slate-900/40">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="p-3.5 space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="h-3.5 w-24 rounded skeleton" style={{ animationDelay: `${i * 0.1}s` }} />
                      <div className="h-4 w-16 rounded-full skeleton" style={{ animationDelay: `${i * 0.1 + 0.05}s` }} />
                    </div>
                    <div className="flex justify-between">
                      <div className="h-2.5 w-16 rounded skeleton" style={{ animationDelay: `${i * 0.1 + 0.1}s` }} />
                      <div className="h-2.5 w-16 rounded skeleton" style={{ animationDelay: `${i * 0.1 + 0.15}s` }} />
                    </div>
                  </div>
                ))}
              </div>
            ) : starLoadError ? (
              <div className="p-5 space-y-2 text-center">
                <AlertTriangle className="h-6 w-6 text-rose-400/60 mx-auto" />
                <p className="text-xs text-rose-400/80 leading-relaxed">{starLoadError}</p>
              </div>
            ) : filteredStars.length === 0 ? (
              <div className="p-5 space-y-3 text-center">
                <Filter className="h-6 w-6 text-slate-600 mx-auto" />
                <p className="text-xs text-slate-500 leading-relaxed">No targets match this filter</p>
                {(searchQuery || typeFilter !== 'all') && (
                  <button
                    onClick={() => { setSearchQuery(''); setTypeFilter('all'); }}
                    className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mx-auto transition-colors cursor-pointer"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Clear filters
                  </button>
                )}
              </div>
            ) : (
              filteredStars.map(star => {
                const isSelected = selectedPopoverStar && selectedPopoverStar.id === star.id;
                return (
                  <div
                    key={star.id}
                    ref={isSelected ? selectedItemRef : null}
                    className={`p-3.5 cursor-pointer flex flex-col gap-1.5 transition-colors duration-150 group ${
                      isSelected
                        ? 'bg-indigo-950/15 border-l-2 border-indigo-500'
                        : 'hover:bg-[#0f172a]/40 active:bg-[#0f172a]/60'
                    }`}
                    onClick={() => setSelectedPopoverStar(star)}
                  >
                    <div className="flex justify-between items-center">
                      <strong className="text-xs text-slate-200 font-mono group-hover:text-indigo-400 transition-colors duration-150">
                        TIC {star.id}
                      </strong>
                      <Badge variant="outline" className={`text-[9px] font-medium px-1.5 py-0.25 ${badgeColors[star.classification]}`}>
                        {star.classification}
                      </Badge>
                    </div>
                    <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                      <span>RA: {star.ra.toFixed(1)}°</span>
                      <span>Dec: {star.dec.toFixed(1)}°</span>
                    </div>
                  </div>
                );
              })
            )}
              </div>
              {/* Bottom shadow */}
              <div className="scroll-shadow-bottom absolute bottom-0 left-0 right-0 h-5 z-10 pointer-events-none" />
            </div>
          </Card>
      </div>

      {/* Selected Target Details & Sky Snapshot */}
      {selectedPopoverStar && (
        <Card className="bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md overflow-hidden animate-in slide-in-from-bottom-3 duration-500">
          <CardHeader className="pb-3 border-b border-slate-800/60 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-md font-semibold text-slate-200">
                Target Coordinate & Sky Telemetry — TIC {selectedPopoverStar.id}
              </CardTitle>
              <CardDescription className="text-slate-400 text-xs mt-1">
                Visualizing field positioning and classification credentials
              </CardDescription>
            </div>
            <Badge variant="outline" className={`font-semibold px-2.5 py-1 ${badgeColors[selectedPopoverStar.classification]}`}>
              {selectedPopoverStar.classification}
            </Badge>
          </CardHeader>
          <CardContent className="pt-5 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 space-y-5 text-xs font-mono text-slate-400">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                  <span className="text-[10px] text-slate-500 font-medium font-sans">Right Ascension (RA)</span>
                  <span className="text-slate-200 text-sm font-semibold mt-1 font-mono">{selectedPopoverStar.ra.toFixed(4)}°</span>
                </div>
                <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                  <span className="text-[10px] text-slate-500 font-medium font-sans">Declination (Dec)</span>
                  <span className="text-slate-200 text-sm font-semibold mt-1 font-mono">{selectedPopoverStar.dec.toFixed(4)}°</span>
                </div>
                <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                  <span className="text-[10px] text-slate-500 font-medium font-sans">Classifier Confidence</span>
                  <span className="text-indigo-300 text-sm font-semibold mt-1 font-mono">{(selectedPopoverStar.confidence * 100).toFixed(1)}%</span>
                </div>
                <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                  <span className="text-[10px] text-slate-500 font-medium font-sans">Mock Period</span>
                  <span className="text-slate-200 text-sm font-semibold mt-1 font-mono">
                    {((Number(selectedPopoverStar.id) % 15) + 1.25).toFixed(3)} d
                  </span>
                </div>
              </div>
              <div className="pt-2">
                <Button 
                  onClick={handleInspectNavigate} 
                  className="w-full bg-indigo-650 hover:bg-indigo-500 text-white font-medium text-xs py-2 shadow-md cursor-pointer"
                >
                  Inspect Telemetry Details & Light Curve
                  <ChevronRight className="h-4.5 w-4.5 ml-1 shrink-0" />
                </Button>
              </div>
            </div>
            <div className="border-t md:border-t-0 md:border-l border-slate-800/40 md:pl-6 pt-4 md:pt-0">
              <div className="sky-snapshot-card-wrapper [&>div]:pt-0 [&>div]:border-t-0 [&>div>div:first-child]:hidden">
                <SkySnapshot ticId={selectedPopoverStar.id} />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Map Legend card */}
      <Card className="bg-[#0f172a]/10 border-slate-900">
        <CardContent className="p-4 flex flex-wrap gap-6 justify-center text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-emerald-500 inline-block glow-cyan" />
            <span>Exoplanet Candidate</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-orange-500 inline-block" />
            <span>Binary Star System</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-slate-500 inline-block" />
            <span>Stellar Blend / Background</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-sky-500 inline-block" />
            <span>Active Starspots</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
