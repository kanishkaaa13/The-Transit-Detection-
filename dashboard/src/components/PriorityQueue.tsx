import { useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  ArrowUpDown, 
  AlertTriangle, 
  ChevronRight, 
  TrendingUp
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

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
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [minConfidence, setMinConfidence] = useState<number>(60); // min confidence in %

  // Color mapping
  const badgeColors = {
    'Exoplanet': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 glow-cyan',
    'Binary Star': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    'Stellar Blend': 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    'Starspot': 'bg-sky-500/10 text-sky-400 border-sky-500/20'
  };

  useEffect(() => {
    setLoading(true);
    fetch('/api/sky-map-stars')
      .then(res => res.json())
      .then((data: StarTarget[]) => {
        const ranked = getAllTargetsRanked(data);
        setRankedStars(ranked);
        setFilteredStars(ranked);
      })
      .catch(err => {
        console.error("Error loading targets for queue:", err);
      })
      .finally(() => {
        setLoading(false);
      });
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

  return (
    <div className="space-y-6">
      {/* Filters Control Card */}
      <Card className="bg-[#0f172a]/40 border-slate-800 glow-purple backdrop-blur-md">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
            {/* Search target by ID */}
            <div className="relative">
              <span className="text-slate-400 text-xs block mb-1.5 font-medium">Search Star ID</span>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
                <Input
                  type="text"
                  placeholder="Enter TIC ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value.replace(/\D/g, ''))}
                  className="pl-8 bg-[#020617]/50 border-slate-700 text-indigo-100 placeholder:text-slate-500 text-xs h-9"
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
                  className="w-full h-9 pl-8 pr-3 rounded-md bg-[#020617]/50 border border-slate-700 text-slate-350 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
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
                <span className="text-indigo-400 font-bold font-mono">{minConfidence}%</span>
              </div>
              <input 
                type="range" 
                min="0" 
                max="100" 
                value={minConfidence} 
                onChange={(e) => setMinConfidence(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Targets Table List Card */}
      <Card className="bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md overflow-hidden">
        <CardHeader className="pb-3 border-b border-slate-800/60">
          <CardTitle className="text-md font-semibold tracking-wide text-slate-100 flex items-center gap-2">
            <TrendingUp className="h-4.5 w-4.5 text-indigo-400" />
            Vetting Priority Queue
          </CardTitle>
          <CardDescription className="text-slate-400 text-xs">
            Targets ranked by classifier confidence score. Select a row to inspect detrended photometry profiles.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="text-center py-20">
              <ArrowUpDown className="h-8 w-8 text-indigo-400 animate-spin mx-auto mb-4" />
              <p className="text-xs text-slate-500">Ranking candidates catalog...</p>
            </div>
          ) : filteredStars.length === 0 ? (
            <div className="text-center py-20 space-y-2">
              <AlertTriangle className="h-10 w-10 text-slate-600 mx-auto" />
              <h4 className="text-sm font-bold text-slate-450">No targets fit screening criteria</h4>
              <p className="text-xs text-slate-500">Try lowering the confidence filter or clearing search fields.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#070a14]/60 text-slate-400 font-semibold">
                    <th className="py-3.5 px-6 font-mono">Vetting Rank</th>
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
                    return (
                      <tr 
                        key={star.id} 
                        onClick={() => onSelectStar(star.id)}
                        className="hover:bg-[#0f172a]/40 cursor-pointer transition-all active:bg-[#0f172a]/60 group border-b border-slate-900/30"
                      >
                        <td className="py-3.5 px-6 text-slate-500 font-mono">
                          #{idx + 1}
                        </td>
                        <td className="py-3.5 px-6 text-slate-100 font-bold font-mono group-hover:text-indigo-400 transition-colors">
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
                        <td className="py-3.5 px-6 text-right text-indigo-400 group-hover:translate-x-1.5 transition-transform duration-200">
                          <ChevronRight className="h-4.5 w-4.5 ml-auto text-indigo-500/80 group-hover:text-indigo-400" />
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
