export type RiskLevel = "low" | "medium" | "high";
export type ActionType = "pass" | "review" | "flag" | "takedown";
export type EvidenceSource = "forensics" | "vision_llm" | "text_rule" | "text_llm";

export interface Evidence {
  source: EvidenceSource;
  name: string;
  score: number;
  weight: number;
  description: string;
  region?: number[] | null;
  severity: string;
}

export interface ImageAnalysis {
  width: number;
  height: number;
  format: string;
  heatmap?: string | null;
  evidence: Evidence[];
  findings: string[];
  image_score: number;
}

export interface TextAnalysis {
  evidence: Evidence[];
  hits: string[];
  text_score: number;
  redline: boolean;
  advice: string[];
}

export interface RiskReport {
  risk_level: RiskLevel;
  risk_score: number;
  action: ActionType;
  reasoning: string;
  suggestions: string[];
  image?: ImageAnalysis | null;
  text?: TextAnalysis | null;
  degraded: boolean;
  elapsed_ms: number;
}

export interface HealthInfo {
  status: string;
  llm_provider: string;
  llm_enabled: boolean;
  vision_enabled: boolean;
}

export interface HistoryItem {
  id: string;
  createdAt: string;
  label: string;
  report: RiskReport;
}
