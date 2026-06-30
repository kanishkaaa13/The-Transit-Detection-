import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react';
import { LightCurveViewer } from './components/LightCurveViewer';
import { SkyMap } from './components/SkyMap';
import { PriorityQueue } from './components/PriorityQueue';
import { 
  Orbit, 
  Database, 
  Cpu, 
  FileText,
  Activity,
  Compass,
  Zap,
  ListTodo,
  Palette,
  Keyboard,
  HelpCircle,
  Clock,
  TrendingUp,
  X,
  CheckCircle2,
  AlertTriangle,
  Info
} from 'lucide-react';

// =================================================================
// GLOBAL TOAST SYSTEM
// =================================================================
export interface Toast {
  id: string;
  message: string;
  variant: 'success' | 'error' | 'info';
}

interface ToastContextValue {
  addToast: (message: string, variant?: Toast['variant'], duration?: number) => void;
}

export const ToastContext = createContext<ToastContextValue>({
  addToast: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}

function ToastStack() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    const t = timersRef.current.get(id);
    if (t) { clearTimeout(t); timersRef.current.delete(id); }
  }, []);

  const addToast = useCallback((message: string, variant: Toast['variant'] = 'success', duration = 3000) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts(prev => [...prev.slice(-4), { id, message, variant }]);
    const timer = setTimeout(() => removeToast(id), duration);
    timersRef.current.set(id, timer);
  }, [removeToast]);

  const icons = {
    success: <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />,
    error:   <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />,
    info:    <Info className="h-4 w-4 text-indigo-400 shrink-0" />,
  };

  const borders = {
    success: 'border-emerald-500/25',
    error:   'border-rose-500/25',
    info:    'border-indigo-500/25',
  };

  return (
    <ToastContext.Provider value={{ addToast }}>
      <div className="fixed bottom-6 right-6 z-[1000] flex flex-col gap-2 items-end pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border ${
              borders[t.variant]
            } bg-[#0b0f1e]/95 backdrop-blur-md shadow-2xl text-xs text-slate-200 max-w-xs w-full animate-in slide-in-from-right-4 fade-in duration-300`}
          >
            {icons[t.variant]}
            <span className="flex-1 leading-snug">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="text-slate-500 hover:text-slate-300 transition-colors cursor-pointer ml-1 shrink-0"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// =================================================================
// FEATURE 2 STUB: getRecentActivity()
// Returns mock timestamped events for the scrolling log feed
// =================================================================
interface ActivityEvent {
  time: string;
  msg: string;
  type: 'system' | 'classifier' | 'habitability' | 'api' | 'zoom';
}

function getRecentActivity(): ActivityEvent[] {
  return [
    { time: '17:09', msg: 'Zoom factor adjusted to scale 4 for Southern Polar region', type: 'zoom' },
    { time: '17:05', msg: 'Run BLS search on TIC 451598465 - Exoplanet candidate mapped', type: 'classifier' },
    { time: '16:58', msg: 'Habitability profile compiled for TIC 257738202', type: 'habitability' },
    { time: '16:44', msg: 'AstronomyAPI star-chart generated for TIC 2054445521', type: 'api' },
    { time: '16:12', msg: 'Light curve downsampled and loaded for TIC 317154919', type: 'system' },
    { time: '15:56', msg: 'ML pipeline synced with prime_targets.csv catalog', type: 'system' }
  ];
}

function App() {
  const [starCount, setStarCount] = useState<number>(0);
  const [starsData, setStarsData] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'viewer' | 'skymap' | 'queue'>('viewer');
  const [selectedStarId, setSelectedStarId] = useState<string>('451598465');

  // =================================================================
  // FEATURE 1 STATE: Live Stats Bar
  // =================================================================
  const [animatedTargets, setAnimatedTargets] = useState(0);
  const [animatedExoplanets, setAnimatedExoplanets] = useState(0);
  const [animatedConfidence, setAnimatedConfidence] = useState(0);
  const lastDectectRun = '17:05:19';

  // =================================================================
  // FEATURE 2 STATE: Collapsible Sidebar Feed
  // =================================================================
  const [showActivityFeed, setShowActivityFeed] = useState<boolean>(false);
  const [activities, setActivities] = useState<ActivityEvent[]>([]);

  // =================================================================
  // FEATURE 4 STATE: Theme Accent Toggle (Purely Cosmetic)
  // =================================================================
  const [accentTheme, setAccentTheme] = useState<'cosmic' | 'aurora'>('cosmic');

  // =================================================================
  // FEATURE 5 STATE: Keyboard Shortcuts help overlay
  // =================================================================
  const [showShortcutsHelp, setShowShortcutsHelp] = useState<boolean>(false);

  // Load count of stars and calculate stats on mount
  useEffect(() => {
    fetch('/api/sky-map-stars')
      .then(res => res.json())
      .then((data: any[]) => {
        setStarsData(data);
        setStarCount(data.length);
        if (data.length > 0 && !data.some(d => d.id === selectedStarId)) {
          setSelectedStarId(data.some(d => d.id === '451598465') ? '451598465' : data[0].id);
        }
      })
      .catch(() => {});

    // Initialize activities list
    setActivities(getRecentActivity());
  }, []);

  // Animate stats values on mount or whenever stars data is updated
  useEffect(() => {
    if (starsData.length === 0) return;
    const total = starsData.length;
    const exoplanets = starsData.filter(s => s.classification === 'Exoplanet').length;
    const avgConf = Math.round((starsData.reduce((sum, s) => sum + s.confidence, 0) / total) * 100);

    // Animate total targets
    let c1 = 0;
    const t1 = setInterval(() => {
      c1 += 1;
      setAnimatedTargets(c1);
      if (c1 >= total) clearInterval(t1);
    }, Math.max(12, 1000 / total));

    // Animate exoplanets
    let c2 = 0;
    const t2 = setInterval(() => {
      c2 += 1;
      setAnimatedExoplanets(c2);
      if (c2 >= exoplanets) clearInterval(t2);
    }, Math.max(12, 1000 / exoplanets));

    // Animate average confidence score
    let c3 = 0;
    const t3 = setInterval(() => {
      c3 += 1;
      setAnimatedConfidence(c3);
      if (c3 >= avgConf) clearInterval(t3);
    }, 10);

    return () => {
      clearInterval(t1);
      clearInterval(t2);
      clearInterval(t3);
    };
  }, [starsData]);

  // =================================================================
  // FEATURE 5 INTERACTION: Keyboard Shortcuts implementation
  // =================================================================
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore shortcut trigger keys if the user is typing in form inputs
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        if (e.key === 'Escape') {
          e.target.blur();
        }
        return;
      }

      if (e.key === '/') {
        e.preventDefault();
        const searchInput = document.querySelector('input[type="text"]') as HTMLInputElement;
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      } else if (e.key === '1') {
        setActiveTab('viewer');
      } else if (e.key === '2') {
        setActiveTab('skymap');
      } else if (e.key === '3') {
        setActiveTab('queue');
      } else if (e.key === '?' || e.key === 'h' || e.key === 'H') {
        setShowShortcutsHelp(prev => !prev);
      } else if (e.key === 'Escape') {
        setShowShortcutsHelp(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSelectStar = (ticId: string) => {
    setSelectedStarId(ticId);
    setActiveTab('viewer'); // Navigate to detail view
    // Log target selection activity dynamically
    setActivities(prev => [
      { time: new Date().toTimeString().split(' ')[0].slice(0, 5), msg: `Selected star TIC ${ticId} for review`, type: 'system' },
      ...prev
    ]);
  };

  return (
    <ToastStack>
    <div className={`min-h-screen bg-[#030712] text-slate-100 font-sans cosmic-grid flex flex-col scrollbar-accent ${accentTheme === 'aurora' ? 'theme-aurora' : ''}`}>
      {/* ---------------------------------------------------------
          Navbar / Header
          --------------------------------------------------------- */}
      <header className="border-b border-slate-800/80 bg-[#070b19]/60 backdrop-blur-md sticky top-0 z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
          {/* Brand/Title */}
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-accent-light rounded-lg border border-accent-light shadow-accent animate-pulse">
              <Orbit className="h-6 w-6 text-accent" />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl font-black tracking-widest uppercase bg-gradient-to-r accent-gradient-text bg-clip-text text-transparent font-heading">
                TESS Exoplanet Explorer
              </h1>
              <p className="text-[10px] text-slate-400 font-semibold tracking-wider uppercase mt-0.5">
                NASA Transit Photometry Analysis Workspace
              </p>
            </div>
          </div>

          {/* System/Telemetry Badges & Controls */}
          <div className="flex flex-wrap gap-3 items-center">
            {/* FEATURE 4 COMPONENT: Theme Accent Color Toggle */}
            <button 
              onClick={() => setAccentTheme(prev => prev === 'cosmic' ? 'aurora' : 'cosmic')}
              title="Change Cosmetic Color Theme"
              className="flex items-center gap-1.5 px-3 py-1 bg-[#020617]/50 rounded-full border border-slate-800/60 text-xs text-slate-400 hover:text-accent border-accent-light-hover transition-all cursor-pointer"
            >
              <Palette className="h-3.5 w-3.5 text-accent" />
              <span>Theme:</span>
              <strong className="text-accent font-semibold capitalize font-mono">
                {accentTheme === 'cosmic' ? 'Cosmic' : 'Aurora'}
              </strong>
            </button>

            {/* Collapsible Activity Feed Trigger Toggle */}
            <button 
              onClick={() => setShowActivityFeed(prev => !prev)}
              className={`flex items-center gap-1.5 px-3 py-1 bg-[#020617]/50 rounded-full border border-slate-800/60 text-xs text-slate-400 hover:text-accent transition-all cursor-pointer ${showActivityFeed ? 'border-accent text-accent' : ''}`}
            >
              <Activity className="h-3.5 w-3.5" />
              <span>Activity Log</span>
            </button>

            <div className="flex items-center gap-1.5 px-3 py-1 bg-[#020617]/50 rounded-full border border-slate-800/60 text-xs">
              <Database className="h-3.5 w-3.5 text-cyan-400" />
              <span className="text-slate-400">Preloaded:</span>
              <strong className="text-cyan-400 font-mono">{starCount || 'Loading...'}</strong>
            </div>

            <div className="flex items-center gap-1.5 px-3 py-1 bg-[#020617]/50 rounded-full border border-slate-800/60 text-xs">
              <Cpu className="h-3.5 w-3.5 text-accent-glow" />
              <span className="text-slate-400">Classifier:</span>
              <strong className="text-accent-glow uppercase font-mono">1D CNN v1.0</strong>
            </div>

            <div className="flex items-center gap-1.5 px-3.5 py-1 bg-emerald-500/5 rounded-full border border-emerald-500/20 text-xs">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping inline-block" />
              <span className="text-emerald-400 font-semibold tracking-wider">PIPELINE READY</span>
            </div>
          </div>
        </div>
      </header>

      {/* =================================================================
          FEATURE 1: LIVE STATS BAR
          Placed below the header with animated number count-ups on load
          ================================================================= */}
      <section className="bg-[#0b0f1e]/40 border-b border-slate-800/60 py-3.5 px-6 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-8 items-center text-center md:text-left">
          <div className="flex items-center gap-3 justify-center md:justify-start">
            <Database className="h-4.5 w-4.5 text-accent animate-pulse" />
            <div>
              <span className="text-[10px] text-slate-500 block uppercase font-mono tracking-wider">Targets Mapped</span>
              <strong className="text-md md:text-lg text-slate-100 font-bold font-mono transition-all">
                {animatedTargets}
              </strong>
            </div>
          </div>
          <div className="flex items-center gap-3 justify-center md:justify-start">
            <Orbit className="h-4.5 w-4.5 text-emerald-400 animate-spin" style={{ animationDuration: '6s' }} />
            <div>
              <span className="text-[10px] text-slate-500 block uppercase font-mono tracking-wider">Candidates Found</span>
              <strong className="text-md md:text-lg text-slate-100 font-bold font-mono">
                {animatedExoplanets}
              </strong>
            </div>
          </div>
          <div className="flex items-center gap-3 justify-center md:justify-start">
            <TrendingUp className="h-4.5 w-4.5 text-cyan-400" />
            <div>
              <span className="text-[10px] text-slate-500 block uppercase font-mono tracking-wider">Avg AI Confidence</span>
              <strong className="text-md md:text-lg text-slate-100 font-bold font-mono">
                {animatedConfidence}%
              </strong>
            </div>
          </div>
          <div className="flex items-center gap-3 justify-center md:justify-start">
            <Clock className="h-4.5 w-4.5 text-indigo-400" />
            <div>
              <span className="text-[10px] text-slate-500 block uppercase font-mono tracking-wider">Last Pipeline Run</span>
              <strong className="text-xs md:text-sm text-indigo-300 font-bold font-mono">
                {lastDectectRun}
              </strong>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------
          Main Layout Dashboard
          --------------------------------------------------------- */}
      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 relative">
        <div className="flex flex-col lg:flex-row gap-6 items-start">
          
          {/* Main workspace container */}
          <div className="flex-1 w-full space-y-6">
            {/* Intro Block / Mission Status banner */}
            <div className="p-6 rounded-xl border border-slate-850 bg-gradient-to-r from-[#0b0c16]/80 via-[#070913]/90 to-[#02050c]/80 backdrop-blur-md relative overflow-hidden flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
              <div className="absolute right-0 top-0 h-40 w-40 bg-accent-light rounded-full blur-3xl pointer-events-none" />
              <div className="absolute left-1/3 bottom-0 h-24 w-24 bg-cyan-500/5 rounded-full blur-2xl pointer-events-none" />
              
              <div className="space-y-1 z-10">
                <h2 className="text-lg font-bold text-slate-100 tracking-wide flex items-center gap-2">
                  <Zap className="h-4 w-4 text-accent" />
                  Mission Control Dashboard
                </h2>
                <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
                  Interact with astronomical TESS photometry light curves from the target selection catalog. Run the Box Least Squares (BLS) periodogram transit-hunter and Convolutional Neural Networks on-demand to identify potential exoplanetary transit candidates.
                </p>
              </div>

              <div className="flex gap-4 w-full md:w-auto shrink-0 z-10">
                <div className="flex-1 p-3 bg-[#020617]/50 rounded-lg border border-slate-800/40 text-center min-w-[100px]">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Cadence</span>
                  <strong className="text-xs text-accent font-semibold font-mono">120s (SPOC)</strong>
                </div>
                <div className="flex-1 p-3 bg-[#020617]/50 rounded-lg border border-slate-800/40 text-center min-w-[100px]">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Sectors</span>
                  <strong className="text-xs text-accent font-semibold font-mono">Multi-Sector</strong>
                </div>
              </div>
            </div>

            {/* Tab switch Navigation bar */}
            <div className="flex border-b border-slate-800/80">
              <button 
                className={`px-6 py-3 text-xs sm:text-sm font-black uppercase tracking-wider border-b-2 flex items-center gap-2 transition-all ${
                  activeTab === 'viewer' 
                    ? 'border-accent text-accent font-heading bg-accent-light shadow-[inset_0_-2px_0_rgb(var(--accent-color))]' 
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
                onClick={() => setActiveTab('viewer')}
              >
                <Activity className="h-4 w-4" />
                Light Curve Viewer <span className="text-[10px] text-slate-500 font-mono hidden md:inline ml-1">(Key: 1)</span>
              </button>
              <button 
                className={`px-6 py-3 text-xs sm:text-sm font-black uppercase tracking-wider border-b-2 flex items-center gap-2 transition-all ${
                  activeTab === 'skymap' 
                    ? 'border-accent text-accent font-heading bg-accent-light shadow-[inset_0_-2px_0_rgb(var(--accent-color))]' 
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
                onClick={() => setActiveTab('skymap')}
              >
                <Compass className="h-4 w-4" />
                Southern Sky Map <span className="text-[10px] text-slate-500 font-mono hidden md:inline ml-1">(Key: 2)</span>
              </button>
              <button 
                className={`px-6 py-3 text-xs sm:text-sm font-black uppercase tracking-wider border-b-2 flex items-center gap-2 transition-all ${
                  activeTab === 'queue' 
                    ? 'border-accent text-accent font-heading bg-accent-light shadow-[inset_0_-2px_0_rgb(var(--accent-color))]' 
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
                onClick={() => setActiveTab('queue')}
              >
                <ListTodo className="h-4 w-4" />
                Priority Queue <span className="text-[10px] text-slate-500 font-mono hidden md:inline ml-1">(Key: 3)</span>
              </button>
            </div>

            {/* Tab views — key forces remount on switch, animate-in gives fade+slide */}
            <div key={activeTab} className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
              {activeTab === 'viewer' ? (
                <LightCurveViewer 
                  selectedStarId={selectedStarId} 
                  onSelectStar={setSelectedStarId} 
                />
              ) : activeTab === 'skymap' ? (
                <SkyMap onSelectStar={handleSelectStar} />
              ) : (
                <PriorityQueue onSelectStar={handleSelectStar} />
              )}
            </div>
          </div>

          {/* =================================================================
              FEATURE 2 COMPONENT: Collapsible sidebar for recent actions
              ================================================================= */}
          {showActivityFeed && (
            <aside className="w-full lg:w-80 bg-[#070b19]/90 border border-slate-800 rounded-xl p-4 space-y-4 shadow-2xl shrink-0 backdrop-blur-md animate-in slide-in-from-right duration-300">
              <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-200 uppercase tracking-wider">
                  <Activity className="h-4 w-4 text-accent" />
                  Recent Vetting Activity
                </div>
                <button 
                  onClick={() => setShowActivityFeed(false)}
                  className="p-1 hover:text-white text-slate-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-3.5 max-h-[500px] overflow-y-auto pr-1.5 scrollbar-accent">
                {activities.map((act, index) => (
                  <div key={index} className="flex gap-2.5 items-start text-xs border-b border-slate-900/60 pb-3 last:border-0 last:pb-0">
                    <span className="font-mono text-slate-500 bg-[#020617]/80 px-1.5 py-0.5 rounded text-[10px]">
                      {act.time}
                    </span>
                    <div className="flex-1 space-y-0.5">
                      <p className="text-slate-300 font-medium leading-relaxed">{act.msg}</p>
                      <span className={`text-[9px] uppercase tracking-wider font-semibold font-mono ${
                        act.type === 'classifier' ? 'text-emerald-400' :
                        act.type === 'habitability' ? 'text-amber-400' :
                        act.type === 'api' ? 'text-cyan-400' : 'text-slate-500'
                      }`}>
                        :: {act.type}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </aside>
          )}

        </div>
      </main>

      {/* ---------------------------------------------------------
          Footer
          --------------------------------------------------------- */}
      <footer className="border-t border-slate-850 bg-[#02050c]/80 py-6 px-6 text-xs text-slate-500 mt-12">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 text-center md:text-left">
          <div className="space-y-1">
            <p>
              🔭 <strong>TESS Transit Detection Pipeline Dashboard</strong> &copy; 2026.
            </p>
            <p className="text-slate-600">
              Photometric dataset sourced from NASA Transiting Exoplanet Survey Satellite (TESS) SPOC catalog.
            </p>
          </div>
          <div className="flex gap-6 text-slate-400">
            <a href="https://heasarc.gsfc.nasa.gov/docs/tess/primary-science.html" target="_blank" rel="noopener noreferrer" className="hover:text-indigo-400 flex items-center gap-1 transition-all">
              <FileText className="h-3.5 w-3.5" />
              TESS Science
            </a>
            <a href="https://github.com/kanishkaaa13/The-Transit-Detection-" target="_blank" rel="noopener noreferrer" className="hover:text-indigo-400 flex items-center gap-1 transition-all">
              <Cpu className="h-3.5 w-3.5" />
              ML Pipeline Code
            </a>
          </div>
        </div>
      </footer>

      {/* =================================================================
          FEATURE 5 COMPONENT: Keyboard shortcuts overlay & floating trigger button
          ================================================================= */}
      <div className="fixed bottom-6 right-6 flex items-center gap-2 z-50">
        <button 
          onClick={() => setShowShortcutsHelp(prev => !prev)}
          title="Keyboard Shortcuts Guide"
          className="p-2.5 bg-[#070b19] border border-slate-800 text-slate-400 hover:text-accent rounded-full shadow-2xl hover:scale-105 transition-all cursor-pointer glow-accent-purple"
        >
          <Keyboard className="h-4.5 w-4.5" />
        </button>
      </div>

      {showShortcutsHelp && (
        <div className="fixed inset-0 bg-[#020617]/75 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-[#0f172a] border border-slate-800 max-w-sm w-full rounded-xl p-5 shadow-2xl space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 uppercase tracking-wider">
                <HelpCircle className="h-4.5 w-4.5 text-accent" />
                Keyboard Shortcuts Guide
              </h3>
              <button 
                onClick={() => setShowShortcutsHelp(false)}
                className="p-1 hover:text-white text-slate-500 transition-colors"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            
            <div className="space-y-3 text-xs">
              <div className="flex justify-between items-center py-1.5 border-b border-slate-900/60">
                <span className="text-slate-400">Focus Target Search Input</span>
                <kbd className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-[10px] text-accent font-mono">/</kbd>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-900/60">
                <span className="text-slate-400">Switch to Light Curve Viewer</span>
                <kbd className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-[10px] text-accent font-mono">1</kbd>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-900/60">
                <span className="text-slate-400">Switch to Southern Sky Map</span>
                <kbd className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-[10px] text-accent font-mono">2</kbd>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-900/60">
                <span className="text-slate-400">Switch to Priority Queue</span>
                <kbd className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-[10px] text-accent font-mono">3</kbd>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-900/60">
                <span className="text-slate-400">Toggle Shortcuts Guide</span>
                <kbd className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-[10px] text-accent font-mono">?</kbd>
              </div>
              <div className="flex justify-between items-center py-1.5">
                <span className="text-slate-400">Close Overlay / Blur input</span>
                <kbd className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-[10px] text-accent font-mono">ESC</kbd>
              </div>
            </div>

            <p className="text-[10px] text-slate-500 italic text-center pt-2">
              Press any shortcut key when not typing in search boxes to navigate instantly.
            </p>
          </div>
        </div>
      )}

    </div>
    </ToastStack>
  );
}

export default App;
