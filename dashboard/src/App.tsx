import { useState, useEffect } from 'react';
import { LightCurveViewer } from './components/LightCurveViewer';
import { 
  Orbit, 
  Database, 
  Zap, 
  Cpu, 
  FileText
} from 'lucide-react';

function App() {
  const [starCount, setStarCount] = useState<number>(0);

  // Load count of stars from api list to show on top
  useEffect(() => {
    fetch('/api/tic-ids')
      .then(res => res.json())
      .then(ids => {
        setStarCount(ids.length);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 font-sans cosmic-grid flex flex-col">
      {/* ---------------------------------------------------------
          Navbar / Header
          --------------------------------------------------------- */}
      <header className="border-b border-slate-800/80 bg-[#070b19]/60 backdrop-blur-md sticky top-0 z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
          {/* Brand/Title */}
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-500/10 rounded-lg border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)] animate-pulse">
              <Orbit className="h-6 w-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl font-black tracking-widest uppercase bg-gradient-to-r from-indigo-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent font-heading">
                TESS Exoplanet Explorer
              </h1>
              <p className="text-[10px] text-slate-400 font-semibold tracking-wider uppercase mt-0.5">
                NASA Transit Photometry Analysis Workspace
              </p>
            </div>
          </div>

          {/* System/Telemetry Badges */}
          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex items-center gap-1.5 px-3 py-1 bg-[#020617]/50 rounded-full border border-slate-800/60 text-xs">
              <Database className="h-3.5 w-3.5 text-cyan-400" />
              <span className="text-slate-400">Preloaded Targets:</span>
              <strong className="text-cyan-400 font-mono">{starCount || 'Loading...'}</strong>
            </div>

            <div className="flex items-center gap-1.5 px-3 py-1 bg-[#020617]/50 rounded-full border border-slate-800/60 text-xs">
              <Cpu className="h-3.5 w-3.5 text-purple-400" />
              <span className="text-slate-400">Classifier:</span>
              <strong className="text-purple-400 uppercase font-mono">1D CNN v1.0</strong>
            </div>

            <div className="flex items-center gap-1.5 px-3.5 py-1 bg-emerald-500/5 rounded-full border border-emerald-500/20 text-xs">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping inline-block" />
              <span className="text-emerald-400 font-semibold tracking-wider">PIPELINE READY</span>
            </div>
          </div>
        </div>
      </header>

      {/* ---------------------------------------------------------
          Main Layout Dashboard
          --------------------------------------------------------- */}
      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
        
        {/* Intro Block / Mission Status banner */}
        <div className="mb-8 p-6 rounded-xl border border-slate-850 bg-gradient-to-r from-[#0b0c16]/80 via-[#070913]/90 to-[#02050c]/80 backdrop-blur-md relative overflow-hidden flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="absolute right-0 top-0 h-40 w-40 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute left-1/3 bottom-0 h-24 w-24 bg-cyan-500/5 rounded-full blur-2xl pointer-events-none" />
          
          <div className="space-y-1 z-10">
            <h2 className="text-lg font-bold text-slate-100 tracking-wide flex items-center gap-2">
              <Zap className="h-4 w-4 text-indigo-400" />
              Mission Control Dashboard
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
              Interact with astronomical TESS photometry light curves from the target selection catalog. Run the Box Least Squares (BLS) periodogram transit-hunter and Convolutional Neural Networks on-demand to identify potential exoplanetary transit candidates.
            </p>
          </div>

          <div className="flex gap-4 w-full md:w-auto shrink-0 z-10">
            <div className="flex-1 p-3 bg-[#020617]/50 rounded-lg border border-slate-800/40 text-center min-w-[100px]">
              <span className="text-[10px] text-slate-400 block mb-0.5">Cadence</span>
              <strong className="text-xs text-indigo-300 font-semibold font-mono">120s (SPOC)</strong>
            </div>
            <div className="flex-1 p-3 bg-[#020617]/50 rounded-lg border border-slate-800/40 text-center min-w-[100px]">
              <span className="text-[10px] text-slate-400 block mb-0.5">Sectors</span>
              <strong className="text-xs text-indigo-300 font-semibold font-mono">Multi-Sector</strong>
            </div>
          </div>
        </div>

        {/* Mounted Light Curve Viewer component */}
        <LightCurveViewer />

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
    </div>
  );
}

export default App;
