import { useState, useEffect } from 'react';
import { apiPath } from '../config';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import {
  TrendingUp,
  X,
  BarChart3,
  Shield,
  Layers,
} from 'lucide-react';

interface PerClassMetrics {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

interface ModelPerformanceData {
  model_type: string;
  dataset_size: number;
  num_classes: number;
  class_names: string[];
  cross_validation: {
    folds: number;
    weighted_f1: number;
    overall_accuracy: number;
    per_class: Record<string, PerClassMetrics>;
    confusion_matrix: number[][];
  };
  held_out_test: {
    test_size: number;
    test_accuracy: number;
    test_weighted_f1: number;
    per_class: Record<string, PerClassMetrics>;
  };
}

const CLASS_COLORS: Record<string, string> = {
  Planet: '#22d3ee',
  EB: '#f97316',
  Blend: '#a78bfa',
  Noise: '#64748b',
  FP: '#f43f5e',
};

function getF1ColorClass(f1: number): string {
  const pct = f1 * 100;
  if (pct > 80) return 'text-emerald-400';
  if (pct >= 50) return 'text-amber-400';
  return 'text-rose-455'; // vibrant rose-500 equivalent color class (text-rose-500 or text-rose-400)
}

function getF1HexColor(f1: number): string {
  const pct = f1 * 100;
  if (pct > 80) return '#34d399'; // emerald-400
  if (pct >= 50) return '#fbbf24'; // amber-400
  return '#f43f5e'; // rose-500
}

export function ModelPerformancePanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState<ModelPerformanceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || data) return;
    setLoading(true);

    // Try the API first, then fall back to static JSON in /public
    const fetchUrl = apiPath('/api/model-performance');
    const staticUrl = '/model_performance.json';

    fetch(fetchUrl)
      .then((res) => {
        if (!res.ok) throw new Error('api');
        return res.json();
      })
      .catch(() => fetch(staticUrl).then((r) => r.json()))
      .then((json: ModelPerformanceData) => {
        setData(json);
        setError(null);
      })
      .catch(() => setError('Run stage4_evaluate.py to generate metrics.'))
      .finally(() => setLoading(false));
  }, [isOpen, data]);

  // Bar chart data
  const barData =
    data?.cross_validation?.per_class
      ? Object.entries(data.cross_validation.per_class).map(([cls, m]) => ({
          name: cls,
          F1: Math.round(m.f1 * 1000) / 10,
          Precision: Math.round(m.precision * 1000) / 10,
          Recall: Math.round(m.recall * 1000) / 10,
        }))
      : [];

  return (
    <>
      {/* Trigger button — subtle pill in the header area */}
      <button
        id="model-performance-trigger"
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-1.5 px-3 py-1 bg-[#020617]/50 rounded-full border border-slate-800/60 text-xs text-slate-400 hover:text-accent border-accent-light-hover transition-all cursor-pointer"
      >
        <BarChart3 className="h-3.5 w-3.5 text-emerald-400" />
        <span>Model Metrics</span>
      </button>

      {/* Modal overlay */}
      {isOpen && (
        <div className="fixed inset-0 bg-[#020617]/80 backdrop-blur-sm z-[998] flex items-center justify-center p-4">
          <div
            className="bg-[#0b0f1e] border border-slate-800 max-w-2xl w-full max-h-[90vh] flex flex-col rounded-2xl shadow-2xl overflow-hidden animate-in fade-in-0 zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-gradient-to-r from-[#0b0f1e] via-[#111827] to-[#0b0f1e] shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
                  <Shield className="h-5 w-5 text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                    Stage 4 Model Performance
                  </h3>
                  <p className="text-[10px] text-slate-500 font-mono">
                    {data ? `${data.model_type} · ${data.dataset_size.toLocaleString()} samples · 5-Fold Stratified CV` : 'Loading...'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 hover:text-white text-slate-500 transition-colors rounded-lg hover:bg-slate-800/60 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-5 space-y-5 flex-1 overflow-y-auto scrollbar-accent">
              {loading && (
                <div className="text-center py-10">
                  <div className="animate-spin h-8 w-8 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto mb-3" />
                  <p className="text-xs text-slate-400">Loading evaluation metrics...</p>
                </div>
              )}

              {error && (
                <div className="text-center py-10">
                  <p className="text-xs text-rose-400">{error}</p>
                </div>
              )}

              {data && !loading && (() => {
                const totalSupport = Object.values(data.cross_validation.per_class).reduce((sum, m) => sum + m.support, 0);
                const weightedAvgF1 = totalSupport > 0 
                  ? Object.values(data.cross_validation.per_class).reduce((sum, m) => sum + (m.f1 * m.support), 0) / totalSupport
                  : 0;

                return (
                  <>
                    {/* Label above metrics panel */}
                    <div className="text-[11px] text-slate-400 font-semibold bg-slate-900/60 border border-slate-800/80 px-3 py-2 rounded-lg inline-block w-full text-center">
                      5-Fold Cross-Validation on TOI Catalog Training Set
                    </div>

                    {/* ── KPI Cards ── */}
                    <div className="grid grid-cols-3 gap-3">
                      <div className="p-4 bg-[#020617]/60 rounded-xl border border-slate-800/50 text-center">
                        <span className="text-[10px] text-slate-500 block uppercase tracking-wider font-mono mb-1">
                          CV Accuracy
                        </span>
                        <strong className="text-2xl font-black text-emerald-400 font-mono">
                          {(data.cross_validation.overall_accuracy * 100).toFixed(1)}%
                        </strong>
                      </div>
                      <div className="p-4 bg-[#020617]/60 rounded-xl border border-slate-800/50 text-center">
                        <span className="text-[10px] text-slate-500 block uppercase tracking-wider font-mono mb-1">
                          Weighted F1
                        </span>
                        <strong className="text-2xl font-black text-cyan-400 font-mono">
                          {(data.cross_validation.weighted_f1 * 100).toFixed(1)}%
                        </strong>
                      </div>
                      <div className="p-4 bg-[#020617]/60 rounded-xl border border-slate-800/50 text-center">
                        <span className="text-[10px] text-slate-500 block uppercase tracking-wider font-mono mb-1">
                          Test Accuracy
                        </span>
                        <strong className="text-2xl font-black text-amber-400 font-mono">
                          {(data.held_out_test.test_accuracy * 100).toFixed(1)}%
                        </strong>
                      </div>
                    </div>

                    {/* ── Per-class F1 Bar Chart ── */}
                    <div className="bg-[#020617]/40 rounded-xl border border-slate-800/40 p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <TrendingUp className="h-4 w-4 text-accent" />
                        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                          Per-Class F1 Scores
                        </span>
                      </div>
                      <div className="h-52">
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart data={barData} barCategoryGap="20%">
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis
                              dataKey="name"
                              tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 700 }}
                              axisLine={{ stroke: '#334155' }}
                            />
                            <YAxis
                              domain={[0, 100]}
                              tick={{ fill: '#94a3b8', fontSize: 10 }}
                              axisLine={{ stroke: '#334155' }}
                              tickFormatter={(v: number) => `${v}%`}
                            />
                            <Tooltip
                              contentStyle={{
                                background: '#0f172a',
                                border: '1px solid #334155',
                                borderRadius: 8,
                                fontSize: 11,
                              }}
                              formatter={(value: any) => [`${value}%`]}
                            />
                            <Bar dataKey="F1" radius={[6, 6, 0, 0]} maxBarSize={40}>
                              {barData.map((entry) => (
                                <Cell
                                  key={entry.name}
                                  fill={getF1HexColor(entry.F1 / 100)}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* ── Per-class detail table ── */}
                    <div className="space-y-2.5">
                      <div className="bg-[#020617]/40 rounded-xl border border-slate-800/40 overflow-hidden">
                        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800/40">
                          <Layers className="h-4 w-4 text-accent" />
                          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                            Per-Class Metrics (5-Fold CV)
                          </span>
                        </div>
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-slate-500 uppercase tracking-wider border-b border-slate-800/40">
                              <th className="text-left px-4 py-2.5 font-semibold">Class</th>
                              <th className="text-right px-4 py-2.5 font-semibold">Precision</th>
                              <th className="text-right px-4 py-2.5 font-semibold">Recall</th>
                              <th className="text-right px-4 py-2.5 font-semibold">F1</th>
                              <th className="text-right px-4 py-2.5 font-semibold">Support</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(data.cross_validation.per_class).map(([cls, m]) => (
                              <tr
                                key={cls}
                                className="border-b border-slate-900/40 last:border-0 hover:bg-slate-800/20 transition-colors"
                              >
                                <td className="px-4 py-2.5 font-bold" style={{ color: CLASS_COLORS[cls] || '#e2e8f0' }}>
                                  {cls}
                                </td>
                                <td className="text-right px-4 py-2.5 text-slate-300 font-mono">
                                  {(m.precision * 100).toFixed(1)}%
                                </td>
                                <td className="text-right px-4 py-2.5 text-slate-300 font-mono">
                                  {(m.recall * 100).toFixed(1)}%
                                </td>
                                <td className={`text-right px-4 py-2.5 font-mono font-bold ${getF1ColorClass(m.f1)}`}>
                                  {(m.f1 * 100).toFixed(1)}%
                                </td>
                                <td className="text-right px-4 py-2.5 text-slate-400 font-mono">
                                  {m.support.toLocaleString()}
                                </td>
                              </tr>
                            ))}
                            {/* Weighted average F1 row */}
                            <tr className="border-t border-slate-800 bg-[#020617]/50 font-semibold text-slate-200">
                              <td className="px-4 py-2.5 font-bold">Weighted Average</td>
                              <td className="text-right px-4 py-2.5 font-mono text-slate-500">-</td>
                              <td className="text-right px-4 py-2.5 font-mono text-slate-500">-</td>
                              <td className={`text-right px-4 py-2.5 font-mono font-bold ${getF1ColorClass(weightedAvgF1)}`}>
                                {(weightedAvgF1 * 100).toFixed(1)}%
                              </td>
                              <td className="text-right px-4 py-2.5 text-slate-300 font-mono">
                                {totalSupport.toLocaleString()}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      {/* Class imbalance note below the table */}
                      <p className="text-[10px] text-amber-500/90 bg-amber-500/5 border border-amber-500/10 rounded-lg p-2.5 flex items-start gap-1.5 leading-relaxed font-sans">
                        <span className="text-xs leading-none mt-0.5 shrink-0">⚠</span>
                        <span>
                          <strong>Class imbalance detected:</strong> Blend class has 53x more training examples than Noise. Consider SMOTE oversampling or class weights in next training iteration.
                        </span>
                      </p>
                    </div>

                    {/* ── Confusion Matrix Image ── */}
                    <div className="bg-[#020617]/40 rounded-xl border border-slate-800/40 p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <BarChart3 className="h-4 w-4 text-accent" />
                        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                          Confusion Matrix (5-Fold CV)
                        </span>
                      </div>
                      <div className="flex justify-center">
                        <img
                          src="/confusion_matrix.png"
                          alt="Confusion Matrix Heatmap"
                          className="max-w-full rounded-lg border border-slate-800/40"
                          style={{ maxHeight: 380 }}
                        />
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
