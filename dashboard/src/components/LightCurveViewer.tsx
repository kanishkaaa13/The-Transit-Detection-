import React, { useState, useEffect, useRef } from 'react';
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
  AlertTriangle, 
  Activity, 
  RefreshCw, 
  BarChart2, 
  Compass,
  Globe,
  Sun,
  FileText,
  MessageSquare,
  X,
  Send,
  Sparkles,
  CheckCircle2,
  XCircle
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
  // Extended fields
  snr: number;
  rPlanet: number;
  distance: number;
  stellarAge: number;
  inHabitableZone: boolean;
  planetType: string;
}

// Simple planet type classification stub
export function getPlanetTypeLabel(
  classification: string,
  rPlanet: number,
  period: number
): string {
  if (classification !== 'Exoplanet') {
    if (classification === 'Binary Star') return 'Eclipsing Binary';
    if (classification === 'Stellar Blend') return 'Background Blend';
    if (classification === 'Starspot') return 'Stellar Spot Activity';
    return 'Stellar Signal';
  }
  
  if (rPlanet >= 8) {
    if (period < 10) return 'Hot Jupiter';
    return 'Cold Gas Giant';
  }
  if (rPlanet >= 3.0 && rPlanet < 8.0) {
    if (period < 15) return 'Hot Neptune';
    return 'Warm Sub-Neptune';
  }
  if (rPlanet >= 1.25 && rPlanet < 3.0) {
    return 'Super-Earth';
  }
  return 'Terrestrial (Rocky)';
}

// Paragraph template summary generator stub
export function generateSummary(data: DetectionResult, ticId: string): string {
  const {
    event,
    classification,
    confidence,
    period,
    depth,
    duration,
    snr,
    rPlanet,
    distance,
    stellarAge,
    inHabitableZone,
    planetType
  } = data;

  const confPercent = (confidence * 100).toFixed(1);
  const depthPpm = (depth * 1e6).toFixed(0);
  const depthPercent = (depth * 100).toFixed(4);

  if (classification === 'Exoplanet') {
    const hzText = inHabitableZone 
      ? "crucially lies within the host star's habitable zone (HZ), suggesting surface temperatures compatible with liquid water"
      : "orbits outside the host star's liquid-water habitable zone boundary";

    return `Target system designation ${event} (TIC ${ticId}) displays a high-confidence (${confPercent}%) periodic transit signal characteristic of a transiting exoplanet. The Box Least Squares (BLS) periodogram solver resolves an orbital period of ${period.toFixed(4)} days, with an observed transit event duration of ${duration.toFixed(2)} hours. The transit signal exhibits a depth of ${depthPercent}% (${depthPpm} ppm), indicating a stellar radius occlusion corresponds to an estimated planet radius of ${rPlanet.toFixed(2)} Earth radii (R⊕). This physical size classifies the candidate body as a "${planetType}". The signal exhibits a strong empirical Signal-to-Noise Ratio (SNR) of ${snr.toFixed(1)}. Located at a distance of ${distance.toFixed(1)} light-years from Earth, the host stellar system has an estimated age of ${stellarAge.toFixed(1)} Gyr. The candidate planet ${hzText}, representing a high-priority target for post-detection radial velocity follow-ups and transmission spectroscopy modeling.`;
  }

  if (classification === 'Binary Star') {
    return `Stellar target TIC ${ticId} displays a deep periodic eclipse signature classified with ${confPercent}% confidence as an eclipsing binary system. The eclipse signal features an orbital period of ${period.toFixed(4)} days and a duration of ${duration.toFixed(2)} hours, with a primary transit depth of ${depthPercent}% (${depthPpm} ppm). The massive signal occlusion and high SNR of ${snr.toFixed(1)} suggests mutual eclipse events between stellar companions. The system lies at a distance of ${distance.toFixed(1)} light-years with a stellar age of ${stellarAge.toFixed(1)} Gyr. This stellar-origin eclipsing signature is excluded from the planetary target catalog candidate list.`;
  }

  if (classification === 'Starspot') {
    return `Target TIC ${ticId} exhibits long-term sinusoidal flux modulations with an estimated period of ${period.toFixed(4)} days and transit-like depths of ${depthPercent}% (${depthPpm} ppm), resolved at a confidence level of ${confPercent}%. This variation is classified as stellar active starspot rotation. The host star, located at a distance of ${distance.toFixed(1)} light-years and aged approximately ${stellarAge.toFixed(1)} Gyr, exhibits high chromospheric activity. This rotational signature has been flagged to prevent false-alarm planetary transit detections.`;
  }

  // Stellar Blend or other
  return `Photometric analysis of TIC ${ticId} indicates a periodic signal with a period of ${period.toFixed(4)} days, transit duration of ${duration.toFixed(2)} hours, and depth of ${depthPercent}% (${depthPpm} ppm), classified as a background stellar blend with a confidence of ${confPercent}%. The observed SNR is ${snr.toFixed(1)}, located at a distance of ${distance.toFixed(1)} light-years. The signal is likely contaminated by background eclipsing binaries (BEB) or stellar blends within the pixel aperture and is screened out of the exoplanetary catalog.`;
}

// Basic markdown parser
export function renderMessageContent(text: string): React.ReactNode[] {
  return text.split('\n').map((line, i) => {
    const boldRegex = /\*\*(.*?)\*\*/g;
    let match;
    const elements: React.ReactNode[] = [];
    let lastIndex = 0;
    
    while ((match = boldRegex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        elements.push(line.substring(lastIndex, match.index));
      }
      elements.push(<strong key={match.index} className="text-white font-semibold">{match[1]}</strong>);
      lastIndex = boldRegex.lastIndex;
    }
    if (lastIndex < line.length) {
      elements.push(line.substring(lastIndex));
    }
    
    if (line.trim().startsWith('* ')) {
      return (
        <li key={i} className="list-disc ml-4 my-1 pl-1 text-slate-300">
          {elements.length > 0 ? elements : line.substring(2)}
        </li>
      );
    }
    
    return (
      <p key={i} className="mb-2 last:mb-0">
        {elements.length > 0 ? elements : line}
      </p>
    );
  });
}

// AI Chat mock query responder stub
export function askAboutStar(data: DetectionResult | null, question: string, ticId: string): Promise<string> {
  return new Promise((resolve) => {
    setTimeout(() => {
      if (!data) {
        resolve("Please run the 'Detect Signal' pipeline first so I can analyze this star's transit telemetry.");
        return;
      }

      const q = question.toLowerCase();
      
      if (q.includes('habitable') || q.includes('life') || q.includes('hz') || q.includes('liquid')) {
        if (data.inHabitableZone) {
          resolve(`Yes, **TIC ${ticId}** is a highly exciting target! The candidate planet (${data.event}) has an estimated radius of **${data.rPlanet.toFixed(2)} R⊕**, placing it in the **${data.planetType}** regime. 

Most importantly, our classification model determines that its orbit **lies within the habitable zone**. Here are key habitability metrics:
* **Stellar Irradiance Level**: Favorable for liquid surface water templates.
* **Planet Class**: ${data.planetType} (likely rocky cores or gas-dwarf envelopes).
* **SNR**: **${data.snr.toFixed(1)}** (high signal quality for follow-up studies).`);
        } else {
          resolve(`No, the candidate planet **${data.event}** around **TIC ${ticId}** is estimated to orbit **outside the habitable zone** of its host star. 

Given its short orbital period of **${data.period.toFixed(2)} days** and its size (**${data.rPlanet.toFixed(2)} R⊕**), it likely experiences high surface irradiance, placing it in the hot regime (e.g. **${data.planetType}**). It is a valuable target for transit timing variations but not for biosignature detection.`);
        }
      } else if (q.includes('period') || q.includes('orbit') || q.includes('year') || q.includes('days')) {
        resolve(`The resolved orbital period for **TIC ${ticId}** is **${data.period.toFixed(4)} days** (${(data.period * 24).toFixed(1)} hours). 

This is calculated from the periodic dips in the SPOC light curve. The transit itself lasts for approximately **${data.duration.toFixed(2)} hours** each orbit.`);
      } else if (q.includes('size') || q.includes('radius') || q.includes('mass') || q.includes('earth')) {
        if (data.classification === 'Exoplanet') {
          resolve(`The estimated physical radius of this exoplanet candidate is **${data.rPlanet.toFixed(2)} Earth radii (R⊕)**. 

This size is derived from the observed transit depth of **${(data.depth * 100).toFixed(4)}%** (${(data.depth * 1e6).toFixed(0)} ppm) relative to the host star's radius. A depth of this size suggests a **${data.planetType}** classification.`);
        } else {
          resolve(`This target is classified as a **${data.classification}** with **${(data.confidence * 100).toFixed(1)}%** confidence. 

Because it is not classified as a planetary candidate (its deep eclipse depth of **${(data.depth * 100).toFixed(2)}%** indicates stellar occultation), we do not report a planetary radius.`);
        }
      } else if (q.includes('snr') || q.includes('noise') || q.includes('quality')) {
        resolve(`The transit signal for **TIC ${ticId}** exhibits a Signal-to-Noise Ratio (SNR) of **${data.snr.toFixed(1)}**. 

Signals with an SNR above **7.0** are generally considered statistically significant. An SNR of **${data.snr.toFixed(1)}** indicates a highly robust detection, suggesting low instrumental noise during the transit windows.`);
      } else if (q.includes('distance') || q.includes('light-year') || q.includes('where') || q.includes('age')) {
        resolve(`The host star is located at a distance of **${data.distance.toFixed(1)} light-years** from Earth in the TESS Southern Sky Field. 

The star's estimated age is **${data.stellarAge.toFixed(1)} billion years (Gyr)**. This is key context for understanding the evolutionary history and potential stability of any orbiting bodies.`);
      } else {
        // Default generic response
        resolve(`Hello! I'm analyzing the telemetry for **TIC ${ticId}** (classification: **${data.classification}**, confidence: **${(data.confidence * 100).toFixed(1)}%**).

Here is a quick scientific log:
* **Object Name**: ${data.event}
* **Orbital Period**: ${data.period.toFixed(4)} days
* **Transit Depth**: ${(data.depth * 100).toFixed(4)}%
* **Planet Type**: ${data.planetType}
* **Habitability**: ${data.inHabitableZone ? "In Habitable Zone (YES)" : "Outside Habitable Zone (NO)"}

Ask me specific questions about its **habitability**, **size/radius**, **orbital period**, or **distance**!`);
      }
    }, 1000);
  });
}

// AI Reasoning test helper stub
export interface FeatureTest {
  name: string;
  passed: boolean;
  explanation: string;
  importance: number;
}

export interface ReasoningResult {
  rankedFeatures: FeatureTest[];
  summary: string;
}

export function getClassReasoning(data: DetectionResult): ReasoningResult {
  const { classification, rPlanet, depth, snr } = data;
  const depthPercent = (depth * 100).toFixed(4);

  if (classification === 'Exoplanet') {
    return {
      rankedFeatures: [
        {
          name: "R_planet size check",
          passed: true,
          importance: 0.95,
          explanation: `Planet size is ${rPlanet.toFixed(2)} R⊕ — consistent with sub-Neptune/Super-Earth class bounds (excludes massive brown dwarf/star occultations).`
        },
        {
          name: "Secondary eclipse check",
          passed: true,
          importance: 0.88,
          explanation: "No secondary eclipses are resolved above noise threshold — rules out self-luminous binary companions."
        },
        {
          name: "Odd-even depth check",
          passed: true,
          importance: 0.82,
          explanation: "Odd and even transits show matching depths within 1-sigma — excludes alternating eclipsing binaries."
        },
        {
          name: "Depth × (1 + contratio) blend check",
          passed: true,
          importance: 0.70,
          explanation: "Observed depth of " + depthPercent + "% remains consistent with target star dilution limits."
        },
        {
          name: "Density consistency check",
          passed: true,
          importance: 0.65,
          explanation: "Transit duration implies a stellar density matching host star main-sequence properties."
        }
      ],
      summary: `The neural net classified this signal as an Exoplanet candidate because the transit events show high spatial symmetry and zero secondary eclipse dips. The calculated physical size of ${rPlanet.toFixed(2)} R⊕ matches exoplanetary constraints, and the signal SNR of ${snr.toFixed(1)} confirms a significant detection.`
    };
  }

  if (classification === 'Binary Star') {
    return {
      rankedFeatures: [
        {
          name: "Secondary eclipse check",
          passed: false,
          importance: 0.96,
          explanation: "A secondary eclipse event is resolved at phase 0.5 — directly indicates a stellar companion system."
        },
        {
          name: "Odd-even depth check",
          passed: false,
          importance: 0.92,
          explanation: "Odd-even transit depth difference is significant — indicates alternating primary and secondary eclipses."
        },
        {
          name: "R_planet size check",
          passed: false,
          importance: 0.85,
          explanation: "Inferred transit size is too large for planetary boundaries — indicates secondary star radius."
        },
        {
          name: "Depth × (1 + contratio) blend check",
          passed: true,
          importance: 0.50,
          explanation: "Strong, undiluted eclipsing event detected at high SNR."
        },
        {
          name: "Density consistency check",
          passed: false,
          importance: 0.40,
          explanation: "Calculated companion density is typical for M-dwarf or low-mass stellar binaries."
        }
      ],
      summary: `The classifier selected Eclipsing Binary based on the presence of alternating primary and secondary eclipses. The massive companion dimensions exceed exoplanet limits, and a distinct secondary occultation was detected.`
    };
  }

  if (classification === 'Stellar Blend') {
    return {
      rankedFeatures: [
        {
          name: "Depth × (1 + contratio) blend check",
          passed: false,
          importance: 0.94,
          explanation: "Blend check shows high dilution factor — transit signal originates from a diluted background source."
        },
        {
          name: "Density consistency check",
          passed: false,
          importance: 0.70,
          explanation: "Derived stellar density is highly inconsistent with host dwarf parameters."
        },
        {
          name: "R_planet size check",
          passed: false,
          importance: 0.60,
          explanation: "Planetary radius cannot be accurately constrained due to severe background light contamination."
        },
        {
          name: "Secondary eclipse check",
          passed: true,
          importance: 0.55,
          explanation: "No discrete secondary eclipses are resolved within the blended aperture profile."
        },
        {
          name: "Odd-even depth check",
          passed: true,
          importance: 0.50,
          explanation: "Odd/even transit depths are consistent within noise bounds."
        }
      ],
      summary: `Classified as a Stellar Blend. The transit signal suffers from high background light dilution inside the TESS aperture pixel grid. The signal is likely a background binary and has been screened from the exoplanet targets.`
    };
  }

  // Starspot
  return {
    rankedFeatures: [
      {
        name: "Density consistency check",
        passed: false,
        importance: 0.90,
        explanation: "Duration of transit-like dips spans across rotational phases, leading to an anomalous density check."
      },
      {
        name: "R_planet size check",
        passed: false,
        importance: 0.75,
        explanation: "Gradual ingress/egress transit shape is inconsistent with a solid disk occulting the star."
      },
      {
        name: "Secondary eclipse check",
        passed: true,
        importance: 0.65,
        explanation: "No discrete flat-bottomed secondary eclipses are found."
      },
      {
        name: "Odd-even depth check",
        passed: true,
        importance: 0.60,
        explanation: "No alternating depth modulations exist; flux variation is smooth."
      },
      {
        name: "Depth × (1 + contratio) blend check",
        passed: true,
        importance: 0.50,
        explanation: "Signal origin is confirmed as local star emission, not a background source."
      }
    ],
    summary: `Classified as active Starspots. The sinusoidal modulation matches the host star's rotation period. The broad ingress/egress shape and long-term variations are typical of rotating surface spots rather than planetary transits.`
  };
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
      
      // Default extended fields
      let snr = 6.0 + (digitSum % 25);
      let rPlanet = 0.8 + (numId % 120) / 10;
      let distance = 50 + (numId % 1000);
      let stellarAge = 1.5 + (digitSum % 8) * 0.8;
      let inHabitableZone = (digitSum % 7) === 0;

      // Force realistic values for demo TIC IDs already in the repo
      if (ticId === '451598465') {
        classification = 'Exoplanet';
        confidence = 0.945;
        event = 'TOI-1431.01';
        period = 3.512;
        depth = 0.0035; // 3500 ppm
        duration = 2.45;
        snr = 14.2;
        rPlanet = 11.2; // 11.2 R_earth (Jupiter-sized)
        distance = 120.5;
        stellarAge = 4.2;
        inHabitableZone = false;
      } else if (ticId === '2054445521') {
        classification = 'Binary Star';
        confidence = 0.982;
        event = 'EB-SYS-2054';
        period = 12.434;
        depth = 0.0820; // 8.2%
        duration = 4.8;
        snr = 92.5;
        rPlanet = 0;
        distance = 840.0;
        stellarAge = 2.1;
        inHabitableZone = false;
      } else if (ticId === '257325189') {
        classification = 'Stellar Blend';
        confidence = 0.714;
        event = 'BLEND-2573';
        period = 1.252;
        depth = 0.0012; // 1200 ppm
        duration = 1.8;
        snr = 5.8;
        rPlanet = 0;
        distance = 1450.0;
        stellarAge = 7.3;
        inHabitableZone = false;
      } else if (ticId === '317154919') {
        classification = 'Starspot';
        confidence = 0.841;
        event = 'SPOT-3171';
        period = 28.45;
        depth = 0.0045; // 4500 ppm
        duration = 12.2;
        snr = 8.4;
        rPlanet = 0;
        distance = 245.0;
        stellarAge = 1.1;
        inHabitableZone = false;
      } else if (ticId === '257738202') {
        // Habitable Super Earth Candidate!
        classification = 'Exoplanet';
        confidence = 0.885;
        event = 'TOI-843.01';
        period = 42.52;
        depth = 0.00042; // 420 ppm
        duration = 3.82;
        snr = 9.8;
        rPlanet = 1.62; // 1.62 R_earth (Super-Earth)
        distance = 45.2;
        stellarAge = 6.4;
        inHabitableZone = true;
      }

      // Generate label based on parameters
      const planetType = getPlanetTypeLabel(classification, rPlanet, period);

      resolve({
        event,
        classification,
        confidence,
        period,
        depth,
        duration,
        snr,
        rPlanet,
        distance,
        stellarAge,
        inHabitableZone,
        planetType
      });
    }, 1500);
  });
}

export function LightCurveViewer({ 
  selectedStarId, 
  onSelectStar 
}: { 
  selectedStarId?: string; 
  onSelectStar?: (id: string) => void;
}) {
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

  // Report states
  const [reportText, setReportText] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  // AI Chat Panel States
  const [isAiPanelOpen, setIsAiPanelOpen] = useState<boolean>(false);
  const [chatMessages, setChatMessages] = useState<{ sender: 'user' | 'assistant', text: string }[]>([]);
  const [chatInput, setChatInput] = useState<string>('');
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // AI Reasoning States
  const [isWhyOpen, setIsWhyOpen] = useState<boolean>(false);

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

  // Listen for external star selections
  useEffect(() => {
    if (selectedStarId && selectedStarId !== activeTicId) {
      setTicId(selectedStarId);
      loadLightCurve(selectedStarId);
    }
  }, [selectedStarId]);

  const loadLightCurve = async (idToLoad: string) => {
    if (!idToLoad.trim()) return;
    setLoading(true);
    setError(null);
    setDetectionResult(null); // Reset previous detection result
    setActiveTicId(idToLoad);

    if (onSelectStar) {
      onSelectStar(idToLoad);
    }

    try {
      const fetchUrl = `/data/lightcurves/${idToLoad}.json`;
      console.log(`[LightCurveViewer] Fetching path: ${fetchUrl} for TIC ID: ${idToLoad}`);
      const response = await fetch(fetchUrl);
      if (!response.ok) {
        throw new Error("No data for this target — try one of the preloaded targets");
      }
      const rawData: LightCurvePoint[] = await response.json();
      
      if (!rawData || rawData.length === 0) {
        throw new Error("No data for this target — try one of the preloaded targets");
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

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || aiLoading) return;

    const userQ = chatInput.trim();
    setChatMessages(prev => [...prev, { sender: 'user', text: userQ }]);
    setChatInput('');
    setAiLoading(true);

    try {
      const response = await askAboutStar(detectionResult, userQ, activeTicId);
      setChatMessages(prev => [...prev, { sender: 'assistant', text: response }]);
    } catch (err) {
      console.error("AI chat failed:", err);
      setChatMessages(prev => [...prev, { sender: 'assistant', text: "Error: Failed to process query. Please retry." }]);
    } finally {
      setAiLoading(false);
    }
  };

  // Reset chat messages when star target changes
  useEffect(() => {
    setChatMessages([
      { 
        sender: 'assistant', 
        text: `Hello! I am your TESS Copilot. I have loaded the telemetry for **TIC ${activeTicId || 'N/A'}**. 

You can ask me questions about its **habitability**, **orbital period**, **estimated planet size**, or **stellar host age**.` 
      }
    ]);
  }, [activeTicId]);

  // Scroll to bottom of chat
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, aiLoading]);

  const handleGenerateReport = () => {
    if (!detectionResult) return;
    const summary = generateSummary(detectionResult, activeTicId);
    setReportText(summary);
  };

  const handleCopyClipboard = () => {
    if (!reportText) return;
    navigator.clipboard.writeText(reportText)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(err => {
        console.error("Failed to copy text:", err);
      });
  };

  const handleDownloadPDF = () => {
    if (!reportText || !detectionResult) return;
    import('jspdf').then(({ jsPDF }) => {
      const doc = new jsPDF();
      
      // Decorative Header
      doc.setFillColor(7, 11, 25);
      doc.rect(0, 0, 210, 40, 'F');
      
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.text("🔭 TESS SIGNAL ANALYSIS REPORT", 14, 20);
      
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.text(`TARGET DESIGNATION: TIC ${activeTicId} | OBJECT DESIGNATION: ${detectionResult.event}`, 14, 30);
      
      // Title
      doc.setTextColor(15, 23, 42);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(14);
      doc.text("Scientific Summary & Parameters", 14, 55);
      
      doc.setDrawColor(226, 232, 240);
      doc.line(14, 58, 196, 58);
      
      // Paragraph text
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.setTextColor(51, 65, 85);
      const splitText = doc.splitTextToSize(reportText, 182);
      doc.text(splitText, 14, 68);
      
      // Table Header
      const tableStartY = 80 + (splitText.length * 5);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(12);
      doc.text("Parameter Metrics Table", 14, tableStartY);
      doc.line(14, tableStartY + 3, 196, tableStartY + 3);
      
      // Table Content
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      let y = tableStartY + 10;
      const drawRow = (label: string, valStr: string) => {
        doc.setFont("helvetica", "bold");
        doc.text(label, 14, y);
        doc.setFont("helvetica", "normal");
        doc.text(valStr, 90, y);
        y += 7;
      };
      
      drawRow("Orbital Period:", `${detectionResult.period.toFixed(4)} days`);
      drawRow("Transit Depth:", `${(detectionResult.depth * 100).toFixed(4)}% (${(detectionResult.depth * 1e6).toFixed(0)} ppm)`);
      drawRow("Transit Duration:", `${detectionResult.duration.toFixed(2)} hours`);
      drawRow("Estimated Planet Size:", detectionResult.classification === 'Exoplanet' ? `${detectionResult.rPlanet.toFixed(2)} R_earth` : "N/A");
      drawRow("Distance to Star:", `${detectionResult.distance.toFixed(1)} light-years`);
      drawRow("Host Stellar Age:", `${detectionResult.stellarAge.toFixed(1)} Gyr`);
      drawRow("Signal SNR:", `${detectionResult.snr.toFixed(1)}`);
      drawRow("Habitable Zone:", detectionResult.inHabitableZone ? "YES" : "NO");
      drawRow("Designation Type:", `${detectionResult.planetType}`);
      
      // Footer
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      doc.text("Report compiled automatically via TESS Exoplanet Transit Analysis Pipeline.", 14, 280);
      
      doc.save(`TIC_${activeTicId}_Scientific_Report.pdf`);
    }).catch(err => {
      console.error("Failed to generate PDF:", err);
    });
  };

  // Reset report text when target star changes or detection runs
  useEffect(() => {
    setReportText(null);
    setIsWhyOpen(false);
  }, [activeTicId, detectionResult]);

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

  const reasoning = detectionResult ? getClassReasoning(detectionResult) : null;

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
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTicId(e.target.value.replace(/\D/g, ''))}
                />
              </div>

              {availableIds.length > 0 && (
                <div className="w-full sm:w-64">
                  <select
                    className="w-full h-10 px-3 rounded-md bg-[#020617]/60 border border-slate-700 text-indigo-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                    value={ticId}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
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
                {detecting ? (
                  // ML Processing State
                  <div className="text-center py-8 space-y-4">
                    <RefreshCw className="h-10 w-10 text-cyan-400 animate-spin mx-auto" />
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-indigo-300">Running Neural Net Classifier...</p>
                      <p className="text-xs text-slate-400 animate-pulse">Running BLS Periodogram search...</p>
                    </div>
                  </div>
                ) : detectionResult ? (
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
                    {/* Parameters Stat Cards Grid */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <BarChart2 className="h-3.5 w-3.5 text-cyan-400" />
                        Stellar & Planet Parameters
                      </h4>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                          <span className="text-[10px] text-slate-500 font-medium">Orbital Period</span>
                          <span className="font-mono text-slate-200 text-sm font-semibold mt-1">
                            {detectionResult.period.toFixed(4)} <span className="text-[10px] text-slate-500 font-sans">days</span>
                          </span>
                        </div>
                        <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                          <span className="text-[10px] text-slate-500 font-medium">Transit Depth</span>
                          <span className="font-mono text-slate-200 text-sm font-semibold mt-1">
                            {(detectionResult.depth * 100).toFixed(4)}% 
                            <span className="text-[9px] text-slate-500 font-sans block">
                              ({(detectionResult.depth * 1e6).toFixed(0)} ppm)
                            </span>
                          </span>
                        </div>
                        <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                          <span className="text-[10px] text-slate-500 font-medium">Transit Duration</span>
                          <span className="font-mono text-slate-200 text-sm font-semibold mt-1">
                            {detectionResult.duration.toFixed(2)} <span className="text-[10px] text-slate-500 font-sans">hours</span>
                          </span>
                        </div>
                        <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                          <span className="text-[10px] text-slate-500 font-medium">Estimated Planet Size</span>
                          <span className="font-mono text-slate-200 text-sm font-semibold mt-1">
                            {detectionResult.classification === 'Exoplanet' ? `${detectionResult.rPlanet.toFixed(2)} R⊕` : 'N/A'}
                          </span>
                        </div>
                        <div className="p-3 bg-[#020617]/40 rounded-lg border border-slate-900/60 flex flex-col justify-between">
                          <span className="text-[10px] text-slate-500 font-medium">Distance</span>
                          <span className="font-mono text-slate-200 text-sm font-semibold mt-1">
                            {detectionResult.distance.toFixed(1)} <span className="text-[10px] text-slate-500 font-sans">ly</span>
                          </span>
                        </div>
                        <div className="p-3 bg-[#020617]/40 rounded-lg border border-[#38bdf8]/10 bg-sky-950/5 flex flex-col justify-between shadow-[0_0_15px_rgba(56,189,248,0.02)]">
                          <span className="text-[10px] text-sky-400/80 font-medium">Signal SNR</span>
                          <span className="font-mono text-sky-300 text-sm font-bold mt-1">
                            {detectionResult.snr.toFixed(1)}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* AI Reasoning Panel */}
                    {reasoning && (
                      <div className="space-y-3 pt-3 border-t border-slate-800/40 animate-in fade-in duration-300">
                        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                          AI Classifier Reasoning
                        </h4>
                        
                        {/* Ranked feature tests list */}
                        <div className="space-y-2">
                          {reasoning.rankedFeatures
                            .sort((a, b) => b.importance - a.importance)
                            .map((test, index) => {
                              const IconComponent = test.passed ? CheckCircle2 : XCircle;
                              const iconColor = test.passed ? 'text-emerald-400' : 'text-rose-450';
                              const bgColor = test.passed ? 'bg-emerald-500/5 border-emerald-500/10' : 'bg-rose-500/5 border-rose-500/10';
                              
                              return (
                                <div 
                                  key={index}
                                  className={`p-2.5 rounded-lg border text-[11px] leading-relaxed flex items-start gap-2.5 ${bgColor}`}
                                >
                                  <IconComponent className={`h-4 w-4 shrink-0 mt-0.5 ${iconColor}`} />
                                  <div>
                                    <span className="font-semibold text-slate-200 block mb-0.5">
                                      #{index + 1}: {test.name}
                                    </span>
                                    <span className="text-slate-400">
                                      {test.explanation}
                                    </span>
                                  </div>
                                </div>
                              );
                            })}
                        </div>

                        {/* Expandable "Why this classification?" section */}
                        <div className="border border-slate-800 rounded-lg overflow-hidden bg-[#020617]/20">
                          <button 
                            type="button"
                            className="w-full px-3 py-2 text-left text-xs font-medium text-slate-350 hover:text-slate-100 bg-[#020617]/50 flex justify-between items-center transition-all"
                            onClick={() => setIsWhyOpen(!isWhyOpen)}
                          >
                            <span>Why this classification?</span>
                            <span className="text-[9px] text-slate-500 font-mono">{isWhyOpen ? '▼' : '▶'}</span>
                          </button>
                          {isWhyOpen && (
                            <div className="p-3 text-[11px] text-slate-400 leading-relaxed border-t border-slate-850/60 bg-[#020617]/10 animate-in fade-in duration-200">
                              {reasoning.summary}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

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
                ) : (
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
                )}
              </CardContent>
            </Card>

            {/* Habitability Card - Rendered conditionally when detection results exist */}
            {detectionResult && (
              <Card className="bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md overflow-hidden animate-in slide-in-from-bottom-3 duration-500">
                <CardHeader className="pb-3 border-b border-slate-800/60">
                  <CardTitle className="text-md font-semibold tracking-wide text-slate-100 flex items-center gap-2">
                    <Globe className="h-4.5 w-4.5 text-emerald-400" />
                    Habitability Profile
                  </CardTitle>
                  <CardDescription className="text-slate-400 text-[11px]">
                    Stellar habitable zone and planet properties evaluation
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-5 space-y-4">
                  {/* HZ Status Indicator block */}
                  <div className={`p-4 rounded-lg border flex items-center gap-4 transition-all ${
                    detectionResult.inHabitableZone 
                      ? 'bg-emerald-950/10 border-emerald-500/20 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.05)]' 
                      : 'bg-slate-900/30 border-slate-850 text-slate-400'
                  }`}>
                    {detectionResult.inHabitableZone ? (
                      <>
                        <div className="p-2 bg-emerald-500/10 rounded-full border border-emerald-500/20 shadow-[0_0_10px_rgba(52,211,153,0.15)] animate-pulse">
                          <Globe className="h-6 w-6 text-emerald-400" />
                        </div>
                        <div>
                          <strong className="text-xs uppercase tracking-wider block font-semibold">Habitable Zone</strong>
                          <span className="text-sm font-bold text-emerald-300">IN HZ: YES</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="p-2 bg-slate-800/30 rounded-full border border-slate-800/30">
                          <Sun className="h-6 w-6 text-slate-500" />
                        </div>
                        <div>
                          <strong className="text-xs uppercase tracking-wider block font-medium">Habitable Zone</strong>
                          <span className="text-sm font-bold text-slate-400">IN HZ: NO</span>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Details */}
                  <div className="space-y-3 text-xs">
                    <div className="flex justify-between items-center py-2 border-b border-slate-900/50">
                      <span className="text-slate-500">Planet Designation Type</span>
                      <Badge className="bg-indigo-950/20 text-indigo-300 border-indigo-500/20 text-[10px] font-semibold">
                        {detectionResult.planetType}
                      </Badge>
                    </div>

                    <div className="flex justify-between items-center py-2 border-b border-slate-900/50">
                      <span className="text-slate-500">Stellar Age Estimate</span>
                      <span className="text-slate-300 font-medium font-mono">
                        {detectionResult.stellarAge.toFixed(1)} <span className="text-[10px] text-slate-500">Gyr</span>
                      </span>
                    </div>

                    <div className="flex justify-between items-center py-2">
                      <span className="text-slate-500">Distance</span>
                      <span className="text-slate-300 font-medium font-mono">
                        {detectionResult.distance.toFixed(1)} <span className="text-[10px] text-slate-500">ly</span>
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Summary Report Card - Rendered conditionally when detection results exist */}
            {detectionResult && (
              <Card className="bg-[#0f172a]/30 border-slate-800/80 backdrop-blur-md overflow-hidden animate-in slide-in-from-bottom-3 duration-500">
                <CardHeader className="pb-3 border-b border-slate-800/60">
                  <CardTitle className="text-md font-semibold tracking-wide text-slate-100 flex items-center gap-2">
                    <FileText className="h-4.5 w-4.5 text-indigo-400" />
                    Stellar Summary Report
                  </CardTitle>
                  <CardDescription className="text-slate-400 text-[11px]">
                    Generate and download scientific summary reports
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-5 space-y-4">
                  {!reportText ? (
                    <Button 
                      className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-all shadow-md shadow-indigo-500/10 active:scale-95"
                      onClick={handleGenerateReport}
                    >
                      Generate Report
                    </Button>
                  ) : (
                    <div className="space-y-4 animate-in fade-in duration-300">
                      <div className="p-3.5 bg-[#020617]/50 rounded-lg border border-slate-900/60 text-[11px] text-slate-300 leading-relaxed font-sans max-h-48 overflow-y-auto scrollbar">
                        {reportText}
                      </div>
                      
                      <div className="flex gap-2">
                        <Button 
                          variant="outline" 
                          className="flex-1 text-xs border-slate-700 hover:bg-slate-800 text-slate-200"
                          onClick={handleCopyClipboard}
                        >
                          {copied ? 'Copied!' : 'Copy Text'}
                        </Button>
                        <Button 
                          className="flex-1 text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
                          onClick={handleDownloadPDF}
                        >
                          Download PDF
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

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

      {/* Floating AI Chat Trigger Button */}
      <button 
        onClick={() => setIsAiPanelOpen(true)}
        className="fixed bottom-6 right-6 p-4 rounded-full bg-indigo-650 hover:bg-indigo-500 text-white shadow-xl shadow-indigo-500/25 z-40 transition-all active:scale-95 flex items-center gap-2 group border border-indigo-400/20"
      >
        <MessageSquare className="h-5 w-5 text-white" />
        <span className="max-w-0 overflow-hidden group-hover:max-w-xs transition-all duration-300 ease-out text-xs font-semibold uppercase tracking-wider whitespace-nowrap">
          Ask Copilot
        </span>
      </button>

      {/* Collapsible Slide-in AI Sidebar */}
      <div className={`fixed inset-y-0 right-0 w-80 sm:w-96 bg-[#090d1a] border-l border-slate-800/80 shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out transform ${
        isAiPanelOpen ? 'translate-x-0' : 'translate-x-full'
      }`}>
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-850 bg-[#070a14] flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-indigo-500/10 rounded-md border border-indigo-500/20">
              <Sparkles className="h-4 w-4 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">AI Signal Copilot</h3>
              <p className="text-[9px] text-slate-500 font-mono">Target: TIC {activeTicId}</p>
            </div>
          </div>
          <button 
            onClick={() => setIsAiPanelOpen(false)}
            className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="h-4.5 w-4.5" />
          </button>
        </div>

        {/* Sidebar Messages Area */}
        <div className="flex-grow p-4 overflow-y-auto space-y-4 scrollbar">
          {chatMessages.map((msg, idx) => (
            <div 
              key={idx} 
              className={`flex flex-col max-w-[85%] ${
                msg.sender === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'
              }`}
            >
              <div 
                className={`p-3 rounded-xl text-xs leading-relaxed ${
                  msg.sender === 'user' 
                    ? 'bg-indigo-600 text-white rounded-tr-none' 
                    : 'bg-[#0f172a] border border-slate-850 text-slate-300 rounded-tl-none'
                }`}
              >
                {msg.sender === 'user' ? msg.text : renderMessageContent(msg.text)}
              </div>
              <span className="text-[9px] text-slate-600 mt-1 uppercase tracking-wider font-semibold font-mono">
                {msg.sender === 'user' ? 'Scientist' : 'Copilot'}
              </span>
            </div>
          ))}

          {/* AI Typings loader */}
          {aiLoading && (
            <div className="flex flex-col max-w-[85%] mr-auto items-start">
              <div className="p-3 bg-[#0f172a] border border-slate-850 rounded-xl rounded-tl-none flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce" />
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce delay-100" />
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce delay-200" />
              </div>
              <span className="text-[9px] text-slate-600 mt-1 uppercase tracking-wider font-semibold font-mono">Copilot</span>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Sidebar Input Form */}
        <form onSubmit={handleSendMessage} className="p-4 border-t border-slate-850 bg-[#070a14] space-y-2">
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder={detectionResult ? "Ask about period, size, HZ status..." : "Run detection first..."}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={aiLoading}
              className="bg-[#020617] border-slate-700 text-xs h-9 focus:ring-indigo-500"
            />
            <Button 
              type="submit" 
              disabled={aiLoading || !chatInput.trim()}
              className="h-9 px-3 bg-indigo-600 hover:bg-indigo-500 text-white shrink-0"
            >
              <Send className="h-3.5 w-3.5" />
            </Button>
          </div>
          <p className="text-[9px] text-slate-600 text-center font-mono">
            Analyzes active target photometry and parameters.
          </p>
        </form>
      </div>
    </div>
  );
}
