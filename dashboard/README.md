# TESS Exoplanet Dashboard - Backend Integration Guide

This document outlines the TypeScript interfaces and mock helper stubs implemented in the dashboard client. These stubs are ready to be wired into real ML pipeline endpoints, API controllers, or LLM integrations.

---

## 1. Global TypeScript Interfaces

The core data structures used by all stubs are declared in the codebase:

```typescript
export interface DetectionResult {
  event: string;              // Designation (e.g. "TOI-1431.01")
  classification: 'Exoplanet' | 'Binary Star' | 'Stellar Blend' | 'Starspot';
  confidence: number;         // Decimal value between 0.0 and 1.0 (e.g., 0.945)
  period: number;             // Orbital period in days (e.g. 3.512)
  depth: number;              // Fractional transit depth (e.g. 0.0035 = 3500 ppm)
  duration: number;           // Transit event duration in hours (e.g. 2.45)
  snr: number;                // Signal-to-Noise ratio (e.g., 14.2)
  rPlanet: number;            // Estimated planet radius in Earth radii (R⊕)
  distance: number;           // Distance to host system in light-years
  stellarAge: number;         // Host star age estimate in billion years (Gyr)
  inHabitableZone: boolean;   // Evaluates if target orbits in stellar habitable zone
  planetType: string;         // Physical category description (e.g. "Hot Jupiter")
}

export interface FeatureTest {
  name: string;               // E.g. "R_planet size check"
  passed: boolean;            // Success status of the test
  explanation: string;        // One-line plain English explanation
  importance: number;         // Relative importance / SHAP value ranking metric
}

export interface ReasoningResult {
  rankedFeatures: FeatureTest[];
  summary: string;            // Why this classification? summary text
}

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

export interface EnrichedDetectionResult extends DetectionResult {
  reasoning: ReasoningResult;
  habitability: HabitabilityAssessment;
}
```

---

## 2. Mock Helper Stubs & Signatures

All helper stubs are exported from [LightCurveViewer.tsx](file:///c:/Users/Kanishka/Desktop/The-Transit-Detection-/dashboard/src/components/LightCurveViewer.tsx) and [PriorityQueue.tsx](file:///c:/Users/Kanishka/Desktop/The-Transit-Detection-/dashboard/src/components/PriorityQueue.tsx).

### A. `detectSignal(ticId)`
Simulates the core exoplanet detection ML pipeline (originally utilizing a 1D CNN classifier).
* **Expected Input**: 
  * `ticId`: `string` (e.g., `"451598465"`)
* **Expected Output**: `Promise<DetectionResult>`
* **Signature**:
```typescript
export function detectSignal(ticId: string): Promise<DetectionResult>
```
* **Integration Plan**: Replace the `setTimeout` simulation block with an HTTP `POST` or `GET` fetch request directed at your local Python flask/fastapi web server running the CNN prediction model:
```typescript
const response = await fetch(`/api/predict/${ticId}`);
const result: DetectionResult = await response.json();
return result;
```

---

### B. `getPlanetTypeLabel(classification, rPlanet, period)`
Implements rule-based labeling of planet physical categories based on radius and proximity.
* **Expected Inputs**:
  * `classification`: `string` (e.g. `"Exoplanet"`, `"Binary Star"`)
  * `rPlanet`: `number` (estimated planet size in Earth radii $R_{\oplus}$)
  * `period`: `number` (orbital period in days)
* **Expected Output**: `string` (e.g., `"Hot Jupiter"`, `"Warm Sub-Neptune"`, `"Super-Earth"`, `"Terrestrial (Rocky)"`)
* **Signature**:
```typescript
export function getPlanetTypeLabel(
  classification: string,
  rPlanet: number,
  period: number
): string
```

---

### C. `generateSummary(starData, ticId)`
Compiles tabular parameters, stellar properties, and classification states into a readable scientific paragraph.
* **Expected Inputs**:
  * `data`: `DetectionResult` (resolved target data object)
  * `ticId`: `string` (the active TIC identifier)
* **Expected Output**: `string` (scientific paragraph text)
* **Signature**:
```typescript
export function generateSummary(data: DetectionResult, ticId: string): string
```

---

### D. `askAboutStar(starData, question, ticId)`
Lets the user ask natural language questions about the active star's photometry and parameters, utilizing a built-in glossary fallback.
* **Expected Inputs**:
  * `data`: `EnrichedDetectionResult | null` (current star data with reasoning and habitability nested profiles)
  * `question`: `string` (the scientist's query text)
  * `ticId`: `string` (active TIC ID)
* **Expected Output**: `Promise<string>` (assistant response paragraph with basic Markdown support)
* **Signature**:
```typescript
export function askAboutStar(
  data: EnrichedDetectionResult | null,
  question: string,
  ticId: string
): Promise<string>
```
* **Integration Plan**: Route the question alongside the star's telemetry payload to an LLM agent endpoint. System instructions can guide the LLM to write in Markdown and answer questions grounded strictly in the provided telemetry parameters.

---

### E. `getClassReasoning(starData)`
Provides decision interpretability details, ranked by feature importance / SHAP weights.
* **Expected Inputs**:
  * `data`: `DetectionResult` (current star data)
* **Expected Output**: `ReasoningResult` (ranked list of feature tests and a descriptive text summary)
* **Signature**:
```typescript
export function getClassReasoning(data: DetectionResult): ReasoningResult
```

---

### F. `getHabitabilityAssessment(starData)`
Provides derived habitability indicators and orbit vetting limits for SVG diagram mapping.
* **Expected Inputs**:
  * `data`: `DetectionResult` (current star data)
* **Expected Output**: `HabitabilityAssessment`
* **Signature**:
```typescript
export function getHabitabilityAssessment(data: DetectionResult): HabitabilityAssessment
```

---

### G. `getAllTargetsRanked(starsList)`
Ranks all preloaded TESS stars by classifier confidence.
* **Expected Inputs**:
  * `starsList`: `StarTarget[]` (array of star data nodes)
* **Expected Output**: `StarTarget[]` (sorted by confidence descending)
* **Signature**:
```typescript
export function getAllTargetsRanked(starsList: StarTarget[]): StarTarget[]
```
