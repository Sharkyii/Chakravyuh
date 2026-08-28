"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { motion } from "framer-motion";
import CountUp from "react-countup";
import { ReactFlow, Background, Controls, MarkerType, type Node as FlowNode, type Edge as FlowEdge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { nodeTypes } from "@/components/graph/nodeTypes";
import { layoutWithDagre } from "@/lib/graphLayout";
import { edgeStatusColor } from "@/lib/graphColors";
import {
  Shield,
  Lock,
  Key,
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
  Zap
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

const BOOT_SEQUENCE = [
  "initializing secure session...",
  "verifying TLS 1.3 handshake... OK",
  "loading model artifacts (xgboost v1.8)...",
  "connecting to fraud detection API... OK",
  "checking attestation signature... OK",
  "decrypting analyst workspace...",
  "access granted.",
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

export default function AnalystPortal() {
  // Boot / access sequence -- replaces a login form with a simulated secure
  // boot animation (no credentials to demo). "isLoggedIn" name kept as-is
  // since other effects below key off it.
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [bootLineCount, setBootLineCount] = useState(0);

  useEffect(() => {
    if (isLoggedIn) return;
    if (bootLineCount >= BOOT_SEQUENCE.length) {
      const finish = setTimeout(() => setIsLoggedIn(true), 500);
      return () => clearTimeout(finish);
    }
    const delay = bootLineCount === 0 ? 400 : 260 + Math.random() * 260;
    const t = setTimeout(() => setBootLineCount((c) => c + 1), delay);
    return () => clearTimeout(t);
  }, [bootLineCount, isLoggedIn]);

  const restartBoot = () => {
    setBootLineCount(0);
    setIsLoggedIn(false);
  };

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
    try {
      const res = await fetch(`${API_BASE_URL}/api/analyst/trigger-retrain`, {
        method: "POST"
      });
      if (res.ok) {
        alert("Model successfully retrained!");
        await checkRetrainStatus();
        await fetchModelHistory();
        await fetchMetrics();
      } else {
        alert("Failed to retrain model.");
      }
    } catch (err) {
      console.warn("Failed to trigger retrain:", err);
      alert("Error triggering model retrain.");
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
    if (isLoggedIn) {
      fetchScenarios();
      fetchMetrics();
      checkRetrainStatus();
      fetchModelHistory();
      fetchFamilyMetrics();
    }
  }, [isLoggedIn]);

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

  if (!isLoggedIn) {
    const bootDone = bootLineCount >= BOOT_SEQUENCE.length;
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-6 relative overflow-hidden">
        {/* Abstract Cyber Grid Background */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,95,0,0.1),transparent_70%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f0f15_1px,transparent_1px),linear-gradient(to_bottom,#0f0f15_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

        <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900/80 p-8 shadow-2xl backdrop-blur-xl relative z-10 animate-fade-in">
          <div className="flex flex-col items-center mb-8">
            <div className="relative mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg shadow-orange-600/20">
              {!bootDone && (
                <span className="absolute inset-0 rounded-2xl bg-orange-500 animate-ping opacity-30" />
              )}
              {bootDone ? (
                <CheckCircle className="h-8 w-8 text-white relative" />
              ) : (
                <Lock className="h-8 w-8 text-white relative animate-pulse" />
              )}
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">CHAKRAVYUH</h1>
            <p className="text-sm text-zinc-400 mt-1 text-center">Mastercard Fraud Prevention Analyst Portal</p>
          </div>

          <div className="rounded-xl border border-zinc-800 bg-black/60 p-4 font-mono text-xs text-emerald-400 min-h-[168px]">
            {BOOT_SEQUENCE.slice(0, bootLineCount).map((line, i) => (
              <div key={i} className="flex items-start gap-2 py-0.5">
                <span className="text-zinc-600 shrink-0">[{String(i + 1).padStart(2, "0")}]</span>
                <span className={i === bootLineCount - 1 && line.startsWith("access granted") ? "text-orange-400 font-semibold" : ""}>
                  {"> "}{line}
                </span>
              </div>
            ))}
            {!bootDone && (
              <span className="inline-block w-2 h-3.5 bg-emerald-400 animate-pulse align-middle ml-6" />
            )}
          </div>

          <div className="mt-5 h-1 w-full rounded-full bg-zinc-800 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-amber-500 to-orange-600 transition-all duration-300 ease-out"
              style={{ width: `${Math.min(100, (bootLineCount / BOOT_SEQUENCE.length) * 100)}%` }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-zinc-100 font-sans">
      {/* Top Header */}
      <header className="border-b border-zinc-900 bg-zinc-950 sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#ff5f00] shadow-sm">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-black tracking-wider text-white">CHAKRAVYUH</h1>
            <p className="text-[9px] text-zinc-500 uppercase tracking-widest font-bold">Mastercard GenAI Fraud Defence Lab</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex bg-zinc-950/80 border border-zinc-800 rounded-xl p-1 gap-1">
          <button
            onClick={() => setActiveTab("scoring")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "scoring"
                ? "bg-zinc-800 text-orange-500 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Activity className="h-4 w-4" />
            Risk Scoring Studio
          </button>
          <button
            onClick={() => setActiveTab("closed-loop")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "closed-loop"
                ? "bg-zinc-800 text-orange-500 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Layers className="h-4 w-4" />
            Closed-Loop Intelligence
          </button>
          <button
            onClick={() => setActiveTab("graph")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "graph"
                ? "bg-zinc-800 text-orange-500 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Network className="h-4 w-4" />
            Attack Connection Graph
          </button>
          <button
            onClick={() => setActiveTab("playground")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "playground"
                ? "bg-zinc-800 text-orange-500 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Zap className="h-4 w-4" />
            Attack Simulator Playground
          </button>
        </nav>

        {/* Right side settings/logout */}
        <div className="flex items-center gap-3">
          <button
            onClick={restartBoot}
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-zinc-800 bg-zinc-900 text-red-400 hover:bg-red-950/20 hover:border-red-900/50 transition text-xs font-semibold"
          >
            <LogOut className="h-3.5 w-3.5" />
            Logout
          </button>
        </div>
      </header>

      {/* System Status Sub-header */}
      <div className="bg-zinc-950 border-b border-zinc-900/80 px-6 py-2.5 flex items-center justify-between text-[9px] font-bold font-mono tracking-widest text-zinc-500 uppercase select-none">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> API Gateway: Connected</span>
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Database: Active (24,800 Nodes)</span>
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Model: v1.8 (Active)</span>
        </div>
        <div className="hidden sm:block">
          <span>Active Session: Admin Portal</span>
        </div>
      </div>

      {/* Main Workspace Area */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {/* TAB 1: RISK SCORING STUDIO */}
        {activeTab === "scoring" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            {/* Control Panel (Scenarios & Inputs) - 5 Cols */}
            <section className="lg:col-span-5 flex flex-col gap-6">
              {/* Scenario selector */}
              <div className={`rounded-2xl border bg-zinc-900/40 p-5 backdrop-blur-md transition-all ${
                guideActive && guideStep === "choose_scenario"
                  ? "border-orange-500 ring-2 ring-orange-500/30 shadow-lg shadow-orange-500/10"
                  : "border-zinc-800"
              }`}>
                <div className="flex items-center justify-between mb-3">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Select Simulation Scenario
                  </label>
                  {guideActive && guideStep === "choose_scenario" && (
                    <span className="text-[10px] bg-orange-500/20 text-orange-400 border border-orange-500/40 px-2 py-0.5 rounded-full font-bold animate-pulse">
                      💡 Choose any simulation scenario from dropdown
                    </span>
                  )}
                </div>
                {Object.keys(scenarios).length === 0 ? (
                  <div className="h-11 bg-zinc-950 rounded-xl animate-pulse" />
                ) : (
                  <select
                    value={selectedScenarioName}
                    onChange={(e) => {
                      setSelectedScenarioName(e.target.value);
                      if (guideActive && guideStep === "choose_scenario") {
                        setGuideStep("inspect_parameters");
                      }
                    }}
                    className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-zinc-200 outline-none transition focus:border-orange-500"
                  >
                    {Object.keys(scenarios).map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Transaction Param overrides */}
              <div className={`rounded-2xl border bg-zinc-950/40 p-5 backdrop-blur-md flex-1 flex flex-col gap-6 transition-all ${
                guideActive && guideStep === "inspect_parameters"
                  ? "border-orange-500 ring-2 ring-orange-500/30 shadow-lg shadow-orange-500/10"
                  : "border-zinc-900"
              }`}>
                <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
                  <h3 className="text-xs font-bold text-white uppercase tracking-widest">
                    Override Parameter Signals
                  </h3>
                  {guideActive && guideStep === "inspect_parameters" && (
                    <span className="text-[10px] bg-orange-500/20 text-orange-400 border border-orange-500/40 px-2 py-0.5 rounded-full font-bold animate-pulse">
                      💡 Review parameter signals & click &quot;Run Risk Assessment&quot;
                    </span>
                  )}
                </div>

                {/* Category 1: Financial Profile */}
                <div className="space-y-4">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">
                    Financial Profile
                  </span>
                  
                  <div>
                    <div className="flex justify-between text-xs font-medium mb-1.5">
                      <span className="text-zinc-400">Transaction Amount (INR)</span>
                      <span className="text-zinc-200 font-mono font-bold">₹{parseFloat(txnOverrides.amount || 0).toLocaleString()}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="150000"
                      step="100"
                      value={txnOverrides.amount || 0}
                      onChange={(e) => updateOverrideField("amount", parseFloat(e.target.value))}
                      className="w-full accent-[#ff5f00]"
                    />
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {[500, 15000, 50000, 120000].map(amt => (
                        <button
                          key={amt}
                          type="button"
                          onClick={() => updateOverrideField("amount", amt)}
                          className="px-2 py-0.5 text-[9px] font-semibold rounded bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700 transition"
                        >
                          ₹{amt >= 100000 ? `${amt/100000}L` : amt >= 1000 ? `${amt/1000}k` : amt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Category 2: Behavioral Signals */}
                <div className="space-y-4 border-t border-zinc-900/60 pt-4">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">
                    Behavioral Signals
                  </span>
                  
                  {/* PIN Attempts */}
                  <div>
                    <div className="flex justify-between text-xs font-medium mb-1.5">
                      <span className="text-zinc-400">Failed PIN Attempts</span>
                      <span className="text-zinc-200 font-mono font-bold">{txnOverrides.pin_attempts || 0}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="5"
                      step="1"
                      value={txnOverrides.pin_attempts || 0}
                      onChange={(e) => updateOverrideField("pin_attempts", parseInt(e.target.value))}
                      className="w-full accent-[#ff5f00]"
                    />
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {[0, 1, 3, 5].map(pins => (
                        <button
                          key={pins}
                          type="button"
                          onClick={() => updateOverrideField("pin_attempts", pins)}
                          className="px-2 py-0.5 text-[9px] font-semibold rounded bg-zinc-905 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700 transition"
                        >
                          {pins} {pins === 1 ? "attempt" : "attempts"}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Beneficiary Age */}
                  <div>
                    <div className="flex justify-between text-xs font-medium mb-1.5">
                      <span className="text-zinc-400">Beneficiary Age (Time since addition)</span>
                      <span className="text-zinc-200 font-mono font-bold">
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
                      className="w-full accent-[#ff5f00]"
                    />
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {[0, 1, 7, 30].map(days => (
                        <button
                          key={days}
                          type="button"
                          onClick={() => updateOverrideField("beneficiary_added_ago_s", days * 86400)}
                          className="px-2 py-0.5 text-[9px] font-semibold rounded bg-zinc-905 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700 transition"
                        >
                          {days === 0 ? "New" : `${days}d`}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Category 3: Network Topology */}
                <div className="space-y-4 border-t border-zinc-900/60 pt-4">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">
                    Network Linkages
                  </span>
                  
                  {/* Graph Edge Count */}
                  <div>
                    <div className="flex justify-between text-xs font-medium mb-1.5">
                      <span className="text-zinc-400">Graph Edge Count (Payer-Payee Linkage)</span>
                      <span className="text-zinc-200 font-mono font-bold">{txnOverrides.edge_count || 0}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="50"
                      step="1"
                      value={txnOverrides.edge_count || 0}
                      onChange={(e) => updateOverrideField("edge_count", parseFloat(e.target.value))}
                      className="w-full accent-[#ff5f00]"
                    />
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {[1, 5, 15, 30].map(edges => (
                        <button
                          key={edges}
                          type="button"
                          onClick={() => updateOverrideField("edge_count", edges)}
                          className="px-2 py-0.5 text-[9px] font-semibold rounded bg-zinc-905 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700 transition"
                        >
                          {edges} {edges === 1 ? "edge" : "edges"}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Category 4: Threat Channels */}
                <div className="space-y-3 border-t border-zinc-900/60 pt-4">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">
                    Threat Channels
                  </span>
                  <div className="grid grid-cols-2 gap-4">
                    <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-900 cursor-pointer hover:border-zinc-800 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.screen_share_active}
                        onChange={(e) => updateOverrideField("screen_share_active", e.target.checked)}
                        className="accent-[#ff5f00] h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-medium text-zinc-400">Screen Sharing</span>
                    </label>

                    <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-900 cursor-pointer hover:border-zinc-800 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.call_active_during_txn}
                        onChange={(e) => updateOverrideField("call_active_during_txn", e.target.checked)}
                        className="accent-[#ff5f00] h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-medium text-zinc-400">Active Call</span>
                    </label>

                    <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-900 cursor-pointer hover:border-zinc-800 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.accessibility_service_active}
                        onChange={(e) => updateOverrideField("accessibility_service_active", e.target.checked)}
                        className="accent-[#ff5f00] h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-medium text-zinc-400">Accessibility API</span>
                    </label>

                    <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-900 cursor-pointer hover:border-zinc-800 transition">
                      <input
                        type="checkbox"
                        checked={!!txnOverrides.ip_is_proxy}
                        onChange={(e) => updateOverrideField("ip_is_proxy", e.target.checked)}
                        className="accent-[#ff5f00] h-4 w-4 rounded bg-zinc-950"
                      />
                      <span className="text-xs font-medium text-zinc-400">Proxy/VPN IP</span>
                    </label>
                  </div>
                </div>

                <button
                  onClick={runScoringAssessment}
                  disabled={isScoring}
                  className="w-full flex items-center justify-center gap-2 mt-auto py-3.5 rounded-xl bg-[#ff5f00] font-bold text-white shadow-sm border border-[#ff5f00] hover:bg-[#ff5f00]/90 active:scale-98 transition disabled:opacity-50"
                >
                  {isScoring ? (
                    <>
                      <RefreshCw className="h-5 w-5 animate-spin" />
                      Analyzing Risk Patterns...
                    </>
                  ) : (
                    <>
                      <Play className="h-5 w-5" />
                      Run Risk Assessment
                    </>
                  )}
                </button>

                {scoreError && (
                  <div
                    data-testid="score-error"
                    className="flex items-center gap-2 p-3 text-sm text-red-400 bg-red-950/30 border border-red-900/60 rounded-xl"
                  >
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>{scoreError}</span>
                  </div>
                )}
              </div>
            </section>

            {/* Results Panel - 7 Cols */}
            <section className="lg:col-span-7 flex flex-col gap-6">
              {isScoring ? (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/20 p-8 backdrop-blur-md flex flex-col items-center justify-center text-center flex-1 min-h-[400px] animate-shimmer relative overflow-hidden">
                  <div className="z-10 flex flex-col items-center">
                    <Shield className="h-16 w-16 text-[#ff5f00] mb-4 animate-pulse" />
                    <h3 className="text-lg font-bold text-white tracking-wide">Scoring Transaction...</h3>
                    <p className="text-sm text-zinc-400 mt-2 font-mono">
                      Running ML Risk Evaluator & LLM Analyst Agent
                    </p>
                  </div>
                </div>
              ) : !scoreResult ? (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/20 p-8 backdrop-blur-md flex flex-col items-center justify-center text-center flex-1 min-h-[400px]">
                  <Shield className="h-16 w-16 text-zinc-700 mb-4 animate-pulse" />
                  <h3 className="text-lg font-semibold text-zinc-400">Studio Ingestion Ready</h3>
                  <p className="text-sm text-zinc-500 max-w-sm mt-2">
                    Review and adjust the transaction override parameters on the left and execute the assessment to run live ML decision and GenAI analyst logic.
                  </p>
                </div>
              ) : (
                <div className={`rounded-2xl border bg-zinc-900/40 p-6 backdrop-blur-md flex-1 flex flex-col gap-6 animate-fade-in transition-all ${
                  guideActive && guideStep === "submit_feedback"
                    ? "border-orange-500 ring-2 ring-orange-500/30 shadow-lg shadow-orange-500/10"
                    : "border-zinc-800"
                }`}>
                  {guideActive && guideStep === "submit_feedback" && (
                    <div className="p-3 bg-orange-500/10 border border-orange-500/30 rounded-xl flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">💡</span>
                        <span className="text-xs text-orange-300 font-semibold">
                          Review calculated risk score and SHAP features, then scroll down to log your feedback verdict.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Gauge and Decision header */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center border-b border-zinc-800/80 pb-6">
                    {/* Radial SVG Gauge */}
                    <div className="flex flex-col items-center justify-center">
                      <div className="relative h-28 w-28 flex items-center justify-center">
                        <svg className="absolute inset-0 h-full w-full -rotate-90">
                          <circle
                            cx="56"
                            cy="56"
                            r="48"
                            stroke="#18181b"
                            strokeWidth="10"
                            fill="transparent"
                          />
                          <circle
                            cx="56"
                            cy="56"
                            r="48"
                            stroke={
                              scoreResult.risk_level === "CRITICAL" || scoreResult.risk_level === "HIGH"
                                ? "#EF4444"
                                : scoreResult.risk_level === "MEDIUM"
                                ? "#F97316"
                                : "#10B981"
                            }
                            strokeWidth="10"
                            fill="transparent"
                            strokeDasharray={2 * Math.PI * 48}
                            strokeDashoffset={2 * Math.PI * 48 * (1 - scoreResult.risk_score / 100)}
                            strokeLinecap="round"
                            className="transition-all duration-1000 ease-out"
                          />
                        </svg>
                        <div className="text-center">
                          <span className="text-2xl font-bold text-white font-mono">
                            <CountUp end={scoreResult.risk_score} decimals={0} duration={1} />
                          </span>
                          <span className="text-[10px] text-zinc-500 block font-semibold uppercase tracking-wider">
                            / 100
                          </span>
                        </div>
                      </div>
                      <span className="text-[10px] text-zinc-400 mt-2 font-bold tracking-widest uppercase">Risk Assessment</span>
                    </div>

                    {/* Threat Details */}
                    <div className="flex flex-col gap-2.5 md:border-l md:border-zinc-850 md:pl-6">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Risk Level</span>
                      <div>
                        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider border ${
                          scoreResult.risk_level === "CRITICAL" || scoreResult.risk_level === "HIGH"
                            ? "bg-red-950/40 border-red-500/30 text-red-400"
                            : scoreResult.risk_level === "MEDIUM"
                            ? "bg-orange-950/40 border-orange-500/30 text-orange-400"
                            : "bg-emerald-950/40 border-emerald-500/30 text-emerald-400"
                        }`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${
                            scoreResult.risk_level === "CRITICAL" || scoreResult.risk_level === "HIGH"
                              ? "bg-red-500 animate-pulse"
                              : scoreResult.risk_level === "MEDIUM"
                              ? "bg-orange-500"
                              : "bg-emerald-500"
                          }`} />
                          {scoreResult.risk_level}
                        </div>
                      </div>
                      <span className="text-[10px] text-zinc-500 font-mono">
                        CONFIDENCE: {(scoreResult.model_confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    {/* Decision Action */}
                    <div className="flex flex-col gap-2.5 md:border-l md:border-zinc-850 md:pl-6">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Action Recommendation</span>
                      <div>
                        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider border ${
                          scoreResult.recommended_action === "BLOCK"
                            ? "bg-red-950/20 border-red-900/50 text-red-400"
                            : scoreResult.recommended_action === "REVIEW"
                            ? "bg-orange-950/20 border-orange-900/50 text-orange-400"
                            : "bg-emerald-950/20 border-emerald-900/50 text-emerald-400"
                        }`}>
                          {scoreResult.recommended_action === "BLOCK" ? (
                            <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                          ) : scoreResult.recommended_action === "REVIEW" ? (
                            <AlertTriangle className="h-3 w-3 text-orange-400" />
                          ) : (
                            <CheckCircle className="h-3 w-3 text-emerald-400" />
                          )}
                          {scoreResult.recommended_action}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Predicted Attack Family Card */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                          Top Predicted Attack Vector
                        </span>
                        <h4 className="text-base font-bold text-white capitalize">
                          {scoreResult.top_attack_family
                            ? scoreResult.top_attack_family.replace(/_/g, " ")
                            : "Unavailable"}
                        </h4>
                      </div>
                      <div className="text-right">
                        <span className="text-2xl font-black text-orange-500 font-mono">
                          <CountUp end={scoreResult.top_attack_probability * 100} decimals={1} duration={1} preserveValue />%
                        </span>
                        <span className="text-[9px] text-zinc-500 block uppercase tracking-wider font-bold">Classifier Match</span>
                      </div>
                    </div>
                    {/* Full Attack Family Breakdown -- all 13, not just the top match */}
                    {scoreResult.attack_probabilities && Object.keys(scoreResult.attack_probabilities).length > 1 && (
                      <div className="pt-3 border-t border-zinc-800 space-y-1.5">
                        {Object.entries(scoreResult.attack_probabilities)
                          .sort((a, b) => b[1] - a[1])
                          .map(([family, prob]) => (
                            <div key={family} className="flex items-center gap-2">
                              <span className="w-36 shrink-0 text-[10px] font-mono text-zinc-400 capitalize truncate">
                                {family.replace(/_/g, " ")}
                              </span>
                              <div className="flex-1 h-1.5 rounded-full bg-zinc-900 overflow-hidden">
                                <motion.div
                                  className={`h-full rounded-full ${family === scoreResult.top_attack_family ? "bg-orange-500" : "bg-zinc-600"}`}
                                  initial={{ width: 0 }}
                                  animate={{ width: `${prob * 100}%` }}
                                  transition={{ duration: 0.6, ease: "easeOut" }}
                                />
                              </div>
                              <span className="w-12 shrink-0 text-right text-[10px] font-mono text-zinc-500">
                                {(prob * 100).toFixed(1)}%
                              </span>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>

                  {/* Signals List */}
                  <div>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-2">
                      Model Feature Contributions (SHAP)
                    </span>
                    {(!scoreResult.shap_contributions || scoreResult.shap_contributions.length === 0) ? (
                      <span className="text-sm text-zinc-500 italic block p-3 rounded-xl bg-zinc-950/20 border border-zinc-900">
                        No significant feature contributions. Normal behavior profile.
                      </span>
                    ) : (
                      <div className="space-y-2">
                        {scoreResult.shap_contributions.map((sig, idx) => (
                          <div
                            key={idx}
                            className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-900 group hover:border-zinc-700 transition"
                          >
                            <div className="h-6 w-6 rounded-lg bg-orange-950/30 flex items-center justify-center shrink-0">
                              <Target className="h-3 w-3 text-orange-500" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex justify-between items-center mb-1">
                                <span className="text-xs font-semibold text-zinc-300 truncate font-mono">
                                  {sig.feature}
                                </span>
                                <span className={`text-xs font-bold font-mono ${sig.direction === "increases_risk" ? "text-red-400" : "text-emerald-400"}`}>
                                  {sig.shap_value > 0 ? "+" : ""}{sig.shap_value.toFixed(2)}
                                </span>
                              </div>
                              <div className="w-full bg-zinc-900 rounded-full h-1 overflow-hidden">
                                <div
                                  className={`h-full ${sig.direction === "increases_risk" ? "bg-red-500" : "bg-emerald-500"}`}
                                  style={{ width: `${Math.min(Math.abs(sig.shap_value) * 10, 100)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                        {/* AI Analyst Decision Audit Timeline */}
                  <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5 mt-auto">
                    <div className="flex items-center justify-between mb-4 border-b border-zinc-900 pb-2.5">
                      <div className="flex items-center gap-2">
                        <Cpu className="h-4 w-4 text-[#ff5f00]" />
                        <span className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">
                          Chakravyuh AI Analyst Insight
                        </span>
                      </div>
                    </div>

                    {/* Vertical Timeline */}
                    <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-[1px] before:bg-zinc-800">
                      {/* Step 1: Ingestion */}
                      <div className="relative">
                        <span className="absolute -left-6 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-zinc-950 border border-emerald-500">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        </span>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Step 1: Signal Ingestion</span>
                          <span className="text-[8px] font-mono text-zinc-600 uppercase">Success</span>
                        </div>
                        <p className="text-[11px] text-zinc-400 mt-1">
                          Analyzed transaction on rail <span className="font-mono text-zinc-300 font-bold uppercase">{txnOverrides.rail || "upi_p2p"}</span>. Amount ₹{parseFloat(txnOverrides.amount || 0).toLocaleString()} ingested.
                        </p>
                      </div>

                      {/* Step 2: Scoring Engine */}
                      <div className="relative">
                        <span className="absolute -left-6 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-zinc-950 border border-orange-500">
                          <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                        </span>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Step 2: ML Scoring Engine</span>
                          <span className="text-[8px] font-mono text-orange-500 uppercase font-bold">Passed</span>
                        </div>
                        <p className="text-[11px] text-zinc-400 mt-1">
                          XGBoost model completed evaluation. Base fraud probability scored at <span className="font-mono text-zinc-300 font-bold">{(scoreResult.fraud_probability * 100).toFixed(1)}%</span>. Failed PIN overrides checked.
                        </p>
                      </div>

                      {/* Step 3: GenAI Interpretation */}
                      <div className="relative">
                        <span className="absolute -left-6 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-zinc-950 border border-violet-500">
                          <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-pulse" />
                        </span>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Step 3: GenAI Contextual Narrative</span>
                          <span className="text-[8px] font-mono text-violet-400 uppercase font-bold">Gemini-v1</span>
                        </div>
                        <div className="mt-1.5 bg-zinc-950/60 p-3 rounded-lg border border-zinc-900 space-y-2">
                          <p className="text-xs text-zinc-300 leading-relaxed font-sans">
                            <TypewriterText text={scoreResult.llm_analysis.fraud_explanation} />
                          </p>
                          <p className="text-[11px] text-[#ff5f00] italic font-medium pt-1.5 border-t border-zinc-900/80">
                            <TypewriterText text={scoreResult.llm_analysis.attack_family_interpretation} />
                          </p>
                        </div>
                      </div>

                      {/* Step 4: Analyst checklist */}
                      <div className="relative">
                        <span className="absolute -left-6 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-zinc-950 border border-amber-500">
                          <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                        </span>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Step 4: Remediation Plan</span>
                          <span className="text-[8px] font-mono text-amber-500 uppercase font-bold">Action Required</span>
                        </div>
                        <div className="mt-2 space-y-1.5">
                          {scoreResult.llm_analysis.investigation_steps.map((step, sIdx) => (
                            <div key={sIdx} className="flex items-start gap-2 text-[11px] text-zinc-400">
                              <ChevronRight className="h-3.5 w-3.5 text-[#ff5f00] shrink-0 mt-0.5" />
                              <span>{step}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Caveats info block */}
                    <div className="text-[10px] text-zinc-500 flex gap-1.5 items-start bg-zinc-950/40 p-2.5 rounded-lg border border-zinc-900 mt-4">
                      <Info className="h-3.5 w-3.5 text-zinc-500 shrink-0 mt-0.5" />
                      <span>{scoreResult.llm_analysis.uncertainty_caveats}</span>
                    </div>
                  </div>

                  {/* Closed-Loop Analyst Feedback Loop */}
                  <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 border-t-2 border-t-orange-600/50">
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                      Closed-Loop Analyst Feedback Loop
                    </span>
                    <p className="text-xs text-zinc-400 mb-3">
                      Submit the actual outcome of this transaction. Feedbacks are recorded in a local SQLite datastore. When 5 total verdicts are met, the option to retrain the live XGBoost model will become available.
                    </p>
                    {feedbackSuccess ? (
                      <div className="flex items-center gap-3 p-3 rounded-xl bg-emerald-950/20 border border-emerald-900/50 text-sm text-emerald-400">
                        <CheckCircle className="h-5 w-5 shrink-0" />
                        <div>
                          <p className="font-bold">Feedback Incorporated!</p>
                          <p className="text-[11px] text-emerald-500 mt-0.5">Real-time outcome saved. Go to the Closed-Loop tab to view live model retraining and evolution history.</p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-3">
                        <button
                          disabled={submittingFeedback}
                          onClick={() => submitFeedbackOutcome("legitimate")}
                          className="flex-1 py-2 rounded-lg border border-emerald-800/40 bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/40 font-semibold text-xs transition disabled:opacity-50"
                        >
                          Confirm Clean / Approve
                        </button>
                        <button
                          disabled={submittingFeedback}
                          onClick={() => submitFeedbackOutcome("fraud")}
                          className="flex-1 py-2 rounded-lg border border-red-800/40 bg-red-950/20 text-red-400 hover:bg-red-950/40 font-semibold text-xs transition disabled:opacity-50"
                        >
                          Report Fraud / Block
                        </button>
                      </div>
                    )}

                    {shouldRetrain && (
                      <div className="mt-4 p-3 rounded-lg bg-orange-500/20 border border-orange-500/30">
                        <p className="text-orange-300 font-semibold text-xs mb-2">✓ Ready to Retrain</p>
                        <button
                          onClick={handleTriggerRetrain}
                          disabled={retraining}
                          className="w-full py-2 rounded-lg bg-orange-600 hover:bg-orange-500 disabled:bg-zinc-700 text-white font-bold flex items-center justify-center gap-2 transition text-xs"
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
                      </div>
                    )}
                  </div>

                  {/* Step 4: 3-Way Guided Exploration Paths */}
                  {(feedbackSuccess || guideStep === "choose_destination") && (
                    <div className="rounded-xl border border-orange-500/40 bg-zinc-950/80 p-4 ring-2 ring-orange-500/20 shadow-lg shadow-orange-500/10 animate-fade-in space-y-3">
                      <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">🎯</span>
                          <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                            Explore Chakravyuh Defense Modules
                          </h4>
                        </div>
                        <span className="text-[10px] bg-orange-500/20 text-orange-400 border border-orange-500/40 px-2 py-0.5 rounded-full font-bold">
                          Next Destination
                        </span>
                      </div>

                      <p className="text-xs text-zinc-400">
                        Select any of the 3 modules below to continue the guided exploration of the platform:
                      </p>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                        {/* Destination 1: Closed-Loop */}
                        <button
                          onClick={() => {
                            setActiveTab("closed-loop");
                            if (guideActive) setGuideStep("closed_loop");
                          }}
                          className="flex flex-col text-left p-3 rounded-lg border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 hover:border-orange-500/50 transition group"
                        >
                          <div className="flex items-center justify-between text-zinc-400 group-hover:text-orange-400 mb-1.5">
                            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">Module 1</span>
                            <Layers className="h-4 w-4" />
                          </div>
                          <span className="text-xs font-bold text-zinc-200 group-hover:text-white block mb-1">
                            Closed-Loop Intelligence
                          </span>
                          <span className="text-[10px] text-zinc-400 leading-relaxed">
                            Compare Gen A vs Gen B drift metrics, audit SQLite feedback logs, and trigger curriculum model retraining.
                          </span>
                          <span className="text-[10px] text-orange-400 font-bold mt-2 inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                            Open Closed-Loop ➔
                          </span>
                        </button>

                        {/* Destination 2: Threat Graph */}
                        <button
                          onClick={() => {
                            setActiveTab("graph");
                            if (guideActive) setGuideStep("graph");
                          }}
                          className="flex flex-col text-left p-3 rounded-lg border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 hover:border-orange-500/50 transition group"
                        >
                          <div className="flex items-center justify-between text-zinc-400 group-hover:text-orange-400 mb-1.5">
                            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">Module 2</span>
                            <Network className="h-4 w-4" />
                          </div>
                          <span className="text-xs font-bold text-zinc-200 group-hover:text-white block mb-1">
                            Attack Connection Graph
                          </span>
                          <span className="text-[10px] text-zinc-400 leading-relaxed">
                            Visualize interactive subgraphs, detect active remote screen hijackers, and unmask multi-hop mule routes.
                          </span>
                          <span className="text-[10px] text-orange-400 font-bold mt-2 inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                            Open Threat Graph ➔
                          </span>
                        </button>

                        {/* Destination 3: Attack Playground */}
                        <button
                          onClick={() => {
                            setActiveTab("playground");
                            if (guideActive) setGuideStep("playground");
                          }}
                          className="flex flex-col text-left p-3 rounded-lg border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 hover:border-orange-500/50 transition group"
                        >
                          <div className="flex items-center justify-between text-zinc-400 group-hover:text-orange-400 mb-1.5">
                            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">Module 3</span>
                            <Zap className="h-4 w-4" />
                          </div>
                          <span className="text-xs font-bold text-zinc-200 group-hover:text-white block mb-1">
                            Simulator Playground
                          </span>
                          <span className="text-[10px] text-zinc-400 leading-relaxed">
                            Inject synthetic fraud campaigns across 58 frozen vectors to stress-test real-time hop-by-hop detection.
                          </span>
                          <span className="text-[10px] text-orange-400 font-bold mt-2 inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                            Open Simulator ➔
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
              <div className="rounded-2xl border border-orange-500/40 bg-zinc-950/80 p-5 ring-2 ring-orange-500/20 shadow-lg shadow-orange-500/10 animate-fade-in flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="h-9 w-9 rounded-xl bg-orange-600/10 border border-orange-500/30 flex items-center justify-center text-orange-400 shrink-0 mt-0.5">
                    <Layers className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                        Closed-Loop Intelligence Walkthrough
                      </h3>
                      <span className="text-[9px] bg-orange-500/20 text-orange-400 border border-orange-500/40 px-2 py-0.5 rounded-full font-bold">
                        Active Guide
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed max-w-3xl">
                      <strong className="text-zinc-200">1. Comparative Metrics & Drift:</strong> Compare Gen A (Baseline) vs Gen B (Retrained) below to observe PR-AUC gains and false-positive elimination.
                      <br />
                      <strong className="text-zinc-200">2. Automated Retraining:</strong> Every 5 human verdicts logged in the studio accumulate in SQLite and trigger automated curriculum retraining to patch evasion blindspots.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => {
                      setActiveTab("graph");
                      if (guideActive) setGuideStep("graph");
                    }}
                    className="px-3.5 py-1.5 bg-orange-600 hover:bg-orange-500 text-white font-bold text-xs rounded-lg transition flex items-center gap-1"
                  >
                    Next: Threat Graph ➔
                  </button>
                </div>
              </div>
            )}

            {/* Concept explainer */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
              <h2 className="text-lg font-bold text-white mb-2">What is the Closed-Loop Cycle?</h2>
              <p className="text-sm text-zinc-400 leading-relaxed">
                The Chakravyuh Closed Loop describes our adaptive, adversarial security cycle. 
                Instead of static, hand-written rules that attackers quickly study and bypass, the loop works dynamically:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6 border-t border-zinc-800 pt-6">
                <div className="flex gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-600/10 border border-orange-500/20 text-orange-500">
                    <span className="font-bold text-sm">1</span>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white mb-1">Observe Leaks</h4>
                    <p className="text-xs text-zinc-500 leading-relaxed">
                      The ML detector&apos;s features are audited. Features that form &quot;tells&quot; (like fixed ASN blocks or shallow-copy lookalikes) are identified.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-600/10 border border-orange-500/20 text-orange-500">
                    <span className="font-bold text-sm">2</span>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white mb-1">Adapt Attack Spec</h4>
                    <p className="text-xs text-zinc-500 leading-relaxed">
                      The scenario generator receives model feature importances, dynamically shifting parameters (e.g. routing and limits) to avoid detection thresholds.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-600/10 border border-orange-500/20 text-orange-500">
                    <span className="font-bold text-sm">3</span>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white mb-1">Retrain and Defend</h4>
                    <p className="text-xs text-zinc-500 leading-relaxed">
                      The detector retrains on these newly optimized, adaptive evasion campaigns. This raises the detection floor, forcing the attacker&apos;s cost up.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Model Provenance Strip -- the frozen as-trained ground truth,
                distinct from the feedback-adjusted cards below */}
            {metricsData?.model_provenance && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 px-5 py-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] font-mono">
                <div className="flex items-center gap-1.5">
                  <Cpu className="h-3.5 w-3.5 text-orange-500 shrink-0" />
                  <span className="text-zinc-300 font-bold">
                    {metricsData.model_provenance.model_version || "unknown model"}
                  </span>
                </div>
                {metricsData.model_provenance.trained_timestamp && (
                  <span className="text-zinc-500">
                    trained{" "}
                    <span className="text-zinc-300">
                      {new Date(metricsData.model_provenance.trained_timestamp).toLocaleString()}
                    </span>
                  </span>
                )}
                {metricsData.model_provenance.held_out_attack_family && (
                  <span className="text-zinc-500">
                    held-out family{" "}
                    <span className="text-zinc-300 capitalize">
                      {metricsData.model_provenance.held_out_attack_family.replace(/_/g, " ")}
                    </span>
                  </span>
                )}
                {metricsData.model_provenance.test_pr_auc != null && (
                  <span className="text-zinc-500">
                    as-trained test PR-AUC{" "}
                    <span className="text-emerald-400 font-bold">
                      {(metricsData.model_provenance.test_pr_auc * 100).toFixed(2)}%
                    </span>
                  </span>
                )}
                <span className="text-zinc-600 italic sm:ml-auto">
                  Cards below start from this baseline and drift with simulated analyst feedback.
                </span>
              </div>
            )}

            {/* Gen A vs Gen B Comparison — Attack Generation Evolution */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
              <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                <Zap className="h-4 w-4 text-orange-500" />
                Attack Generation Evolution: Gen A → Gen B
              </h3>
              <p className="text-xs text-zinc-500 mb-5">
                Original vs. adaptive attack variants after closed-loop feature audit.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Gen A: Original */}
                <div className="rounded-xl border border-zinc-700/50 bg-zinc-950/40 p-4">
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Gen A: Original (Static)</span>
                  <div className="mt-3 space-y-2 text-xs text-zinc-400">
                    <div className="flex justify-between items-center">
                      <span>Attack Family</span>
                      <span className="font-mono font-bold text-zinc-200">adversarial_evasion</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>PR-AUC (test)</span>
                      <span className="font-mono font-bold text-emerald-400">99.72%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>Recall @ 0.1% FPR</span>
                      <span className="font-mono font-bold text-emerald-400">99.42%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>Detection Gap</span>
                      <span className="font-mono font-bold text-red-400">0.58%</span>
                    </div>
                    <div className="border-t border-zinc-700/30 my-2 pt-2">
                      <span className="text-[10px] text-zinc-500">Default route pool, normal beneficiary age</span>
                    </div>
                  </div>
                </div>

                {/* Gen B: Adaptive */}
                <div className="rounded-xl border border-orange-500/30 bg-orange-950/10 p-4">
                  <span className="text-[10px] font-bold text-orange-400 uppercase tracking-widest">Gen B: Adaptive (Evolved)</span>
                  <div className="mt-3 space-y-2 text-xs text-zinc-400">
                    <div className="flex justify-between items-center">
                      <span>Attack Family</span>
                      <span className="font-mono font-bold text-zinc-200">adversarial_evasion</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>PR-AUC (test)</span>
                      <span className="font-mono font-bold text-emerald-300">99.97%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>Recall @ 0.1% FPR</span>
                      <span className="font-mono font-bold text-emerald-300">100.00%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>Improvement</span>
                      <span className="font-mono font-bold text-orange-300">+0.58%</span>
                    </div>
                    <div className="border-t border-orange-500/20 my-2 pt-2">
                      <span className="text-[10px] text-orange-400">Single top counterparty + age floor</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-4 p-3 rounded-lg bg-zinc-950/60 border border-zinc-700/30">
                <p className="text-[11px] text-zinc-500">
                  <span className="text-zinc-300 font-semibold">Measurement (Real):</span> Retraining on Gen B&rsquo;s adaptive attacks
                  achieved <span className="text-emerald-300 font-bold">perfect recall (100.00% @ 0.1% FPR)</span> on the
                  previously weak <span className="text-orange-400">adversarial_evasion</span> family.
                  The closed-loop mechanism works end-to-end without manual steps (read <span className="font-mono text-[10px]">docs/closed-loop.md</span>).
                </p>
              </div>
            </div>

            {/* Model History Comparison */}
            {modelHistory.length > 0 && (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
                <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-blue-500" />
                  Model Evolution History (Real Metrics comparison)
                </h3>
                <p className="text-xs text-zinc-500 mb-5">
                  Actual evaluated performance comparing the initial baseline model to the retrained models.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {modelHistory.map((meta: any, idx: number) => (
                    <div key={idx} className="rounded-xl border border-zinc-700/50 bg-zinc-950/40 p-4">
                      <span className="text-[10px] font-bold text-blue-400 uppercase tracking-widest">{meta.label}</span>
                      <div className="mt-3 space-y-2 text-xs text-zinc-400">
                        <div className="flex justify-between items-center">
                          <span>Model Version</span>
                          <span className="font-mono font-bold text-zinc-200">{meta.version}</span>
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
                          <span>PR-AUC (test)</span>
                          <span className="font-mono font-bold text-emerald-400">{(meta.pr_auc * 100).toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span>Precision</span>
                          <span className="font-mono font-bold text-emerald-400">{(meta.precision * 100).toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span>Recall</span>
                          <span className="font-mono font-bold text-emerald-400">{(meta.recall * 100).toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span>Evasion Rate</span>
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
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Target className="h-4 w-4 text-orange-500" />
                    Adversarial Campaign Recall (Per-Family Breakdown)
                  </h3>
                  <button
                    onClick={() => setShowFamilyBreakdown(!showFamilyBreakdown)}
                    className="px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-[10px] font-bold text-zinc-300 transition"
                  >
                    {showFamilyBreakdown ? "Hide Detailed Metrics" : "Show Detailed Metrics"}
                  </button>
                </div>
                <p className="text-xs text-zinc-500 mb-5">
                  Detailed evaluation of the active model against each individual synthetic fraud family across key operating points.
                </p>

                {showFamilyBreakdown && (
                  <div className="overflow-x-auto border border-zinc-800 rounded-xl bg-zinc-950/40">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-zinc-800 bg-zinc-950/80 text-zinc-400 font-bold uppercase tracking-wider text-[10px]">
                          <th className="px-4 py-3">Attack Family</th>
                          <th className="px-4 py-3 text-right">Samples (N)</th>
                          <th className="px-4 py-3 text-right">Mean Prob.</th>
                          <th className="px-4 py-3 text-right">Recall @ 0.1% FPR</th>
                          <th className="px-4 py-3 text-right">Recall @ 1.0% FPR</th>
                          <th className="px-4 py-3 text-right">Recall @ Selected Thresh</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-900">
                        {familyMetrics.by_family.map((f: any, idx: number) => {
                          if (f.family === "__legit__") return null;
                          return (
                            <tr key={idx} className="hover:bg-zinc-900/30 transition text-zinc-300">
                              <td className="px-4 py-3 font-semibold text-zinc-200 capitalize">
                                {f.family.replace(/_/g, " ")}
                              </td>
                              <td className="px-4 py-3 text-right font-mono text-zinc-400">{f.n}</td>
                              <td className="px-4 py-3 text-right font-mono text-zinc-400">{(f.mean_prob * 100).toFixed(1)}%</td>
                              <td className="px-4 py-3 text-right font-mono font-semibold text-emerald-400">
                                {f.recall_01pct !== null ? `${(f.recall_01pct * 100).toFixed(1)}%` : "N/A"}
                              </td>
                              <td className="px-4 py-3 text-right font-mono font-semibold text-emerald-400">
                                {f.recall_1pct !== null ? `${(f.recall_1pct * 100).toFixed(1)}%` : "N/A"}
                              </td>
                              <td className="px-4 py-3 text-right font-mono font-semibold text-orange-400">
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
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {metricsData?.recorded_metrics.map((item, idx) => (
                <div key={idx} className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 backdrop-blur-md flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                      {item.metric}
                    </span>
                    <span className="text-3xl font-black text-white font-mono">
                      <CountUp end={item.value * 100} decimals={2} duration={1.5} preserveValue />%
                    </span>
                  </div>
                  {/* Miniature Circle Progress */}
                  <div className="h-12 w-12 relative flex items-center justify-center">
                    <svg className="absolute inset-0 h-full w-full -rotate-90">
                      <circle cx="24" cy="24" r="20" stroke="#18181b" strokeWidth="4" fill="transparent" />
                      <circle
                        cx="24"
                        cy="24"
                        r="20"
                        stroke="#F97316"
                        strokeWidth="4"
                        fill="transparent"
                        strokeDasharray={2 * Math.PI * 20}
                        strokeDashoffset={2 * Math.PI * 20 * (1 - item.value)}
                        strokeLinecap="round"
                      />
                    </svg>
                    <TrendingUp className="h-4 w-4 text-orange-500" />
                  </div>
                </div>
              ))}
              {/* Alert volume card — shows real-world feasibility: ~5 alerts per 1k means analyst can handle it */}
              {metricsData?.model_provenance?.alerts_per_1000 != null && (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 backdrop-blur-md flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                      Alerts per 1,000 txns
                    </span>
                    <span className="text-3xl font-black text-white font-mono">
                      ~{metricsData.model_provenance.alerts_per_1000.toFixed(1)}
                    </span>
                    <span className="text-[9px] text-zinc-500 mt-1 block">at F1-optimal threshold</span>
                  </div>
                  <Activity className="h-8 w-8 text-orange-500" />
                </div>
              )}
            </div>

            {/* Feature Importance Panel */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Feature Importance Bar chart - 7 Cols */}
              <div className="md:col-span-8 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-6">
                  Live Model Feature Importances (Top 10)
                </h3>

                {isLoadingMetrics ? (
                  <div className="h-64 bg-zinc-950/40 rounded-xl animate-pulse" />
                ) : !metricsData || metricsData.feature_importances.length === 0 ? (
                  <div className="h-64 flex items-center justify-center border border-zinc-800 border-dashed rounded-xl">
                    <span className="text-sm text-zinc-500">Train model to visualize feature importances</span>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {metricsData.feature_importances.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-4">
                        <span className="text-xs text-zinc-400 font-mono w-44 truncate text-right">
                          {item.feature}
                        </span>
                        <div className="flex-1 h-5 bg-zinc-950 rounded-md overflow-hidden relative border border-zinc-900">
                          <div
                            style={{ width: `${item.importance * 100}%` }}
                            className="h-full bg-gradient-to-r from-orange-500 to-amber-500 rounded-r-md transition-all duration-1000"
                          />
                        </div>
                        <span className="text-xs text-zinc-300 font-mono font-bold w-12">
                          {(item.importance * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Targets & Configuration - 5 Cols */}
              <div className="md:col-span-4 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md flex flex-col gap-4">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-2">
                  Next Campaign Target Parameters
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed mb-4">
                  Derived dynamically from the importance values on the left. The next training data generator run will automatically inject these targets to evade model thresholds:
                </p>

                {metricsData && metricsData.adaptive_config && Object.keys(metricsData.adaptive_config).length > 0 ? (
                  <div className="space-y-4 flex-1">
                    {Object.entries(metricsData.adaptive_config).map(([key, val]) => (
                      <div key={key} className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800">
                        <span className="text-[10px] font-bold text-orange-500 uppercase tracking-widest block mb-1">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="text-sm font-bold text-white font-mono">
                          {typeof val === "boolean" ? val.toString().toUpperCase() : val}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-6 border border-dashed border-zinc-800 rounded-xl text-center">
                    <RefreshCw className="h-8 w-8 text-zinc-700 mb-2 animate-spin" />
                    <span className="text-xs text-zinc-500">
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
              <div className="lg:col-span-12 rounded-2xl border border-orange-500/40 bg-zinc-950/80 p-5 ring-2 ring-orange-500/20 shadow-lg shadow-orange-500/10 animate-fade-in flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="h-9 w-9 rounded-xl bg-orange-600/10 border border-orange-500/30 flex items-center justify-center text-orange-400 shrink-0 mt-0.5">
                    <Network className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                        Threat Topology & Graph Analysis Walkthrough
                      </h3>
                      <span className="text-[9px] bg-orange-500/20 text-orange-400 border border-orange-500/40 px-2 py-0.5 rounded-full font-bold">
                        Active Guide
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed max-w-3xl">
                      <strong className="text-zinc-200">1. Subgraph Topology:</strong> Displays payer, payee, and attacker remote channel nodes (e.g. active voice calls, screen sharing tools).
                      <br />
                      <strong className="text-zinc-200">2. Mule Linkages & Lifecycle:</strong> Toggle between single-transaction view and the 4-phase lifecycle map to reveal multi-hop mule forwarding networks.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => {
                      setActiveTab("playground");
                      if (guideActive) setGuideStep("playground");
                    }}
                    className="px-3.5 py-1.5 bg-orange-600 hover:bg-orange-500 text-white font-bold text-xs rounded-lg transition flex items-center gap-1"
                  >
                    Next: Simulator Playground ➔
                  </button>
                </div>
              </div>
            )}

            {/* The SVG Network Canvas - 8 Cols */}
            <div className="lg:col-span-8 rounded-2xl border border-zinc-900 bg-zinc-950/40 p-6 backdrop-blur-md flex flex-col relative min-h-[520px]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider">Network Connection Graph</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Toggle between the generic lifecycle map and live transaction linkages.
                  </p>
                </div>
                
                {/* View Mode Toggle & Clear */}
                <div className="flex items-center gap-3">
                  {graphViewMode === "transaction" && scoreResult?.network_graph && (
                    <button
                      onClick={clearGraphHistory}
                      className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-red-400 border border-red-900/30 bg-red-950/10 rounded-lg hover:bg-red-950/20 transition"
                    >
                      Clear History
                    </button>
                  )}
                  <div className="flex bg-zinc-950 border border-zinc-900 rounded-lg p-1 gap-1">
                    <button
                      onClick={() => setGraphViewMode("lifecycle")}
                      className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded transition-all ${
                        graphViewMode === "lifecycle"
                          ? "bg-zinc-800 text-white"
                          : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      Lifecycle Map
                    </button>
                    <button
                      onClick={() => setGraphViewMode("transaction")}
                      className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded transition-all ${
                        graphViewMode === "transaction"
                          ? "bg-zinc-800 text-white"
                          : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      Transaction Linkage
                    </button>
                  </div>
                </div>
              </div>

              {/* SVG Grid */}
              <div className="flex-1 relative border border-zinc-900 bg-zinc-950 rounded-xl overflow-hidden min-h-[440px]">
                {/* Visual grid overlay */}
                <div className="absolute inset-0 bg-[linear-gradient(to_right,#16161a_1px,transparent_1px),linear-gradient(to_bottom,#16161a_1px,transparent_1px)] bg-[size:2rem_2rem] pointer-events-none" />

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
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#3f3f46" />
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
                            stroke={isHighlighted ? "#f97316" : "#18181b"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.8 : 0.4}
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
                            stroke={isHighlighted ? "#f97316" : "#18181b"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.8 : 0.4}
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
                            stroke={isHighlighted ? "#f97316" : "#18181b"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.8 : 0.4}
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
                            stroke={isHighlighted ? "#f97316" : "#18181b"}
                            strokeWidth={isHighlighted ? "1.5" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.8 : 0.4}
                            className="transition-all duration-300"
                          />
                        );
                      })
                    )}

                    {/* Draw Nodes */}
                    {ATTACK_NODES.map(node => {
                      const isSelected = selectedNode && selectedNode.id === node.id;
                      return (
                        <g
                          key={node.id}
                          onClick={() => setSelectedNode(node)}
                          className="cursor-pointer group"
                        >
                          <circle
                            cx={`${node.x}%`}
                            cy={`${node.y}%`}
                            r={isSelected ? "13" : "10"}
                            fill="#09090b"
                            stroke={isSelected ? "#ff5f00" : "#27272a"}
                            strokeWidth={isSelected ? "3" : "1.5"}
                            className="transition-all duration-300 group-hover:stroke-orange-500"
                          />
                          <circle
                            cx={`${node.x}%`}
                            cy={`${node.y}%`}
                            r="3"
                            fill={isSelected ? "#ff5f00" : "#52525b"}
                          />
                          <text
                            x={`${node.x}%`}
                            y={`${node.y + 6}%`}
                            textAnchor="middle"
                            fill={isSelected ? "#ffffff" : "#a1a1aa"}
                            fontSize="9"
                            fontWeight={isSelected ? "bold" : "normal"}
                            className="transition-colors duration-300 select-none group-hover:fill-white"
                          >
                            {node.name}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                ) : (
                  // Dynamic Transaction Graph
                  <div className="w-full h-full min-h-[440px] relative animate-fade-in flex flex-col">
                    {!scoreResult?.network_graph || scoreResult.network_graph.nodes.length === 0 ? (
                      <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
                        <Network className="h-12 w-12 text-zinc-800 mb-3" />
                        <span className="text-sm font-semibold text-zinc-400">No Transaction Network Loaded</span>
                        <p className="text-xs text-zinc-600 max-w-sm mt-1">
                          Go to the Risk Scoring Studio, choose a simulation scenario, click &quot;Run Risk Assessment&quot;, and return to visualize its dynamic counterparty connections.
                        </p>
                      </div>
                    ) : (
                      <>
                        {/* Campaign Alert Banner inside Canvas */}
                        {scoreResult.campaign_alerts && scoreResult.campaign_alerts.length > 0 && (
                          <div className="z-10 bg-emerald-950/20 border-b border-emerald-900/30 px-4 py-3 space-y-1.5 max-h-24 overflow-y-auto animate-fade-in">
                            {scoreResult.campaign_alerts.map((alert, aIdx) => (
                              <div key={aIdx} className="flex items-start gap-2 text-[10px] font-bold text-emerald-400">
                                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-emerald-500 mt-0.5" />
                                <span>{alert}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        <div className="flex-1 relative">
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
                            <Background color="#16161a" gap={32} />
                            <Controls />
                          </ReactFlow>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* Grid Phase Labels */}
                {graphViewMode === "lifecycle" && (
                  <div className="absolute top-3 left-0 w-full grid grid-cols-5 text-center text-[9px] font-bold text-zinc-500 uppercase tracking-widest pointer-events-none border-b border-zinc-900 pb-2">
                    <span>1. Infiltration</span>
                    <span>2. Probing</span>
                    <span>3. Execution</span>
                    <span>4. Evasion</span>
                    <span>5. Exfiltration</span>
                  </div>
                )}
              </div>
            </div>

            {/* Sidebar Details Panel - 4 Cols */}
            <div className="lg:col-span-4 flex flex-col gap-6">
              {graphViewMode === "lifecycle" ? (
                // Lifecycle Details (Original)
                !selectedNode ? (
                  <div className="rounded-2xl border border-zinc-900 bg-zinc-950/40 p-6 backdrop-blur-md flex flex-col items-center justify-center text-center flex-1">
                    <Network className="h-10 w-10 text-zinc-700 mb-2" />
                    <span className="text-xs text-zinc-500">Select a vector node on the map to review threat logs</span>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-zinc-900 bg-zinc-950/40 p-6 backdrop-blur-md flex-1 flex flex-col gap-5 animate-fade-in">
                    <div className="flex items-start justify-between border-b border-zinc-900 pb-3">
                      <div>
                        <span className="inline-block text-[9px] font-black bg-orange-600/10 border border-orange-500/20 text-orange-500 px-2 py-0.5 rounded uppercase tracking-wider mb-1">
                          Generator {selectedNode.id}
                        </span>
                        <h3 className="text-sm font-extrabold text-white">{selectedNode.name}</h3>
                      </div>
                      <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">
                        {selectedNode.phase} Phase
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">Description</span>
                      <p className="text-xs text-zinc-300 leading-relaxed">
                        {selectedNode.description}
                      </p>
                    </div>

                    <div>
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1.5">Target Rails</span>
                      <span className="inline-block text-xs font-semibold px-3 py-1 rounded-lg bg-zinc-950 border border-zinc-900 text-zinc-300">
                        {selectedNode.rail}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">Observable Signature</span>
                      <p className="text-xs text-zinc-400 font-mono bg-zinc-950/40 p-2.5 rounded-lg border border-zinc-900">
                        {selectedNode.signature}
                      </p>
                    </div>

                    {/* Ratings */}
                    <div className="grid grid-cols-2 gap-4 mt-auto border-t border-zinc-900 pt-4">
                      <div>
                        <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                          Novelty Rating
                        </span>
                        <div className="flex gap-1">
                          {[1, 2, 3, 4, 5].map(star => (
                            <div
                              key={star}
                              className={`h-2 flex-1 rounded-sm ${
                                star <= selectedNode.novelty ? "bg-orange-500" : "bg-zinc-800"
                              }`}
                            />
                          ))}
                        </div>
                      </div>

                      <div>
                        <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                          Detection Difficulty
                        </span>
                        <div className="flex gap-1">
                          {[1, 2, 3, 4, 5].map(star => (
                            <div
                              key={star}
                              className={`h-2 flex-1 rounded-sm ${
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
                  <div className="rounded-2xl border border-zinc-900 bg-zinc-950/40 p-6 backdrop-blur-md flex flex-col items-center justify-center text-center flex-1">
                    <Network className="h-10 w-10 text-zinc-700 mb-2" />
                    <span className="text-xs text-zinc-500">Select a node in the network to inspect its linkage metadata</span>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-zinc-900 bg-zinc-950/40 p-6 backdrop-blur-md flex-1 flex flex-col gap-5 animate-fade-in">
                    <div className="flex items-start justify-between border-b border-zinc-900 pb-3">
                      <div>
                        <span className={`inline-block text-[9px] font-black px-2 py-0.5 rounded uppercase tracking-wider mb-1 ${
                          selectedTransactionNode.risk === "critical" || selectedTransactionNode.risk === "high"
                            ? "bg-red-500/10 border border-red-500/30 text-red-400"
                            : selectedTransactionNode.risk === "medium" || selectedTransactionNode.risk === "warning"
                            ? "bg-orange-500/10 border border-orange-500/30 text-orange-400"
                            : "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400"
                        }`}>
                          Risk: {selectedTransactionNode.risk.toUpperCase()}
                        </span>
                        <h3 className="text-sm font-extrabold text-white">{selectedTransactionNode.label}</h3>
                      </div>
                      <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider">
                        {selectedTransactionNode.type.replace(/_/g, " ")} Node
                      </span>
                    </div>

                    <div className="space-y-4">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-2">Node Parameters</span>
                      <div className="space-y-2">
                        {Object.entries(selectedTransactionNode.details).map(([key, val]: [string, any]) => (
                          <div key={key} className="flex justify-between border-b border-zinc-900/60 pb-1.5 text-xs">
                            <span className="text-zinc-500 font-medium">{key}</span>
                            <span className="text-zinc-300 font-mono font-bold">{val}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              )}

              {/* Session Transaction Timeline -- every run accumulated in
                  this session's graph, reused here for free */}
              {graphViewMode === "transaction" && scoreResult?.network_graph && scoreResult.network_graph.nodes.length > 0 && (
                <div className="rounded-2xl border border-zinc-900 bg-zinc-950/40 p-4 backdrop-blur-md">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-3">
                    Session Transaction Timeline
                  </span>
                  <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                    {scoreResult.network_graph.nodes
                      .filter((n) => n.type === "payee")
                      .map((n) => {
                        const isActive = selectedTransactionNode?.id === n.id;
                        return (
                          <button
                            key={n.id}
                            onClick={() => setSelectedTransactionNode(n)}
                            className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg border text-left transition ${
                              isActive
                                ? "border-orange-500/40 bg-orange-950/20"
                                : "border-zinc-900 bg-zinc-950/40 hover:border-zinc-800"
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span
                                className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                                  n.risk === "critical" || n.risk === "high"
                                    ? "bg-red-500"
                                    : n.risk === "medium" || n.risk === "warning"
                                    ? "bg-orange-500"
                                    : "bg-emerald-500"
                                }`}
                              />
                              <span className="text-xs font-mono text-zinc-300 truncate">
                                {n.details["Transaction ID"]}
                              </span>
                            </div>
                            <span className="text-[10px] font-mono text-zinc-500 shrink-0">
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
              <div className="lg:col-span-3 rounded-2xl border border-orange-500/40 bg-zinc-950/80 p-5 ring-2 ring-orange-500/20 shadow-lg shadow-orange-500/10 animate-fade-in flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="h-9 w-9 rounded-xl bg-orange-600/10 border border-orange-500/30 flex items-center justify-center text-orange-400 shrink-0 mt-0.5">
                    <Zap className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                        Attack Simulator Playground Walkthrough
                      </h3>
                      <span className="text-[9px] bg-orange-500/20 text-orange-400 border border-orange-500/40 px-2 py-0.5 rounded-full font-bold">
                        Active Guide
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed max-w-3xl">
                      <strong className="text-zinc-200">1. Attack Family Catalog:</strong> Choose from 13 generator families (e.g., Scam-induced Push, Mule Network, Credential Takeover) and set attack intensity.
                      <br />
                      <strong className="text-zinc-200">2. Live Campaign Flood:</strong> Injects synthetic transactions into the scoring pipeline one by one to stress-test real-time detection and graph hop propagation.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => {
                      setActiveTab("scoring");
                      if (guideActive) setGuideStep("choose_scenario");
                    }}
                    className="px-3.5 py-1.5 bg-orange-600 hover:bg-orange-500 text-white font-bold text-xs rounded-lg transition flex items-center gap-1"
                  >
                    Restart Tour (Scoring Studio) ➔
                  </button>
                </div>
              </div>
            )}

            {/* Left Sidebar: Controls */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md space-y-6">
              <div>
                <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                  <Settings className="h-4 w-4 text-orange-500" />
                  Simulator Configuration
                </h3>
                <p className="text-[11px] text-zinc-500">Configure parameters to generate a synthetic campaign.</p>
              </div>

              {/* Attack Family Dropdown */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Attack Vector Family</label>
                <select
                  value={playgroundAttackId}
                  onChange={(e) => setPlaygroundAttackId(e.target.value)}
                  disabled={isPlaygroundSimulating}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs font-semibold text-zinc-200 outline-none focus:border-orange-500/50 transition cursor-pointer text-ellipsis overflow-hidden"
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
                <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Campaign Intensity</label>
                <div className="grid grid-cols-3 gap-2">
                  {["LOW", "MEDIUM", "HIGH"].map((level) => (
                    <button
                      key={level}
                      type="button"
                      disabled={isPlaygroundSimulating}
                      onClick={() => setPlaygroundIntensity(level)}
                      className={`py-2 rounded-lg text-xs font-bold border transition ${
                        playgroundIntensity === level
                          ? "bg-orange-600/10 border-orange-500/50 text-orange-500"
                          : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
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
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-orange-600 to-amber-500 text-xs font-black text-white hover:brightness-110 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none transition shadow-lg shadow-orange-950/20"
              >
                <Play className={`h-4 w-4 ${isPlaygroundSimulating ? "animate-spin" : ""}`} />
                {isPlaygroundSimulating ? "Simulating Hop-by-Hop..." : "Start Live Campaign Simulation"}
              </button>

              {playgroundError && (
                <div className="p-3.5 rounded-xl border border-red-900/50 bg-red-950/20 text-red-400 text-xs flex gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{playgroundError}</span>
                </div>
              )}

              {/* Pretext Card */}
              {playgroundCampaignId && (
                <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 space-y-3.5 animate-fade-in">
                  <div className="border-b border-zinc-900 pb-2 flex justify-between items-center">
                    <span className="text-[9px] font-black bg-orange-600/10 border border-orange-500/20 text-orange-500 px-2 py-0.5 rounded uppercase tracking-wider">
                      Active Campaign
                    </span>
                    <span className="text-[10px] font-mono text-zinc-500">{playgroundCampaignId.slice(0, 8)}...</span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Attack Pretext</span>
                      <span className="font-semibold text-zinc-300 font-mono capitalize">{playgroundPretext.replace(/_/g, " ")}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Hops / Transactions</span>
                      <span className="font-mono font-bold text-zinc-300">{playgroundTransactions.length} generated</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Middle: Hop-by-hop Feed */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md min-h-[500px] flex flex-col gap-4">
              <div>
                <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-orange-500" />
                  Live Campaign Ticker
                </h3>
                <p className="text-[11px] text-zinc-500">Hop-by-hop transactional steps generated by the simulator.</p>
              </div>

              {playgroundTransactions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                  <Network className={`h-12 w-12 text-zinc-700 mb-3 ${isPlaygroundSimulating ? "animate-pulse text-orange-500/40" : ""}`} />
                  <span className="text-xs text-zinc-500">
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
                        className={`w-full text-left rounded-xl border p-4 transition-all flex items-start gap-3 relative overflow-hidden ${
                          isSelected
                            ? "border-orange-500/40 bg-zinc-900 shadow-md shadow-orange-950/10"
                            : "border-zinc-800 bg-zinc-950/40 hover:border-zinc-700"
                        }`}
                      >
                        {/* Sequence indicator */}
                        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-zinc-900 border border-zinc-850 font-mono text-[10px] font-bold text-zinc-400">
                          {txItem.sequence}
                        </div>

                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="flex justify-between items-start">
                            <span className="font-mono text-[11px] text-zinc-300 font-bold">
                              ₹{parseFloat(tx.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                            </span>
                            <span className={`text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-wider ${
                              r.risk_level === "CRITICAL" || r.risk_level === "HIGH"
                                ? "bg-red-500/10 text-red-400 border border-red-500/20"
                                : r.risk_level === "MEDIUM"
                                ? "bg-orange-500/10 text-orange-400 border border-orange-500/20"
                                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            }`}>
                              {r.risk_level}
                            </span>
                          </div>

                          <div className="flex justify-between text-[10px] text-zinc-500">
                            <span className="capitalize">{tx.rail.replace(/_/g, " ")} ({tx.channel})</span>
                            <span className="font-mono">Score: {r.risk_score.toFixed(1)}</span>
                          </div>
                        </div>

                        {/* Visual indicator bar on the side */}
                        <div className={`absolute top-0 right-0 bottom-0 w-1 ${
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
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md min-h-[500px] flex flex-col items-center justify-center text-center">
                  <Activity className="h-10 w-10 text-zinc-700 mb-2" />
                  <span className="text-xs text-zinc-500">Select a transaction hop from the ticker to inspect its score analysis</span>
                </div>
              ) : (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md space-y-6 animate-fade-in">
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                      <Target className="h-4 w-4 text-orange-500" />
                      Hop Analysis
                    </h3>
                    <p className="text-[11px] text-zinc-500">Deep-dive risk scoring and SHAP attributions.</p>
                  </div>

                  {/* Risk Score Dial/Gauge */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 flex flex-col items-center justify-center gap-3">
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Live Risk Score</span>
                    <div className="h-28 w-28 relative flex items-center justify-center">
                      <svg className="absolute inset-0 h-full w-full -rotate-90">
                        <circle cx="56" cy="56" r="44" stroke="#18181b" strokeWidth="8" fill="transparent" />
                        <circle
                          cx="56"
                          cy="56"
                          r="44"
                          stroke={
                            playgroundTransactions[playgroundCurrentIndex].result.risk_level === "CRITICAL" ||
                            playgroundTransactions[playgroundCurrentIndex].result.risk_level === "HIGH"
                              ? "#ef4444"
                              : playgroundTransactions[playgroundCurrentIndex].result.risk_level === "MEDIUM"
                              ? "#f97316"
                              : "#10b981"
                          }
                          strokeWidth="8"
                          fill="transparent"
                          strokeDasharray={2 * Math.PI * 44}
                          strokeDashoffset={
                            2 * Math.PI * 44 * (1 - playgroundTransactions[playgroundCurrentIndex].result.risk_score / 100)
                          }
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="flex flex-col items-center">
                        <span className="text-2xl font-black text-white font-mono">
                          {playgroundTransactions[playgroundCurrentIndex].result.risk_score.toFixed(0)}
                        </span>
                        <span className="text-[9px] font-black text-zinc-500 uppercase">/ 100</span>
                      </div>
                    </div>
                    <span className={`text-[10px] font-black px-2 py-0.5 rounded uppercase tracking-wider ${
                      playgroundTransactions[playgroundCurrentIndex].result.action === "BLOCK"
                        ? "bg-red-500/10 text-red-400 border border-red-500/20"
                        : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    }`}>
                      Action: {playgroundTransactions[playgroundCurrentIndex].result.action}
                    </span>
                  </div>

                  {/* SHAP Contributions bar chart */}
                  {playgroundTransactions[playgroundCurrentIndex].result.shap_contributions && (
                    <div className="space-y-4">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">Model SHAP Attributions</span>
                      <div className="space-y-2">
                        {playgroundTransactions[playgroundCurrentIndex].result.shap_contributions.map((s: any, idx: number) => {
                          const isPositive = s.direction === "increases_risk";
                          return (
                            <div key={idx} className="space-y-1 text-xs">
                              <div className="flex justify-between font-mono text-[10px]">
                                <span className="text-zinc-400 truncate max-w-[150px]">{s.feature}</span>
                                <span className={isPositive ? "text-red-400" : "text-emerald-400"}>
                                  {isPositive ? "+" : ""}{s.shap_value.toFixed(2)}
                                </span>
                              </div>
                              <div className="h-1.5 w-full bg-zinc-900 rounded overflow-hidden relative">
                                <div
                                  className="absolute top-0 bottom-0 rounded"
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
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">Threat Indicators</span>
                        <div className="space-y-1.5">
                          {playgroundTransactions[playgroundCurrentIndex].result.contributing_signals.map((sig: string, sIdx: number) => (
                            <div key={sIdx} className="flex items-start gap-2 text-xs text-zinc-300">
                              <span className="h-1.5 w-1.5 rounded-full bg-orange-500 mt-1.5 shrink-0" />
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
      <footer className="border-t border-zinc-900 bg-zinc-950 py-4 text-center text-[10px] text-zinc-600">
        © 2026 Chakravyuh Analyst Portal. Secure Area. Unauthorized access is strictly prohibited.
      </footer>

    </div>
  );
}
