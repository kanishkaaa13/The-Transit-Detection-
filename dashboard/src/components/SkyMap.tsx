import { useState, useEffect } from 'react';
import { 
  ResponsiveContainer, 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid,
  Cell
} from 'recharts';
import { 
  Compass, 
  Info, 
  Filter, 
  Search, 
  Orbit,
  Star,
  RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

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

  // Filter stars based on query and type filter
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

  const handlePointClick = (data: any) => {
    if (data && data.id) {
      onSelectStar(data.id);
    }
  };

  // Custom tooltips for Recharts scatter plot
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data: SkyStar = payload[0].payload;
      return (
        <div className="bg-[#020617] border border-slate-800 p-3 rounded-lg shadow-xl text-xs space-y-1.5 backdrop-blur-md">
          <div className="flex justify-between items-center gap-6">
            <span className="font-bold text-slate-100 font-mono">TIC {data.id}</span>
            <Badge variant="outline" className={`text-[10px] font-semibold ${badgeColors[data.classification]}`}>
              {data.classification}
            </Badge>
          </div>
          <div className="text-slate-400 space-y-0.5 font-mono">
            <p>RA: {data.ra.toFixed(4)}°</p>
            <p>Dec: {data.dec.toFixed(4)}°</p>
            <p>Confidence: {(data.confidence * 100).toFixed(1)}%</p>
          </div>
          <p className="text-[10px] text-indigo-400 italic pt-1.5 border-t border-slate-900 mt-1">
            Click target point to view light curve
          </p>
        </div>
      );
    }
    return null;
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
                <p className="text-xs text-slate-400">Celestial coordinates of dwarf stars targeted for transit signals</p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
              {/* Search target by ID */}
              <div className="relative flex-1 sm:w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
                <Input
                  type="text"
                  placeholder="Filter by TIC ID..."
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
                  className="w-full h-9 pl-8 pr-3 rounded-md bg-[#020617]/50 border border-slate-700 text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
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
        {/* Right side Celestial Scatter Chart (3 cols) */}
        <Card className="lg:col-span-3 bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md min-h-[500px] flex flex-col">
          <CardHeader className="pb-2">
            <CardTitle className="text-md font-semibold text-slate-200 flex items-center gap-2">
              <Orbit className="h-4.5 w-4.5 text-indigo-400" />
              Stellar Field Distribution
            </CardTitle>
            <CardDescription className="text-slate-400 text-xs">
              Declination (Dec) vs. Right Ascension (RA) mapping. Click points to jump to detail view.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex items-center justify-center p-6">
            {loading ? (
              <div className="text-center py-20 space-y-4">
                <RefreshCw className="h-8 w-8 text-indigo-400 animate-spin mx-auto" />
                <p className="text-xs text-slate-500">Mapping celestial target catalog...</p>
              </div>
            ) : filteredStars.length === 0 ? (
              <div className="text-center py-20 space-y-2">
                <Info className="h-10 w-10 text-slate-600 mx-auto" />
                <h4 className="text-sm font-bold text-slate-400">No targets found</h4>
                <p className="text-xs text-slate-500">Try adjusting your filters or search query.</p>
              </div>
            ) : (
              <div className="h-[400px] w-full mt-2">
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
                      domain={[0, 360]}
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
                      domain={[-90, -80]} // TESS Southern Polar Cap covers -90 to -80 Declination
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
                    <Tooltip content={<CustomTooltip />} />
                    <Scatter 
                      name="Stellar Coordinates" 
                      data={filteredStars} 
                      onClick={(node) => handlePointClick(node)}
                      className="cursor-pointer"
                    >
                      {filteredStars.map((entry, index) => (
                        <Cell 
                          key={`cell-${index}`} 
                          fill={colors[entry.classification]} 
                          className="hover:scale-155 hover:stroke-white hover:stroke-2 transition-all duration-200"
                        />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Left side Targets Quick Navigation List (1 col) */}
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
                  className="p-3.5 hover:bg-[#0f172a]/40 cursor-pointer flex flex-col gap-1.5 transition-all active:bg-[#0f172a]/60 group"
                  onClick={() => onSelectStar(star.id)}
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
