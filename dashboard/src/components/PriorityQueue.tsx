import { useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  ArrowUpDown, 
  AlertTriangle, 
  ChevronRight, 
  TrendingUp,
  Scale,
  X,
  Check,
  RotateCcw,
  Orbit
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface StarTarget {
  id: string;
  ra: number;
  dec: number;
  classification: 'Exoplanet' | 'Binary Star' | 'Stellar Blend' | 'Starspot';
  confidence: number;
}

interface PriorityQueueProps {
  onSelectStar: (ticId: string) => void;
}

// Stub function returning the preloaded targets sorted by confidence descending
export function getAllTargetsRanked(starsList: StarTarget[]): StarTarget[] {
  return [...starsList].sort((a, b) => b.confidence - a.confidence);
}

export function PriorityQueue({ onSelectStar }: PriorityQueueProps) {
  const [rankedStars, setRankedStars] = useState<StarTarget[]>([]);
  const [filteredStars, setFilteredStars] = useState<StarTarget[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [minConfidence, setMinConfidence] = useState<number>(60); // min confidence in %

  // =================================================================
  // FEATURE 3 STATE: Comparison Mode
  // =================================================================
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isComparing, setIsComparing] = useState<boolean>(false);

  // Color mapping
  const badgeColors = {
    'Exoplanet': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 glow-cyan',
    'Binary Star': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    'Stellar Blend': 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    'Starspot': 'bg-sky-500/10 text-sky-400 border-sky-500/20'
  };

  const fetchTargets = () => {
    setLoading(true);
    setLoadError(null);
    fetch('/api/sky-map-stars')
      .then(res => {
        if (!res.ok) throw new Error(`Failed to load target catalog (HTTP ${res.status})`);
        return res.json();
      })
      .then((data: StarTarget[]) => {
        const ranked = getAllTargetsRanked(data);
        setRankedStars(ranked);
        setFilteredStars(ranked);
      })
      .catch((err: Error) => {
        console.error('PriorityQueue: fetch failed:', err);
        setLoadError(err.message ?? 'Failed to load the target catalog. Check your connection and try again.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchTargets();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Filter lists based on search, classification type, and minimum confidence threshold
  useEffect(() => {
    let result = rankedStars;

    if (searchQuery.trim()) {
      result = result.filter(s => s.id.includes(searchQuery.trim()));
    }

    if (typeFilter !== 'all') {
      result = result.filter(s => s.classification === typeFilter);
    }

    // Min confidence check (confidence is 0.0 - 1.0)
    result = result.filter(s => s.confidence * 100 >= minConfidence);

    setFilteredStars(result);
  }, [searchQuery, typeFilter, minConfidence, rankedStars]);

  const getPriorityInfo = (conf: number) => {
    const score = conf * 100;
    if (score >= 85) {
      return { label: 'High', color: 'bg-red-500/10 text-rose-400 border-rose-500/25 shadow-[0_0_12px_rgba(244,63,94,0.06)]' };
    }
    if (score >= 60) {
      return { label: 'Medium', color: 'bg-amber-500/10 text-amber-400 border-amber-500/25' };
    }
    return { label: 'Low', color: 'bg-slate-800/40 text-slate-500 border-slate-850' };
  };

  // Toggle selection checkbox
  const handleToggleSelect = (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); // prevent triggering row selection/inspect navigation
    setSelectedIds(prev => {
      if (prev.includes(id)) {
        return prev.filter(x => x !== id);
      } else {
        if (prev.length >= 3) {
          alert("You can select up to 3 targets to compare.");
          return prev;
        }
        return [...prev, id];
      }
    });
  };

  // Deterministic mock parameters generator for comparison side-by-side cards
  const getMockComparisonParams = (id: string) => {
    const numId = Number(id) || 0;
    return {
      period: ((numId % 15) + 1.25).toFixed(4),
      depth: ((numId % 40) + 1.5).toFixed(2),
      duration: ((numId % 6) + 1.2).toFixed(2),
      radius: ((numId % 8) + 1.1).toFixed(2),
      snr: ((numId % 25) + 7.5).toFixed(1),
      hab: (numId % 3 === 0 ? "YES (Zone center)" : "NO (Outer border)")
    };
  };

  return (
    <div className="space-y-6">
      {/* Filters Control Card */}
      <Card className="bg-[#0f172a]/40 border-slate-800 backdrop-blur-md">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
            {/* Search target by ID */}
            <div className="relative">
              <span className="text-slate-400 text-xs block mb-1.5 font-medium">Search Star ID</span>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-505" />
                <Input
                  type="text"
                  placeholder="Enter TIC ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value.replace(/\D/g, ''))}
                  className="pl-8 bg-[#020617]/50 border-slate-700 text-slate-100 placeholder:text-slate-500 text-xs h-9"
                />
              </div>
            </div>

            {/* Classification Type dropdown filter */}
            <div>
              <span className="text-slate-400 text-xs block mb-1.5 font-medium">Pipeline Classification</span>
              <div className="relative">
                <Filter className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="w-full h-9 pl-8 pr-3 rounded-md bg-[#020617]/50 border border-slate-700 text-slate-350 focus:outline-none focus:ring-1 focus:ring-accent text-xs"
                >
                  <option value="all">All Classifications</option>
                  <option value="Exoplanet">Exoplanets</option>
                  <option value="Binary Star">Binary Stars</option>
                  <option value="Stellar Blend">Stellar Blends</option>
                  <option value="Starspot">Starspots</option>
                </select>
              </div>
            </div>

            {/* Minimum Confidence threshold slider */}
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1.5 font-medium">
                <span>Min Confidence Threshold</span>
                <span className="text-accent font-bold font-mono">{minConfidence}%</span>
              </div>
              <input 
                type="range" 
                min="0" 
                max="100" 
                value={minConfidence} 
                onChange={(e) => setMinConfidence(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent-color"
              />
            </div>

            {/* FEATURE 3: Comparison Mode trigger button */}
            <div className="pt-4 md:pt-0">
              <span className="text-slate-500 text-[10px] uppercase font-mono block mb-1.5">Vetting tools</span>
              <Button
                disabled={selectedIds.length < 2}
                onClick={() => setIsComparing(true)}
                className="w-full text-xs font-bold bg-accent hover:bg-accent-light border border-accent-light text-slate-100 flex items-center justify-center gap-2 h-9 cursor-pointer"
              >
                <Scale className="h-4 w-4" />
                <span>Compare Selected ({selectedIds.length})</span>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* =================================================================
          FEATURE 3 COMPARISON MODULE LAYOUT
          Displays side-by-side targets values when comparison mode is active
          ================================================================= */}
      {isComparing && (
        <Card className="bg-[#0b0f1e]/80 border border-accent glow-accent-cyan p-5 rounded-xl space-y-4 backdrop-blur-md animate-in zoom-in-95 duration-200">
          <div className="flex justify-between items-center pb-2.5 border-b border-slate-800">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Scale className="h-4.5 w-4.5 text-accent" />
              Side-By-Side Candidate Comparison Profile
            </h3>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-slate-400 hover:text-white"
              onClick={() => {
                setIsComparing(false);
                setSelectedIds([]);
              }}
            >
              <X className="h-4.5 w-4.5" />
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {selectedIds.map(starId => {
              const starObj = rankedStars.find(s => s.id === starId);
              if (!starObj) return null;
              const mock = getMockComparisonParams(starId);
              const priority = getPriorityInfo(starObj.confidence);
              return (
                <Card key={starId} className="bg-[#020617]/70 border border-slate-800 p-4 space-y-3.5">
                  <div className="flex justify-between items-center">
                    <strong className="text-sm text-slate-100 font-mono">TIC {starId}</strong>
                    <Badge variant="outline" className={`text-[9px] font-semibold ${badgeColors[starObj.classification]}`}>
                      {starObj.classification}
                    </Badge>
                  </div>

                  <div className="space-y-2 text-xs divide-y divide-slate-900/60 text-slate-400">
                    <div className="flex justify-between py-1.5">
                      <span>Coordinates (RA/Dec)</span>
                      <span className="text-slate-200 font-mono text-[10px]">
                        {starObj.ra.toFixed(1)}° / {starObj.dec.toFixed(1)}°
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Classifier Confidence</span>
                      <strong className="text-accent font-mono">
                        {(starObj.confidence * 100).toFixed(1)}%
                      </strong>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Vetting Priority</span>
                      <Badge className={`text-[8px] font-bold uppercase tracking-wider border ${priority.color}`}>
                        {priority.label}
                      </Badge>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Orbital Period (P)</span>
                      <strong className="text-slate-200 font-mono">{mock.period} d</strong>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Transit Depth</span>
                      <strong className="text-slate-200 font-mono">{mock.depth} ppt</strong>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Transit Duration</span>
                      <strong className="text-slate-200 font-mono">{mock.duration} h</strong>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Planet Size (Rp)</span>
                      <strong className="text-cyan-400 font-mono">{mock.radius} R⊕</strong>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Signal SNR</span>
                      <strong className="text-slate-200 font-mono">{mock.snr}</strong>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span>Habitable Zone (HZ)</span>
                      <strong className={mock.hab.includes("YES") ? "text-emerald-400 font-semibold" : "text-amber-400/80"}>
                        {mock.hab}
                      </strong>
                    </div>
                  </div>

                  <Button 
                    onClick={() => {
                      setIsComparing(false);
                      onSelectStar(starId);
                    }}
                    className="w-full bg-accent hover:bg-accent/80 text-white font-medium text-[10px] h-8 mt-2 shadow-md cursor-pointer"
                  >
                    Vet Photometry Curve
                    <ChevronRight className="h-3 w-3 ml-1" />
                  </Button>
                </Card>
              );
            })}
          </div>
        </Card>
      )}

      {/* Targets Table List Card */}
      <Card className="bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md overflow-hidden">
        <CardHeader className="pb-3 border-b border-slate-800/60">
          <CardTitle className="text-md font-semibold tracking-wide text-slate-100 flex items-center gap-2">
            <TrendingUp className="h-4.5 w-4.5 text-accent" />
            Vetting Priority Queue
          </CardTitle>
          <CardDescription className="text-slate-400 text-xs">
            Targets ranked by classifier confidence score. Check boxes to select 2-3 targets for side-by-side comparison.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#070a14]/60 text-slate-400 font-semibold">
                    <th className="py-3.5 px-6 select-none w-12 text-center">Compare</th>
                    <th className="py-3.5 px-4 font-mono">Vetting Rank</th>
                    <th className="py-3.5 px-6 font-mono">TIC Target ID</th>
                    <th className="py-3.5 px-6">Classification</th>
                    <th className="py-3.5 px-6 font-mono">Confidence</th>
                    <th className="py-3.5 px-6">Vetting Priority</th>
                    <th className="py-3.5 px-6 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/40">
                  {[...Array(5)].map((_, i) => (
                    <tr key={i} className="border-b border-slate-900/30">
                      <td className="py-4 px-6 text-center">
                        <div className="h-4.5 w-4.5 mx-auto rounded border border-slate-800 skeleton" style={{ animationDelay: `${i * 0.05}s` }} />
                      </td>
                      <td className="py-4 px-4">
                        <div className="h-3.5 w-8 rounded skeleton" style={{ animationDelay: `${i * 0.05 + 0.05}s` }} />
                      </td>
                      <td className="py-4 px-6">
                        <div className="h-4 w-24 rounded skeleton font-mono" style={{ animationDelay: `${i * 0.05 + 0.1}s` }} />
                      </td>
                      <td className="py-4 px-6">
                        <div className="h-4.5 w-20 rounded skeleton" style={{ animationDelay: `${i * 0.05 + 0.15}s` }} />
                      </td>
                      <td className="py-4 px-6">
                        <div className="h-4 w-12 rounded skeleton font-mono" style={{ animationDelay: `${i * 0.05 + 0.2}s` }} />
                      </td>
                      <td className="py-4 px-6">
                        <div className="h-4.5 w-16 rounded skeleton" style={{ animationDelay: `${i * 0.05 + 0.25}s` }} />
                      </td>
                      <td className="py-4 px-6 text-right">
                        <div className="h-4 w-4 ml-auto rounded skeleton" style={{ animationDelay: `${i * 0.05 + 0.3}s` }} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : loadError ? (
            // Fetch error state with retry
            <div className="py-20 px-8 space-y-4 text-center relative overflow-hidden">
              <div className="relative mx-auto w-20 h-20 flex items-center justify-center">
                {/* Outer ring */}
                <div className="absolute inset-0 rounded-full border border-rose-500/10" />
                <div className="absolute inset-2 rounded-full border border-rose-500/15" />
                <div className="absolute inset-4 rounded-full bg-rose-500/5 flex items-center justify-center">
                  <Orbit className="h-8 w-8 text-rose-500/20 animate-spin" style={{ animationDuration: '6s' }} />
                </div>
                <div className="absolute bottom-0 right-0 w-6 h-6 rounded-full bg-[#0f172a] border border-rose-500/25 flex items-center justify-center">
                  <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
                </div>
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-rose-300">Catalog Load Failed</h4>
                <p className="text-xs text-slate-550 max-w-xs mx-auto leading-relaxed">{loadError}</p>
              </div>
              <button
                onClick={fetchTargets}
                className="mx-auto flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition-all active:scale-95 cursor-pointer"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry
              </button>
            </div>
          ) : filteredStars.length === 0 ? (
            // Empty state — no targets match the current filters
            <div className="py-16 px-8 space-y-4 text-center relative overflow-hidden">
              <div className="relative mx-auto w-20 h-20 flex items-center justify-center">
                {/* Outer ring */}
                <div className="absolute inset-0 rounded-full border border-slate-700/10" />
                <div className="absolute inset-2 rounded-full border border-slate-700/15" />
                <div className="absolute inset-4 rounded-full bg-slate-800/10 flex items-center justify-center">
                  <Orbit className="h-8 w-8 text-slate-500/30 animate-spin" style={{ animationDuration: '8s' }} />
                </div>
                <div className="absolute bottom-0 right-0 w-6 h-6 rounded-full bg-[#0f172a] border border-slate-700/30 flex items-center justify-center">
                  <Filter className="h-3.5 w-3.5 text-slate-400" />
                </div>
              </div>
              <div className="space-y-1.5">
                <h4 className="text-sm font-bold text-slate-400">No targets match this confidence threshold</h4>
                <p className="text-xs text-slate-500 max-w-xs mx-auto leading-relaxed">
                  {searchQuery
                    ? `No results for TIC "${searchQuery}"`
                    : typeFilter !== 'all'
                    ? `No ${typeFilter} targets at ≥${minConfidence}% confidence`
                    : `No targets at ≥${minConfidence}% confidence`
                  }
                </p>
              </div>
              {(searchQuery || typeFilter !== 'all' || minConfidence > 0) && (
                <button
                  onClick={() => { setSearchQuery(''); setTypeFilter('all'); setMinConfidence(60); }}
                  className="mx-auto flex items-center gap-2 px-4 py-2 bg-transparent border border-slate-750 hover:border-indigo-500 text-slate-300 hover:text-indigo-300 text-xs font-medium rounded-lg transition-all cursor-pointer"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Clear Filters
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#070a14]/60 text-slate-400 font-semibold">
                    <th className="py-3.5 px-6 select-none w-12 text-center">Compare</th>
                    <th className="py-3.5 px-4 font-mono">Vetting Rank</th>
                    <th className="py-3.5 px-6 font-mono">TIC Target ID</th>
                    <th className="py-3.5 px-6">Classification</th>
                    <th className="py-3.5 px-6 font-mono">Confidence</th>
                    <th className="py-3.5 px-6">Vetting Priority</th>
                    <th className="py-3.5 px-6 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/60">
                  {filteredStars.map((star, idx) => {
                    const priority = getPriorityInfo(star.confidence);
                    const isChecked = selectedIds.includes(star.id);
                    return (
                      <tr 
                        key={star.id} 
                        onClick={() => onSelectStar(star.id)}
                        className="hover:bg-[#0f172a]/40 cursor-pointer transition-all active:bg-[#0f172a]/60 group border-b border-slate-900/30"
                      >
                        {/* Checkbox select column */}
                        <td className="py-3.5 px-6 text-center" onClick={(e) => handleToggleSelect(e, star.id)}>
                          <div className={`h-4.5 w-4.5 rounded border flex items-center justify-center transition-all ${
                            isChecked 
                              ? 'bg-accent border-accent text-slate-950 font-bold' 
                              : 'border-slate-700 bg-[#020617]/50 hover:border-slate-500'
                          }`}>
                            {isChecked && <Check className="h-3 w-3 text-slate-950 stroke-[3px]" />}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-slate-500 font-mono">
                          #{idx + 1}
                        </td>
                        <td className="py-3.5 px-6 text-slate-100 font-bold font-mono group-hover:text-accent transition-colors">
                          TIC {star.id}
                        </td>
                        <td className="py-3.5 px-6">
                          <Badge variant="outline" className={`text-[10px] font-semibold ${badgeColors[star.classification]}`}>
                            {star.classification}
                          </Badge>
                        </td>
                        <td className="py-3.5 px-6 text-slate-350 font-bold font-mono">
                          {(star.confidence * 100).toFixed(1)}%
                        </td>
                        <td className="py-3.5 px-6">
                          <Badge className={`text-[9px] font-semibold uppercase tracking-wider border ${priority.color}`}>
                            {priority.label}
                          </Badge>
                        </td>
                        <td className="py-3.5 px-6 text-right text-accent group-hover:translate-x-1.5 transition-transform duration-200">
                          <ChevronRight className="h-4.5 w-4.5 ml-auto text-slate-550 group-hover:text-accent" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
