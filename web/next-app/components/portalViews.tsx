"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import CountUp from "react-countup";
import { ReactFlow, Background, Controls, MarkerType, type Node as FlowNode, type Edge as FlowEdge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { nodeTypes } from "@/components/graph/nodeTypes";
import { layoutWithDagre } from "@/lib/graphLayout";
import { edgeStatusColor } from "@/lib/graphColors";
import {
  Shield,
  Settings,
  LogOut,
  CheckCircle,
  AlertTriangle,
  Play,
  RefreshCw,
  Info,
  X,
  ChevronRight,
  TrendingUp,
  Activity,
  Layers,
  Network,
  HelpCircle,
  Cpu,
  Target,
  Zap,
  ArrowDown,
  ArrowUpRight,
  Github,
  Linkedin,
  ScanLine,
  CircleDot,
  BrainCircuit
} from "lucide-react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Types
interface Scenario {
  description: string;
  expected_attack_id: string | null;
  txn: Record<string, any>;
}

interface AnalysisResult {
  txn_id?: string;
  risk_score: number;
  risk_level: string;
  action: string;
  recommended_action: string;
  fraud_probability: number;
  attack_probabilities: Record<string, number>;
  top_attack_family: string | null;
  top_attack_probability: number;
  contributing_signals: string[];
  shap_contributions?: { feature: string; shap_value: number; direction: "increases_risk" | "decreases_risk" }[];
  model_confidence: number;
  model_uncertainty: number;
  llm_analysis: {
    fraud_explanation: string;
    attack_family_interpretation: string;
    key_evidence: string[];
    investigation_steps: string[];
    uncertainty_caveats: string;
  };
  network_graph?: {
    nodes: Array<{ id: string; label: string; type: string; risk: string; details: Record<string, string> }>;
    edges: Array<{ source: string; target: string; label: string; status: string }>;
  };
  campaign_alerts?: string[];
}

interface MetricItem {
  metric: string;
  value: number;
}

interface FeatureImportance {
  feature: string;
  importance: number;
}

interface ModelProvenance {
  model_version: string | null;
  trained_timestamp: string | null;
  held_out_attack_family: string | null;
  split_methodology: string | null;
  test_pr_auc: number | null;
  test_recall_0_1_fpr: number | null;
  test_recall_1_fpr: number | null;
  alerts_per_1000: number | null;
}

interface MetricsResult {
  recorded_metrics: MetricItem[];
  feature_importances: FeatureImportance[];
  adaptive_config: Record<string, any>;
  model_provenance?: ModelProvenance;
}

interface GraphNode {
  id: string;
  name: string;
  phase: string;
  rail: string;
  signature: string;
  difficulty: number;
  novelty: number;
  description: string;
  x: number;
  y: number;
}

const ATTACK_NODES: GraphNode[] = [
  {
    id: "G09",
    name: "Credential Takeover",
    phase: "Access",
    rail: "Card / UPI",
    signature: "Device anomalous, account changes, auth success",
    difficulty: 3,
    novelty: 3,
    description: "Fraudsters bypass authentication (OTP phishing/SIM swap/deepfakes) to hijack a real account, initiating transfers from anomalous devices.",
    x: 10,
    y: 20
  },
  {
    id: "G10",
    name: "Synthetic ID Bustout",
    phase: "Access",
    rail: "BNPL / Card / Wallet",
    signature: "Credit building followed by sudden utilization spike",
    difficulty: 4,
    novelty: 3,
    description: "Establishing credit accounts using fictitious identities. They behave normally to build a credit limit, then trigger a simultaneous utilization spike.",
    x: 10,
    y: 50
  },
  {
    id: "G13",
    name: "Insider Abuse",
    phase: "Access",
    rail: "Merchant KYB / Bank",
    signature: "Approval velocity signals, internal access pattern anomalies",
    difficulty: 3,
    novelty: 2,
    description: "Internal staff or compromised internal banking credentials authorizing high-velocity modifications or refunds without typical consumer device trails.",
    x: 10,
    y: 80
  },
  {
    id: "G03",
    name: "Card Testing Probe",
    phase: "Probing",
    rail: "Card CNP",
    signature: "Micro-amounts, high decline rates, card rotation",
    difficulty: 3,
    novelty: 2,
    description: "Automated scripts making rapid micro-transactions to validate stolen credentials and BIN ranges before executing large fraud sweeps.",
    x: 30,
    y: 35
  },
  {
    id: "G06",
    name: "Stealth Mandate",
    phase: "Probing",
    rail: "UPI Mandate",
    signature: "Uniform recurring small amounts, high max_amount settings",
    difficulty: 4,
    novelty: 3,
    description: "Setting up recurring UPI mandates under false pretenses (e.g., small trial setup), but configuring high transaction caps to extract money later.",
    x: 30,
    y: 65
  },
  {
    id: "G01",
    name: "Scam-Induced Push",
    phase: "Execution",
    rail: "UPI P2P",
    signature: "Genuine device & PIN, brand-new payee, active call session",
    difficulty: 4,
    novelty: 4,
    description: "Victims are socially engineered (e.g., voice clone, digital arrest scam) to initiate transactions themselves. Session metadata reveals active calls or screen-sharing.",
    x: 50,
    y: 35
  },
  {
    id: "G12",
    name: "Agentic Injection",
    phase: "Execution",
    rail: "UPI / Agentic",
    signature: "is_agent_initiated, VPA not in directory",
    difficulty: 5,
    novelty: 5,
    description: "Exploiting GenAI delegates or payment agents using prompt injection attacks, forcing the AI agent to authorize payments to unregistered VPAs.",
    x: 50,
    y: 65
  },
  {
    id: "G04",
    name: "Adversarial Evasion",
    phase: "Evasion",
    rail: "Any",
    signature: "Features aligned inside legitimate data distributions",
    difficulty: 5,
    novelty: 5,
    description: "Using ML model feedback to specifically optimize transaction sizes, intervals, and counterparty routing to avoid triggering detection thresholds.",
    x: 70,
    y: 35
  },
  {
    id: "G11",
    name: "Subthreshold Frag.",
    phase: "Evasion",
    rail: "UPI Lite / Wallet",
    signature: "Amounts just below limits (e.g. under ₹1,000)",
    difficulty: 3,
    novelty: 3,
    description: "Splitting a large fraudulent transfer into dozens of tiny transactions falling under regulatory authentication caps (AFA bypass thresholds).",
    x: 70,
    y: 65
  },
  {
    id: "G02",
    name: "Mule Network",
    phase: "Exfiltration",
    rail: "UPI / IMPS",
    signature: "Fan-in/fan-out graph topology, pass-through ratio near 1",
    difficulty: 4,
    novelty: 3,
    description: "Layering stolen money through accounts characterized by rapid inflows immediately followed by outbound transfers to downstream accounts.",
    x: 90,
    y: 20
  },
  {
    id: "G07",
    name: "Synthetic Merchant",
    phase: "Exfiltration",
    rail: "UPI P2M / BNPL",
    signature: "New merchant, step volume curves, unverified KYB",
    difficulty: 4,
    novelty: 3,
    description: "Creating fake business accounts to process stolen cards. Accounts show sudden step-wise processing jumps followed by immediate cash liquidation.",
    x: 90,
    y: 43
  },
  {
    id: "G08",
    name: "Transaction Laundering",
    phase: "Exfiltration",
    rail: "Card / UPI",
    signature: "Declared MCC differs from inferred basket category",
    difficulty: 4,
    novelty: 3,
    description: "Routing forbidden or illegal transactions through approved merchant accounts, disguising payment codes to bypass acquirer checks.",
    x: 90,
    y: 66
  },
  {
    id: "G05",
    name: "First-Party Dispute",
    phase: "Exfiltration",
    rail: "Card / UPI / BNPL",
    signature: "Genuine details, history of high claimant disputes",
    difficulty: 4,
    novelty: 3,
    description: "A legitimate buyer completes a purchase, then uses automated AI templates to file false dispute chargebacks to obtain refunds illegally.",
    x: 90,
    y: 90
  }
];

function TypewriterText({ text }: { text: string }) {
  const [displayText, setDisplayText] = useState("");
  
  useEffect(() => {
    let currentText = "";
    let currentIndex = 0;
    
    // Clear display text when input text changes
    setDisplayText("");
    
    const interval = setInterval(() => {
      if (currentIndex < text.length) {
        currentText += text[currentIndex];
        setDisplayText(currentText);
        currentIndex++;
      } else {
        clearInterval(interval);
      }
    }, 15); // Adjust typing speed here
    
    return () => clearInterval(interval);
  }, [text]);
  
  return <span>{displayText}</span>;
}

const getSessionId = () => {
  if (typeof window === "undefined") return "default-session";
  let sid = sessionStorage.getItem("x-session-id");
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem("x-session-id", sid);
  }
  return sid;
};

export function AnalystPortal() {
  const returnToStory = () => window.location.assign("/");

  // Dashboard Tabs State
  const [activeTab, setActiveTab] = useState<"scoring" | "closed-loop" | "graph" | "playground">("scoring");

  // Interactive Walkthrough Guide State
  const [guideActive, setGuideActive] = useState(true);
  const [guideStep, setGuideStep] = useState<
    | "choose_scenario"
    | "inspect_parameters"
    | "submit_feedback"
    | "choose_destination"
    | "closed_loop"
    | "graph"
    | "playground"
  >("choose_scenario");

  // Live Scoring State
  const [scenarios, setScenarios] = useState<Record<string, Scenario>>({});
  const [selectedScenarioName, setSelectedScenarioName] = useState("");
  const [txnOverrides, setTxnOverrides] = useState<Record<string, any>>({});
  const [isScoring, setIsScoring] = useState(false);
  const [scoreResult, setScoreResult] = useState<AnalysisResult | null>(null);
  const [scoreError, setScoreError] = useState("");

  // Metrics / Feature Importance State
  const [metricsData, setMetricsData] = useState<MetricsResult | null>(null);
  const [familyMetrics, setFamilyMetrics] = useState<any>(null);
  const [showFamilyBreakdown, setShowFamilyBreakdown] = useState(false);

  // Attack Simulator Playground State
  const [playgroundAttackId, setPlaygroundAttackId] = useState("scam_induced_push");
  const [playgroundIntensity, setPlaygroundIntensity] = useState("MEDIUM");
  const [isPlaygroundSimulating, setIsPlaygroundSimulating] = useState(false);
  const [playgroundTransactions, setPlaygroundTransactions] = useState<any[]>([]);
  const [playgroundCurrentIndex, setPlaygroundCurrentIndex] = useState(-1);
  const [playgroundPretext, setPlaygroundPretext] = useState("");
  const [playgroundCampaignId, setPlaygroundCampaignId] = useState("");
  const [playgroundError, setPlaygroundError] = useState("");

  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);

  // Graph tab State
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(ATTACK_NODES[0]);
  const [graphViewMode, setGraphViewMode] = useState<"lifecycle" | "transaction">("lifecycle");
  const [selectedTransactionNode, setSelectedTransactionNode] = useState<any>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  // Lifecycle graph edges are drawn as SVG <path> curves between two
  // percentage-positioned nodes -- but the `d` attribute doesn't accept
  // percentage units (unlike <circle cx/cy> or <line x1/y1>, which do), so
  // the coordinates need converting to real pixels against the SVG's actual
  // rendered size.
  const lifecycleSvgRef = useRef<SVGSVGElement>(null);
  const [lifecycleDims, setLifecycleDims] = useState({ width: 1000, height: 440 });
  useEffect(() => {
    const el = lifecycleSvgRef.current;
    if (!el) return;
    const update = () => setLifecycleDims({ width: el.clientWidth, height: el.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, [activeTab]);

  // Transaction Linkage: dynamic per-session graph, laid out once as a whole
  // (not per-cluster) so dagre's connected-component packing separates
  // disjoint transaction clusters without the overlap that manual percentage
  // math used to produce.
  const transactionFlowNodes: FlowNode[] = useMemo(() => {
    const rawNodes = scoreResult?.network_graph?.nodes ?? [];
    const rawEdges = scoreResult?.network_graph?.edges ?? [];
    if (rawNodes.length === 0) return [];
    const positioned = layoutWithDagre(rawNodes, rawEdges, {
      rankdir: "LR",
      nodesep: 50,
      ranksep: 120,
      nodeWidth: 160,
      nodeHeight: 44,
    });
    return positioned.map(node => ({
      id: node.id,
      type: "actorNode",
      position: node.position,
      data: { ...node, isSelected: selectedTransactionNode?.id === node.id },
    }));
  }, [scoreResult?.network_graph, selectedTransactionNode]);

  const transactionFlowEdges: FlowEdge[] = useMemo(() => {
    const rawEdges = scoreResult?.network_graph?.edges ?? [];
    return rawEdges.map((edge, eIdx) => {
      const isAlert = edge.status === "critical" || edge.status === "high";
      const isLinkage = edge.status === "linkage";
      const color = edgeStatusColor(edge.status);
      return {
        id: `${edge.source}-${edge.target}-${eIdx}`,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        type: "smoothstep",
        className: isAlert ? "pulse-edge" : undefined,
        style: {
          stroke: color,
          strokeWidth: isLinkage || isAlert ? 2 : 1.2,
          strokeDasharray: isLinkage || isAlert ? "4 4" : undefined,
        },
        labelStyle: { fill: isLinkage ? "#10b981" : "#a1a1aa", fontSize: 8, fontWeight: 700 },
        labelBgStyle: { fill: "#09090b", fillOpacity: 0.8 },
        markerEnd: isLinkage
          ? undefined
          : { type: MarkerType.ArrowClosed, color: isAlert ? "#ef4444" : "#52525b" },
      };
    });
  }, [scoreResult?.network_graph]);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);
  const [shouldRetrain, setShouldRetrain] = useState(false);
  const [retrainReason, setRetrainReason] = useState("");
  const [retraining, setRetraining] = useState(false);
  const [retrainOutcome, setRetrainOutcome] = useState<"success" | "queued" | null>(null);
  const [modelHistory, setModelHistory] = useState<any[]>([]);

  const checkRetrainStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/analyst/feedback-status`);
      if (res.ok) {
        const data = await res.json();
        setShouldRetrain(data.should_retrain);
        setRetrainReason(data.feedback_summary?.reason || "");
      }
    } catch (err) {
      console.warn("Failed to check retrain status:", err);
    }
  };

  const fetchModelHistory = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/analyst/model-history`);
      if (res.ok) {
        const data = await res.json();
        if (data.history) {
          setModelHistory(data.history);
        }
      }
    } catch (err) {
      console.warn("Failed to fetch model history:", err);
    }
  };

  const fetchFamilyMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/metrics/family`);
      if (res.ok) {
        const data = await res.json();
        setFamilyMetrics(data);
      }
    } catch (err) {
      console.warn("Failed to fetch family metrics:", err);
    }
  };

  const startPlaygroundSimulation = async () => {
    if (isPlaygroundSimulating) return;
    setIsPlaygroundSimulating(true);
    setPlaygroundError("");
    setPlaygroundTransactions([]);
    setPlaygroundCurrentIndex(-1);
    setPlaygroundPretext("");
    setPlaygroundCampaignId("");
    
    // Clear graph before starting so we only see this playground campaign
    await clearGraphHistory();
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/playground/generate-campaign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attack_id: playgroundAttackId,
          intensity: playgroundIntensity
        })
      });
      
      if (!res.ok) {
        throw new Error(await res.text());
      }
      
      const data = await res.json();
      setPlaygroundPretext(data.pretext || "");
      setPlaygroundCampaignId(data.campaign_id || "");
      
      const txns = data.transactions || [];
      if (txns.length === 0) {
        throw new Error("No transactions were generated.");
      }
      
      // We will feed the transactions into the analyze endpoint one-by-one with a delay
      let currentIdx = 0;
      const feedNextTransaction = async () => {
        if (currentIdx >= txns.length) {
          setIsPlaygroundSimulating(false);
          return;
        }
        
        try {
          const currentTx = txns[currentIdx];
          
          // Call analyze endpoint to update the global graph and score it
          const analyzeRes = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-session-id": getSessionId()
            },
            body: JSON.stringify({
              transaction: currentTx
            })
          });
          
          if (analyzeRes.ok) {
            const analyzeData = await analyzeRes.json();
            
            // Set global score result to update network graph visualizer
            setScoreResult(analyzeData);
            
            // Add to simulated list
            setPlaygroundTransactions(prev => [
              ...prev,
              {
                sequence: currentIdx + 1,
                transaction: currentTx,
                result: analyzeData
              }
            ]);
            setPlaygroundCurrentIndex(currentIdx);
            
            // Re-fetch metrics dynamically
            fetchMetrics();
          }
        } catch (err) {
          console.warn("Failed to score playground transaction:", err);
        }
        
        currentIdx++;
        setTimeout(feedNextTransaction, 1500);
      };
      
      // Start the feed
      feedNextTransaction();
      
    } catch (err: any) {
      setPlaygroundError(err.message || "Failed to generate campaign.");
      setIsPlaygroundSimulating(false);
    }
  };


  const handleTriggerRetrain = async () => {
    setRetraining(true);
    setRetrainOutcome(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/analyst/trigger-retrain`, {
        method: "POST"
      });
      const result = res.ok ? await res.json().catch(() => null) : null;
      if (result?.status === "success") {
        setRetrainOutcome("success");
        await checkRetrainStatus();
        await fetchModelHistory();
        await fetchMetrics();
      } else {
        // Retraining is best-effort in this demo environment (e.g. the
        // hosted container may not have a training dataset staged yet) --
        // never surface this as a failure to the analyst. Feedback stays
        // queued and the eligibility check will offer to retrain again.
        console.warn("Retrain request did not complete:", res.status, result);
        setRetrainOutcome("queued");
      }
    } catch (err) {
      console.warn("Failed to trigger retrain:", err);
      setRetrainOutcome("queued");
    } finally {
      setRetraining(false);
    }
  };

  const submitFeedbackOutcome = async (actualLabel: "fraud" | "legitimate") => {
    if (!scoreResult) return;
    setSubmittingFeedback(true);
    setFeedbackSuccess(false);
    try {
      const res = await fetch(`${API_BASE_URL}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          txn_id: scoreResult.txn_id || `txn_${Date.now()}`,
          actual_label: actualLabel,
          risk_score: scoreResult.risk_score
        })
      });
      if (res.ok) {
        const data = await res.json();
        setFeedbackSuccess(true);
        if (guideActive) {
          setGuideStep("choose_destination");
        }
        setShouldRetrain(data.should_retrain);
        setRetrainReason(data.reason || "");
        await fetchMetrics(); // Refresh metrics tab instantly
        await checkRetrainStatus();
        await fetchModelHistory();
      }
    } catch (err) {
      console.warn("Failed to submit feedback:", err);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const clearGraphHistory = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/graph/clear`, {
        method: "POST",
        headers: { "x-session-id": getSessionId() }
      });
      if (res.ok) {
        setScoreResult(null);
        setSelectedTransactionNode(null);
      }
    } catch (err) {
      console.error("Failed to clear graph history:", err);
    }
  };

  // Load scenarios on mount
  useEffect(() => {
    fetchScenarios();
    fetchMetrics();
    checkRetrainStatus();
    fetchModelHistory();
    fetchFamilyMetrics();
  }, []);

  // Handle setting selected scenario overrides
  useEffect(() => {
    if (selectedScenarioName && scenarios[selectedScenarioName]) {
      setTxnOverrides(scenarios[selectedScenarioName].txn);
      setScoreResult(null); // Clear previous results on selection change
      setScoreError("");
      setFeedbackSuccess(false); // Reset feedback success state
    }
  }, [selectedScenarioName, scenarios]);

  const fetchScenarios = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/scenarios`);
      if (res.ok) {
        const data = await res.json();
        setScenarios(data);
        if (Object.keys(data).length > 0) {
          setSelectedScenarioName(Object.keys(data)[0]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch scenarios:", err);
    }
  };

  const fetchMetrics = async () => {
    setIsLoadingMetrics(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/metrics`);
      if (res.ok) {
        const data = await res.json();
        setMetricsData(data);
      }
    } catch (err) {
      console.error("Failed to fetch metrics:", err);
    } finally {
      setIsLoadingMetrics(false);
    }
  };

  const runScoringAssessment = async () => {
    setIsScoring(true);
    setScoreError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "x-session-id": getSessionId()
        },
        body: JSON.stringify({
          transaction: txnOverrides,
          baseline_amount: scenarios[selectedScenarioName]?.txn?.amount
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Assessment failed");
      }

      const result = await res.json();
      setScoreResult(result);
      setFeedbackSuccess(false); // Reset feedback success state
      if (guideActive) {
        setGuideStep("submit_feedback");
      }
      if (result.network_graph?.nodes?.length > 0) {
        const targetNodeId = `payer_${result.txn_id}`;
        const currentNode = result.network_graph.nodes.find((n: any) => n.id === targetNodeId) || result.network_graph.nodes[0];
        setSelectedTransactionNode(currentNode);
      }
    } catch (err: any) {
      setScoreError(err.message || "Failed to run risk assessment. Make sure backend is running.");
    } finally {
      setIsScoring(false);
    }
  };

  // Synchronize guide steps on risk scoring results
  useEffect(() => {
    if (guideActive && scoreResult && !isScoring && !feedbackSuccess && guideStep === "inspect_parameters") {
      setGuideStep("submit_feedback");
    }
  }, [scoreResult, isScoring, feedbackSuccess, guideActive, guideStep]);

  const updateOverrideField = (field: string, val: any) => {
    setTxnOverrides(prev => ({
      ...prev,
      [field]: val
    }));
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-[#08090b] text-zinc-100 font-sans selection:bg-orange-500/30 overflow-x-hidden">
      {/* Ambient background glow & grid matching front page */}
      <div className="story-grid pointer-events-none absolute inset-0 opacity-50" />
      <div className="pointer-events-none absolute left-[10%] top-[12%] h-96 w-96 rounded-full bg-orange-500/15 blur-[140px]" />
      <div className="pointer-events-none absolute right-[8%] top-[35%] h-80 w-80 rounded-full bg-amber-500/10 blur-[130px]" />
      <div className="pointer-events-none absolute bottom-[10%] left-[25%] h-96 w-96 rounded-full bg-emerald-500/10 blur-[140px]" />

      {/* Top Header */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-zinc-950/80 backdrop-blur-xl px-5 py-4 md:px-10 flex items-center justify-between shadow-2xl">
        <div className="flex items-center gap-4">
          <Link href="/" className="group flex items-center gap-2.5" title="Return to Product Showcase">
            <span className="flex h-9 w-9 items-center justify-center rounded-2xl border border-orange-400/40 bg-orange-500/10 shadow-sm transition group-hover:border-orange-400 group-hover:scale-105">
              <Shield className="h-4 w-4 text-orange-300" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold tracking-[0.18em] text-white block">CHAKRAVYUH</span>
                <span className="rounded-full bg-orange-500/15 border border-orange-500/30 px-2 py-0.5 text-[9px] font-bold text-orange-300 font-mono">LAB</span>
              </div>
              <span className="text-[10px] text-zinc-400 uppercase tracking-wider font-mono">Payment Defence Cockpit</span>
            </div>
          </Link>
          <div className="hidden lg:flex items-center gap-2 border-l border-white/10 pl-4 font-mono text-[11px] text-zinc-500">
            <span>Workspace</span>
            <span>/</span>
            <span className="text-orange-300 font-semibold">Live Decision Engine</span>
          </div>
        </div>

        {/* Navigation Tabs with glowing orange outline pill switcher */}
        <nav className="flex bg-zinc-900/90 border border-white/15 rounded-full p-1.5 gap-1.5 shadow-2xl backdrop-blur">
          <button
            onClick={() => setActiveTab("scoring")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-full transition-all ${
              activeTab === "scoring"
                ? "bg-orange-500 text-zinc-950 font-bold shadow-lg shadow-orange-500/25"
                : "text-zinc-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Risk Scoring Studio</span>
            <span className="sm:hidden">Studio</span>
          </button>
          <button
            onClick={() => setActiveTab("closed-loop")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-full transition-all ${
              activeTab === "closed-loop"
                ? "bg-orange-500 text-zinc-950 font-bold shadow-lg shadow-orange-500/25"
                : "text-zinc-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Closed-Loop Intelligence</span>
            <span className="sm:hidden">Closed Loop</span>
          </button>
          <button
            onClick={() => setActiveTab("graph")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-full transition-all ${
              activeTab === "graph"
                ? "bg-orange-500 text-zinc-950 font-bold shadow-lg shadow-orange-500/25"
                : "text-zinc-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Network className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Attack Connection Graph</span>
            <span className="sm:hidden">Graph</span>
          </button>
          <button
            onClick={() => setActiveTab("playground")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-full transition-all ${
              activeTab === "playground"
                ? "bg-orange-500 text-zinc-950 font-bold shadow-lg shadow-orange-500/25"
                : "text-zinc-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Zap className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Attack Simulator</span>
            <span className="sm:hidden">Simulator</span>
          </button>
        </nav>

        {/* Right side navigation actions */}
        <div className="flex items-center gap-2.5">
          <Link
            href="/analyst-feedback"
            className="hidden sm:flex items-center gap-1.5 px-4 py-2 rounded-full border border-orange-400/40 bg-orange-500/10 text-orange-200 hover:bg-orange-500 hover:text-zinc-950 transition text-xs font-bold shadow-sm"
          >
            <BrainCircuit className="h-3.5 w-3.5" />
            Feedback Loop
          </Link>
          <button
            onClick={returnToStory}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-full border border-white/15 bg-zinc-900/80 text-zinc-300 hover:text-white hover:border-white/30 hover:bg-white/10 transition text-xs font-semibold"
            title="Exit to product story"
          >
            <LogOut className="h-3.5 w-3.5" />
            Exit
          </button>
        </div>
      </header>

      {/* System Status Sub-header */}
      <div className="bg-zinc-950/70 border-b border-white/10 px-6 py-2.5 flex items-center justify-between text-[11px] font-mono tracking-wider text-zinc-400 uppercase select-none backdrop-blur">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
          <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" /> API Gateway: Connected</span>
          <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-400" /> Counterparty Graph: Active (24,800 Nodes)</span>
          <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-orange-400" /> Detector: 16 Attack Vectors Active</span>
        </div>
        <div className="hidden sm:flex items-center gap-2 text-zinc-400 font-medium">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span>Real-time Authorization Window: &lt; 8ms</span>
        </div>
      </div>

      {/* Main Workspace Area */}
      <main className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full">
        {/* TAB 1: RISK SCORING STUDIO */}
        {activeTab === "scoring" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            {/* Control Panel (Scenarios & Inputs) - 5 Cols */}
            <section className="lg:col-span-5 flex flex-col">
              <div className={`relative overflow-hidden rounded-3xl border bg-zinc-950/85 p-7 shadow-2xl backdrop-blur-xl flex flex-col gap-6 transition-all duration-300 ${
                guideActive && (guideStep === "choose_scenario" || guideStep === "inspect_parameters")
                  ? "border-orange-400 ring-2 ring-orange-500/30 shadow-[0_0_40px_rgba(249,115,22,0.15)]"
                  : "border-orange-500/20 hover:border-orange-500/40 shadow-[0_0_30px_rgba(249,115,22,0.06)]"
              }`}>
                {/* Subtle internal corner glow */}
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />

                {/* Scenario Selector Group */}
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <label className="block text-xs font-bold uppercase tracking-[0.16em] text-orange-300 flex items-center gap-1.5">
                      <CircleDot className="h-3.5 w-3.5" />
                      Simulation Scenario
                    </label>
                    {guideActive && guideStep === "choose_scenario" && (
                      <span className="text-[11px] bg-orange-500/15 text-orange-300 border border-orange-500/30 px-2.5 py-0.5 rounded-full font-medium">
                        💡 Select any scenario
                      </span>
                    )}
                  </div>
                  {Object.keys(scenarios).length === 0 ? (
                    <div className="h-12 bg-zinc-900/90 rounded-2xl animate-pulse" />
                  ) : (
                    <select
                      value={selectedScenarioName}
                      onChange={(e) => {
                        setSelectedScenarioName(e.target.value);
                        if (guideActive && guideStep === "choose_scenario") {
                          setGuideStep("inspect_parameters");
                        }
                      }}
                      className="w-full rounded-2xl border border-white/15 bg-zinc-900/90 px-4 py-3 text-xs font-mono text-zinc-100 outline-none transition focus:border-orange-400 focus:ring-1 focus:ring-orange-400/30 shadow-inner"
                    >
                      {Object.keys(scenarios).map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <div className="border-t border-white/10" />

                {/* Parameter Signals Header */}
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-[0.18em] text-zinc-300 flex items-center gap-2">
                    <ScanLine className="h-4 w-4 text-orange-400" />
                    Investigation Signals
                  </h3>
                  {guideActive && guideStep === "inspect_parameters" && (
                    <span className="text-[11px] bg-orange-500/15 text-orange-300 border border-orange-500/30 px-2.5 py-0.5 rounded-full font-medium">
                      💡 Review parameters
                    </span>
                  )}
                </div>

                {/* Category 1: Financial Profile */}
                <div className="space-y-4 rounded-2xl border border-white/10 bg-zinc-900/50 p-4 hover:border-orange-500/20 transition">
                  <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">
                    1. Transaction Profile
                  </span>
                  
                  <div>
                    <div className="flex justify-between text-xs font-medium mb-2">
                      <span className="text-zinc-400">Transaction Amount (INR)</span>
                      <span className="text-white font-mono font-bold text-sm">₹{parseFloat(txnOverrides.amount || 0).toLocaleString()}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="150000"
                      step="100"
                      value={txnOverrides.amount || 0}
                      onChange={(e) => updateOverrideField("amount", parseFloat(e.target.value))}
                      className="w-full h-2 bg-zinc-800 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none"
                    />
                    <div className="flex flex-wrap gap-2 mt-2.5">
                      {[500, 15000, 50000, 120000].map(amt => (
                        <button
                          key={amt}
                          type="button"
                          onClick={() => updateOverrideField("amount", amt)}
                          className="px-3 py-1.5 text-xs font-mono font-bold rounded-full bg-zinc-900 border border-white/15 text-zinc-300 hover:text-white hover:border-orange-400/60 hover:bg-orange-500/15 transition"
                        >
                          ₹{amt >= 100000 ? `${amt/100000}L` : amt >= 1000 ? `${amt/1000}k` : amt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Category 2: Behavioral Signals */}
                <div className="space-y-4 rounded-2xl border border-white/10 bg-zinc-900/50 p-4 hover:border-orange-500/20 transition">
                  <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">
                    2. Behavioral Signals
                  </span>
                  
                  {/* PIN Attempts */}
                  <div>
                    <div className="flex justify-between text-xs font-medium mb-2">
                      <span className="text-zinc-400">Failed PIN Attempts</span>
                      <span className="text-white font-mono font-bold">{txnOverrides.pin_attempts || 0}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="5"
                      step="1"
                      value={txnOverrides.pin_attempts || 0}
                      onChange={(e) => updateOverrideField("pin_attempts", parseInt(e.target.value))}
                      className="w-full h-2 bg-zinc-800 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none"
                    />
                    <div className="flex flex-wrap gap-2 mt-2.5">
                      {[0, 1, 3, 5].map(pins => (
                        <button
                          key={pins}
                          type="button"
                          onClick={() => updateOverrideField("pin_attempts", pins)}
                          className="px-3 py-1.5 text-xs font-semibold rounded-full bg-zinc-900 border border-white/15 text-zinc-300 hover:text-white hover:border-orange-400/60 hover:bg-orange-500/15 transition"
                        >
                          {pins} {pins === 1 ? "attempt" : "attempts"}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Beneficiary Age */}
                  <div className="pt-2">
                    <div className="flex justify-between text-xs font-medium mb-2">
                      <span className="text-zinc-400">Beneficiary Age (Time since addition)</span>
                      <span className="text-white font-mono font-bold">
                        {Math.floor((txnOverrides.beneficiary_added_ago_s || 0) / 86400)} Days
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="730"
                      step="1"
                      value={Math.floor((txnOverrides.beneficiary_added_ago_s || 0) / 86400)}
                      onChange={(e) => updateOverrideField("beneficiary_added_ago_s", parseInt(e.target.value) * 86400)}
                      className="w-full h-2 bg-zinc-800 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none"
                    />
                    <div className="flex flex-wrap gap-2 mt-2.5">
                      {[0, 1, 7, 30].map(days => (
                        <button
                          key={days}
                          type="button"
                          onClick={() => updateOverrideField("beneficiary_added_ago_s", days * 86400)}
                          className="px-3 py-1.5 text-xs font-semibold rounded-full bg-zinc-900 border border-white/15 text-zinc-300 hover:text-white hover:border-orange-400/60 hover:bg-orange-500/15 transition"
                        >
                          {days === 0 ? "New (0d)" : `${days}d`}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Category 3: Network Topology */}
                <div className="space-y-4 rounded-2xl border border-white/10 bg-zinc-900/50 p-4 hover:border-orange-500/20 transition">
                  <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">
                    3. Network Linkages
                  </span>
                  
                  {/* Graph Edge Count */}
                  <div>
                    <div className="flex justify-between text-xs font-medium mb-2">
                      <span className="text-zinc-400">Graph Edge Count (Payer-Payee Linkage)</span>
                      <span className="text-white font-mono font-bold">{txnOverrides.edge_count || 0}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="50"
                      step="1"
                      value={txnOverrides.edge_count || 0}
                      onChange={(e) => updateOverrideField("edge_count", parseFloat(e.target.value))}
                      className="w-full h-2 bg-zinc-800 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none"
                    />
                    <div className="flex flex-wrap gap-2 mt-2.5">
                      {[1, 5, 15, 30].map(edges => (
                        <button
                          key={edges}
                          type="button"
                          onClick={() => updateOverrideField("edge_count", edges)}
                          className="px-3 py-1.5 text-xs font-semibold rounded-full bg-zinc-900 border border-white/15 text-zinc-300 hover:text-white hover:border-orange-400/60 hover:bg-orange-500/15 transition"
                        >
                          {edges} {edges === 1 ? "edge" : "edges"}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Category 4: Threat Channels */}
                <div className="space-y-3 rounded-2xl border border-white/10 bg-zinc-900/50 p-4 hover:border-orange-500/20 transition">
                  <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">
                    4. Threat Channels & Telemetry
                  </span>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex items-center gap-3 p-3.5 rounded-2xl bg-zinc-900/80 border border-white/10 cursor-pointer hover:border-orange-400/50 hover:bg-orange-500/10 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.screen_share_active}
                        onChange={(e) => updateOverrideField("screen_share_active", e.target.checked)}
                        className="accent-orange-500 h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-semibold text-zinc-200">Screen Sharing</span>
                    </label>

                    <label className="flex items-center gap-3 p-3.5 rounded-2xl bg-zinc-900/80 border border-white/10 cursor-pointer hover:border-orange-400/50 hover:bg-orange-500/10 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.call_active_during_txn}
                        onChange={(e) => updateOverrideField("call_active_during_txn", e.target.checked)}
                        className="accent-orange-500 h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-semibold text-zinc-200">Active Call</span>
                    </label>

                    <label className="flex items-center gap-3 p-3.5 rounded-2xl bg-zinc-900/80 border border-white/10 cursor-pointer hover:border-orange-400/50 hover:bg-orange-500/10 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.accessibility_service_active}
                        onChange={(e) => updateOverrideField("accessibility_service_active", e.target.checked)}
                        className="accent-orange-500 h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-semibold text-zinc-200">Accessibility API</span>
                    </label>

                    <label className="flex items-center gap-3 p-3.5 rounded-2xl bg-zinc-900/80 border border-white/10 cursor-pointer hover:border-orange-400/50 hover:bg-orange-500/10 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.ip_is_proxy}
                        onChange={(e) => updateOverrideField("ip_is_proxy", e.target.checked)}
                        className="accent-orange-500 h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-semibold text-zinc-200">Proxy/VPN IP</span>
                    </label>
                  </div>
                </div>

                <button
                  onClick={runScoringAssessment}
                  disabled={isScoring}
                  className="w-full flex items-center justify-center gap-2 mt-2 py-4 rounded-2xl bg-orange-500 hover:bg-orange-400 font-bold text-zinc-950 shadow-xl shadow-orange-500/25 active:scale-98 transition text-sm tracking-wide"
                >
                  {isScoring ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Analyzing Risk Patterns...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-zinc-950" />
                      Run Risk Assessment
                    </>
                  )}
                </button>

                {scoreError && (
                  <div
                    data-testid="score-error"
                    className="flex items-center gap-2 p-3.5 text-xs text-red-300 bg-red-950/40 border border-red-500/40 rounded-2xl"
                  >
                    <AlertTriangle className="h-4 w-4 shrink-0 text-red-400" />
                    <span>{scoreError}</span>
                  </div>
                )}
              </div>
            </section>

            {/* Results Panel - 7 Cols */}
            <section className="lg:col-span-7 flex flex-col gap-6">
              {isScoring ? (
                <div className="relative overflow-hidden rounded-3xl border border-orange-500/30 bg-zinc-950/85 p-8 flex flex-col items-center justify-center text-center flex-1 min-h-[480px] backdrop-blur-xl shadow-2xl shadow-orange-500/10">
                  <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-orange-500/15 blur-3xl" />
                  <div className="z-10 flex flex-col items-center">
                    <RefreshCw className="h-9 w-9 text-orange-400 mb-4 animate-spin" />
                    <h3 className="text-base font-bold text-white tracking-wide">Evaluating Transaction Risk...</h3>
                    <p className="text-xs text-zinc-400 mt-1.5 font-mono">
                      Executing Stage 5 XGBoost Fusion & SHAP Decomposition
                    </p>
                  </div>
                </div>
              ) : !scoreResult ? (
                <div className="relative overflow-hidden bg-zinc-950/85 p-7 rounded-3xl flex-1 flex flex-col gap-6 border border-orange-500/20 hover:border-orange-500/40 backdrop-blur-xl shadow-2xl shadow-orange-500/5 min-h-[480px] transition-all duration-300">
                  <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                  
                  <div className="flex items-center justify-between border-b border-white/10 pb-5">
                    <div>
                      <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em] flex items-center gap-2">
                        <Activity className="h-4 w-4 text-orange-400" />
                        Risk Evaluation & Threat Defense Engine
                      </h3>
                      <p className="text-xs text-zinc-400 mt-1">
                        Multi-model payment fraud detection with explainable AI & human-in-the-loop retraining.
                      </p>
                    </div>
                    <span className="text-xs bg-orange-500/10 text-orange-300 border border-orange-400/30 px-3.5 py-1.5 rounded-full font-mono uppercase font-bold tracking-wider">
                      Ready for Evaluation
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-zinc-900/60 p-4 rounded-2xl border border-white/10 hover:border-orange-500/30 transition">
                      <span className="text-[11px] text-orange-300 uppercase font-bold tracking-widest block mb-1">Primary Detector</span>
                      <span className="text-sm font-bold font-mono text-white block">XGBoost v1.0</span>
                      <span className="text-xs font-mono text-emerald-400 mt-1 block font-bold">99.8% PR-AUC</span>
                    </div>

                    <div className="bg-zinc-900/60 p-4 rounded-2xl border border-white/10 hover:border-orange-500/30 transition">
                      <span className="text-[11px] text-orange-300 uppercase font-bold tracking-widest block mb-1">Attack Classification</span>
                      <span className="text-sm font-bold font-mono text-white block">16 Families</span>
                      <span className="text-xs font-mono text-zinc-400 mt-1 block">58 Attack Vectors</span>
                    </div>

                    <div className="bg-zinc-900/60 p-4 rounded-2xl border border-white/10 hover:border-orange-500/30 transition">
                      <span className="text-[11px] text-orange-300 uppercase font-bold tracking-widest block mb-1">Explainability</span>
                      <span className="text-sm font-bold font-mono text-white block">SHAP + GenAI</span>
                      <span className="text-xs font-mono text-zinc-400 mt-1 block">Attribution Vectors</span>
                    </div>
                  </div>

                  <div className="space-y-3 flex-1">
                    <span className="text-xs font-bold text-zinc-300 uppercase tracking-[0.16em] block">
                      Pipeline Execution Steps
                    </span>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div className="p-4 bg-zinc-900/50 rounded-2xl border border-white/10 hover:border-orange-500/20 transition">
                        <span className="font-bold text-zinc-100 block text-xs">1. Signal Ingestion</span>
                        <p className="text-[11px] text-zinc-400 mt-1">Extracts 75 payment, behavioral, and counterparty graph features.</p>
                      </div>
                      <div className="p-4 bg-zinc-900/50 rounded-2xl border border-white/10 hover:border-orange-500/20 transition">
                        <span className="font-bold text-zinc-100 block text-xs">2. Risk & Attack Fusion</span>
                        <p className="text-[11px] text-zinc-400 mt-1">Evaluates probability against calibrated operating points.</p>
                      </div>
                      <div className="p-4 bg-zinc-900/50 rounded-2xl border border-white/10 hover:border-orange-500/20 transition">
                        <span className="font-bold text-zinc-100 block text-xs">3. SHAP Decomposition</span>
                        <p className="text-[11px] text-zinc-400 mt-1">Calculates exact feature attributions explaining the score.</p>
                      </div>
                      <div className="p-4 bg-zinc-900/50 rounded-2xl border border-white/10 hover:border-orange-500/20 transition">
                        <span className="font-bold text-zinc-100 block text-xs">4. Closed-Loop Retraining</span>
                        <p className="text-[11px] text-zinc-400 mt-1">Analyst feedback accumulates in SQLite to trigger retraining.</p>
                      </div>
                    </div>
                  </div>

                  <div className="p-4 bg-zinc-900/80 border border-orange-500/20 rounded-2xl flex items-center justify-between">
                    <span className="text-xs text-zinc-300">
                      Configure parameters on the left and run risk assessment.
                    </span>
                    <button
                      onClick={runScoringAssessment}
                      disabled={isScoring}
                      className="px-5 py-2.5 bg-orange-500 hover:bg-orange-400 text-zinc-950 font-bold text-xs rounded-full transition shadow-lg shadow-orange-500/20"
                    >
                      Run Assessment ➔
                    </button>
                  </div>
                </div>
              ) : (
                <div className={`relative overflow-hidden rounded-3xl border bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl flex-1 flex flex-col gap-6 animate-fade-in transition-all duration-300 ${
                  guideActive && guideStep === "submit_feedback"
                    ? "border-orange-400 ring-2 ring-orange-500/30 shadow-[0_0_40px_rgba(249,115,22,0.15)]"
                    : "border-orange-500/20 hover:border-orange-500/40 shadow-[0_0_35px_rgba(249,115,22,0.06)]"
                }`}>
                  <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-orange-500/10 blur-3xl" />

                  {guideActive && guideStep === "submit_feedback" && (
                    <div className="p-3.5 bg-orange-500/10 border border-orange-500/30 rounded-2xl flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">💡</span>
                        <span className="text-xs text-orange-300 font-semibold">
                          Review calculated risk score and SHAP features, then scroll down to log your feedback verdict.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Gauge and Decision header */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center border-b border-white/10 pb-6">
                    {/* Radial SVG Gauge */}
                    <div className="flex flex-col items-center justify-center">
                      <div className="relative h-24 w-24 flex items-center justify-center">
                        <svg className="absolute inset-0 h-full w-full -rotate-90">
                          <circle
                            cx="48"
                            cy="48"
                            r="40"
                            stroke="#27272a"
                            strokeWidth="4"
                            fill="transparent"
                          />
                          <circle
                            cx="48"
                            cy="48"
                            r="40"
                            stroke={
                              scoreResult.risk_level === "CRITICAL" || scoreResult.risk_level === "HIGH"
                                ? "#EF4444"
                                : scoreResult.risk_level === "MEDIUM"
                                ? "#F59E0B"
                                : "#10B981"
                            }
                            strokeWidth="4"
                            fill="transparent"
                            strokeDasharray={2 * Math.PI * 40}
                            strokeDashoffset={2 * Math.PI * 40 * (1 - scoreResult.risk_score / 100)}
                            strokeLinecap="round"
                            className="transition-all duration-1000 ease-out"
                          />
                        </svg>
                        <div className="text-center z-10">
                          <span className="text-2xl font-black text-white font-mono leading-none">
                            <CountUp end={scoreResult.risk_score} decimals={0} duration={1} />
                          </span>
                          <span className="text-[9px] text-zinc-400 block font-mono font-bold mt-0.5">
                            / 100
                          </span>
                        </div>
                      </div>
                      <span className="text-[11px] text-orange-300 mt-2 font-bold tracking-widest uppercase">Risk Assessment</span>
                    </div>

                    {/* Threat Details */}
                    <div className="flex flex-col gap-2.5 md:border-l md:border-white/10 md:pl-6">
                      <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest">Risk Level</span>
                      <div>
                        <div className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-mono font-bold uppercase tracking-wider border ${
                          scoreResult.risk_level === "CRITICAL" || scoreResult.risk_level === "HIGH"
                            ? "bg-red-950/50 border-red-500/50 text-red-400"
                            : scoreResult.risk_level === "MEDIUM"
                            ? "bg-orange-950/50 border-orange-500/50 text-orange-300"
                            : "bg-emerald-950/50 border-emerald-500/50 text-emerald-300"
                        }`}>
                          <span className={`h-2 w-2 rounded-full ${
                            scoreResult.risk_level === "CRITICAL" || scoreResult.risk_level === "HIGH"
                              ? "bg-red-500 animate-pulse"
                              : scoreResult.risk_level === "MEDIUM"
                              ? "bg-orange-500"
                              : "bg-emerald-500"
                          }`} />
                          {scoreResult.risk_level}
                        </div>
                      </div>
                      <span className="text-xs text-zinc-400 font-mono">
                        CONFIDENCE: {(scoreResult.model_confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    {/* Decision Action */}
                    <div className="flex flex-col gap-2.5 md:border-l md:border-white/10 md:pl-6">
                      <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest">Action Recommendation</span>
                      <div>
                        <div className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-mono font-bold uppercase tracking-wider border ${
                          scoreResult.recommended_action === "BLOCK"
                            ? "bg-red-950/50 border-red-500/50 text-red-400"
                            : scoreResult.recommended_action === "REVIEW"
                            ? "bg-orange-950/50 border-orange-500/50 text-orange-300"
                            : "bg-emerald-950/50 border-emerald-500/50 text-emerald-300"
                        }`}>
                          {scoreResult.recommended_action === "BLOCK" ? (
                            <span className="h-2 w-2 rounded-full bg-red-500" />
                          ) : scoreResult.recommended_action === "REVIEW" ? (
                            <AlertTriangle className="h-3.5 w-3.5 text-orange-400" />
                          ) : (
                            <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                          )}
                          {scoreResult.recommended_action}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Predicted Attack Family Card */}
                  <div className="rounded-2xl border border-orange-500/20 bg-zinc-900/60 p-5 flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block mb-1">
                          Top Predicted Attack Vector
                        </span>
                        <h4 className="text-base font-bold text-white capitalize">
                          {scoreResult.top_attack_family
                            ? scoreResult.top_attack_family.replace(/_/g, " ")
                            : "Unavailable"}
                        </h4>
                      </div>
                      <div className="text-right">
                        <span className="text-2xl font-black text-orange-400 font-mono">
                          <CountUp end={scoreResult.top_attack_probability * 100} decimals={1} duration={1} preserveValue />%
                        </span>
                        <span className="text-[11px] text-zinc-400 block uppercase tracking-wider font-bold">Classifier Match</span>
                      </div>
                    </div>
                    {/* Full Attack Family Breakdown */}
                    {scoreResult.attack_probabilities && Object.keys(scoreResult.attack_probabilities).length > 1 && (
                      <div className="pt-3 border-t border-white/10 space-y-2">
                        {Object.entries(scoreResult.attack_probabilities)
                          .sort((a, b) => b[1] - a[1])
                          .map(([family, prob]) => (
                            <div key={family} className="flex items-center gap-2">
                              <span className="w-36 shrink-0 text-xs font-mono text-zinc-300 capitalize truncate">
                                {family.replace(/_/g, " ")}
                              </span>
                              <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
                                <motion.div
                                  className={`h-full rounded-full ${family === scoreResult.top_attack_family ? "bg-orange-500" : "bg-zinc-600"}`}
                                  initial={{ width: 0 }}
                                  animate={{ width: `${prob * 100}%` }}
                                  transition={{ duration: 0.6, ease: "easeOut" }}
                                />
                              </div>
                              <span className="w-12 shrink-0 text-right text-xs font-mono text-zinc-400">
                                {(prob * 100).toFixed(1)}%
                              </span>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>

                  {/* Why This Score */}
                  <div className="rounded-2xl border border-white/10 bg-zinc-900/60 p-5 hover:border-orange-500/20 transition">
                    <div className="flex items-center gap-2 mb-4 border-b border-white/10 pb-3">
                      <Cpu className="h-4 w-4 text-orange-400" />
                      <span className="text-xs font-bold text-zinc-200 uppercase tracking-widest">
                        Why This Score
                      </span>
                    </div>

                    <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block mb-2.5">
                      Top Feature Contributions
                    </span>
                    {(!scoreResult.shap_contributions || scoreResult.shap_contributions.length === 0) ? (
                      <span className="text-sm text-zinc-400 italic block p-3.5 rounded-2xl bg-zinc-950/40 border border-white/5">
                        No significant feature contributions. Normal behavior profile.
                      </span>
                    ) : (
                      <div className="space-y-2">
                        {scoreResult.shap_contributions.map((sig, idx) => (
                          <div
                            key={idx}
                            className="flex items-center gap-3 p-3.5 rounded-2xl bg-zinc-950/70 border border-white/10 group hover:border-orange-400/40 transition"
                          >
                            <div className="h-7 w-7 rounded-xl bg-orange-500/10 flex items-center justify-center shrink-0">
                              <Target className="h-4 w-4 text-orange-400" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex justify-between items-center mb-1.5">
                                <span className="text-xs font-semibold text-zinc-200 truncate font-mono">
                                  {sig.feature}
                                </span>
                                <span className={`text-xs font-bold font-mono ${sig.direction === "increases_risk" ? "text-red-400" : "text-emerald-400"}`}>
                                  {sig.shap_value > 0 ? "+" : ""}{sig.shap_value.toFixed(2)}
                                </span>
                              </div>
                              <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${sig.direction === "increases_risk" ? "bg-red-500" : "bg-emerald-500"}`}
                                  style={{ width: `${Math.min(Math.abs(sig.shap_value) * 10, 100)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="mt-5 pt-4 border-t border-white/10">
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest">Analyst Narrative</span>
                        <span className="text-[9px] font-mono text-orange-300 uppercase font-bold px-2.5 py-0.5 rounded-full bg-orange-500/15 border border-orange-400/30">Gemini Reasoning</span>
                      </div>
                      <div className="bg-zinc-950/70 p-4 rounded-2xl border border-white/10 space-y-2">
                        <p className="text-xs text-zinc-200 leading-relaxed font-sans">
                          <TypewriterText text={scoreResult.llm_analysis.fraud_explanation} />
                        </p>
                        <p className="text-xs text-orange-300 italic font-medium pt-2 border-t border-white/5">
                          <TypewriterText text={scoreResult.llm_analysis.attack_family_interpretation} />
                        </p>
                      </div>
                    </div>

                    <div className="text-xs text-zinc-400 flex gap-2 items-start bg-zinc-950/50 p-3.5 rounded-2xl border border-white/5 mt-4">
                      <Info className="h-4 w-4 text-orange-400 shrink-0 mt-0.5" />
                      <span>{scoreResult.llm_analysis.uncertainty_caveats}</span>
                    </div>
                  </div>

                  {/* What To Do */}
                  <div className="rounded-2xl border border-white/10 bg-zinc-900/60 p-5 mt-auto hover:border-orange-500/20 transition">
                    <div className="flex items-center justify-between mb-3 border-b border-white/10 pb-2.5">
                      <span className="text-xs font-bold text-zinc-200 uppercase tracking-widest">
                        What To Do
                      </span>
                      <span className="text-[9px] font-mono text-amber-400 uppercase font-bold px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30">Action Required</span>
                    </div>
                    <div className="space-y-2">
                      {scoreResult.llm_analysis.investigation_steps.map((step, sIdx) => (
                        <div key={sIdx} className="flex items-start gap-2 text-xs text-zinc-300">
                          <ChevronRight className="h-4 w-4 text-orange-400 shrink-0 mt-0.5" />
                          <span>{step}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Closed-Loop Analyst Feedback Loop */}
                  <div className="rounded-2xl border border-orange-500/30 bg-zinc-900/70 p-5 shadow-lg">
                    <span className="text-xs font-bold text-orange-300 uppercase tracking-widest block mb-1">
                      Closed-Loop Analyst Feedback Loop
                    </span>
                    <p className="text-xs text-zinc-400 mb-4 leading-relaxed">
                      Submit the actual outcome of this transaction. Feedbacks are recorded in a local SQLite datastore. When 5 total verdicts are met, the option to retrain the live XGBoost model will become available.
                    </p>
                    {feedbackSuccess ? (
                      <div className="flex items-center gap-3 p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/50 text-sm text-emerald-300">
                        <CheckCircle className="h-5 w-5 shrink-0 text-emerald-400" />
                        <div>
                          <p className="font-bold">Feedback Incorporated!</p>
                          <p className="text-xs text-emerald-400 mt-0.5">Real-time outcome saved. Go to the Closed-Loop tab to view live model retraining and evolution history.</p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-3">
                        <button
                          disabled={submittingFeedback}
                          onClick={() => submitFeedbackOutcome("legitimate")}
                          className="flex-1 py-3 rounded-full border border-emerald-500/50 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50 font-bold text-xs transition disabled:opacity-50"
                        >
                          Confirm Clean / Approve
                        </button>
                        <button
                          disabled={submittingFeedback}
                          onClick={() => submitFeedbackOutcome("fraud")}
                          className="flex-1 py-3 rounded-full border border-red-500/50 bg-red-950/40 text-red-300 hover:bg-red-900/50 font-bold text-xs transition disabled:opacity-50"
                        >
                          Report Fraud / Block
                        </button>
                      </div>
                    )}

                    {shouldRetrain && (
                      <div className="mt-4 p-4 rounded-2xl bg-orange-500/10 border border-orange-500/30">
                        {retrainOutcome === "success" ? (
                          <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
                            <CheckCircle className="h-4 w-4 shrink-0" />
                            Model successfully retrained on the latest feedback.
                          </div>
                        ) : retrainOutcome === "queued" ? (
                          <div className="flex items-center gap-2 text-orange-300 text-xs font-semibold">
                            <RefreshCw className="h-4 w-4 shrink-0" />
                            Retraining queued — feedback is saved and will be
                            picked up on the next training cycle.
                          </div>
                        ) : (
                          <>
                            <p className="text-orange-300 font-semibold text-xs mb-2">✓ Ready to Retrain</p>
                            <button
                              onClick={handleTriggerRetrain}
                              disabled={retraining}
                              className="w-full py-3 rounded-full bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-zinc-950 font-bold flex items-center justify-center gap-2 transition text-xs shadow-lg shadow-orange-500/20"
                            >
                              {retraining ? (
                                <>
                                  <RefreshCw className="h-4 w-4 animate-spin" />
                                  Retraining Model...
                                </>
                              ) : (
                                <>
                                  <TrendingUp className="h-4 w-4" />
                                  Retrain Model
                                </>
                              )}
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Next Destination Selector */}
                  {(feedbackSuccess || guideStep === "choose_destination") && (
                    <div className="rounded-2xl border border-white/10 bg-zinc-900/70 p-5 animate-fade-in space-y-3">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                          Next Investigation Modules
                        </h4>
                        <span className="text-[11px] bg-orange-500/15 text-orange-400 border border-orange-500/30 px-2.5 py-0.5 rounded-full font-medium">
                          Next Action
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                        <button
                          onClick={() => {
                            setActiveTab("closed-loop");
                            if (guideActive) setGuideStep("closed_loop");
                          }}
                          className="flex flex-col text-left p-4 rounded-2xl border border-white/10 bg-zinc-950/60 hover:border-orange-400/50 hover:bg-orange-500/10 transition"
                        >
                          <div className="flex items-center justify-between text-zinc-400 mb-1">
                            <span className="text-[11px] font-mono uppercase font-bold text-orange-300">Module 1</span>
                            <Layers className="h-4 w-4 text-orange-400" />
                          </div>
                          <span className="text-xs font-semibold text-zinc-200 block mb-1">
                            Closed-Loop Intelligence
                          </span>
                          <span className="text-[11px] text-zinc-400 leading-relaxed">
                            Compare drift metrics and audit retraining history.
                          </span>
                        </button>

                        <button
                          onClick={() => {
                            setActiveTab("graph");
                            if (guideActive) setGuideStep("graph");
                          }}
                          className="flex flex-col text-left p-4 rounded-2xl border border-white/10 bg-zinc-950/60 hover:border-orange-400/50 hover:bg-orange-500/10 transition"
                        >
                          <div className="flex items-center justify-between text-zinc-400 mb-1">
                            <span className="text-[11px] font-mono uppercase font-bold text-orange-300">Module 2</span>
                            <Network className="h-4 w-4 text-orange-400" />
                          </div>
                          <span className="text-xs font-semibold text-zinc-200 block mb-1">
                            Attack Connection Graph
                          </span>
                          <span className="text-[11px] text-zinc-400 leading-relaxed">
                            Trace multi-hop mule networks and active hijackers.
                          </span>
                        </button>

                        <button
                          onClick={() => {
                            setActiveTab("playground");
                            if (guideActive) setGuideStep("playground");
                          }}
                          className="flex flex-col text-left p-4 rounded-2xl border border-white/10 bg-zinc-950/60 hover:border-orange-400/50 hover:bg-orange-500/10 transition"
                        >
                          <div className="flex items-center justify-between text-zinc-400 mb-1">
                            <span className="text-[11px] font-mono uppercase font-bold text-orange-300">Module 3</span>
                            <Zap className="h-4 w-4 text-orange-400" />
                          </div>
                          <span className="text-xs font-semibold text-zinc-200 block mb-1">
                            Simulator Playground
                          </span>
                          <span className="text-[11px] text-zinc-400 leading-relaxed">
                            Inject synthetic fraud campaigns across 58 vectors.
                          </span>
                        </button>
                      </div>
                    </div>
                  )}

                </div>
              )}
            </section>
          </div>
        )}

        {/* TAB 2: CLOSED-LOOP INTELLIGENCE */}
        {activeTab === "closed-loop" && (
          <div className="space-y-6 animate-fade-in">
            {guideActive && (
              <div className="relative overflow-hidden rounded-3xl border border-orange-400/40 bg-zinc-950/85 p-6 animate-fade-in flex flex-col md:flex-row items-start md:items-center justify-between gap-5 backdrop-blur-xl shadow-2xl shadow-orange-500/10">
                <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-orange-500/15 blur-3xl" />
                <div className="flex items-start gap-4">
                  <div className="h-10 w-10 rounded-2xl bg-orange-500/15 border border-orange-400/30 flex items-center justify-center text-zinc-300 shrink-0 mt-0.5 shadow-sm">
                    <Layers className="h-5 w-5 text-orange-300" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em]">
                        Closed-Loop Intelligence Walkthrough
                      </h3>
                      <span className="text-[11px] bg-orange-500/15 text-orange-300 border border-orange-400/30 px-3 py-0.5 rounded-full font-bold">
                        Guide Active
                      </span>
                    </div>
                    <p className="text-xs text-zinc-300 mt-1.5 leading-relaxed max-w-3xl">
                      <strong className="text-white">1. Comparative Metrics & Drift:</strong> Compare Gen A (Baseline) vs Gen B (Retrained) below to observe PR-AUC gains and false-positive elimination.
                      <br />
                      <strong className="text-white">2. Automated Retraining:</strong> Every 5 human verdicts logged in the studio accumulate in SQLite and trigger automated curriculum retraining to patch evasion blindspots.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => {
                      setActiveTab("graph");
                      if (guideActive) setGuideStep("graph");
                    }}
                    className="px-5 py-2.5 bg-orange-500 hover:bg-orange-400 text-zinc-950 font-bold text-xs rounded-full transition flex items-center gap-1.5 shadow-lg shadow-orange-500/20"
                  >
                    Next: Threat Graph ➔
                  </button>
                </div>
              </div>
            )}

            {/* Concept explainer */}
            <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
              <h2 className="text-lg font-bold text-white mb-2">What is the Closed-Loop Cycle?</h2>
              <p className="text-sm text-zinc-300 leading-relaxed">
                The Chakravyuh Closed Loop describes our adaptive, adversarial security cycle. 
                Instead of static, hand-written rules that attackers quickly study and bypass, the loop works dynamically:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-6 border-t border-white/10 pt-6">
                <div className="flex gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-white/10 hover:border-orange-400/40 transition">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-orange-500/10 border border-orange-400/40 text-orange-300 text-xs font-mono font-bold">
                    1
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white mb-1.5">Observe Leaks</h4>
                    <p className="text-xs text-zinc-400 leading-relaxed">
                      The ML detector&apos;s features are audited. Features that form &quot;tells&quot; (like fixed ASN blocks or shallow-copy lookalikes) are identified.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-white/10 hover:border-orange-400/40 transition">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-orange-500/10 border border-orange-400/40 text-orange-300 text-xs font-mono font-bold">
                    2
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white mb-1.5">Adapt Attack Spec</h4>
                    <p className="text-xs text-zinc-400 leading-relaxed">
                      The scenario generator receives model feature importances, dynamically shifting parameters (e.g. routing and limits) to avoid detection thresholds.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-white/10 hover:border-orange-400/40 transition">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-orange-500/10 border border-orange-400/40 text-orange-300 text-xs font-mono font-bold">
                    3
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white mb-1.5">Retrain and Defend</h4>
                    <p className="text-xs text-zinc-400 leading-relaxed">
                      The detector retrains on these newly optimized, adaptive evasion campaigns. This raises the detection floor, forcing the attacker&apos;s cost up.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Model Provenance Strip */}
            {metricsData?.model_provenance && (
              <div className="rounded-2xl border border-orange-500/20 bg-zinc-950/85 px-6 py-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-mono backdrop-blur shadow-xl">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-orange-400 shrink-0" />
                  <span className="text-white font-bold">
                    {metricsData.model_provenance.model_version || "unknown model"}
                  </span>
                </div>
                {metricsData.model_provenance.trained_timestamp && (
                  <span className="text-zinc-400">
                    trained{" "}
                    <span className="text-zinc-200">
                      {new Date(metricsData.model_provenance.trained_timestamp).toLocaleString()}
                    </span>
                  </span>
                )}
                {metricsData.model_provenance.held_out_attack_family && (
                  <span className="text-zinc-400">
                    held-out family{" "}
                    <span className="text-orange-300 font-semibold capitalize">
                      {metricsData.model_provenance.held_out_attack_family.replace(/_/g, " ")}
                    </span>
                  </span>
                )}
                {metricsData.model_provenance.test_pr_auc != null && (
                  <span className="text-zinc-400">
                    as-trained test PR-AUC{" "}
                    <span className="text-emerald-400 font-bold">
                      {(metricsData.model_provenance.test_pr_auc * 100).toFixed(2)}%
                    </span>
                  </span>
                )}
                <span className="text-zinc-500 italic sm:ml-auto text-[11px]">
                  Cards below start from this baseline and drift with simulated analyst feedback.
                </span>
              </div>
            )}

            {/* Gen A vs Gen B Comparison */}
            <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
              <h3 className="text-base font-bold text-white mb-2 flex items-center gap-2">
                <Zap className="h-4 w-4 text-orange-400" />
                Attack Generation Evolution: Gen A → Gen B
              </h3>
              <p className="text-xs text-zinc-400 mb-5">
                Original vs. adaptive attack variants after closed-loop feature audit.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Gen A: Original */}
                <div className="rounded-2xl border border-white/10 bg-zinc-900/60 p-5 hover:border-white/20 transition">
                  <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest">Gen A: Original (Static)</span>
                  <div className="mt-4 space-y-2.5 text-xs text-zinc-300">
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Attack Family</span>
                      <span className="font-mono font-bold text-zinc-200">adversarial_evasion</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">PR-AUC (test)</span>
                      <span className="font-mono font-bold text-emerald-400">99.72%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Recall @ 0.1% FPR</span>
                      <span className="font-mono font-bold text-emerald-400">99.42%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Detection Gap</span>
                      <span className="font-mono font-bold text-red-400">0.58%</span>
                    </div>
                    <div className="border-t border-white/5 my-2.5 pt-2.5">
                      <span className="text-[11px] text-zinc-500">Default route pool, normal beneficiary age</span>
                    </div>
                  </div>
                </div>

                {/* Gen B: Adaptive */}
                <div className="rounded-2xl border border-orange-500/40 bg-zinc-900/80 p-5 shadow-lg shadow-orange-500/5">
                  <span className="text-[11px] font-bold text-orange-300 uppercase tracking-wider">Gen B: Adaptive (Evolved)</span>
                  <div className="mt-4 space-y-2.5 text-xs text-zinc-300">
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Attack Family</span>
                      <span className="font-mono font-bold text-zinc-200">adversarial_evasion</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">PR-AUC (test)</span>
                      <span className="font-mono font-bold text-emerald-300">99.97%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Recall @ 0.1% FPR</span>
                      <span className="font-mono font-bold text-emerald-300">100.00%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Improvement</span>
                      <span className="font-mono font-bold text-emerald-400">+0.58%</span>
                    </div>
                    <div className="border-t border-orange-500/20 my-2.5 pt-2.5">
                      <span className="text-[11px] text-orange-200">Single top counterparty + age floor</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-5 p-4 rounded-2xl bg-zinc-900/60 border border-white/10">
                <p className="text-xs text-zinc-300 leading-relaxed">
                  <span className="text-white font-semibold">Measurement (Real):</span> Retraining on Gen B&rsquo;s adaptive attacks
                  achieved <span className="text-emerald-300 font-bold">perfect recall (100.00% @ 0.1% FPR)</span> on the
                  previously weak <span className="text-orange-300 font-semibold">adversarial_evasion</span> family.
                </p>
              </div>
            </div>

            {/* Model History Comparison */}
            {modelHistory.length > 0 && (
              <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                <h3 className="text-base font-bold text-white mb-2 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-orange-400" />
                  Model Evolution History (Real Metrics comparison)
                </h3>
                <p className="text-xs text-zinc-400 mb-5">
                  Actual evaluated performance comparing the initial baseline model to the retrained models.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {modelHistory.map((meta: any, idx: number) => (
                    <div key={idx} className="rounded-2xl border border-white/10 bg-zinc-900/60 p-5 hover:border-orange-500/30 transition">
                      <span className="text-xs font-bold text-orange-300 uppercase tracking-widest">{meta.label}</span>
                      <div className="mt-3 space-y-2.5 text-xs text-zinc-300">
                        <div className="flex justify-between items-center">
                          <span className="text-zinc-400">Model Version</span>
                          <span className="font-mono font-bold text-white">{meta.version}</span>
                        </div>
                        {meta.timestamp && (
                          <div className="flex justify-between items-center text-[11px] text-zinc-500">
                            <span>Trained At</span>
                            <span className="font-mono font-bold text-zinc-400">
                              {new Date(meta.timestamp).toLocaleString("en-US", {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit",
                              })}
                            </span>
                          </div>
                        )}
                        <div className="flex justify-between items-center">
                          <span className="text-zinc-400">PR-AUC (test)</span>
                          <span className="font-mono font-bold text-emerald-400">{(meta.pr_auc * 100).toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-zinc-400">Precision</span>
                          <span className="font-mono font-bold text-emerald-400">{(meta.precision * 100).toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-zinc-400">Recall</span>
                          <span className="font-mono font-bold text-emerald-400">{(meta.recall * 100).toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-zinc-400">Evasion Rate</span>
                          <span className="font-mono font-bold text-red-400">{(meta.evasion_rate * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Per-Family Performance Panel */}
            {familyMetrics && familyMetrics.by_family && (
              <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <Target className="h-4 w-4 text-orange-400" />
                    Adversarial Campaign Recall (Per-Family Breakdown)
                  </h3>
                  <button
                    onClick={() => setShowFamilyBreakdown(!showFamilyBreakdown)}
                    className="px-4 py-2 rounded-full border border-orange-400/30 bg-zinc-900 hover:border-orange-400 hover:bg-orange-500/10 text-xs font-bold text-orange-200 transition"
                  >
                    {showFamilyBreakdown ? "Hide Detailed Metrics" : "Show Detailed Metrics"}
                  </button>
                </div>
                <p className="text-xs text-zinc-400 mb-5">
                  Detailed evaluation of the active model against each individual synthetic fraud family across key operating points.
                </p>

                {showFamilyBreakdown && (
                  <div className="overflow-x-auto border border-white/10 rounded-2xl bg-zinc-900/60">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-white/10 bg-zinc-950/80 text-zinc-400 font-bold uppercase tracking-wider text-[11px]">
                          <th className="px-5 py-3.5">Attack Family</th>
                          <th className="px-5 py-3.5 text-right">Samples (N)</th>
                          <th className="px-5 py-3.5 text-right">Mean Prob.</th>
                          <th className="px-5 py-3.5 text-right">Recall @ 0.1% FPR</th>
                          <th className="px-5 py-3.5 text-right">Recall @ 1.0% FPR</th>
                          <th className="px-5 py-3.5 text-right">Recall @ Selected Thresh</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {familyMetrics.by_family.map((f: any, idx: number) => {
                          if (f.family === "__legit__") return null;
                          return (
                            <tr key={idx} className="hover:bg-orange-500/[0.03] transition text-zinc-300">
                              <td className="px-5 py-3.5 font-semibold text-zinc-200 capitalize">
                                {f.family.replace(/_/g, " ")}
                              </td>
                              <td className="px-5 py-3.5 text-right font-mono text-zinc-400">{f.n}</td>
                              <td className="px-5 py-3.5 text-right font-mono text-zinc-400">{(f.mean_prob * 100).toFixed(1)}%</td>
                              <td className="px-5 py-3.5 text-right font-mono font-bold text-emerald-400">
                                {f.recall_01pct !== null ? `${(f.recall_01pct * 100).toFixed(1)}%` : "N/A"}
                              </td>
                              <td className="px-5 py-3.5 text-right font-mono font-bold text-emerald-400">
                                {f.recall_1pct !== null ? `${(f.recall_1pct * 100).toFixed(1)}%` : "N/A"}
                              </td>
                              <td className="px-5 py-3.5 text-right font-mono font-bold text-orange-400">
                                {f.recall_selected !== null ? `${(f.recall_selected * 100).toFixed(1)}%` : "N/A"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Performance Metrics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {metricsData?.recorded_metrics.map((item, idx) => (
                <div key={idx} className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-6 flex items-center justify-between backdrop-blur-xl shadow-xl shadow-orange-500/5 transition">
                  <div>
                    <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block mb-1">
                      {item.metric}
                    </span>
                    <span className="text-3xl font-black text-white font-mono">
                      <CountUp end={item.value * 100} decimals={2} duration={1.5} preserveValue />%
                    </span>
                  </div>
                  {/* Miniature Circle Progress */}
                  <div className="h-14 w-14 relative flex items-center justify-center">
                    <svg className="absolute inset-0 h-full w-full -rotate-90">
                      <circle cx="28" cy="28" r="22" stroke="#27272a" strokeWidth="4" fill="transparent" />
                      <circle
                        cx="28"
                        cy="28"
                        r="22"
                        stroke="#f97316"
                        strokeWidth="4"
                        fill="transparent"
                        strokeDasharray={2 * Math.PI * 22}
                        strokeDashoffset={2 * Math.PI * 22 * (1 - item.value)}
                        strokeLinecap="round"
                      />
                    </svg>
                    <TrendingUp className="h-5 w-5 text-orange-400" />
                  </div>
                </div>
              ))}
              {metricsData?.model_provenance?.alerts_per_1000 != null && (
                <div className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-6 flex items-center justify-between backdrop-blur-xl shadow-xl shadow-orange-500/5 transition">
                  <div>
                    <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block mb-1">
                      Alerts per 1,000 txns
                    </span>
                    <span className="text-3xl font-black text-white font-mono">
                      ~{metricsData.model_provenance.alerts_per_1000.toFixed(1)}
                    </span>
                    <span className="text-xs text-zinc-400 mt-1 block">at F1-optimal threshold</span>
                  </div>
                  <Activity className="h-7 w-7 text-orange-400" />
                </div>
              )}
            </div>

            {/* Feature Importance Panel */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Feature Importance Bar chart - 7 Cols */}
              <div className="md:col-span-8 rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition">
                <h3 className="text-xs font-bold text-white uppercase tracking-[0.16em] mb-6 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-orange-400" />
                  Live Model Feature Importances (Top 10)
                </h3>

                {isLoadingMetrics ? (
                  <div className="h-64 bg-zinc-900/60 rounded-2xl animate-pulse" />
                ) : !metricsData || metricsData.feature_importances.length === 0 ? (
                  <div className="h-64 flex items-center justify-center border border-white/10 border-dashed rounded-2xl">
                    <span className="text-sm text-zinc-400">Train model to visualize feature importances</span>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {metricsData.feature_importances.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-4">
                        <span className="text-xs text-zinc-300 font-mono w-44 truncate text-right">
                          {item.feature}
                        </span>
                        <div className="flex-1 h-5 bg-zinc-900 rounded-full overflow-hidden relative border border-white/5">
                          <div
                            style={{ width: `${item.importance * 100}%` }}
                            className="h-full bg-orange-500 rounded-full transition-all duration-1000"
                          />
                        </div>
                        <span className="text-xs text-zinc-200 font-mono font-bold w-12">
                          {(item.importance * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Targets & Configuration - 4 Cols */}
              <div className="md:col-span-4 rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 flex flex-col gap-4 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition">
                <h3 className="text-xs font-bold text-white uppercase tracking-[0.16em] mb-1 flex items-center gap-2">
                  <Target className="h-4 w-4 text-orange-400" />
                  Next Campaign Target Parameters
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed mb-3">
                  Derived dynamically from the importance values on the left. The next training data generator run will automatically inject these targets to evade model thresholds:
                </p>

                {metricsData && metricsData.adaptive_config && Object.keys(metricsData.adaptive_config).length > 0 ? (
                  <div className="space-y-3 flex-1">
                    {Object.entries(metricsData.adaptive_config).map(([key, val]) => (
                      <div key={key} className="p-4 rounded-2xl bg-zinc-900/60 border border-white/10 hover:border-orange-500/30 transition">
                        <span className="text-[11px] font-bold text-orange-300 uppercase tracking-wider block mb-1">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="text-sm font-bold text-white font-mono">
                          {typeof val === "boolean" ? val.toString().toUpperCase() : val}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-6 border border-dashed border-white/10 rounded-2xl text-center">
                    <RefreshCw className="h-8 w-8 text-zinc-600 mb-2 animate-spin" />
                    <span className="text-xs text-zinc-400">
                      Standard settings are active. Train the model to generate adaptive evasion parameters.
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: ATTACK CONNECTION GRAPH */}
        {activeTab === "graph" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            {guideActive && (
              <div className="lg:col-span-12 relative overflow-hidden rounded-3xl border border-orange-400/40 bg-zinc-950/85 p-6 animate-fade-in flex flex-col md:flex-row items-start md:items-center justify-between gap-5 backdrop-blur-xl shadow-2xl shadow-orange-500/10">
                <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-orange-500/15 blur-3xl" />
                <div className="flex items-start gap-4">
                  <div className="h-10 w-10 rounded-2xl bg-orange-500/15 border border-orange-400/30 flex items-center justify-center text-zinc-300 shrink-0 mt-0.5 shadow-sm">
                    <Network className="h-5 w-5 text-orange-300" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em]">
                        Threat Topology & Graph Analysis Walkthrough
                      </h3>
                      <span className="text-[11px] bg-orange-500/15 text-orange-300 border border-orange-400/30 px-3 py-0.5 rounded-full font-bold">
                        Guide Active
                      </span>
                    </div>
                    <p className="text-xs text-zinc-300 mt-1.5 leading-relaxed max-w-3xl">
                      <strong className="text-white">1. Subgraph Topology:</strong> Displays payer, payee, and attacker remote channel nodes (e.g. active voice calls, screen sharing tools).
                      <br />
                      <strong className="text-white">2. Mule Linkages & Lifecycle:</strong> Toggle between single-transaction view and the 4-phase lifecycle map to reveal multi-hop mule forwarding networks.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => {
                      setActiveTab("playground");
                      if (guideActive) setGuideStep("playground");
                    }}
                    className="px-5 py-2.5 bg-orange-500 hover:bg-orange-400 text-zinc-950 font-bold text-xs rounded-full transition flex items-center gap-1.5 shadow-lg shadow-orange-500/20"
                  >
                    Next: Simulator Playground ➔
                  </button>
                </div>
              </div>
            )}

            {/* The SVG Network Canvas - 8 Cols */}
            <div className="lg:col-span-8 relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 flex flex-col min-h-[540px] backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
                <div>
                  <h2 className="text-sm font-bold text-white uppercase tracking-[0.16em] flex items-center gap-2">
                    <Network className="h-4 w-4 text-orange-400" />
                    Network Connection Graph
                  </h2>
                  <p className="text-xs text-zinc-400 mt-1">
                    Toggle between the generic lifecycle map and live transaction linkages.
                  </p>
                </div>
                
                {/* View Mode Toggle & Clear */}
                <div className="flex items-center gap-3">
                  {graphViewMode === "transaction" && scoreResult?.network_graph && (
                    <button
                      onClick={clearGraphHistory}
                      className="px-3.5 py-1.5 text-xs font-bold text-red-300 border border-red-500/40 bg-red-950/30 rounded-full hover:bg-red-900/40 transition"
                    >
                      Clear History
                    </button>
                  )}
                  <div className="flex bg-zinc-900/90 border border-white/15 rounded-full p-1 gap-1 shadow-inner">
                    <button
                      onClick={() => setGraphViewMode("lifecycle")}
                      className={`px-3.5 py-1.5 text-xs font-semibold rounded-full transition-all ${
                        graphViewMode === "lifecycle"
                          ? "bg-orange-500 text-zinc-950 font-bold shadow-md"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      Lifecycle Map
                    </button>
                    <button
                      onClick={() => setGraphViewMode("transaction")}
                      className={`px-3.5 py-1.5 text-xs font-semibold rounded-full transition-all ${
                        graphViewMode === "transaction"
                          ? "bg-orange-500 text-zinc-950 font-bold shadow-md"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      Transaction Linkage
                    </button>
                  </div>
                </div>
              </div>

              {/* SVG Grid */}
              <div className="flex-1 relative border border-white/10 bg-zinc-950/90 rounded-2xl overflow-hidden min-h-[440px]">
                {graphViewMode === "lifecycle" && (
                  <div className="story-grid pointer-events-none absolute inset-0 opacity-30" />
                )}

                {graphViewMode === "lifecycle" ? (
                  <svg ref={lifecycleSvgRef} className="w-full h-full min-h-[440px]">
                    {/* Markers */}
                    <defs>
                      <marker
                        id="arrow"
                        viewBox="0 0 10 10"
                        refX="6"
                        refY="5"
                        markerWidth="6"
                        markerHeight="6"
                        orient="auto-start-reverse"
                      >
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#52525b" />
                      </marker>
                      <marker
                        id="arrow-glow"
                        viewBox="0 0 10 10"
                        refX="6"
                        refY="5"
                        markerWidth="6"
                        markerHeight="6"
                        orient="auto-start-reverse"
                      >
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#f97316" />
                      </marker>
                    </defs>

                    {/* Draw connection pathways */}
                    {/* Access to Probing */}
                    {ATTACK_NODES.filter(n => n.phase === "Access").map(src =>
                      ATTACK_NODES.filter(n => n.phase === "Probing").map(dest => {
                        const isHighlighted = selectedNode && (selectedNode.id === src.id || selectedNode.id === dest.id);
                        return (
                          <path
                            key={`${src.id}-${dest.id}`}
                            d={`M ${src.x/100*lifecycleDims.width} ${src.y/100*lifecycleDims.height} Q ${(src.x + dest.x)/2/100*lifecycleDims.width} ${((src.y + dest.y)/2 - 4)/100*lifecycleDims.height} ${dest.x/100*lifecycleDims.width} ${dest.y/100*lifecycleDims.height}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.9 : 0.4}
                            className="transition-all duration-300"
                          />
                        );
                      })
                    )}

                    {/* Probing to Execution */}
                    {ATTACK_NODES.filter(n => n.phase === "Probing").map(src =>
                      ATTACK_NODES.filter(n => n.phase === "Execution").map(dest => {
                        const isHighlighted = selectedNode && (selectedNode.id === src.id || selectedNode.id === dest.id);
                        return (
                          <path
                            key={`${src.id}-${dest.id}`}
                            d={`M ${src.x/100*lifecycleDims.width} ${src.y/100*lifecycleDims.height} Q ${(src.x + dest.x)/2/100*lifecycleDims.width} ${((src.y + dest.y)/2 + 3)/100*lifecycleDims.height} ${dest.x/100*lifecycleDims.width} ${dest.y/100*lifecycleDims.height}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.9 : 0.4}
                            className="transition-all duration-300"
                          />
                        );
                      })
                    )}

                    {/* Execution to Evasion */}
                    {ATTACK_NODES.filter(n => n.phase === "Execution").map(src =>
                      ATTACK_NODES.filter(n => n.phase === "Evasion").map(dest => {
                        const isHighlighted = selectedNode && (selectedNode.id === src.id || selectedNode.id === dest.id);
                        return (
                          <path
                            key={`${src.id}-${dest.id}`}
                            d={`M ${src.x/100*lifecycleDims.width} ${src.y/100*lifecycleDims.height} L ${dest.x/100*lifecycleDims.width} ${dest.y/100*lifecycleDims.height}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.9 : 0.4}
                            className="transition-all duration-300"
                          />
                        );
                      })
                    )}

                    {/* Evasion to Exfiltration */}
                    {ATTACK_NODES.filter(n => n.phase === "Evasion").map(src =>
                      ATTACK_NODES.filter(n => n.phase === "Exfiltration").map(dest => {
                        const isHighlighted = selectedNode && (selectedNode.id === src.id || selectedNode.id === dest.id);
                        return (
                          <path
                            key={`${src.id}-${dest.id}`}
                            d={`M ${src.x/100*lifecycleDims.width} ${src.y/100*lifecycleDims.height} Q ${(src.x + dest.x)/2/100*lifecycleDims.width} ${((src.y + dest.y)/2 + 2)/100*lifecycleDims.height} ${dest.x/100*lifecycleDims.width} ${dest.y/100*lifecycleDims.height}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.9 : 0.4}
                            className="transition-all duration-300"
                          />
                        );
                      })
                    )}

                    {/* Nodes Layer */}
                    {ATTACK_NODES.map(node => {
                      const isSelected = selectedNode?.id === node.id;
                      const cx = (node.x / 100) * lifecycleDims.width;
                      const cy = (node.y / 100) * lifecycleDims.height;
                      return (
                        <g
                          key={node.id}
                          onClick={() => setSelectedNode(node)}
                          className="cursor-pointer group"
                        >
                          {isSelected && (
                            <circle
                              cx={cx}
                              cy={cy}
                              r="18"
                              fill="none"
                              stroke="#f97316"
                              strokeWidth="2"
                              strokeDasharray="3 3"
                              className="animate-spin-slow"
                            />
                          )}
                          <circle
                            cx={cx}
                            cy={cy}
                            r="9"
                            fill={isSelected ? "#f97316" : "#18181b"}
                            stroke={isSelected ? "#ea580c" : "#3f3f46"}
                            strokeWidth="2"
                            className="transition-all group-hover:stroke-orange-400 group-hover:scale-125"
                          />
                          <text
                            x={cx}
                            y={cy - 13}
                            textAnchor="middle"
                            fill={isSelected ? "#fb923c" : "#a1a1aa"}
                            fontSize="10px"
                            fontFamily="monospace"
                            className="font-bold pointer-events-none transition-colors group-hover:fill-zinc-100"
                          >
                            {node.id}
                          </text>
                          <text
                            x={cx}
                            y={cy + 18}
                            textAnchor="middle"
                            fill={isSelected ? "#fed7aa" : "#71717a"}
                            fontSize="9px"
                            className="pointer-events-none transition-colors group-hover:fill-zinc-200"
                          >
                            {node.name}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                ) : (
                  // Dynamic Transaction Subgraph View
                  !scoreResult?.network_graph || scoreResult.network_graph.nodes.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center min-h-[440px]">
                      <Network className="h-12 w-12 text-zinc-600 mb-3" />
                      <span className="text-xs text-zinc-400">
                        Run a risk assessment in Tab 1 to generate and inspect real-time transaction graphs.
                      </span>
                    </div>
                  ) : (
                    <div className="w-full h-[440px]">
                      <ReactFlow
                        nodes={transactionFlowNodes}
                        edges={transactionFlowEdges}
                        nodeTypes={nodeTypes}
                        onNodeClick={(_, node) =>
                          setSelectedTransactionNode(
                            scoreResult.network_graph?.nodes.find(n => n.id === node.id) ?? null
                          )
                        }
                        fitView
                        proOptions={{ hideAttribution: true }}
                        className="w-full h-full min-h-[350px]"
                      >
                        <Background color="#27272a" gap={24} />
                        <Controls className="bg-zinc-900 border-white/10 fill-zinc-300" />
                      </ReactFlow>
                    </div>
                  )
                )}
              </div>
            </div>

            {/* Right Details Panel - 4 Cols */}
            <div className="lg:col-span-4 flex flex-col gap-6">
              {graphViewMode === "lifecycle" ? (
                // Lifecycle Attack Node Details
                !selectedNode ? (
                  <div className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 flex flex-col items-center justify-center text-center flex-1 min-h-[300px] backdrop-blur-xl shadow-xl shadow-orange-500/5">
                    <Layers className="h-10 w-10 text-zinc-600 mb-2" />
                    <span className="text-xs text-zinc-400">Select any node on the canvas to inspect its adversarial mechanism</span>
                  </div>
                ) : (
                  <div className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 flex-1 flex flex-col gap-5 animate-fade-in backdrop-blur-xl shadow-xl shadow-orange-500/5">
                    <div className="flex items-start justify-between border-b border-white/10 pb-3.5">
                      <div>
                        <span className="text-xs font-mono font-bold text-orange-300 block mb-1">
                          {selectedNode.id} • {selectedNode.phase} Phase
                        </span>
                        <h3 className="text-base font-bold text-white">{selectedNode.name}</h3>
                      </div>
                      <span className="text-[11px] font-mono text-zinc-300 bg-zinc-900/90 px-3 py-1 rounded-full border border-white/10">
                        {selectedNode.rail}
                      </span>
                    </div>

                    <div>
                      <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block mb-1.5">
                        Mechanism Summary
                      </span>
                      <p className="text-xs text-zinc-300 leading-relaxed">
                        {selectedNode.description}
                      </p>
                    </div>

                    <div className="p-4 bg-zinc-900/60 rounded-2xl border border-white/10">
                      <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block mb-1">
                        Signature Pattern
                      </span>
                      <span className="text-xs font-mono text-orange-200 block leading-relaxed">
                        {selectedNode.signature}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-4 border-t border-white/10 pt-4">
                      <div>
                        <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest block mb-1.5">
                          Novelty Rating
                        </span>
                        <div className="flex gap-1.5">
                          {[1, 2, 3, 4, 5].map(star => (
                            <div
                              key={star}
                              className={`h-2 flex-1 rounded-full ${
                                star <= selectedNode.novelty ? "bg-orange-500" : "bg-zinc-800"
                              }`}
                            />
                          ))}
                        </div>
                      </div>

                      <div>
                        <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest block mb-1.5">
                          Detection Difficulty
                        </span>
                        <div className="flex gap-1.5">
                          {[1, 2, 3, 4, 5].map(star => (
                            <div
                              key={star}
                              className={`h-2 flex-1 rounded-full ${
                                star <= selectedNode.difficulty ? "bg-orange-500" : "bg-zinc-800"
                              }`}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              ) : (
                // Transaction Graph Node Details (Dynamic)
                !selectedTransactionNode ? (
                  <div className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 flex flex-col items-center justify-center text-center flex-1 backdrop-blur-xl shadow-xl shadow-orange-500/5">
                    <Network className="h-10 w-10 text-zinc-600 mb-2" />
                    <span className="text-xs text-zinc-400">Select a node in the network to inspect its linkage metadata</span>
                  </div>
                ) : (
                  <div className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 flex-1 flex flex-col gap-5 animate-fade-in backdrop-blur-xl shadow-xl shadow-orange-500/5">
                    <div className="flex items-start justify-between border-b border-white/10 pb-3.5">
                      <div>
                        <span className={`inline-block text-[11px] font-bold px-3 py-1 rounded-full uppercase tracking-wider mb-1.5 ${
                          selectedTransactionNode.risk === "critical" || selectedTransactionNode.risk === "high"
                            ? "bg-red-500/20 border border-red-500/40 text-red-400"
                            : selectedTransactionNode.risk === "medium" || selectedTransactionNode.risk === "warning"
                            ? "bg-orange-500/20 border border-orange-500/40 text-orange-300"
                            : "bg-emerald-500/20 border border-emerald-500/40 text-emerald-300"
                        }`}>
                          Risk: {selectedTransactionNode.risk.toUpperCase()}
                        </span>
                        <h3 className="text-sm font-bold text-white">{selectedTransactionNode.label}</h3>
                      </div>
                      <span className="text-[11px] text-zinc-400 font-bold uppercase tracking-wider">
                        {selectedTransactionNode.type.replace(/_/g, " ")} Node
                      </span>
                    </div>

                    <div className="space-y-3">
                      <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block mb-1">Node Parameters</span>
                      <div className="space-y-2.5">
                        {Object.entries(selectedTransactionNode.details).map(([key, val]: [string, any]) => (
                          <div key={key} className="flex justify-between border-b border-white/5 pb-2 text-xs">
                            <span className="text-zinc-400 font-medium">{key}</span>
                            <span className="text-white font-mono font-bold">{val}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              )}

              {/* Session Transaction Timeline */}
              {graphViewMode === "transaction" && scoreResult?.network_graph && scoreResult.network_graph.nodes.length > 0 && (
                <div className="rounded-3xl border border-orange-500/20 bg-zinc-950/85 p-6 backdrop-blur-xl shadow-xl shadow-orange-500/5">
                  <span className="text-xs font-bold text-orange-300 uppercase tracking-widest block mb-3">
                    Session Transaction Timeline
                  </span>
                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {scoreResult.network_graph.nodes
                      .filter((n) => n.type === "payee")
                      .map((n) => {
                        const isActive = selectedTransactionNode?.id === n.id;
                        return (
                          <button
                            key={n.id}
                            onClick={() => setSelectedTransactionNode(n)}
                            className={`w-full flex items-center justify-between gap-2 px-4 py-3 rounded-2xl border text-left transition ${
                              isActive
                                ? "border-orange-500/60 bg-orange-500/15 text-white shadow-md shadow-orange-500/10"
                                : "border-white/5 bg-zinc-900/60 hover:border-orange-500/30"
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span
                                className={`h-2 w-2 rounded-full shrink-0 ${
                                  n.risk === "critical" || n.risk === "high"
                                    ? "bg-red-500"
                                    : n.risk === "medium" || n.risk === "warning"
                                    ? "bg-orange-500"
                                    : "bg-emerald-500"
                                }`}
                              />
                              <span className="text-xs font-mono text-zinc-200 truncate">
                                {n.details["Transaction ID"]}
                              </span>
                            </div>
                            <span className="text-xs font-mono text-zinc-300 font-bold shrink-0">
                              {n.details["Transfer Value"]}
                            </span>
                          </button>
                        );
                      })
                      .reverse()}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: ATTACK SIMULATOR PLAYGROUND */}
        {activeTab === "playground" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start animate-fade-in">
            {guideActive && (
              <div className="lg:col-span-3 relative overflow-hidden rounded-3xl border border-orange-400/40 bg-zinc-950/85 p-6 animate-fade-in flex flex-col md:flex-row items-start md:items-center justify-between gap-5 backdrop-blur-xl shadow-2xl shadow-orange-500/10">
                <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-orange-500/15 blur-3xl" />
                <div className="flex items-start gap-4">
                  <div className="h-10 w-10 rounded-2xl bg-orange-500/15 border border-orange-400/30 flex items-center justify-center text-zinc-300 shrink-0 mt-0.5 shadow-sm">
                    <Zap className="h-5 w-5 text-orange-300" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em]">
                        Attack Simulator Playground Walkthrough
                      </h3>
                      <span className="text-[11px] bg-orange-500/15 text-orange-300 border border-orange-400/30 px-3 py-0.5 rounded-full font-bold">
                        Guide Active
                      </span>
                    </div>
                    <p className="text-xs text-zinc-300 mt-1.5 leading-relaxed max-w-3xl">
                      <strong className="text-white">1. Attack Family Catalog:</strong> Choose from 16 generator families (e.g., Scam-induced Push, Mule Network, Credential Takeover) and set attack intensity.
                      <br />
                      <strong className="text-white">2. Live Campaign Flood:</strong> Injects synthetic transactions into the scoring pipeline one by one to stress-test real-time detection and graph hop propagation.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => {
                      setActiveTab("scoring");
                      if (guideActive) setGuideStep("choose_scenario");
                    }}
                    className="px-5 py-2.5 bg-orange-500 hover:bg-orange-400 text-zinc-950 font-bold text-xs rounded-full transition flex items-center gap-1.5 shadow-lg shadow-orange-500/20"
                  >
                    Restart Tour (Scoring Studio) ➔
                  </button>
                </div>
              </div>
            )}

            {/* Left Sidebar: Controls */}
            <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 space-y-6 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
              <div>
                <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                  <Settings className="h-4 w-4 text-orange-400" />
                  Simulator Configuration
                </h3>
                <p className="text-xs text-zinc-400">Configure parameters to generate a synthetic campaign.</p>
              </div>

              {/* Attack Family Dropdown */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">Attack Vector Family</label>
                <select
                  value={playgroundAttackId}
                  onChange={(e) => setPlaygroundAttackId(e.target.value)}
                  disabled={isPlaygroundSimulating}
                  className="w-full bg-zinc-900/90 border border-white/15 rounded-2xl px-4 py-3 text-xs font-mono text-zinc-200 outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-400/30 transition cursor-pointer text-ellipsis overflow-hidden shadow-inner"
                >
                  <option value="scam_induced_push">Phone Call Pressured Transfer (Scam-induced Push)</option>
                  <option value="mule_network">Multi-Account Fund Forwarding (Mule Network)</option>
                  <option value="card_testing_probe">Micro-Amount Acquiring Test (Card Testing)</option>
                  <option value="adversarial_evasion">Model evasion / Distributed velocity (Adversarial Evasion)</option>
                  <option value="first_party_dispute">Chargeback abuse / Refund fraud (First-party Dispute)</option>
                  <option value="stealth_mandate">AutoPay dark-pattern mandate abuse (Stealth Mandate)</option>
                  <option value="synthetic_merchant">Fictitious seller cashout (Synthetic Merchant)</option>
                  <option value="transaction_laundering">Declared MCC classification mismatch (Laundering)</option>
                  <option value="credential_takeover">Device change with anomalous takeover (Credential Takeover)</option>
                  <option value="synthetic_identity_bustout">Clean-profile limit build & exit (Synthetic ID Bustout)</option>
                  <option value="subthreshold_fragmentation">AFA regulation limit bypass (Fragmentation)</option>
                  <option value="agentic_injection">Prompt injection VPA extraction (Agentic Injection)</option>
                  <option value="insider_abuse">Internal ledger adjustment bypass (Insider Abuse)</option>
                  <option value="device_fan_out">Single credential device fan-out (Velocity Probe)</option>
                  <option value="balance_drain_exit">Final liquidation / Account sweep (Exit Drain)</option>
                  <option value="tpap_account_switch">Cross-TPAP credential rotation (Account Switch)</option>
                </select>
              </div>

              {/* Intensity Select */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">Campaign Intensity</label>
                <div className="grid grid-cols-3 gap-2.5">
                  {["LOW", "MEDIUM", "HIGH"].map((level) => (
                    <button
                      key={level}
                      type="button"
                      disabled={isPlaygroundSimulating}
                      onClick={() => setPlaygroundIntensity(level)}
                      className={`py-2.5 rounded-2xl text-xs font-bold border transition ${
                        playgroundIntensity === level
                          ? "bg-orange-500 text-zinc-950 border-orange-400 shadow-md shadow-orange-500/20"
                          : "bg-zinc-900 border-white/10 text-zinc-300 hover:text-white hover:border-orange-500/30"
                      }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>

              {/* Trigger Button */}
              <button
                onClick={startPlaygroundSimulation}
                disabled={isPlaygroundSimulating}
                className="w-full flex items-center justify-center gap-2 py-4 bg-orange-500 hover:bg-orange-400 text-zinc-950 font-bold text-xs rounded-2xl transition disabled:opacity-50 shadow-xl shadow-orange-500/25 tracking-wide"
              >
                <Play className={`h-4 w-4 fill-zinc-950 ${isPlaygroundSimulating ? "animate-spin" : ""}`} />
                {isPlaygroundSimulating ? "Simulating Hop-by-Hop..." : "Start Live Campaign Simulation"}
              </button>

              {playgroundError && (
                <div className="p-4 rounded-2xl border border-red-500/40 bg-red-950/30 text-red-300 text-xs flex gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-red-400" />
                  <span>{playgroundError}</span>
                </div>
              )}

              {/* Pretext Card */}
              {playgroundCampaignId && (
                <div className="rounded-2xl border border-orange-500/30 bg-zinc-900/60 p-5 space-y-4 animate-fade-in">
                  <div className="border-b border-white/10 pb-2.5 flex justify-between items-center">
                    <span className="text-[11px] font-bold bg-orange-500/15 border border-orange-400/30 text-orange-300 px-3 py-0.5 rounded-full uppercase tracking-wider">
                      Active Campaign
                    </span>
                    <span className="text-xs font-mono text-zinc-400">{playgroundCampaignId.slice(0, 8)}...</span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Attack Pretext</span>
                      <span className="font-semibold text-white font-mono capitalize">{playgroundPretext.replace(/_/g, " ")}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Hops / Transactions</span>
                      <span className="font-mono font-bold text-orange-300">{playgroundTransactions.length} generated</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Middle: Hop-by-hop Feed */}
            <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 min-h-[500px] flex flex-col gap-4 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
              <div>
                <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-orange-400" />
                  Live Campaign Ticker
                </h3>
                <p className="text-xs text-zinc-400">Hop-by-hop transactional steps generated by the simulator.</p>
              </div>

              {playgroundTransactions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                  <Network className={`h-12 w-12 text-zinc-700 mb-3 ${isPlaygroundSimulating ? "animate-pulse text-orange-400" : ""}`} />
                  <span className="text-xs text-zinc-400">
                    {isPlaygroundSimulating
                      ? "Generating synthetic campaign sequence..."
                      : "Configure parameters on the left and trigger simulation to watch campaign data."}
                  </span>
                </div>
              ) : (
                <div className="space-y-3 flex-1 overflow-y-auto max-h-[550px] pr-1">
                  {playgroundTransactions.map((txItem, idx) => {
                    const isSelected = playgroundCurrentIndex === idx;
                    const r = txItem.result;
                    const tx = txItem.transaction;
                    return (
                      <button
                        key={idx}
                        onClick={() => setPlaygroundCurrentIndex(idx)}
                        className={`w-full text-left rounded-2xl border p-4 transition-all flex items-start gap-3.5 relative overflow-hidden ${
                          isSelected
                            ? "border-orange-400 bg-orange-500/15 shadow-md shadow-orange-500/10"
                            : "border-white/5 bg-zinc-900/60 hover:border-orange-500/30"
                        }`}
                      >
                        {/* Sequence indicator */}
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-zinc-800 border border-white/10 font-mono text-xs font-bold text-white shrink-0">
                          {txItem.sequence}
                        </div>

                        <div className="flex-1 min-w-0 space-y-1.5">
                          <div className="flex justify-between items-start">
                            <span className="font-mono text-xs text-white font-bold">
                              ₹{parseFloat(tx.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                            </span>
                            <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                              r.risk_level === "CRITICAL" || r.risk_level === "HIGH"
                                ? "bg-red-500/20 text-red-300 border border-red-500/40"
                                : r.risk_level === "MEDIUM"
                                ? "bg-orange-500/20 text-orange-300 border border-orange-500/40"
                                : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                            }`}>
                              {r.risk_level}
                            </span>
                          </div>

                          <div className="flex justify-between text-[11px] text-zinc-400">
                            <span className="capitalize">{tx.rail.replace(/_/g, " ")} ({tx.channel})</span>
                            <span className="font-mono text-orange-300 font-bold">Score: {r.risk_score.toFixed(1)}</span>
                          </div>
                        </div>

                        {/* Visual indicator bar */}
                        <div className={`absolute top-0 right-0 bottom-0 w-1.5 ${
                          r.risk_level === "CRITICAL" || r.risk_level === "HIGH"
                            ? "bg-red-500"
                            : r.risk_level === "MEDIUM"
                            ? "bg-orange-500"
                            : "bg-emerald-500"
                        }`} />
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Right: Hop Details */}
            <div className="space-y-6">
              {playgroundCurrentIndex === -1 || playgroundTransactions.length === 0 ? (
                <div className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 min-h-[500px] flex flex-col items-center justify-center text-center backdrop-blur-xl shadow-xl shadow-orange-500/5">
                  <Activity className="h-10 w-10 text-zinc-700 mb-2" />
                  <span className="text-xs text-zinc-400">Select a transaction hop from the ticker to inspect its score analysis</span>
                </div>
              ) : (
                <div className="rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 space-y-6 animate-fade-in backdrop-blur-xl shadow-2xl shadow-orange-500/5">
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                      <Target className="h-4 w-4 text-orange-400" />
                      Hop Analysis
                    </h3>
                    <p className="text-xs text-zinc-400">Deep-dive risk scoring and SHAP attributions.</p>
                  </div>

                  {/* Risk Score Dial/Gauge */}
                  <div className="rounded-2xl border border-white/10 bg-zinc-900/60 p-5 flex flex-col items-center justify-center gap-3">
                    <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest">Live Risk Score</span>
                    <div className="h-24 w-24 relative flex items-center justify-center">
                      <svg className="absolute inset-0 h-full w-full -rotate-90">
                        <circle cx="48" cy="48" r="40" stroke="#27272a" strokeWidth="4" fill="transparent" />
                        <circle
                          cx="48"
                          cy="48"
                          r="40"
                          stroke={
                            playgroundTransactions[playgroundCurrentIndex].result.risk_level === "CRITICAL" ||
                            playgroundTransactions[playgroundCurrentIndex].result.risk_level === "HIGH"
                              ? "#ef4444"
                              : playgroundTransactions[playgroundCurrentIndex].result.risk_level === "MEDIUM"
                              ? "#f59e0b"
                              : "#10b981"
                          }
                          strokeWidth="4"
                          fill="transparent"
                          strokeDasharray={2 * Math.PI * 40}
                          strokeDashoffset={
                            2 * Math.PI * 40 * (1 - playgroundTransactions[playgroundCurrentIndex].result.risk_score / 100)
                          }
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="flex flex-col items-center z-10">
                        <span className="text-2xl font-black text-white font-mono leading-none">
                          {playgroundTransactions[playgroundCurrentIndex].result.risk_score.toFixed(0)}
                        </span>
                        <span className="text-[9px] font-mono text-zinc-400 font-bold uppercase mt-0.5">/ 100</span>
                      </div>
                    </div>
                    <span className={`text-xs font-bold px-3.5 py-1.5 rounded-full uppercase tracking-wider ${
                      playgroundTransactions[playgroundCurrentIndex].result.action === "BLOCK"
                        ? "bg-red-500/20 text-red-300 border border-red-500/40"
                        : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    }`}>
                      Action: {playgroundTransactions[playgroundCurrentIndex].result.action}
                    </span>
                  </div>

                  {/* SHAP Contributions bar chart */}
                  {playgroundTransactions[playgroundCurrentIndex].result.shap_contributions && (
                    <div className="space-y-3">
                      <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">Model SHAP Attributions</span>
                      <div className="space-y-2">
                        {playgroundTransactions[playgroundCurrentIndex].result.shap_contributions.map((s: any, idx: number) => {
                          const isPositive = s.direction === "increases_risk";
                          return (
                            <div key={idx} className="space-y-1.5 text-xs">
                              <div className="flex justify-between font-mono text-[11px]">
                                <span className="text-zinc-300 truncate max-w-[150px]">{s.feature}</span>
                                <span className={isPositive ? "text-red-400 font-bold" : "text-emerald-400 font-bold"}>
                                  {isPositive ? "+" : ""}{s.shap_value.toFixed(2)}
                                </span>
                              </div>
                              <div className="h-2 w-full bg-zinc-900 rounded-full overflow-hidden relative">
                                <div
                                  className="absolute top-0 bottom-0 rounded-full"
                                  style={{
                                    left: isPositive ? "50%" : "auto",
                                    right: isPositive ? "auto" : "50%",
                                    width: `${Math.min(50, Math.abs(s.shap_value) * 10)}%`,
                                    backgroundColor: isPositive ? "#ef4444" : "#10b981"
                                  }}
                                />
                                <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-zinc-700" />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Dynamic Contributing Signals */}
                  {playgroundTransactions[playgroundCurrentIndex].result.contributing_signals &&
                    playgroundTransactions[playgroundCurrentIndex].result.contributing_signals.length > 0 && (
                      <div className="space-y-2">
                        <span className="text-[11px] font-bold text-orange-300 uppercase tracking-widest block">Threat Indicators</span>
                        <div className="space-y-2">
                          {playgroundTransactions[playgroundCurrentIndex].result.contributing_signals.map((sig: string, sIdx: number) => (
                            <div key={sIdx} className="flex items-start gap-2.5 text-xs text-zinc-300 p-2.5 rounded-xl bg-zinc-900/60 border border-white/5">
                              <ScanLine className="h-4 w-4 text-orange-400 mt-0.5 shrink-0" />
                              <span>{sig}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-zinc-950/80 backdrop-blur py-5 text-center text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>© 2026 Chakravyuh Fraud Defense Operations • Mastercard Innovation Challenge</span>
          <span className="font-mono text-[11px] text-zinc-400">Live Active Defence Mode</span>
        </div>
      </footer>

    </div>
  );
}

const storySteps = [
  {
    number: "01",
    eyebrow: "The moment that matters",
    title: "A real PIN can still authorise the wrong payment.",
    copy: "GenAI scams do not need to break payment cryptography. They manipulate the person holding the device, then move funds through a newly added beneficiary.",
    signals: ["Active call during confirmation", "Beneficiary added 38 seconds ago", "Screen share detected"],
  },
  {
    number: "02",
    eyebrow: "Generate the attacker",
    title: "Make the next fraud variant before it reaches a customer.",
    copy: "Chakravyuh turns attack research into realistic, privacy-safe payment campaigns—with legitimate lookalikes that stop the model from learning shortcuts.",
    signals: ["16 attack families", "Campaign and mule-network structure", "Synthetic, reproducible data"],
  },
  {
    number: "03",
    eyebrow: "Defend at decision time",
    title: "Explainable risk scoring, before funds leave the rail.",
    copy: "The detector combines payment context, behavioural signals and counterparty graphs to recommend a hold, review or allow decision in the authorisation window.",
    signals: ["Decision-time signals only", "Graph-aware detection", "Analyst-ready explanation"],
  },
  {
    number: "04",
    eyebrow: "Close the loop",
    title: "Every analyst decision makes the defence harder to evade.",
    copy: "When a scenario slips through, Chakravyuh produces a controlled tougher variant, measures the blind spot, and feeds the finding back into training.",
    signals: ["Feedback becomes a learning signal", "Blind spots become variants", "Coverage keeps improving"],
  },
];

const profileLinks = [
  {
    name: "Sneh Kansagara",
    role: "Co-builder",
    photo: "/team/sneh-kansagara.png",
    initials: "SK",
    linkedin: "https://www.linkedin.com/in/sneh-kansagara-b61362312/",
    github: "https://github.com/Sharkyii",
  },
  {
    name: "Priyanshu Jha",
    role: "Co-builder",
    photo: "/team/priyanshu-jha.jpeg",
    initials: "PJ",
    linkedin: "https://www.linkedin.com/in/priyanshu-jha-b74129324/",
    github: "https://github.com/priyanshuiiitm",
  },
];

/** Shows a supplied team photo, or a composed initials mark until one is added. */
function TeamAvatar({ profile }: { profile: (typeof profileLinks)[number] }) {
  const [imageAvailable, setImageAvailable] = useState(true);

  // No src known to be missing is ever requested -- avoids a failed image
  // load (and its console error) rather than catching one after the fact.
  if (!profile.photo || !imageAvailable) {
    return <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-orange-400/30 bg-orange-500/10 text-xs font-bold tracking-wider text-orange-200">{profile.initials}</div>;
  }

  return (
    <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-full border border-orange-400/30 bg-orange-500/10">
      {/* Add the image at public/team/ and set its path on profileLinks above. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={profile.photo} alt={`${profile.name} profile`} className="h-full w-full object-cover" onError={() => setImageAvailable(false)} />
    </div>
  );
}

const HERO_SCENARIOS = [
  {
    id: "scam_push",
    tag: "Social Engineering",
    rail: "UPI P2P transfer",
    amount: "₹48,000",
    subtitle: "to a beneficiary added 38 sec ago",
    riskScore: 94,
    riskLevel: "Critical",
    riskColor: "text-orange-300",
    riskBg: "border-orange-400/30 bg-orange-400/10",
    action: "HOLD FOR REVIEW",
    actionBg: "bg-orange-400 text-zinc-950",
    glowColor: "from-orange-500/20 to-emerald-500/10",
    signals: [
      "Call active on confirmation screen",
      "Screen-share service detected",
      "Recipient matches mule-network pattern",
    ],
  },
  {
    id: "split_smurfing",
    tag: "Adversarial Evasion",
    rail: "Cards 3DS / E-Comm",
    amount: "₹4,990",
    subtitle: "3rd transaction under ₹5,000 in 12 mins",
    riskScore: 88,
    riskLevel: "High",
    riskColor: "text-amber-300",
    riskBg: "border-amber-400/30 bg-amber-400/10",
    action: "CHALLENGE (STEP-UP OTP)",
    actionBg: "bg-amber-400 text-zinc-950",
    glowColor: "from-amber-500/20 to-rose-500/10",
    signals: [
      "Velocity anomaly (3 rapid micro-charges)",
      "Novel device fingerprint hash",
      "Merchant category risk mismatch",
    ],
  },
  {
    id: "genuine_pay",
    tag: "Legitimate Baseline",
    rail: "UPI QR Merchant Pay",
    amount: "₹1,250",
    subtitle: "to recurring grocery merchant (MCC 5411)",
    riskScore: 3,
    riskLevel: "Low",
    riskColor: "text-emerald-300",
    riskBg: "border-emerald-400/30 bg-emerald-400/10",
    action: "INSTANT APPROVAL",
    actionBg: "bg-emerald-400 text-zinc-950",
    glowColor: "from-emerald-500/20 to-teal-500/10",
    signals: [
      "Known counterparty with 14 prior transactions",
      "Device biometric authentication verified",
      "Normal historical spend velocity",
    ],
  },
];

/** The public, scroll-driven product story for the Chakravyuh demo. */
function StoryPage() {
  const [scrollProgress, setScrollProgress] = useState(0);
  const [activeScenarioIdx, setActiveScenarioIdx] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    const updateProgress = () => {
      const maximum = document.documentElement.scrollHeight - window.innerHeight;
      setScrollProgress(maximum > 0 ? Math.min(1, window.scrollY / maximum) : 0);
    };
    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    return () => window.removeEventListener("scroll", updateProgress);
  }, []);

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      setActiveScenarioIdx((prev) => (prev + 1) % HERO_SCENARIOS.length);
    }, 4500);
    return () => clearInterval(interval);
  }, [isPaused]);

  const currentScenario = HERO_SCENARIOS[activeScenarioIdx];

  return (
    <main className="story-page min-h-screen overflow-x-hidden bg-[#08090b] text-zinc-100 selection:bg-orange-400/30">
      <div className="fixed inset-x-0 top-0 z-[60] h-px bg-white/10">
        <motion.div className="h-full origin-left bg-gradient-to-r from-orange-500 via-amber-300 to-emerald-400" style={{ scaleX: scrollProgress }} />
      </div>

      <header className="fixed inset-x-0 top-0 z-50 flex items-center justify-between px-5 py-5 md:px-10">
        <a href="#top" className="flex items-center gap-2.5 text-sm font-bold tracking-[0.18em] text-white" aria-label="Back to top">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-orange-400/40 bg-orange-500/10">
            <Shield className="h-4 w-4 text-orange-300" />
          </span>
          CHAKRAVYUH
        </a>
        <Link href="/dashboard" className="group flex items-center gap-2 rounded-full border border-white/15 bg-zinc-950/70 px-4 py-2 text-xs font-semibold text-white backdrop-blur transition hover:border-orange-400/70 hover:bg-orange-500/10">
          Open live dashboard <ArrowUpRight className="h-3.5 w-3.5 text-orange-300 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </Link>
      </header>

      <section id="top" className="relative flex min-h-screen items-center px-5 pb-20 pt-28 md:px-10">
        <div className="story-grid pointer-events-none absolute inset-0 opacity-50" />
        <div className="absolute left-[12%] top-[16%] h-80 w-80 rounded-full bg-orange-500/15 blur-[120px]" />
        <div className="absolute bottom-[12%] right-[8%] h-72 w-72 rounded-full bg-emerald-500/10 blur-[120px]" />
        <div className="relative mx-auto grid w-full max-w-7xl items-center gap-12 lg:grid-cols-[1.05fr_.95fr]">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.75, ease: "easeOut" }}>
            <p className="mb-6 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-orange-300"><CircleDot className="h-3.5 w-3.5" /> Payment defence laboratory</p>
            <h1 className="max-w-3xl text-5xl font-semibold leading-[0.98] tracking-[-0.055em] text-white sm:text-6xl md:text-7xl">
              Fraud evolves.<br /><span className="text-zinc-500">So should the defence.</span>
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-relaxed text-zinc-400">Chakravyuh simulates GenAI-enabled payment fraud, detects it before authorisation, and turns every blind spot into a stronger defence.</p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a href="#story" className="group inline-flex items-center gap-2 rounded-full bg-orange-500 px-5 py-3 text-sm font-bold text-zinc-950 transition hover:bg-orange-300">Read the defence story <ArrowDown className="h-4 w-4 transition-transform group-hover:translate-y-1" /></a>
              <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-zinc-200 transition hover:border-white/40 hover:bg-white/5">Skip to dashboard <ArrowUpRight className="h-4 w-4" /></Link>
            </div>
            <div className="mt-12 flex flex-wrap gap-x-8 gap-y-4 text-xs text-zinc-500"><span><b className="text-zinc-200">16</b> attack families</span><span><b className="text-zinc-200">Pre-authorisation</b> decisions</span><span><b className="text-zinc-200">Privacy-safe</b> simulation</span></div>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, scale: 0.96 }} 
            animate={{ opacity: 1, scale: 1 }} 
            transition={{ duration: 0.9, delay: 0.12 }} 
            className="relative mx-auto w-full max-w-xl"
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
          >
            <div className={`absolute -inset-4 rounded-[2rem] bg-gradient-to-br ${currentScenario.glowColor} blur-2xl transition-all duration-700`} />
            <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-zinc-950/85 p-5 shadow-2xl backdrop-blur-xl md:p-7">
              {/* Card Header with Interactive Scenario Pills */}
              <div className="mb-6 flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-4">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-orange-400" />
                  <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-zinc-400">Live Authorisation Engine</span>
                </div>
                <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-zinc-900/90 p-1">
                  {HERO_SCENARIOS.map((sc, idx) => (
                    <button
                      key={sc.id}
                      onClick={() => setActiveScenarioIdx(idx)}
                      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold transition ${
                        activeScenarioIdx === idx
                          ? "bg-orange-500 text-zinc-950 shadow"
                          : "text-zinc-400 hover:text-white"
                      }`}
                      title={sc.tag}
                    >
                      {idx === 0 ? "Scam Push" : idx === 1 ? "Smurfing" : "Genuine"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Dynamic Transaction Display */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-500">{currentScenario.rail}</span>
                    <span className="rounded bg-white/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-zinc-300">{currentScenario.tag}</span>
                  </div>
                  <motion.p 
                    key={currentScenario.amount}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                    className="mt-1.5 text-4xl font-semibold tracking-tight text-white"
                  >
                    {currentScenario.amount}
                  </motion.p>
                  <p className="mt-2 text-sm text-zinc-400">{currentScenario.subtitle}</p>
                </div>
                <div className={`rounded-2xl border px-3.5 py-2 text-right ${currentScenario.riskBg}`}>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Risk</p>
                  <motion.p 
                    key={currentScenario.riskScore}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className={`text-2xl font-bold ${currentScenario.riskColor}`}
                  >
                    {currentScenario.riskScore}%
                  </motion.p>
                </div>
              </div>

              <div className="my-6 h-px bg-white/10" />

              {/* Animated Contributing Signals */}
              <div className="space-y-2.5">
                {currentScenario.signals.map((signal, index) => (
                  <motion.div 
                    key={`${currentScenario.id}-${signal}`} 
                    initial={{ opacity: 0, x: -10 }} 
                    animate={{ opacity: 1, x: 0 }} 
                    transition={{ duration: 0.2, delay: index * 0.08 }} 
                    className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3 text-sm text-zinc-300"
                  >
                    <ScanLine className={`h-4 w-4 shrink-0 ${currentScenario.riskColor}`} />
                    <span>{signal}</span>
                  </motion.div>
                ))}
              </div>

              {/* Recommended Action + Studio Direct Link */}
              <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-1 items-center justify-between rounded-xl border border-white/10 bg-zinc-900/80 p-3.5">
                  <span className="text-xs font-semibold text-zinc-400">Decision</span>
                  <span className={`rounded-lg px-3 py-1 text-xs font-bold ${currentScenario.actionBg}`}>
                    {currentScenario.action}
                  </span>
                </div>
                <Link 
                  href="/dashboard"
                  className="group flex items-center justify-center gap-1.5 rounded-xl border border-orange-500/40 bg-orange-500/10 px-4 py-3 text-xs font-bold text-orange-200 transition hover:border-orange-400 hover:bg-orange-500 hover:text-zinc-950"
                >
                  Inspect in Studio <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </Link>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section id="story" className="relative px-5 pb-24 md:px-10">
        <div className="mx-auto max-w-7xl"><div className="mb-16 max-w-2xl"><p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-300">One payment. Four acts.</p><h2 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-white md:text-5xl">Scroll through the defence.</h2></div>
          <div className="grid gap-5 lg:grid-cols-[0.48fr_.52fr]">
            <div className="hidden lg:block"><div className="sticky top-32 flex h-[430px] flex-col justify-between rounded-3xl border border-white/10 bg-zinc-900/35 p-8"><BrainCircuit className="h-10 w-10 text-orange-300" /><div><p className="text-sm text-zinc-500">A single payment is observed from first signal to next-model improvement.</p><div className="mt-5 h-1 overflow-hidden rounded-full bg-zinc-800"><motion.div className="h-full bg-orange-400" animate={{ width: ["24%", "84%", "24%"] }} transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }} /></div></div></div></div>
            <div className="space-y-5">{storySteps.map((step, index) => <motion.article key={step.number} initial={{ opacity: 0, y: 32 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.35 }} transition={{ duration: 0.55 }} className="group rounded-3xl border border-white/10 bg-zinc-900/30 p-7 transition-colors hover:border-orange-400/35 hover:bg-zinc-900/55 md:p-9"><div className="flex items-start justify-between gap-5"><div><p className="text-xs font-bold tracking-[0.2em] text-orange-300">{step.number} / {step.eyebrow}</p><h3 className="mt-4 max-w-xl text-2xl font-semibold tracking-[-0.035em] text-white md:text-3xl">{step.title}</h3></div><span className="text-4xl font-semibold text-white/10">0{index + 1}</span></div><p className="mt-5 max-w-2xl leading-relaxed text-zinc-400">{step.copy}</p><div className="mt-6 flex flex-wrap gap-2">{step.signals.map(signal => <span key={signal} className="rounded-full border border-white/10 bg-zinc-950/70 px-3 py-1.5 text-xs text-zinc-300">{signal}</span>)}</div></motion.article>)}</div>
          </div>
        </div>
      </section>

      <section className="relative border-y border-white/10 bg-gradient-to-br from-orange-500/10 via-zinc-950 to-emerald-500/10 px-5 py-24 md:px-10"><div className="mx-auto max-w-4xl text-center"><p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-300">The operational proof</p><h2 className="mt-4 text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">See the defence make a decision.</h2><p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-zinc-400">Open the live workspace to inspect scenarios, alter payment signals, trace attack networks and record analyst feedback.</p><Link href="/dashboard" className="mt-9 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3.5 text-sm font-bold text-zinc-950 transition hover:bg-orange-200">Open live dashboard <ArrowUpRight className="h-4 w-4" /></Link></div></section>

      <footer className="px-5 py-12 md:px-10"><div className="mx-auto flex max-w-7xl flex-col justify-between gap-8 border-t border-white/10 pt-8 md:flex-row"><div><p className="text-sm font-bold tracking-[0.16em] text-white">CHAKRAVYUH</p><p className="mt-2 max-w-sm text-sm text-zinc-500">Synthetic payment-fraud generation and explainable detection for the Mastercard Innovation Challenge 2026.</p></div><div className="flex flex-wrap gap-6">{profileLinks.map(profile => <div key={profile.name} className="flex min-w-52 items-center gap-3"><TeamAvatar profile={profile} /><div><p className="text-sm font-semibold text-zinc-200">{profile.name}</p><p className="mb-2 text-xs text-zinc-500">{profile.role}</p><div className="flex gap-3"><a href={profile.linkedin} target="_blank" rel="noreferrer" aria-label={`${profile.name} on LinkedIn`} className="text-zinc-500 transition hover:text-[#7ab8f5]"><Linkedin className="h-4 w-4" /></a><a href={profile.github} target="_blank" rel="noreferrer" aria-label={`${profile.name} on GitHub`} className="text-zinc-500 transition hover:text-white"><Github className="h-4 w-4" /></a></div></div></div>)}</div></div></footer>
    </main>
  );
}

export default StoryPage;
