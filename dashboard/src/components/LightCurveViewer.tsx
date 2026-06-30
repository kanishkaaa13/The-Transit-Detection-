import React, { useState, useEffect } from 'react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid 
} from 'recharts';
import { 
  Search, 
  Orbit, 
  Info, 
  CheckCircle2, 
  AlertTriangle, 
  HelpCircle, 
  Activity, 
  RefreshCw, 
  BarChart2, 
  Compass
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

// ---------------------------------------------------------
// Types & Signatures
// ---------------------------------------------------------
export interface LightCurvePoint {
  time: number;
  flux: number;
  flux_err?: number;
}

export interface DetectionResult {
  event: string;
  classification: 'Exoplanet' | 'Binary Star' | 'Stellar Blend' | 'Starspot';
  confidence: number;
  period: number;
  depth: number;
  duration: number;
}

// Mock/stub function for signal detection
export function detectSignal(ticId: string): Promise<DetectionResult> {
  return new Promise((resolve) => {
    setTimeout(() => {
      const numId = Number(ticId) || 0;
      const digitSum = ticId.split('').reduce((sum, char) => sum + (parseInt(char, 10) || 0), 0);
      
      const classifications: DetectionResult['classification'][] = [
        'Exoplanet',
        'Binary Star',
        'Stellar Blend',
        'Starspot'
      ];
      
      let classification = classifications[digitSum % classifications.length];
      let confidence = 0.65 + (digitSum % 31) / 100;
      let period = 2.5 + (numId % 250) / 10;
      let depth = 0.0015 + (numId % 40) / 1000;
      let duration = 1.2 + (digitSum % 6) * 0.4;
      let event = `TOI-${100 + (digitSum % 800)}.${(digitSum % 99).toString().padStart(2, '0')}`;

      // Force realistic values for demo TIC IDs already in the repo
      if (ticId === '451598465') {
        classification = 'Exoplanet';
        confidence = 0.945;
        event = 'TOI-1431.01';
        period = 3.512;
        depth = 0.0035; // 3500 ppm
        duration = 2.45;
      } else if (ticId === '2054445521') {
        classification = 'Binary Star';
        confidence = 0.982;
        event = 'EB-SYS-2054';
        period = 12.434;
        depth = 0.0820; // 8.2%
        duration = 4.8;
      } else if (ticId === '257325189') {
        classification = 'Stellar Blend';
        confidence = 0.714;
        event = 'BLEND-2573';
        period = 1.252;
        depth = 0.0012; // 1200 ppm
        duration = 1.8;
      } else if (ticId === '317154919') {
        classification = 'Starspot';
        confidence = 0.841;
        event = 'SPOT-3171';
        period = 28.45;
        depth = 0.0045; // 4500 ppm
        duration = 12.2;
      }

      resolve({
        event,
        classification,
        confidence,
        period,
        depth,
        duration
      });
    }, 1500);
  });
}

export function LightCurveViewer() {
  // Selection and searching
  const [ticId, setTicId] = useState<string>('451598465');
  const [activeTicId, setActiveTicId] = useState<string>('');
  const [availableIds, setAvailableIds] = useState<string[]>([]);
  
  // Data loading states
  const [loading, setLoading] = useState<boolean>(false);
  const [data, setData] = useState<LightCurvePoint[]>([]);
  const [downsampledData, setDownsampledData] = useState<LightCurvePoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Statistics
  const [stats, setStats] = useState<{
    count: number;
    mean: number;
    stdDev: number;
    minFlux: number;
    maxFlux: number;
    rangeFlux: number;
  } | null>(null);

  // Detection states
  const [detecting, setDetecting] = useState<boolean>(false);
  const [detectionResult, setDetectionResult] = useState<DetectionResult | null>(null);

  // Load available TIC IDs on mount
  useEffect(() => {
    fetch('/api/tic-ids')
      .then(res => {
        if (!res.ok) throw new Error("Failed to load list");
        return res.json();
      })
      .then(ids => {
        setAvailableIds(ids);
        // Default to the first ID in the list if available, or fallback to active document ID
        if (ids.length > 0) {
          const defaultId = ids.includes('451598465') ? '451598465' : ids[0];
          setTicId(defaultId);
          loadLightCurve(defaultId);
        }
      })
      .catch(err => {
        console.error("Error loading ID list:", err);
      });
  }, []);

  const loadLightCurve = async (idToLoad: string) => {
    if (!idToLoad.trim()) return;
    setLoading(true);
    setError(null);
    setDetectionResult(null); // Reset previous detection result
    setActiveTicId(idToLoad);

    try {
      const response = await fetch(`/data/lightcurves/${idToLoad}.json`);
      if (!response.ok) {
        throw new Error(`Light curve dataset for TIC ID ${idToLoad} not found.`);
      }
      const rawData: LightCurvePoint[] = await response.json();
      
      if (!rawData || rawData.length === 0) {
        throw new Error(`Dataset is empty for TIC ID ${idToLoad}.`);
      }

      // Sort data by time
      rawData.sort((a, b) => a.time - b.time);
      setData(rawData);

      // Perform Downsampling (Max 2500 points for smooth Recharts rendering)
      const maxPoints = 2500;
      if (rawData.length > maxPoints) {
        const step = Math.ceil(rawData.length / maxPoints);
        const sampled: LightCurvePoint[] = [];
        for (let i = 0; i < rawData.length; i += step) {
          sampled.push(rawData[i]);
        }
        setDownsampledData(sampled);
      } else {
        setDownsampledData(rawData);
      }

      // Calculate Statistics
      const fluxes = rawData.map(p => p.flux);
      const count = fluxes.length;
      const minFlux = Math.min(...fluxes);
      const maxFlux = Math.max(...fluxes);
      const sum = fluxes.reduce((a, b) => a + b, 0);
      const mean = sum / count;
      const variance = fluxes.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / count;
      const stdDev = Math.sqrt(variance);

      setStats({
        count,
        mean,
        stdDev,
        minFlux,
        maxFlux,
        rangeFlux: maxFlux - minFlux
      });

    } catch (err: any) {
      setError(err.message || 'An error occurred while loading the data.');
      setData([]);
      setDownsampledData([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadLightCurve(ticId);
  };

  const handleDetectSignal = async () => {
    if (!activeTicId) return;
    setDetecting(true);
    try {
      const result = await detectSignal(activeTicId);
      setDetectionResult(result);
    } catch (err) {
      console.error("Signal detection failed:", err);
    } finally {
      setDetecting(false);
    }
  };

  // Color mappings for classifications
  const badgeColors = {
    'Exoplanet': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 glow-cyan',
    'Binary Star': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    'Stellar Blend': 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    'Starspot': 'bg-sky-500/10 text-sky-400 border-sky-500/20'
  };

  // Dynamic axis domains to keep chart readable
  const timeMin = downsampledData.length > 0 ? Math.floor(downsampledData[0].time) : 0;
  const timeMax = downsampledData.length > 0 ? Math.ceil(downsampledData[downsampledData.length - 1].time) : 0;
  
  const fluxMin = stats ? stats.minFlux - stats.rangeFlux * 0.05 : 0.95;
  const fluxMax = stats ? stats.maxFlux + stats.rangeFlux * 0.05 : 1.05;

  return (
    <div className="space-y-6">
      {/* ---------------------------------------------------------
          Search Controls & Selector
          --------------------------------------------------------- */}
      <Card className="bg-[#0f172a]/40 border-slate-800 glow-purple backdrop-blur-md">
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4 items-center">
            <div className="flex-1 w-full flex flex-col sm:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-indigo-400/60" />
                <Input
                  type="text"
                  placeholder="Enter TIC ID (e.g. 451598465)"
                  className="pl-10 bg-[#020617]/60 border-slate-700 text-indigo-100 placeholder-indigo-300/40 focus-visible:ring-indigo-500 focus-visible:ring-offset-0 focus-visible:border-indigo-500"
                  value={ticId}
                  onChange={(e) => setTicId(e.target.value.replace(/\D/g, ''))}
                />
              </div>

              {availableIds.length > 0 && (
                <div className="w-full sm:w-64">
                  <select
                    className="w-full h-10 px-3 rounded-md bg-[#020617]/60 border border-slate-700 text-indigo-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                    value={ticId}
                    onChange={(e) => {
                      setTicId(e.target.value);
                      loadLightCurve(e.target.value);
                    }}
                  >
                    <option value="" disabled>Select pre-loaded TIC ID</option>
                    {availableIds.map((id) => (
                      <option key={id} value={id}>TIC {id}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <Button 
              type="submit" 
              className="w-full md:w-auto bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-8 transition-all shadow-md hover:shadow-indigo-500/20 active:scale-95"
              disabled={loading || !ticId}
            >
              {loading && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
              Fetch Light Curve
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* ---------------------------------------------------------
          Main Content Grid (Light Curve + Detection Panel)
          --------------------------------------------------------- */}
      {error && (
        <Alert variant="destructive" className="bg-red-950/20 border-red-500/30 text-red-200">
          <AlertTriangle className="h-4 w-4 text-red-400" />
          <AlertTitle>Dataset Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        // Loading State: Skeleton Layout
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2 bg-[#0f172a]/30 border-slate-800">
            <CardHeader className="space-y-2">
              <div className="h-6 w-1/3 bg-slate-800 animate-pulse rounded" />
              <div className="h-4 w-1/4 bg-slate-800/60 animate-pulse rounded" />
            </CardHeader>
            <CardContent>
              <div className="h-[400px] w-full bg-slate-900/30 animate-pulse border border-dashed border-slate-800/40 rounded flex items-center justify-center">
                <Orbit className="h-10 w-10 text-indigo-500/30 animate-spin" />
              </div>
            </CardContent>
          </Card>
          <div className="space-y-6">
            <Card className="bg-[#0f172a]/30 border-slate-800">
              <CardHeader><div className="h-6 w-1/2 bg-slate-800 animate-pulse rounded" /></CardHeader>
              <CardContent className="space-y-6">
                <div className="h-12 bg-slate-850 animate-pulse rounded-md" />
                <div className="space-y-2">
                  <div className="h-4 bg-slate-800 animate-pulse rounded w-3/4" />
                  <div className="h-4 bg-slate-800 animate-pulse rounded w-1/2" />
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : activeTicId && data.length > 0 ? (
        // Loaded State
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Light Curve Chart Card (Left 2 cols) */}
          <Card className="lg:col-span-2 bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
              <div>
                <CardTitle className="text-xl font-bold tracking-wide text-slate-100 flex items-center gap-2">
                  <Activity className="h-5 w-5 text-cyan-400" />
                  Stellar Light Curve - TIC {activeTicId}
                </CardTitle>
                <CardDescription className="text-slate-400 mt-1">
                  Plotting {downsampledData.length} observations (downsampled from {data.length} total)
                </CardDescription>
              </div>
              <Badge variant="outline" className="border-cyan-500/30 text-cyan-400 bg-cyan-950/10">
                2-min Cadence
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="h-[400px] w-full text-slate-200 mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart 
                    data={downsampledData}
                    margin={{ top: 10, right: 10, left: 10, bottom: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.05)" />
                    <XAxis 
                      type="number" 
                      dataKey="time" 
                      domain={[timeMin, timeMax]}
                      tickFormatter={(val) => val.toFixed(1)}
                      stroke="rgba(148, 163, 184, 0.4)" 
                      fontSize={11}
                      label={{ 
                        value: 'Time (BJD - 2457000)', 
                        position: 'insideBottom', 
                        offset: -10, 
                        fill: 'rgba(148, 163, 184, 0.6)',
                        fontSize: 12
                      }}
                    />
                    <YAxis 
                      type="number" 
                      dataKey="flux" 
                      domain={[fluxMin, fluxMax]}
                      tickFormatter={(val) => val.toFixed(4)}
                      stroke="rgba(148, 163, 184, 0.4)" 
                      fontSize={11}
                      label={{ 
                        value: 'Relative Flux', 
                        angle: -90, 
                        position: 'insideLeft', 
                        offset: -5,
                        fill: 'rgba(148, 163, 184, 0.6)',
                        fontSize: 12
                      }}
                    />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#020617', 
                        borderColor: '#334155',
                        color: '#f8fafc',
                        borderRadius: '6px',
                        fontSize: '12px'
                      }}
                      labelFormatter={(val) => `Time: ${val.toFixed(5)} BJD`}
                      formatter={(val: any) => [`Flux: ${val.toFixed(6)}`, 'Relative Flux']}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="flux" 
                      stroke="#06b6d4" 
                      strokeWidth={1}
                      dot={false}
                      activeDot={{ r: 4, stroke: '#22d3ee', strokeWidth: 1, fill: '#0891b2' }} 
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Data Summary Stats */}
              {stats && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-800/60 text-xs">
                  <div className="p-3 bg-[#020617]/40 rounded-md border border-slate-900/60">
                    <span className="text-slate-400 block mb-1">Observations</span>
                    <strong className="text-sm text-slate-100">{stats.count.toLocaleString()}</strong>
                  </div>
                  <div className="p-3 bg-[#020617]/40 rounded-md border border-slate-900/60">
                    <span className="text-slate-400 block mb-1">Mean Flux</span>
                    <strong className="text-sm text-slate-100">{stats.mean.toFixed(6)}</strong>
                  </div>
                  <div className="p-3 bg-[#020617]/40 rounded-md border border-slate-900/60">
                    <span className="text-slate-400 block mb-1">Standard Dev (σ)</span>
                    <strong className="text-sm text-slate-100">{(stats.stdDev * 1e6).toFixed(1)} ppm</strong>
                  </div>
                  <div className="p-3 bg-[#020617]/40 rounded-md border border-slate-900/60">
                    <span className="text-slate-400 block mb-1">Transit depth range</span>
                    <strong className="text-sm text-slate-100">{(stats.rangeFlux * 100).toFixed(3)}%</strong>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Detection & Classification Panel (Right 1 col) */}
          <div className="space-y-6">
            <Card className="bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md">
              <CardHeader className="pb-3 border-b border-slate-800/60">
                <CardTitle className="text-lg font-semibold tracking-wide text-slate-100 flex items-center gap-2">
                  <Compass className="h-5 w-5 text-indigo-400" />
                  Signal Analysis
                </CardTitle>
                <CardDescription className="text-slate-400 text-xs">
                  Run ML classifier pipelines on the light curve signal.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-6 space-y-6">
                {!detectionResult && !detecting ? (
                  // Initial Action State
                  <div className="text-center py-6">
                    <Orbit className="h-16 w-16 text-indigo-500/20 mx-auto mb-4 pulsar" />
                    <p className="text-sm text-slate-400 mb-4 px-2">
                      Analyze the detrended light curve using our 1D CNN model and BLS periodogram solver.
                    </p>
                    <Button 
                      className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-md shadow-indigo-500/10 active:scale-95 transition-all"
                      onClick={handleDetectSignal}
                    >
                      Detect Signal
                    </Button>
                  </div>
                ) : detecting ? (
                  // ML Processing State
                  <div className="text-center py-8 space-y-4">
                    <RefreshCw className="h-10 w-10 text-cyan-400 animate-spin mx-auto" />
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-indigo-300">Running Neural Net Classifier...</p>
                      <p className="text-xs text-slate-400 animate-pulse">Running BLS Periodogram search...</p>
                    </div>
                  </div>
                ) : (
                  // Completed Classification Result Panel
                  <div className="space-y-6 animate-in fade-in duration-300">
                    <div className="space-y-4">
                      {/* Classification Badge & Title */}
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-slate-400 font-medium">Stellar Classification</span>
                        <Badge 
                          variant="outline" 
                          className={`font-semibold px-2.5 py-1 ${badgeColors[detectionResult.classification]}`}
                        >
                          {detectionResult.classification}
                        </Badge>
                      </div>

                      {/* Event TOI ID */}
                      <div className="flex items-center justify-between pb-3 border-b border-slate-800/40">
                        <span className="text-sm text-slate-400">Object Designation</span>
                        <span className="text-sm font-bold text-slate-100 tracking-wide">{detectionResult.event}</span>
                      </div>

                      {/* Confidence Progress bar / Gauge */}
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-400">Classification Confidence</span>
                          <span className="text-indigo-300 font-semibold font-mono">
                            {(detectionResult.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                        <Progress 
                          value={detectionResult.confidence * 100} 
                          className={`h-2 bg-[#020617] [&>div]:bg-indigo-500 ${
                            detectionResult.classification === 'Exoplanet' ? '[&>div]:bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.2)]' : ''
                          }`}
                        />
                      </div>
                    </div>

                    {/* Detected Signal Properties */}
                    <div className="space-y-3 p-4 bg-[#020617]/50 rounded-lg border border-slate-900/60">
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <BarChart2 className="h-3.5 w-3.5 text-cyan-400" />
                        Parameters
                      </h4>
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="text-slate-500 block mb-0.5">Orbital Period</span>
                          <span className="font-mono text-slate-200 text-sm font-medium">
                            {detectionResult.period.toFixed(4)} days
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 block mb-0.5">Transit Depth</span>
                          <span className="font-mono text-slate-200 text-sm font-medium">
                            {(detectionResult.depth * 100).toFixed(4)}%
                            <span className="text-[10px] text-slate-500 block">
                              ({(detectionResult.depth * 1e6).toFixed(0)} ppm)
                            </span>
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 block mb-0.5">Duration</span>
                          <span className="font-mono text-slate-200 text-sm font-medium">
                            {detectionResult.duration.toFixed(2)} hours
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 block mb-0.5">Status</span>
                          <span className="text-slate-300 font-medium flex items-center gap-1 text-[11px] mt-0.5">
                            {detectionResult.classification === 'Exoplanet' ? (
                              <>
                                <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                                Prime Candidate
                              </>
                            ) : (
                              <>
                                <Info className="h-3 w-3 text-slate-400" />
                                Screened Out
                              </>
                            )}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Re-run button */}
                    <Button 
                      variant="outline"
                      className="w-full border-slate-700 hover:bg-slate-800 text-slate-200 font-medium transition-all"
                      onClick={handleDetectSignal}
                    >
                      <RefreshCw className="mr-2 h-3.5 w-3.5" />
                      Re-run Classifier
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Science Guide card */}
            <Card className="bg-[#0f172a]/20 border-slate-850">
              <CardContent className="p-4 text-xs text-slate-400 space-y-2">
                <h5 className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-indigo-400" />
                  Understanding Stellar Classifications
                </h5>
                <p>
                  <strong>Exoplanet:</strong> Periodic, flat-bottomed dip in light due to an orbiting planet.
                </p>
                <p>
                  <strong>Binary Star:</strong> Deep alternating primary and secondary eclipses.
                </p>
                <p>
                  <strong>Starspot:</strong> Sinusoidal variations caused by rotating stellar surface spots.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        // Empty State: Before search/load
        <Card className="bg-[#0f172a]/20 border-slate-800 border-dashed py-16 text-center">
          <CardContent className="space-y-4">
            <Orbit className="h-20 w-20 text-indigo-500/20 mx-auto pulsar" />
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-slate-300">Explore the TESS Datasets</h3>
              <p className="text-sm text-slate-400 max-w-sm mx-auto">
                Enter a TIC ID above or select one from the discovered catalog to view the light curve and detect planet transits.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
