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
import { SkySnapshot } from '@/components/SkySnapshot';

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

export interface EnrichedDetectionResult extends DetectionResult {
  reasoning: ReasoningResult;
  habitability: HabitabilityAssessment;
}

// AI Chat mock query responder stub
export function askAboutStar(
  data: EnrichedDetectionResult | null, 
  question: string, 
  ticId: string
): Promise<string> {
  return new Promise((resolve) => {
    setTimeout(() => {
      const q = question.toLowerCase();
      
      // Glossary context
      const glossary: { [key: string]: string } = {
        'transit depth': '**Transit Depth** is the fractional decrease in stellar brightness as a planet crosses in front of the star. It is proportional to the ratio of the planet\'s area to the star\'s area: $(R_p/R_*)^2$. Deep transits indicate larger companions.',
        'orbital period': '**Orbital Period** is the time taken for a planet to complete one full orbit around its host star. It is resolved by locating repeating dips in the light curve.',
        'transit duration': '**Transit Duration** is the length of time it takes for a planet to traverse the stellar disk. This parameter helps derive the orbit inclination and the host star density.',
        'snr': '**Signal-to-Noise Ratio (SNR)** measures the strength of the transit signal relative to the stellar noise floor. SNRs above 7.0 are generally considered statistically significant.',
        'habitability': '**Habitability** refers to whether a planet can support liquid surface water. The **Habitable Zone (HZ)** is the range of orbital distances where liquid water is thermodynamically stable.',
        'equilibrium temperature': '**Equilibrium Temperature (Teq)** is the theoretical surface temperature of a planet assuming it absorbs stellar radiation and acts as a blackbody, excluding greenhouse warming.',
        'insolation flux': '**Insolation Flux** is the amount of stellar radiation a planet receives at its orbital distance, measured relative to Earth\'s solar constant ($S_{\\oplus}$).'
      };

      // Check if it is a general glossary question
      for (const term of Object.keys(glossary)) {
        if (q.includes(term) && (!data || q.startsWith('what is') || q.startsWith('explain') || q.includes('meaning') || q.includes('definition'))) {
          resolve(glossary[term]);
          return;
        }
      }

      // If no target data is loaded, prompt to run pipeline
      if (!data) {
        resolve("Please select a target and click 'Detect Signal' first to populate the telemetry profile before asking target-specific questions.");
        return;
      }

      // Target-specific queries:
      // 1. Classification & Vetting Reasoning
      if (q.includes('why') || q.includes('classification') || q.includes('classified') || q.includes('reason') || q.includes('decision')) {
        const testsText = data.reasoning.rankedFeatures
          .map((f, i) => `* **#${i+1} ${f.name}**: ${f.passed ? '✓ Passed' : '✗ Failed'} — ${f.explanation}`)
          .join('\n');
        
        resolve(`**Classification Vetting Analysis for TIC ${ticId}**:
The neural network classified this target as an **${data.classification}** (Confidence: **${(data.confidence * 100).toFixed(1)}%**).

**Vetting Checks Summary**:
${testsText}

**Vetting Conclusion**:
${data.reasoning.summary}`);
        return;
      }

      // 2. Habitability Assessment Details
      if (q.includes('habitable') || q.includes('habitability') || q.includes('hz') || q.includes('life') || q.includes('temperature') || q.includes('teq') || q.includes('insolation')) {
        const hzStatus = data.inHabitableZone 
          ? `**YES**, the candidate orbits inside the Habitable Zone.` 
          : `**NO**, the candidate orbits outside the habitable boundaries.`;

        resolve(`**Habitability Vetting Profile for TIC ${ticId}**:
* **Habitable Zone (HZ)**: ${hzStatus}
* **Planet Type**: ${data.planetType}
* **Equilibrium Temp (Teq)**: **${data.habitability.equilibriumTemp} K**
* **Insolation Flux**: **${data.habitability.insolationFlux.toFixed(2)} S⊕**
* **Orbital Distance (a)**: **${data.habitability.orbitalDistance.toFixed(3)} AU**
* **Stellar effective Temp (Teff)**: **${data.habitability.stellarTeff} K**
* **Stellar Luminosity**: **${data.habitability.stellarLuminosity.toFixed(2)} L⊙**`);
        return;
      }

      // 3. Transit Parameters (Period, Depth, Duration, SNR)
      if (q.includes('period') || q.includes('orbit') || q.includes('depth') || q.includes('duration') || q.includes('snr') || q.includes('size') || q.includes('radius')) {
        resolve(`**Transit Parameters Log for TIC ${ticId}**:
* **Orbital Period**: **${data.period.toFixed(4)} days** (${(data.period * 24).toFixed(1)} hours)
* **Transit Depth**: **${(data.depth * 100).toFixed(4)}%** (${(data.depth * 1e6).toFixed(0)} ppm)
* **Transit Duration**: **${data.duration.toFixed(2)} hours**
* **Planet Radius**: **${data.classification === 'Exoplanet' ? `${data.rPlanet.toFixed(2)} R⊕` : 'N/A'}**
* **Signal-to-Noise Ratio (SNR)**: **${data.snr.toFixed(1)}**`);
        return;
      }

      // Fallback glossary check if question contains keywords but didn't trigger specific flows
      for (const term of Object.keys(glossary)) {
        if (q.includes(term)) {
          resolve(`Here is some background context on **${term}**:
${glossary[term]}

*TIC ${ticId} target specific values:*
- Period: ${data.period.toFixed(4)} days
- Depth: ${(data.depth * 100).toFixed(4)}%
- SNR: ${data.snr.toFixed(1)}`);
          return;
        }
      }

      // Default response
      resolve(`I am familiar with the vetting profile for **TIC ${ticId}**. You can ask me about:
1. **Transit parameters** (e.g., "what is the period", "what is the SNR")
2. **AI Vetting checks** (e.g., "why was it classified as ${data.classification}?")
3. **Habitability status** (e.g., "is it habitable?", "what is the equilibrium temperature?")
4. **General concepts** (e.g., "what is transit depth?")`);
    }, 1000);
  });
}

// Habitability assessment helper stub
export interface HabitabilityAssessment {
  equilibriumTemp: number;     // Kelvin (K)
  insolationFlux: number;      // Relative to Earth (S_⊕)
  orbitalDistance: number;     // Astronomical Units (AU)
  stellarTeff: number;         // Kelvin (K)
  stellarLuminosity: number;   // Solar Luminosity (L_⊙)
  hzInnerBoundary: number;     // AU
  hzOuterBoundary: number;     // AU
  planetOrbitRadius: number;   // AU
  planetStatus: 'inner' | 'hz' | 'outer';
}

export function getHabitabilityAssessment(data: DetectionResult): HabitabilityAssessment {
  const isHz = data.inHabitableZone;
  
  if (isHz) {
    return {
      equilibriumTemp: 262, // K
      insolationFlux: 0.95, // S_⊕
      orbitalDistance: 0.38, // AU
      stellarTeff: 4800, // K
      stellarLuminosity: 0.28, // L_⊙
      hzInnerBoundary: 0.28,
      hzOuterBoundary: 0.52,
      planetOrbitRadius: 0.38,
      planetStatus: 'hz'
    };
  } else {
    // Hot Jupiter / Not in HZ
    return {
      equilibriumTemp: 845, // K
      insolationFlux: 125.4, // S_⊕
      orbitalDistance: 0.045, // AU
      stellarTeff: 5800, // K
      stellarLuminosity: 1.15, // L_⊙
      hzInnerBoundary: 0.72,
      hzOuterBoundary: 1.45,
      planetOrbitRadius: 0.045,
      planetStatus: 'inner'
    };
  }
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
  const [detectionError, setDetectionError] = useState<string | null>(null);

  // Report states
  const [reportText, setReportText] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [pdfError, setPdfError] = useState<boolean>(false);

  // AI Chat Panel States
  const [isAiPanelOpen, setIsAiPanelOpen] = useState<boolean>(false);
  const [chatMessages, setChatMessages] = useState<{ sender: 'user' | 'assistant', text: string, isError?: boolean, retryPayload?: string }[]>([]);
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

      // Filter out NaN / Infinity values that would break the chart
      const validData = rawData.filter(
        p => Number.isFinite(p.flux) && Number.isFinite(p.time)
      );
      if (validData.length === 0) {
        throw new Error("Light curve data appears malformed (all flux values are NaN or invalid) — cannot render chart");
      }
      if (validData.length < rawData.length) {
        console.warn(`[LightCurveViewer] Filtered ${rawData.length - validData.length} NaN/Infinity points from TIC ${idToLoad}`);
      }

      // Sort data by time
      validData.sort((a, b) => a.time - b.time);
      setData(validData);

      // Perform Downsampling (Max 2500 points for smooth Recharts rendering)
      const maxPoints = 2500;
      if (validData.length > maxPoints) {
        const step = Math.ceil(validData.length / maxPoints);
        const sampled: LightCurvePoint[] = [];
        for (let i = 0; i < validData.length; i += step) {
          sampled.push(validData[i]);
        }
        setDownsampledData(sampled);
      } else {
        setDownsampledData(validData);
      }

      // Calculate Statistics
      const fluxes = validData.map(p => p.flux);
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
    setDetectionError(null);
    try {
      const result = await detectSignal(activeTicId);
      setDetectionResult(result);
    } catch (err: any) {
      console.error('Signal detection failed:', err);
      setDetectionError(err?.message ?? 'Classification pipeline failed. Please try again.');
    } finally {
      setDetecting(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent, retryText?: string) => {
    e.preventDefault();
    const userQ = retryText ?? chatInput.trim();
    if (!userQ || aiLoading) return;

    if (!retryText) {
      setChatMessages(prev => [...prev, { sender: 'user', text: userQ }]);
      setChatInput('');
    }
    setAiLoading(true);

    // 15-second safety timeout — prevents a stuck loading spinner
    const safetyTimer = setTimeout(() => {
      setAiLoading(false);
      setChatMessages(prev => [
        ...prev,
        { sender: 'assistant', text: "⚠ Response timed out — the copilot took too long to reply.", isError: true, retryPayload: userQ }
      ]);
    }, 15000);

    try {
      const enrichedContext: EnrichedDetectionResult | null = detectionResult ? {
        ...detectionResult,
        reasoning: getClassReasoning(detectionResult),
        habitability: getHabitabilityAssessment(detectionResult)
      } : null;
      const response = await askAboutStar(enrichedContext, userQ, activeTicId);
      clearTimeout(safetyTimer);
      if (!response || response.trim() === '') {
        setChatMessages(prev => [
          ...prev,
          { sender: 'assistant', text: "⚠ Couldn't get a response — please try again.", isError: true, retryPayload: userQ }
        ]);
      } else {
        setChatMessages(prev => [...prev, { sender: 'assistant', text: response }]);
      }
    } catch (err) {
      clearTimeout(safetyTimer);
      console.error('AI chat failed:', err);
      setChatMessages(prev => [
        ...prev,
        { sender: 'assistant', text: "⚠ Couldn't get a response — please try again.", isError: true, retryPayload: userQ }
      ]);
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
    if (!reportText || !detectionResult) return;
    const rsn = getClassReasoning(detectionResult);
    const hab = getHabitabilityAssessment(detectionResult);
    
    const formattedMarkdown = `
# TESS VETTING & ANALYSIS REPORT - TIC ${activeTicId}

## 1. Target Overview
${reportText}

## 2. Transit Parameters
- Orbital Period: ${detectionResult.period.toFixed(4)} days
- Transit Depth: ${(detectionResult.depth * 100).toFixed(4)}% (${(detectionResult.depth * 1e6).toFixed(0)} ppm)
- Transit Duration: ${detectionResult.duration.toFixed(2)} hours
- Planet Radius: ${detectionResult.classification === 'Exoplanet' ? `${detectionResult.rPlanet.toFixed(2)} R⊕` : 'N/A'}
- Signal SNR: ${detectionResult.snr.toFixed(1)}

## 3. AI Classifier Vetting
- Classification: ${detectionResult.classification} (Confidence: ${(detectionResult.confidence * 100).toFixed(1)}%)
${rsn.rankedFeatures.map((f, i) => `- ${f.passed ? '[PASS]' : '[FAIL]'} #${i+1} ${f.name}: ${f.explanation}`).join('\n')}
- Summary Reasoning: ${rsn.summary}

## 4. Habitability Profile
- In Habitable Zone: ${detectionResult.inHabitableZone ? 'YES' : 'NO'}
- Planet Designation Type: ${detectionResult.planetType}
- Equilibrium Temp (Teq): ${hab.equilibriumTemp} K
- Insolation Flux: ${hab.insolationFlux.toFixed(2)} S⊕
- Semi-Major Axis: ${hab.orbitalDistance.toFixed(3)} AU
- Host Stellar Temp: ${hab.stellarTeff} K
- Host Stellar Lum: ${hab.stellarLuminosity.toFixed(2)} L⊙
- Host Stellar Age: ${detectionResult.stellarAge.toFixed(1)} Gyr
- Distance to System: ${detectionResult.distance.toFixed(1)} light-years
`;

    navigator.clipboard.writeText(formattedMarkdown.trim())
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
    setPdfError(false);
    import('jspdf').then(({ jsPDF }) => {
      const doc = new jsPDF();
      
      // Page 1: Header and Summary
      doc.setFillColor(7, 11, 25);
      doc.rect(0, 0, 210, 40, 'F');
      
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.text("🔭 TESS SIGNAL ANALYSIS REPORT", 14, 20);
      
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.text(`TARGET DESIGNATION: TIC ${activeTicId} | OBJECT DESIGNATION: ${detectionResult.event}`, 14, 30);
      
      // Overview
      doc.setTextColor(15, 23, 42);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.text("1. Target Overview & Summary", 14, 52);
      doc.setDrawColor(226, 232, 240);
      doc.line(14, 55, 196, 55);
      
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9.5);
      doc.setTextColor(51, 65, 85);
      const splitText = doc.splitTextToSize(reportText, 182);
      doc.text(splitText, 14, 62);
      
      // Transit Parameters Table
      const sec2Y = 65 + (splitText.length * 4.5);
      doc.setTextColor(15, 23, 42);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.text("2. Vetting & Transit Parameters", 14, sec2Y);
      doc.line(14, sec2Y + 3, 196, sec2Y + 3);
      
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9.5);
      let y = sec2Y + 10;
      const drawRow = (label: string, valStr: string) => {
        doc.setFont("helvetica", "bold");
        doc.text(label, 14, y);
        doc.setFont("helvetica", "normal");
        doc.text(valStr, 90, y);
        y += 6.5;
      };
      
      drawRow("Orbital Period:", `${detectionResult.period.toFixed(4)} days`);
      drawRow("Transit Depth:", `${(detectionResult.depth * 100).toFixed(4)}% (${(detectionResult.depth * 1e6).toFixed(0)} ppm)`);
      drawRow("Transit Duration:", `${detectionResult.duration.toFixed(2)} hours`);
      drawRow("Estimated Planet Size:", detectionResult.classification === 'Exoplanet' ? `${detectionResult.rPlanet.toFixed(2)} R_earth` : "N/A");
      drawRow("Signal SNR:", `${detectionResult.snr.toFixed(1)}`);
      
      // Habitability Table
      const sec3Y = y + 4;
      doc.setTextColor(15, 23, 42);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.text("3. Habitability Profile & Assessment", 14, sec3Y);
      doc.line(14, sec3Y + 3, 196, sec3Y + 3);
      
      const assessment = getHabitabilityAssessment(detectionResult);
      y = sec3Y + 10;
      drawRow("Habitable Zone Status:", detectionResult.inHabitableZone ? "IN HABITABLE ZONE (YES)" : "OUTSIDE HABITABLE ZONE (NO)");
      drawRow("Designation Type:", `${detectionResult.planetType}`);
      drawRow("Equilibrium Temp (Teq):", `${assessment.equilibriumTemp} K`);
      drawRow("Insolation Flux:", `${assessment.insolationFlux.toFixed(2)} S_earth`);
      drawRow("Stellar Temperature:", `${assessment.stellarTeff} K`);
      drawRow("Stellar Luminosity:", `${assessment.stellarLuminosity.toFixed(2)} L_sun`);

      // Page 1 Footer
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      doc.text("TESS Transit Vetting Report — Page 1 of 2", 14, 285);
      
      // Add Page 2
      doc.addPage();
      
      // Decorative Header Page 2
      doc.setFillColor(7, 11, 25);
      doc.rect(0, 0, 210, 18, 'F');
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.text(`TESS SIGNAL ANALYSIS REPORT — TIC ${activeTicId}`, 14, 12);
      
      // AI Classifier Reasoning
      doc.setTextColor(15, 23, 42);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.text("4. AI Classifier Vetting & Reasoning", 14, 30);
      doc.setDrawColor(226, 232, 240);
      doc.line(14, 33, 196, 33);
      
      const reasoning = getClassReasoning(detectionResult);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(9.5);
      doc.setTextColor(51, 65, 85);
      doc.text(`ML Classification: ${detectionResult.classification} | Confidence: ${(detectionResult.confidence * 100).toFixed(1)}%`, 14, 40);
      
      // Feature check list
      let checkY = 48;
      reasoning.rankedFeatures
        .sort((a, b) => b.importance - a.importance)
        .forEach((test, index) => {
          doc.setFont("helvetica", "bold");
          doc.setTextColor(test.passed ? 16 : 220, test.passed ? 120 : 38, test.passed ? 50 : 38);
          doc.text(test.passed ? "[PASS]" : "[FAIL]", 14, checkY);
          
          doc.setFont("helvetica", "bold");
          doc.setTextColor(30, 41, 59);
          doc.text(`#${index + 1}: ${test.name}`, 32, checkY);
          
          doc.setFont("helvetica", "normal");
          doc.setTextColor(71, 85, 105);
          const splitExplanation = doc.splitTextToSize(test.explanation, 155);
          doc.text(splitExplanation, 32, checkY + 4.5);
          
          checkY += 7.5 + (splitExplanation.length * 4);
        });

      // Vetting Summary Statement
      doc.setTextColor(15, 23, 42);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(11);
      doc.text("Vetting Summary Statement", 14, checkY + 4);
      doc.line(14, checkY + 7, 196, checkY + 7);
      
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9.5);
      doc.setTextColor(51, 65, 85);
      const splitReasoningSummary = doc.splitTextToSize(reasoning.summary, 182);
      doc.text(splitReasoningSummary, 14, checkY + 13);
      
      // Page 2 Footer
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      doc.text("Report compiled automatically via TESS Exoplanet Transit Analysis Pipeline. — Page 2 of 2", 14, 285);
      
      doc.save(`TIC_${activeTicId}_Scientific_Report.pdf`);
    }).catch(err => {
      console.error('PDF generation failed:', err);
      setPdfError(true);
      setTimeout(() => setPdfError(false), 4000);
    });
  };

  // Reset report text and errors when target star changes or detection runs
  useEffect(() => {
    setReportText(null);
    setDetectionError(null);
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
  const assessment = detectionResult ? getHabitabilityAssessment(detectionResult) : null;

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
                ) : detectionError ? (
                  // Detection failure state with retry button
                  <div className="space-y-4">
                    <div className="flex items-start gap-3 p-3.5 bg-rose-950/30 border border-rose-500/25 rounded-lg">
                      <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <p className="text-xs font-semibold text-rose-300">Classification Failed</p>
                        <p className="text-[11px] text-rose-400/70 mt-0.5 leading-relaxed">{detectionError}</p>
                      </div>
                    </div>
                    <Button
                      className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-all active:scale-95"
                      onClick={handleDetectSignal}
                    >
                      <RefreshCw className="mr-2 h-3.5 w-3.5" />
                      Retry Detection
                    </Button>
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

                      {/* Low-confidence warning */}
                      {detectionResult.confidence < 0.50 && (
                        <div className="flex items-start gap-2.5 p-2.5 bg-amber-500/8 border border-amber-500/25 rounded-lg text-[11px]">
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                          <span className="text-amber-300/90 leading-relaxed">
                            <strong>Low confidence ({(detectionResult.confidence * 100).toFixed(1)}%)</strong> — result may be ambiguous. Consider re-running or selecting a different target.
                          </span>
                        </div>
                      )}

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

                    {/* Sky Snapshot Thumbnail */}
                    <SkySnapshot ticId={activeTicId} />

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
            {detectionResult && (() => {
              const assessment = getHabitabilityAssessment(detectionResult);
              const orbitRadiusPx = assessment.planetStatus === 'hz' ? 52 : assessment.planetStatus === 'inner' ? 22 : 90;
              const angle = -Math.PI / 4; // 45 degrees top right quadrant for nice spacing
              const planetX = 140 + orbitRadiusPx * Math.cos(angle);
              const planetY = 70 + orbitRadiusPx * Math.sin(angle);
              
              const orbitColor = assessment.planetStatus === 'hz' ? 'rgba(52, 211, 153, 0.4)' : 'rgba(239, 68, 68, 0.3)';
              const planetColor = assessment.planetStatus === 'hz' ? '#10b981' : '#ef4444';
              const statusBgColor = assessment.planetStatus === 'hz' 
                ? 'bg-emerald-950/10 border-emerald-500/20 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.05)]' 
                : 'bg-rose-955/5 border-rose-500/10 text-rose-400/80';

              return (
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
                  <CardContent className="pt-5 space-y-5">
                    {/* HZ Status Indicator block */}
                    <div className={`p-4 rounded-lg border flex items-center gap-4 transition-all ${statusBgColor}`}>
                      {detectionResult.inHabitableZone ? (
                        <>
                          <div className="p-2 bg-emerald-500/10 rounded-full border border-emerald-500/20 shadow-[0_0_10px_rgba(52,211,153,0.15)] animate-pulse">
                            <Globe className="h-6 w-6 text-emerald-400" />
                          </div>
                          <div>
                            <strong className="text-xs uppercase tracking-wider block font-semibold">Habitable Zone</strong>
                            <span className="text-sm font-bold text-emerald-350">IN HZ: YES</span>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="p-2 bg-rose-500/10 rounded-full border border-rose-500/10">
                            <Sun className="h-6 w-6 text-rose-450" />
                          </div>
                          <div>
                            <strong className="text-xs uppercase tracking-wider block font-medium">Habitable Zone</strong>
                            <span className="text-sm font-bold text-rose-450">IN HZ: NO</span>
                          </div>
                        </>
                      )}
                    </div>

                    {/* Habitable Zone Diagram */}
                    <div className="p-4 bg-[#020617]/50 rounded-lg border border-slate-800/60 flex flex-col items-center">
                      <span className="text-[10px] text-slate-505 font-semibold uppercase tracking-wider self-start mb-2">Orbit Vetting Diagram</span>
                      
                      <svg width="100%" height="140" viewBox="0 0 280 140" className="mx-auto select-none">
                        <defs>
                          <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stopColor="#fef08a" />
                            <stop offset="35%" stopColor="#eab308" stopOpacity="0.8" />
                            <stop offset="100%" stopColor="#eab308" stopOpacity="0" />
                          </radialGradient>
                        </defs>
                        
                        {/* Habitable Zone Shaded Ring */}
                        <circle 
                          cx="140" 
                          cy="70" 
                          r="52" 
                          fill="none" 
                          stroke="rgba(16, 185, 129, 0.15)" 
                          strokeWidth="30" 
                        />
                        <circle 
                          cx="140" 
                          cy="70" 
                          r="52" 
                          fill="none" 
                          stroke="rgba(16, 185, 129, 0.4)" 
                          strokeWidth="1.5" 
                          strokeDasharray="2 4"
                        />

                        {/* Outer boundary limit circle */}
                        <circle cx="140" cy="70" r="67" fill="none" stroke="rgba(148, 163, 184, 0.08)" strokeWidth="1" />
                        {/* Inner boundary limit circle */}
                        <circle cx="140" cy="70" r="37" fill="none" stroke="rgba(148, 163, 184, 0.08)" strokeWidth="1" />

                        {/* Planet Orbit Ring */}
                        <circle 
                          cx="140" 
                          cy="70" 
                          r={orbitRadiusPx} 
                          fill="none" 
                          stroke={orbitColor} 
                          strokeWidth="1.5" 
                          strokeDasharray="4 4" 
                        />

                        {/* Host Star */}
                        <circle cx="140" cy="70" r="18" fill="url(#starGlow)" />
                        <circle cx="140" cy="70" r="6" fill="#fef08a" />

                        {/* Planet Dot */}
                        <circle 
                          cx={planetX} 
                          cy={planetY} 
                          r="5" 
                          fill={planetColor} 
                          className="shadow-glow"
                        />
                        
                        {/* Orbit Vetting labels */}
                        <text x="140" y="24" textAnchor="middle" fill="rgba(148, 163, 184, 0.5)" fontSize="9" fontWeight="bold" letterSpacing="0.1em">
                          HABITABLE ZONE
                        </text>
                        <text x="140" y="130" textAnchor="middle" fill={planetColor} fontSize="10" fontWeight="bold">
                          {assessment.planetStatus === 'hz' ? 'Orbit fits inside HZ' : assessment.planetStatus === 'inner' ? 'Orbit is too close (Too Hot)' : 'Orbit is too far (Too Cold)'}
                        </text>
                      </svg>
                    </div>

                    {/* Derived Assessment Parameters */}
                    <div className="space-y-2.5 text-xs">
                      <div className="flex justify-between items-center py-1.5 border-b border-slate-900/50">
                        <span className="text-slate-500">Planet Designation Type</span>
                        <Badge className="bg-indigo-950/20 text-indigo-300 border-indigo-500/20 text-[10px] font-semibold">
                          {detectionResult.planetType}
                        </Badge>
                      </div>

                      <div className="flex justify-between items-center py-1.5 border-b border-slate-900/50">
                        <span className="text-slate-500">Equilibrium Temp (Teq)</span>
                        <span className="text-slate-300 font-bold font-mono">
                          {assessment.equilibriumTemp} <span className="text-[10px] text-slate-500">K</span>
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1.5 border-b border-slate-900/50">
                        <span className="text-slate-500">Insolation Flux (S_earth)</span>
                        <span className="text-slate-300 font-bold font-mono">
                          {assessment.insolationFlux.toFixed(2)} <span className="text-[10px] text-slate-500">S⊕</span>
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1.5 border-b border-slate-900/50">
                        <span className="text-slate-500">Orbital Distance (a)</span>
                        <span className="text-slate-300 font-bold font-mono">
                          {assessment.orbitalDistance.toFixed(3)} <span className="text-[10px] text-slate-500">AU</span>
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1.5 border-b border-slate-900/50">
                        <span className="text-slate-500">Stellar Temp (Teff)</span>
                        <span className="text-slate-300 font-bold font-mono">
                          {assessment.stellarTeff} <span className="text-[10px] text-slate-500">K</span>
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1.5 border-b border-slate-900/50">
                        <span className="text-slate-500">Stellar Luminosity (L_sun)</span>
                        <span className="text-slate-300 font-bold font-mono">
                          {assessment.stellarLuminosity.toFixed(2)} <span className="text-[10px] text-slate-500">L⊙</span>
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1.5 border-b border-slate-900/50">
                        <span className="text-slate-500">Stellar Age Estimate</span>
                        <span className="text-slate-300 font-medium font-mono">
                          {detectionResult.stellarAge.toFixed(1)} <span className="text-[10px] text-slate-500">Gyr</span>
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1.5">
                        <span className="text-slate-500">Distance to System</span>
                        <span className="text-slate-300 font-medium font-mono">
                          {detectionResult.distance.toFixed(1)} <span className="text-[10px] text-slate-500">ly</span>
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })()}

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
                      <div className="p-4 bg-[#020617]/60 rounded-lg border border-slate-850 space-y-4 max-h-[450px] overflow-y-auto scrollbar text-left font-sans">
                        
                        {/* Section 1: Overview */}
                        <div className="space-y-1.5">
                          <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-1 flex items-center gap-1.5">
                            <Info className="h-3.5 w-3.5 text-indigo-400" />
                            1. Target Overview
                          </h5>
                          <p className="text-[11px] text-slate-350 leading-relaxed font-light">
                            {reportText}
                          </p>
                        </div>

                        {/* Section 2: Parameters */}
                        <div className="space-y-2">
                          <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-1 flex items-center gap-1.5">
                            <BarChart2 className="h-3.5 w-3.5 text-indigo-400" />
                            2. Vetting & Transit Parameters
                          </h5>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
                            <div className="flex justify-between border-b border-slate-905 py-1">
                              <span className="text-slate-500">Orbital Period:</span>
                              <span className="text-slate-300 font-mono font-bold">{detectionResult.period.toFixed(4)} d</span>
                            </div>
                            <div className="flex justify-between border-b border-slate-905 py-1">
                              <span className="text-slate-500">Transit Depth:</span>
                              <span className="text-slate-300 font-mono font-bold">{(detectionResult.depth * 100).toFixed(4)}%</span>
                            </div>
                            <div className="flex justify-between border-b border-slate-905 py-1">
                              <span className="text-slate-500">Transit Duration:</span>
                              <span className="text-slate-300 font-mono font-bold">{detectionResult.duration.toFixed(2)} h</span>
                            </div>
                            <div className="flex justify-between border-b border-slate-905 py-1">
                              <span className="text-slate-500">Planet Size:</span>
                              <span className="text-slate-300 font-mono font-bold">
                                {detectionResult.classification === 'Exoplanet' ? `${detectionResult.rPlanet.toFixed(2)} R⊕` : 'N/A'}
                              </span>
                            </div>
                            <div className="flex justify-between border-b border-slate-905 py-1">
                              <span className="text-slate-500">Signal SNR:</span>
                              <span className="text-slate-300 font-mono font-bold">{detectionResult.snr.toFixed(1)}</span>
                            </div>
                            <div className="flex justify-between border-b border-slate-905 py-1">
                              <span className="text-slate-500">Stellar Age:</span>
                              <span className="text-slate-300 font-mono font-bold">{detectionResult.stellarAge.toFixed(1)} Gyr</span>
                            </div>
                          </div>
                        </div>

                        {/* Section 3: AI Reasoning */}
                        {reasoning && (
                          <div className="space-y-2">
                            <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-1 flex items-center gap-1.5">
                              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                              3. AI Classifier Vetting
                            </h5>
                            <div className="space-y-1.5 text-[10px]">
                              {reasoning.rankedFeatures.map((test, index) => (
                                <div key={index} className="flex items-start gap-1.5">
                                  <span className={test.passed ? 'text-emerald-450 font-bold' : 'text-rose-450 font-bold'}>
                                    {test.passed ? '✓' : '✗'}
                                  </span>
                                  <div className="leading-normal">
                                    <span className="font-semibold text-slate-300">{test.name}: </span>
                                    <span className="text-slate-400">{test.explanation}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Section 4: Habitability Assessment */}
                        {assessment && (
                          <div className="space-y-2">
                            <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-1 flex items-center gap-1.5">
                              <Globe className="h-3.5 w-3.5 text-indigo-400" />
                              4. Habitability Assessment
                            </h5>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
                              <div className="flex justify-between border-b border-slate-905 py-1">
                                <span className="text-slate-500">HZ Status:</span>
                                <span className={detectionResult.inHabitableZone ? 'text-emerald-450 font-bold' : 'text-slate-400'}>
                                  {detectionResult.inHabitableZone ? 'YES' : 'NO'}
                                </span>
                              </div>
                              <div className="flex justify-between border-b border-slate-905 py-1">
                                <span className="text-slate-500">Designation:</span>
                                <span className="text-slate-350">{detectionResult.planetType}</span>
                              </div>
                              <div className="flex justify-between border-b border-slate-905 py-1">
                                <span className="text-slate-500">Equil. Temp (Teq):</span>
                                <span className="text-slate-300 font-mono">{assessment.equilibriumTemp} K</span>
                              </div>
                              <div className="flex justify-between border-b border-slate-905 py-1">
                                <span className="text-slate-500">Insolation Flux:</span>
                                <span className="text-slate-300 font-mono">{assessment.insolationFlux.toFixed(2)} S⊕</span>
                              </div>
                              <div className="flex justify-between border-b border-slate-905 py-1">
                                <span className="text-slate-500">Stellar Teff:</span>
                                <span className="text-slate-300 font-mono">{assessment.stellarTeff} K</span>
                              </div>
                              <div className="flex justify-between border-b border-slate-905 py-1">
                                <span className="text-slate-500">Stellar L_sun:</span>
                                <span className="text-slate-300 font-mono">{assessment.stellarLuminosity.toFixed(2)} L⊙</span>
                              </div>
                            </div>
                          </div>
                        )}

                      </div>
                      
                      <div className="flex gap-2">
                        <Button 
                          variant="outline" 
                          className="flex-1 text-xs border-slate-700 hover:bg-slate-800 text-slate-200 cursor-pointer"
                          onClick={handleCopyClipboard}
                        >
                          {copied ? 'Copied!' : 'Copy Report'}
                        </Button>
                        <Button 
                          className="flex-1 text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium cursor-pointer"
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

            {/* PDF Error Toast */}
            {pdfError && (
              <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-[999] flex items-center gap-3 px-5 py-3 bg-[#1a0a0a] border border-rose-500/40 rounded-xl shadow-2xl text-xs animate-in slide-in-from-bottom-4 duration-300">
                <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
                <span className="text-rose-300 font-medium">⚠ PDF generation failed — please try again</span>
                <button onClick={() => setPdfError(false)} className="ml-2 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
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
                    : msg.isError
                    ? 'bg-rose-950/40 border border-rose-500/25 text-rose-300 rounded-tl-none'
                    : 'bg-[#0f172a] border border-slate-850 text-slate-300 rounded-tl-none'
                }`}
              >
                {msg.sender === 'user' ? msg.text : renderMessageContent(msg.text)}
                {msg.isError && msg.retryPayload && (
                  <button
                    onClick={(e) => handleSendMessage(e as any, msg.retryPayload)}
                    disabled={aiLoading}
                    className="mt-2 flex items-center gap-1 text-[10px] font-semibold text-rose-300 hover:text-white border border-rose-500/30 hover:border-indigo-400/40 hover:bg-indigo-500/10 px-2 py-1 rounded-md transition-all cursor-pointer disabled:opacity-40"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Try again
                  </button>
                )}
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
