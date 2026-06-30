import { useState, useEffect } from 'react';
import { 
  ResponsiveContainer, 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid
} from 'recharts';
import { 
  Compass, 
  Filter, 
  Search, 
  Orbit,
  Star,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ChevronRight,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  AlertTriangle
} from 'lucide-react';
import { fetchMapChartImage } from '@/services/astronomyApi';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

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
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  
  // Interactive Sky Map enhancements
  const [raDomain, setRaDomain] = useState<[number, number]>([0, 360]);
  const [decDomain, setDecDomain] = useState<[number, number]>([-90, -80]);
  const [scaleBySize, setScaleBySize] = useState<boolean>(false);
  const [selectedPopoverStar, setSelectedPopoverStar] = useState<SkyStar | null>(null);

  // Center coordinate state & zoom level (1 = widest to 6 = narrowest, default 4 for closer look)
  const [centerRa, setCenterRa] = useState<number>(0);
  const [centerDec, setCenterDec] = useState<number>(-87);
  const [zoom, setZoom] = useState<number>(4);

  // AstronomyAPI sky map background
  const [mapBgUrl, setMapBgUrl] = useState<string | null>(null);
  const [mapStatus, setMapStatus] = useState<'idle' | 'loading' | 'online' | 'error'>('idle');

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
    fetch('/api/sky-map-stars')
      .then(res => {
        if (!res.ok) throw new Error("Failed to load sky map");
        return res.json();
      })
      .then((data: SkyStar[]) => {
        setStars(data);
        setFilteredStars(data);
      })
      .catch(err => {
        console.error("Error loading sky map:", err);
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

  // Debounced AstronomyAPI fetch (400ms) to update the background image when coordinates or zoom factors change
  useEffect(() => {
    setMapStatus('loading');
    const timer = setTimeout(() => {
      fetchMapChartImage(centerRa, centerDec, zoom).then(url => {
        if (url) {
          setMapBgUrl(url);
          setMapStatus('online');
        } else {
          setMapStatus('error');
        }
      });
    }, 400);

    return () => clearTimeout(timer);
  }, [centerRa, centerDec, zoom]);

  // Align map center to highlighted search targets or manually navigated stars
  useEffect(() => {
    if (selectedPopoverStar) {
      setCenterRa(selectedPopoverStar.ra);
      setCenterDec(selectedPopoverStar.dec);
    }
  }, [selectedPopoverStar]);

  // Zoom handlers
  const handleZoomIn = () => {
    setZoom(prev => Math.min(6, prev + 1));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(1, prev - 1));
  };

  const handleResetZoom = () => {
    setZoom(4);
    setCenterRa(0);
    setCenterDec(-87);
  };

  // Pan handlers — pan shifts the center coordinate by 25% of the visible FOV range
  const handlePan = (direction: 'up' | 'down' | 'left' | 'right') => {
    const level = zoomLevels[zoom] || zoomLevels[4];
    const fov = level.fov;
    const cosDec = Math.cos((centerDec * Math.PI) / 180);
    const raSpan = Math.min(360, fov / (cosDec > 0.01 ? cosDec : 0.01));

    if (direction === 'left') {
      setCenterRa(prev => Math.max(0, prev - raSpan * 0.25));
    } else if (direction === 'right') {
      setCenterRa(prev => Math.min(360, prev + raSpan * 0.25));
    } else if (direction === 'down') {
      setCenterDec(prev => Math.max(-90, prev - fov * 0.25));
    } else if (direction === 'up') {
      setCenterDec(prev => Math.min(-80, prev + fov * 0.25));
    }
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

            {/* AstronomyAPI Sky Chart Status */}
            <div className="flex items-center gap-2">
              {mapStatus === 'online' && (
                <span className="flex items-center gap-1.5 text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-1 rounded-full">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  AstronomyAPI: LIVE
                </span>
              )}
              {mapStatus === 'loading' && (
                <span className="flex items-center gap-1.5 text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-1 rounded-full">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-ping" />
                  Fetching Star Chart…
                </span>
              )}
              {mapStatus === 'error' && (
                <span className="flex items-center gap-1.5 text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-1 rounded-full">
                  <AlertTriangle className="h-3 w-3" />
                  Chart Unavailable — Check .env credentials
                </span>
              )}
              {mapStatus === 'idle' && (
                <span className="flex items-center gap-1.5 text-[10px] text-slate-600 px-2 py-1 rounded-full border border-slate-800">
                  Awaiting star chart…
                </span>
              )}
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
            {loading ? (
              <div className="text-center py-24 space-y-4 my-auto">
                <RefreshCw className="h-8 w-8 text-indigo-400 animate-spin mx-auto" />
                <p className="text-xs text-slate-500">Mapping celestial target catalog...</p>
              </div>
            ) : (
              <div className="relative w-full flex-1 flex flex-col justify-between">
                
                {/* SVG Zoom & Pan Controls Overlay (top-left) */}
                <div className="absolute top-0 left-0 z-10 flex flex-col gap-2 bg-[#020617]/60 p-2.5 rounded-lg border border-slate-800 backdrop-blur-sm">
                  <span className="text-[9px] text-slate-550 font-bold uppercase tracking-wider block text-center mb-1">Controls</span>
                  <div className="flex gap-1.5">
                    <Button size="icon" variant="secondary" className="h-7 w-7 bg-slate-900 border border-slate-800 text-slate-300 hover:text-white" onClick={handleZoomIn} title="Zoom In">
                      <ZoomIn className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="icon" variant="secondary" className="h-7 w-7 bg-slate-900 border border-slate-800 text-slate-300 hover:text-white" onClick={handleZoomOut} title="Zoom Out">
                      <ZoomOut className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="icon" variant="secondary" className="h-7 w-7 bg-slate-900 border border-slate-800 text-slate-300 hover:text-white" onClick={handleResetZoom} title="Reset Scope">
                      <Maximize2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  {/* Pan buttons compass pad */}
                  <div className="grid grid-cols-3 gap-1 mt-2 mx-auto w-[85px]">
                    <div />
                    <Button size="icon" variant="secondary" className="h-6 w-6 bg-slate-900 border border-slate-800 text-slate-400 hover:text-white" onClick={() => handlePan('up')}>
                      <ArrowUp className="h-3 w-3" />
                    </Button>
                    <div />
                    <Button size="icon" variant="secondary" className="h-6 w-6 bg-slate-900 border border-slate-800 text-slate-400 hover:text-white" onClick={() => handlePan('left')}>
                      <ArrowLeft className="h-3 w-3" />
                    </Button>
                    <div className="h-6 w-6 rounded bg-[#020617]/45 border border-slate-900 flex items-center justify-center text-[8px] text-slate-600 font-bold">PAN</div>
                    <Button size="icon" variant="secondary" className="h-6 w-6 bg-slate-900 border border-slate-800 text-slate-400 hover:text-white" onClick={() => handlePan('right')}>
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                    <div />
                    <Button size="icon" variant="secondary" className="h-6 w-6 bg-slate-900 border border-slate-800 text-slate-400 hover:text-white" onClick={() => handlePan('down')}>
                      <ArrowDown className="h-3 w-3" />
                    </Button>
                    <div />
                  </div>
                </div>

                {/* Floating Inspector Popover (bottom-left) */}
                {selectedPopoverStar && (
                  <div className="absolute bottom-0 left-0 z-10 w-60 bg-[#020617]/95 border border-slate-850 p-3.5 rounded-lg shadow-2xl space-y-2.5 backdrop-blur-md animate-in slide-in-from-bottom-2 duration-300">
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

                {/* Recharts Scatter chart viewport with AstronomyAPI sky background */}
                <div
                  className="h-[400px] w-full mt-2 relative rounded-md overflow-hidden"
                  style={mapBgUrl ? {
                    backgroundImage: `url('${mapBgUrl}')`,
                    backgroundSize: 'cover',
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'center',
                    transition: 'background-image 0.5s ease-in-out'
                  } : {}}
                >
                  {/* Loading spinner overlay */}
                  {mapStatus === 'loading' && (
                    <div className="absolute inset-0 bg-[#020617]/70 backdrop-blur-xs flex flex-col items-center justify-center z-20 pointer-events-none transition-all duration-350">
                      <RefreshCw className="h-8 w-8 text-indigo-400 animate-spin mb-2" />
                      <span className="text-xs text-indigo-300 font-mono tracking-wider">Syncing Starfield...</span>
                    </div>
                  )}
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart
                      margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.03)" />
                      <XAxis 
                        type="number" 
                        dataKey="ra" 
                        name="RA" 
                        unit="°" 
                        domain={raDomain}
                        allowDataOverflow={true}
                        stroke="rgba(148, 163, 184, 0.4)"
                        fontSize={11}
                        label={{ 
                          value: 'Right Ascension (RA) deg', 
                          position: 'insideBottom', 
                          offset: -10, 
                          fill: 'rgba(148, 163, 184, 0.6)',
                          fontSize: 12
                        }}
                      />
                      <YAxis 
                        type="number" 
                        dataKey="dec" 
                        name="Dec" 
                        unit="°" 
                        domain={decDomain}
                        allowDataOverflow={true}
                        stroke="rgba(148, 163, 184, 0.4)"
                        fontSize={11}
                        label={{ 
                          value: 'Declination (Dec) deg', 
                          angle: -90, 
                          position: 'insideLeft', 
                          offset: -5, 
                          fill: 'rgba(148, 163, 184, 0.6)',
                          fontSize: 12
                        }}
                      />
                      <Tooltip cursor={{ strokeDasharray: '3 3', stroke: 'rgba(99, 102, 241, 0.2)' }} content={() => null} />
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

        {/* Left Targets Quick Navigation List (1 col) */}
        <Card className="bg-[#0f172a]/20 border-slate-850 flex flex-col max-h-[550px]">
          <CardHeader className="pb-3 border-b border-slate-800/40">
            <CardTitle className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Star className="h-3.5 w-3.5 text-indigo-400" />
              Target List ({filteredStars.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 overflow-y-auto flex-1 divide-y divide-slate-900/60 scrollbar">
            {loading ? (
              <div className="p-6 text-center text-xs text-slate-600">Loading...</div>
            ) : filteredStars.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-600">Empty</div>
            ) : (
              filteredStars.map(star => (
                <div 
                  key={star.id} 
                  className={`p-3.5 cursor-pointer flex flex-col gap-1.5 transition-all group ${
                    selectedPopoverStar && selectedPopoverStar.id === star.id 
                      ? 'bg-indigo-950/15 border-l-2 border-indigo-500' 
                      : 'hover:bg-[#0f172a]/40 active:bg-[#0f172a]/60'
                  }`}
                  onClick={() => setSelectedPopoverStar(star)}
                >
                  <div className="flex justify-between items-center">
                    <strong className="text-xs text-slate-200 font-mono group-hover:text-indigo-400 transition-colors">
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
              ))
            )}
          </CardContent>
        </Card>
      </div>

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
