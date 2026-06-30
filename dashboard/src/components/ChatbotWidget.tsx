import React, { useState, useEffect, useRef } from 'react';
import { 
  X, 
  Send, 
  ArrowRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

import { 
  getClassReasoning, 
  getHabitabilityAssessment, 
  generateSummary
} from './LightCurveViewer';

interface ChatbotWidgetProps {
  setActiveTab?: (tab: string) => void;
  onSelectStar?: (id: string) => void;
  activeStarId?: string;
  activeDetectionResult?: any | null;
  stats?: {
    targetsMapped: number;
    candidatesFound: number;
    avgConfidence: number;
    lastPipelineRun: string;
  };
}

interface Message {
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  actions?: Array<{
    label: string;
    onClick: () => void;
  }>;
}

export function ChatbotWidget({ 
  setActiveTab, 
  onSelectStar, 
  activeStarId, 
  activeDetectionResult, 
  stats 
}: ChatbotWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'assistant',
      text: "Astra online. Mission control parameters initialized. I am here to assist with telemetry interpretation, light curve vetting, and stellar candidate searches. How can I guide your exploration today?",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isThinking]);

  // Default suggestions based on active target state
  const quickReplies = activeDetectionResult 
    ? [
        `Why was TIC ${activeStarId} classified?`,
        `Is TIC ${activeStarId} habitable?`,
        `Show parameters for TIC ${activeStarId}`,
        "Generate summary report"
      ]
    : [
        "How do I search a TIC ID?",
        "What is BLS?",
        "What does AI confidence mean?",
        "How do I read the light curve?"
      ];

  // Helper response parser
  const getBotResponse = (userMessage: string): { text: string; actions?: Array<{ label: string; onClick: () => void }> } => {
    const msg = userMessage.toLowerCase().trim();

    // ==========================================
    // Target-Specific Vetting & Telemetry (Lifting Copilot Features)
    // ==========================================
    const hasTargetResult = !!activeDetectionResult;

    // 1. Vetting & Classification Reasoning
    if (msg.includes('why') || msg.includes('reason') || msg.includes('vetting') || msg.includes('checks')) {
      if (!hasTargetResult) {
        return {
          text: `Astra Alert: No active telemetry loaded for TIC ${activeStarId || 'N/A'}. Please transition to the Light Curve Viewer and select "Detect Signal" to boot up our vetting classification pipeline.`,
          actions: setActiveTab ? [{
            label: "Go to Light Curve Viewer",
            onClick: () => setActiveTab('viewer')
          }] : []
        };
      }
      const reasoning = getClassReasoning(activeDetectionResult);
      const testsText = reasoning.rankedFeatures
        .map((f, i) => `• **#${i+1} ${f.name}**: ${f.passed ? '✓ Passed' : '✗ Failed'} — ${f.explanation}`)
        .join('\n');
      
      return {
        text: `Vetting Vitals for Target TIC ${activeStarId}:\n\n**Vetting Checks Status:**\n${testsText}\n\n**Astra Vetting Analysis:**\n${reasoning.summary}`
      };
    }

    // 2. Habitability Assessment Details
    if (msg.includes('habitable') || msg.includes('habitability') || msg.includes('hz') || msg.includes('life') || msg.includes('temperature') || msg.includes('teq') || msg.includes('insolation')) {
      if (!hasTargetResult) {
        return {
          text: `Astra Alert: Habitability indexes are uncomputed for TIC ${activeStarId || 'N/A'}. Execute "Detect Signal" to calculate equilibrium temperature bounds.`,
          actions: setActiveTab ? [{
            label: "Go to Light Curve Viewer",
            onClick: () => setActiveTab('viewer')
          }] : []
        };
      }
      const hab = getHabitabilityAssessment(activeDetectionResult);
      const hzStatus = activeDetectionResult.inHabitableZone 
        ? `**YES**, the candidate orbits inside the Habitable Zone.` 
        : `**NO**, the candidate orbits outside the habitable boundaries.`;

      return {
        text: `Stellar Habitability Profile [TIC ${activeStarId}]:\n• **Habitable Zone (HZ):** ${hzStatus}\n• **Estimated Planet Type:** ${activeDetectionResult.planetType}\n• **Equilibrium Temperature:** ${hab.equilibriumTemp} K\n• **Insolation Flux:** ${hab.insolationFlux.toFixed(2)} S⊕\n• **Orbital Distance (a):** ${hab.orbitalDistance.toFixed(3)} AU\n• **Stellar Teff:** ${hab.stellarTeff} K\n• **Stellar Luminosity:** ${hab.stellarLuminosity.toFixed(2)} L⊙`
      };
    }

    // 3. Transit Parameters Log
    if (msg.includes('period') || msg.includes('orbit') || msg.includes('depth') || msg.includes('duration') || msg.includes('snr') || msg.includes('size') || msg.includes('radius') || msg.includes('parameters') || msg.includes('metrics')) {
      if (!hasTargetResult) {
        return {
          text: `Astra Alert: Transit parameters are empty for TIC ${activeStarId || 'N/A'}. Please run the periodogram solver pipeline first.`,
          actions: setActiveTab ? [{
            label: "Go to Light Curve Viewer",
            onClick: () => setActiveTab('viewer')
          }] : []
        };
      }
      return {
        text: `Stellar Transit Parameters [TIC ${activeStarId}]:\n• **Orbital Period:** ${activeDetectionResult.period.toFixed(4)} days (${(activeDetectionResult.period * 24).toFixed(1)} hours)\n• **Transit Depth:** ${(activeDetectionResult.depth * 100).toFixed(4)}% (${(activeDetectionResult.depth * 1e6).toFixed(0)} ppm)\n• **Transit Duration:** ${activeDetectionResult.duration.toFixed(2)} hours\n• **Planet Radius:** ${activeDetectionResult.classification === 'Exoplanet' ? `${activeDetectionResult.rPlanet.toFixed(2)} R⊕` : 'N/A'}\n• **Signal-to-Noise Ratio (SNR):** ${activeDetectionResult.snr.toFixed(1)}`
      };
    }

    // 4. Mission Summary Report Generation
    if (msg.includes('report') || msg.includes('summary') || msg.includes('generate')) {
      if (!hasTargetResult) {
        return {
          text: `Astra Alert: Vetting report is unavailable for TIC ${activeStarId || 'N/A'}. Run detection pipeline to generate.`,
          actions: setActiveTab ? [{
            label: "Go to Light Curve Viewer",
            onClick: () => setActiveTab('viewer')
          }] : []
        };
      }
      const summary = generateSummary(activeDetectionResult, activeStarId || '');
      return {
        text: `Copy that — generating stellar summary report for TIC ${activeStarId}:\n\n${summary}`
      };
    }
    
    // 1. Step-by-Step Vetting Instructions
    const ticMatch = msg.match(/tic\s*(\d+)/i) || msg.match(/find\s*planet\s*candidates?\s*for\s*(?:tic\s*)?(\d+)/i);
    if (ticMatch) {
      const ticId = ticMatch[1];
      return {
        text: `Copy that, Scientist. Initiating search parameters for TIC ${ticId}. Here is your vetting path:\n\n1. Switch to the **Light Curve Viewer**.\n2. Enter the target ID **TIC ${ticId}** in the search console.\n3. Click **Fetch Light Curve** to stream NASA photometry.\n4. Head to the **Signal Analysis** console on the right and select **Detect Signal** to boot up our ML classification pipeline.`,
        actions: [
          ...(setActiveTab ? [{
            label: `Go to Light Curve Viewer`,
            onClick: () => setActiveTab('viewer')
          }] : []),
          ...(onSelectStar ? [{
            label: `Load Target TIC ${ticId}`,
            onClick: () => onSelectStar(ticId)
          }] : [])
        ]
      };
    }

    // 2. Tab Navigation Guides
    if (msg.includes('search') || msg.includes('how to find') || msg.includes('viewer') || msg.includes('light curve')) {
      return {
        text: "Affirmative. Vetting targets is completed inside the **Light Curve Viewer** tab. Enter a TIC ID (e.g. 451598465) in the stellar search console, download the 2-minute cadence data stream, and execute transit analysis.",
        actions: setActiveTab ? [{
          label: "Switch to Light Curve Viewer",
          onClick: () => setActiveTab('viewer')
        }] : []
      };
    }

    if (msg.includes('sky map') || msg.includes('map') || msg.includes('southern')) {
      return {
        text: "Roger that. The **Southern Sky Map** tab displays all dwarf stars mapped in our catalog. You can pan, zoom, and highlight stars. Clicking a star pulls up its spatial telemetry and coordinates.",
        actions: setActiveTab ? [{
          label: "Open Southern Sky Map",
          onClick: () => setActiveTab('skymap')
        }] : []
      };
    }

    if (msg.includes('priority queue') || msg.includes('queue') || msg.includes('ranking')) {
      return {
        text: "Telemetry received. The **Vetting Priority Queue** ranks candidate star targets based on our neural network's classification confidence. This lists candidates that require manual validation.",
        actions: setActiveTab ? [{
          label: "Go to Priority Queue",
          onClick: () => setActiveTab('queue')
        }] : []
      };
    }

    // 3. Conceptual Science Answers
    if (msg.includes('bls') || msg.includes('box least squares') || msg.includes('periodogram')) {
      return {
        text: "Science Briefing: The **Box Least Squares (BLS)** algorithm fits a periodic box-like shape to the light curve photometry. It is the gold standard for searching for flat-bottomed dips which indicate an orbiting exoplanet blocking stellar light."
      };
    }

    if (msg.includes('cnn') || msg.includes('classifier') || msg.includes('model') || msg.includes('neural')) {
      return {
        text: "Science Briefing: Our **1D Convolutional Neural Network (CNN)** classifier reads the folded light curve signal and categorizes the target into one of four classes: Exoplanet, Eclipsing Binary Star, Stellar Blend (background noise), or rotating Starspots."
      };
    }

    if (msg.includes('confidence') || msg.includes('ai score') || msg.includes('%')) {
      return {
        text: "Affirmative. **AI Confidence %** represents the probability metric output by our 1D CNN model. A value of 95% indicates high classification stability. Dips under 50% trigger an ambiguity warning."
      };
    }

    if (msg.includes('transit') || msg.includes('method') || msg.includes('how do you find')) {
      return {
        text: "Telemetry science check: The **Transit Method** detects exoplanets by tracking a star's brightness over time. A periodic, uniform dip in the light curve points to an orbiting planet crossing our line of sight."
      };
    }

    if (msg.includes('dip') || msg.includes('dips')) {
      return {
        text: "Stellar photometry logs: A **light curve dip** is a localized drop in relative flux. Periodic, flat-bottomed dips suggest a transiting exoplanet. Alternating deep/shallow dips usually point to a Binary Star system."
      };
    }

    if (msg.includes('stats') || msg.includes('dashboard') || msg.includes('progress')) {
      const total = stats?.targetsMapped ?? 15;
      const exoplanets = stats?.candidatesFound ?? 4;
      const confidence = stats?.avgConfidence ?? 82;
      const pipeline = stats?.lastPipelineRun ?? 'June 30, 2026';
      return {
        text: `Mission Control Status Telemetry:\n• **Targets Mapped:** ${total}\n• **Exoplanet Candidates:** ${exoplanets}\n• **Average Classifier Confidence:** ${confidence}%\n• **Last Pipeline Sync:** ${pipeline}\n\nExplore these details in the dashboard tab views.`
      };
    }

    // 4. Default Fallback
    return {
      text: "Command not recognized. Please ask about TIC target IDs (e.g. 'TIC 451598465'), dashboard tabs, or astronomical terms like 'BLS', '1D CNN', 'transit method', or 'AI confidence'."
    };
  };

  const handleSend = (textToSend: string) => {
    if (!textToSend.trim()) return;

    const userMsg: Message = {
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsThinking(true);

    // Simulate thinking delay (700ms to 1200ms)
    const thinkingTime = 700 + Math.random() * 500;
    setTimeout(() => {
      const response = getBotResponse(textToSend);
      const botMsg: Message = {
        sender: 'assistant',
        text: response.text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        actions: response.actions
      };
      setMessages(prev => [...prev, botMsg]);
      setIsThinking(false);
    }, thinkingTime);
  };

  return (
    <>
      {/* Floating Action Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 p-1 rounded-full bg-[#0a0e1a]/95 hover:bg-slate-900 text-white shadow-2xl z-40 transition-all active:scale-95 flex items-center gap-3 group border border-indigo-550/40 glow-accent-purple overflow-hidden"
        >
          <div className="h-16 w-16 rounded-full overflow-hidden border border-indigo-500/30 bg-[#070b19] relative shrink-0">
            <img src="/astra-avatar.jpg" alt="Astra Bot" className="w-full h-full object-cover" />
          </div>
          <span className="max-w-0 overflow-hidden group-hover:max-w-xs group-hover:pr-4 transition-all duration-300 ease-out text-sm font-semibold uppercase tracking-wider whitespace-nowrap text-indigo-300">
            Astra Assistant
          </span>
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-0 sm:bottom-20 right-0 sm:right-6 w-full sm:w-[410px] h-full sm:h-[560px] bg-[#0a0e1a]/95 border-t sm:border border-slate-800/80 sm:rounded-xl shadow-2xl z-50 flex flex-col backdrop-blur-md overflow-hidden animate-in slide-in-from-bottom-5 duration-300 max-sm:top-0">
          
          {/* Header */}
          <div className="p-3.5 bg-gradient-to-r from-indigo-950/40 via-indigo-900/20 to-transparent border-b border-slate-800/60 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-10 w-10 rounded-full border border-indigo-500/30 overflow-hidden flex items-center justify-center bg-[#070b19] shrink-0">
                <img src="/astra-avatar.jpg" alt="Astra Avatar" className="w-full h-full object-cover" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-100 tracking-wide">Astra</h4>
                <p className="text-[9px] text-slate-500 font-medium uppercase tracking-wider font-mono">Mission Assistant</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 rounded-md hover:bg-slate-800/60 text-slate-550 hover:text-slate-200 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Conversation History */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 scrollbar text-xs">
            {messages.map((msg, idx) => (
              <div key={idx} className="space-y-1">
                <div 
                  className={`flex gap-2 max-w-[85%] ${
                    msg.sender === 'user' ? 'ml-auto flex-row-reverse items-end' : 'mr-auto flex-row items-start'
                  }`}
                >
                  {msg.sender === 'assistant' && (
                    <div className="h-8 w-8 rounded-full border border-indigo-500/30 overflow-hidden shrink-0 bg-[#070b19] mt-0.5 shadow-[0_0_10px_rgba(99,102,241,0.1)]">
                      <img src="/astra-avatar.jpg" alt="Astra Avatar" className="w-full h-full object-cover" />
                    </div>
                  )}
                  <div className="flex flex-col">
                    <div 
                      className={`p-3 rounded-xl leading-relaxed ${
                        msg.sender === 'user' 
                          ? 'bg-indigo-650 text-white rounded-tr-none' 
                          : 'bg-[#0f172a] border border-slate-850 text-slate-300 rounded-tl-none'
                      }`}
                    >
                      {/* Render message line breaks correctly */}
                      {msg.text.split('\n').map((line, lIdx) => (
                        <React.Fragment key={lIdx}>
                          {line}
                          {lIdx < msg.text.split('\n').length - 1 && <br />}
                        </React.Fragment>
                      ))}

                      {/* Integrated actions buttons */}
                      {msg.actions && msg.actions.length > 0 && (
                        <div className="mt-3 space-y-2 border-t border-slate-800/40 pt-2.5">
                          {msg.actions.map((act, aIdx) => (
                            <button
                              key={aIdx}
                              onClick={() => {
                                act.onClick();
                                setIsOpen(false); // minimize chatbot on active navigation click
                              }}
                              className="w-full flex items-center justify-between text-[10px] text-indigo-300 hover:text-white bg-indigo-500/5 hover:bg-indigo-500/15 border border-indigo-500/25 px-2.5 py-1.5 rounded transition-all font-sans font-medium"
                            >
                              <span>{act.label}</span>
                              <ArrowRight className="h-3 w-3 shrink-0" />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <span className="text-[8px] text-slate-650 uppercase tracking-wider font-semibold font-mono mt-1 px-1">
                      {msg.sender === 'user' ? (
                        <>Scientist · {msg.timestamp}</>
                      ) : (
                        <>Astra · {msg.timestamp}</>
                      )}
                    </span>
                  </div>
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {isThinking && (
              <div className="flex gap-2 max-w-[85%] mr-auto items-start animate-pulse">
                <div className="h-8 w-8 rounded-full border border-indigo-500/30 overflow-hidden shrink-0 bg-[#070b19] mt-0.5">
                  <img src="/astra-avatar.jpg" alt="Astra Avatar" className="w-full h-full object-cover" />
                </div>
                <div className="flex flex-col">
                  <div className="p-3 bg-[#0f172a] border border-slate-850 rounded-xl rounded-tl-none flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce" />
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce delay-100" />
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce delay-200" />
                  </div>
                  <span className="text-[8px] text-slate-650 mt-1 px-1 uppercase tracking-wider font-semibold font-mono">Thinking…</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick-reply chip suggestions overlay */}
          {!isThinking && messages[messages.length - 1]?.sender === 'assistant' && (
            <div className="px-4 py-2 border-t border-slate-850/40 bg-[#070a14]/30 flex flex-wrap gap-1.5 select-none">
              {quickReplies.map((reply, rIdx) => (
                <button
                  key={rIdx}
                  onClick={() => handleSend(reply)}
                  className="text-[9px] text-slate-400 hover:text-indigo-300 bg-slate-900/60 hover:bg-indigo-950/20 border border-slate-800 hover:border-indigo-500/30 px-2 py-1 rounded-full transition-all cursor-pointer font-sans"
                >
                  {reply}
                </button>
              ))}
            </div>
          )}

          {/* Input Panel */}
          <form 
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }} 
            className="p-3 bg-[#070a14] border-t border-slate-850 flex gap-2 items-center"
          >
            <Input
              type="text"
              placeholder="Ask Astra (e.g. 'find planet for TIC 451598465')..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isThinking}
              className="bg-[#020617] border-slate-700 text-xs h-8.5 focus-visible:ring-indigo-500 placeholder:text-slate-600 flex-1"
            />
            <Button 
              type="submit"
              disabled={isThinking || !input.trim()}
              className="h-8.5 w-8.5 p-0 bg-indigo-650 hover:bg-indigo-500 text-white shrink-0 flex items-center justify-center cursor-pointer"
            >
              <Send className="h-3.5 w-3.5" />
            </Button>
          </form>
        </div>
      )}
    </>
  );
}
