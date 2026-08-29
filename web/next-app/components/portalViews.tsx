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
  BrainCircuit,
  ChevronDown,
  Check
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
  const [scenarioDropdownOpen, setScenarioDropdownOpen] = useState(false);
  const scenarioDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (scenarioDropdownRef.current && !scenarioDropdownRef.current.contains(event.target as Node)) {
        setScenarioDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Transaction Linkage: Structured Column-Lane Layout
  // Positions each transaction cluster in its own horizontal row.
  // Attackers in Col 1 (x=40), Payers in Col 2 (x=280), Payees in Col 3 (x=520).
  // Vertical threat campaign linkages connect cleanly down Col 2 between Payers.
  const transactionFlowNodes: FlowNode[] = useMemo(() => {
    const rawNodes = scoreResult?.network_graph?.nodes ?? [];
    if (rawNodes.length === 0) return [];

    const txnOrder: string[] = [];
    const nodesByTxn: Record<string, any[]> = {};

    rawNodes.forEach((node: any) => {
      const match = node.id.match(/TXN_\d+/i);
      const txnId = match ? match[0].toUpperCase() : "DEFAULT";
      if (!nodesByTxn[txnId]) {
        nodesByTxn[txnId] = [];
        txnOrder.push(txnId);
      }
      nodesByTxn[txnId].push(node);
    });

    const positionedNodes: FlowNode[] = [];

    txnOrder.forEach((txnId, rIdx) => {
      const rowY = rIdx * 140 + 40;
      const group = nodesByTxn[txnId];

      group.forEach((node: any) => {
        let posX = 280;
        let posY = rowY;

        if (node.type === "attacker" || node.id.startsWith("attacker_")) {
          posX = 40;
        } else if (node.type === "payer" || node.id.startsWith("payer_")) {
          posX = 280;
        } else if (node.type === "payee" || node.id.startsWith("payee_")) {
          posX = 520;
        } else if (node.type === "payer_other" || node.id.startsWith("copayer_")) {
          posX = 280;
          posY = rowY + 65;
        }

        positionedNodes.push({
          id: node.id,
          type: "actorNode",
          position: { x: posX, y: posY },
          data: { ...node, isSelected: selectedTransactionNode?.id === node.id },
        });
      });
    });

    return positionedNodes;
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
        sourceHandle: isLinkage ? "bottom" : "right",
        targetHandle: isLinkage ? "top" : "left",
        label: edge.label,
        type: isLinkage ? "bezier" : "smoothstep",
        animated: isLinkage || isAlert,
        className: isAlert ? "pulse-edge" : undefined,
        style: {
          stroke: isLinkage ? "#10b981" : color,
          strokeWidth: isLinkage ? 2.5 : isAlert ? 2 : 1.5,
          strokeDasharray: isLinkage ? "6 6" : isAlert ? "4 4" : undefined,
        },
        labelStyle: {
          fill: isLinkage ? "#34d399" : "#e4e4e7",
          fontSize: 9,
          fontWeight: 700,
          fontFamily: "monospace",
        },
        labelBgStyle: {
          fill: isLinkage ? "#064e3b" : "#18181b",
          fillOpacity: 0.95,
          stroke: isLinkage ? "#059669" : "#3f3f46",
          strokeWidth: 1,
        },
        labelBgPadding: [8, 4] as [number, number],
        labelBgBorderRadius: 8,
        markerEnd: isLinkage
          ? { type: MarkerType.ArrowClosed, color: "#10b981" }
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
      <div className="story-grid pointer-events-none absolute inset-0 opacity-40" />
      <div className="pointer-events-none absolute left-[10%] top-[12%] h-96 w-96 rounded-full bg-orange-500/[0.04] blur-[160px]" />
      <div className="pointer-events-none absolute right-[8%] top-[35%] h-80 w-80 rounded-full bg-amber-500/[0.03] blur-[150px]" />
      <div className="pointer-events-none absolute bottom-[10%] left-[25%] h-96 w-96 rounded-full bg-emerald-500/[0.03] blur-[160px]" />

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
                  ? "border-orange-400 ring-2 ring-orange-500/30 shadow-[0_0_30px_rgba(249,115,22,0.1)]"
                  : "border-white/10 hover:border-orange-500/30 shadow-xl"
              }`}>
                {/* Subtle internal corner glow */}
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/[0.03] blur-3xl" />

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
                    <div className="relative" ref={scenarioDropdownRef}>
                      <button
                        type="button"
                        onClick={() => setScenarioDropdownOpen(!scenarioDropdownOpen)}
                        className={`w-full rounded-2xl border bg-zinc-900/90 px-4 py-3 text-xs font-mono text-left flex items-center justify-between transition-all duration-200 shadow-inner ${
                          scenarioDropdownOpen
                            ? "border-orange-400 ring-2 ring-orange-500/30 text-white"
                            : "border-white/15 hover:border-orange-500/40 text-zinc-100"
                        }`}
                      >
                        <span className="truncate pr-2 font-medium">
                          {selectedScenarioName || "Select a simulation scenario"}
                        </span>
                        <ChevronDown
                          className={`h-4 w-4 shrink-0 text-orange-400 transition-transform duration-200 ${
                            scenarioDropdownOpen ? "rotate-180" : ""
                          }`}
                        />
                      </button>

                      {scenarioDropdownOpen && (
                        <div className="absolute left-0 right-0 top-full mt-2 z-50 rounded-2xl border border-orange-500/30 bg-zinc-950/95 p-1.5 backdrop-blur-xl shadow-2xl animate-fade-in space-y-1 max-h-72 overflow-y-auto">
                          {Object.keys(scenarios).map((name) => {
                            const isSelected = selectedScenarioName === name;
                            return (
                              <button
                                key={name}
                                type="button"
                                onClick={() => {
                                  setSelectedScenarioName(name);
                                  setScenarioDropdownOpen(false);
                                  if (guideActive && guideStep === "choose_scenario") {
                                    setGuideStep("inspect_parameters");
                                  }
                                }}
                                className={`w-full rounded-xl px-3.5 py-2.5 text-xs font-mono text-left flex items-center justify-between transition-all ${
                                  isSelected
                                    ? "bg-orange-500/20 text-orange-300 font-bold border border-orange-500/30"
                                    : "text-zinc-300 hover:bg-zinc-900 hover:text-white"
                                }`}
                              >
                                <span className="truncate pr-2">{name}</span>
                                {isSelected && <Check className="h-3.5 w-3.5 text-orange-400 shrink-0" />}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
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
                    {(() => {
                      const pct = Math.min(100, Math.max(0, ((txnOverrides.amount || 0) - 1) / (150000 - 1) * 100));
                      return (
                        <input
                          type="range"
                          min="1"
                          max="150000"
                          step="100"
                          value={txnOverrides.amount || 0}
                          onChange={(e) => updateOverrideField("amount", parseFloat(e.target.value))}
                          style={{
                            background: `linear-gradient(to right, #f97316 0%, #f59e0b ${pct}%, #27272a ${pct}%, #27272a 100%)`
                          }}
                          className="w-full h-2 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none transition-all shadow-inner"
                        />
                      );
                    })()}
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
                    {(() => {
                      const pct = Math.min(100, Math.max(0, (txnOverrides.pin_attempts || 0) / 5 * 100));
                      return (
                        <input
                          type="range"
                          min="0"
                          max="5"
                          step="1"
                          value={txnOverrides.pin_attempts || 0}
                          onChange={(e) => updateOverrideField("pin_attempts", parseInt(e.target.value))}
                          style={{
                            background: `linear-gradient(to right, #f97316 0%, #f59e0b ${pct}%, #27272a ${pct}%, #27272a 100%)`
                          }}
                          className="w-full h-2 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none transition-all shadow-inner"
                        />
                      );
                    })()}
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
                    {(() => {
                      const days = Math.floor((txnOverrides.beneficiary_added_ago_s || 0) / 86400);
                      const pct = Math.min(100, Math.max(0, days / 730 * 100));
                      return (
                        <input
                          type="range"
                          min="0"
                          max="730"
                          step="1"
                          value={days}
                          onChange={(e) => updateOverrideField("beneficiary_added_ago_s", parseInt(e.target.value) * 86400)}
                          style={{
                            background: `linear-gradient(to right, #f97316 0%, #f59e0b ${pct}%, #27272a ${pct}%, #27272a 100%)`
                          }}
                          className="w-full h-2 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none transition-all shadow-inner"
                        />
                      );
                    })()}
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
                    {(() => {
                      const pct = Math.min(100, Math.max(0, (txnOverrides.edge_count || 0) / 50 * 100));
                      return (
                        <input
                          type="range"
                          min="0"
                          max="50"
                          step="1"
                          value={txnOverrides.edge_count || 0}
                          onChange={(e) => updateOverrideField("edge_count", parseFloat(e.target.value))}
                          style={{
                            background: `linear-gradient(to right, #f97316 0%, #f59e0b ${pct}%, #27272a ${pct}%, #27272a 100%)`
                          }}
                          className="w-full h-2 rounded-full appearance-none cursor-pointer accent-orange-500 focus:outline-none transition-all shadow-inner"
                        />
                      );
                    })()}
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
                <div className="relative overflow-hidden bg-zinc-950/85 p-6 rounded-3xl flex flex-col gap-5 border border-white/10 hover:border-orange-500/30 backdrop-blur-xl shadow-2xl transition-all duration-300">
                  <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/[0.03] blur-3xl" />
                  
                  {/* Top Header with Compact Centered Status Badge */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
                    <div>
                      <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em] flex items-center gap-2">
                        <Activity className="h-4 w-4 text-orange-400" />
                        Risk Evaluation & Threat Defense Engine
                      </h3>
                      <p className="text-xs text-zinc-400 mt-1">
                        Multi-model payment fraud detection with explainable AI & human-in-the-loop retraining.
                      </p>
                    </div>
                    <div className="shrink-0 flex items-center">
                      <span className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1 text-[11px] font-bold font-mono uppercase tracking-wider text-orange-300 bg-orange-500/10 border border-orange-500/30 rounded-full whitespace-nowrap">
                        <span className="h-1.5 w-1.5 rounded-full bg-orange-400 animate-pulse shrink-0" />
                        Ready for Evaluation
                      </span>
                    </div>
                  </div>

                  {/* 3 Core Architecture Metrics */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="bg-zinc-900/60 p-4 rounded-2xl border border-white/10 hover:border-orange-500/30 transition flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] text-orange-300 uppercase font-bold tracking-widest">Primary Detector</span>
                        <Shield className="h-3.5 w-3.5 text-orange-400" />
                      </div>
                      <div>
                        <span className="text-sm font-bold font-mono text-white block">XGBoost v1.0</span>
                        <span className="text-[11px] font-mono text-emerald-400 mt-1 font-bold inline-block bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/30">
                          99.8% PR-AUC
                        </span>
                      </div>
                    </div>

                    <div className="bg-zinc-900/60 p-4 rounded-2xl border border-white/10 hover:border-orange-500/30 transition flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] text-orange-300 uppercase font-bold tracking-widest">Attack Vectors</span>
                        <Cpu className="h-3.5 w-3.5 text-amber-400" />
                      </div>
                      <div>
                        <span className="text-sm font-bold font-mono text-white block">16 Families</span>
                        <span className="text-[11px] font-mono text-zinc-300 mt-1 font-semibold inline-block bg-zinc-800 px-2 py-0.5 rounded border border-white/10">
                          58 Signature Rules
                        </span>
                      </div>
                    </div>

                    <div className="bg-zinc-900/60 p-4 rounded-2xl border border-white/10 hover:border-orange-500/30 transition flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] text-orange-300 uppercase font-bold tracking-widest">Explainability</span>
                        <Target className="h-3.5 w-3.5 text-emerald-400" />
                      </div>
                      <div>
                        <span className="text-sm font-bold font-mono text-white block">SHAP + GenAI</span>
                        <span className="text-[11px] font-mono text-zinc-300 mt-1 font-semibold inline-block bg-zinc-800 px-2 py-0.5 rounded border border-white/10">
                          Attribution Vectors
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Pipeline Steps in Compact 2x2 Grid */}
                  <div className="space-y-2.5">
                    <span className="text-xs font-bold text-zinc-300 uppercase tracking-[0.16em] block">
                      Pipeline Execution Workflow
                    </span>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div className="p-3.5 bg-zinc-900/60 rounded-2xl border border-white/10 hover:border-orange-500/30 transition">
                        <span className="font-bold text-orange-300 block text-xs mb-0.5">1. Signal Ingestion</span>
                        <p className="text-xs text-zinc-300 leading-relaxed">Extracts 75 payment, behavioral telemetry, and counterparty graph features.</p>
                      </div>
                      <div className="p-3.5 bg-zinc-900/60 rounded-2xl border border-white/10 hover:border-orange-500/30 transition">
                        <span className="font-bold text-orange-300 block text-xs mb-0.5">2. Risk & Attack Fusion</span>
                        <p className="text-xs text-zinc-300 leading-relaxed">Evaluates joint probabilities against calibrated fraud operating points.</p>
                      </div>
                      <div className="p-3.5 bg-zinc-900/60 rounded-2xl border border-white/10 hover:border-orange-500/30 transition">
                        <span className="font-bold text-orange-300 block text-xs mb-0.5">3. SHAP Decomposition</span>
                        <p className="text-xs text-zinc-300 leading-relaxed">Calculates exact positive/negative risk contributors explaining the prediction.</p>
                      </div>
                      <div className="p-3.5 bg-zinc-900/60 rounded-2xl border border-white/10 hover:border-orange-500/30 transition">
                        <span className="font-bold text-orange-300 block text-xs mb-0.5">4. Closed-Loop Retraining</span>
                        <p className="text-xs text-zinc-300 leading-relaxed">Analyst ground-truth feedback logs directly to trigger model retraining.</p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className={`relative overflow-hidden rounded-3xl border bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl flex-1 flex flex-col gap-6 animate-fade-in transition-all duration-300 ${
                  guideActive && guideStep === "submit_feedback"
                    ? "border-orange-400 ring-2 ring-orange-500/30 shadow-[0_0_40px_rgba(249,115,22,0.15)]"
                    : "border-orange-500/20 hover:border-orange-500/40 shadow-[0_0_35px_rgba(249,115,22,0.06)]"
                }`}>
                  <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-orange-500/[0.03] blur-3xl" />

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
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/[0.03] blur-3xl" />
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
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/[0.03] blur-3xl" />
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
            </div>

            {/* Model History Comparison */}
            {modelHistory.length > 0 && (
              <div className="relative overflow-hidden rounded-3xl border border-white/10 hover:border-orange-500/30 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl transition-all duration-300">
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/[0.03] blur-3xl" />
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
            <div className="rounded-3xl border border-white/10 hover:border-orange-500/30 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl transition">
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
                      <span className="text-xs text-zinc-300 font-mono w-48 truncate text-right">
                        {item.feature}
                      </span>
                      <div className="flex-1 h-5 bg-zinc-900 rounded-full overflow-hidden relative border border-white/5">
                        <div
                          style={{ width: `${item.importance * 100}%` }}
                          className="h-full bg-orange-500 rounded-full transition-all duration-1000"
                        />
                      </div>
                      <span className="text-xs text-zinc-200 font-mono font-bold w-14 text-right">
                        {(item.importance * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: ATTACK CONNECTION GRAPH */}
        {activeTab === "graph" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            {guideActive && (
              <div className="lg:col-span-12 relative overflow-hidden rounded-3xl border border-orange-400/40 bg-zinc-950/85 p-6 animate-fade-in flex flex-col md:flex-row items-start md:items-center justify-between gap-5 backdrop-blur-xl shadow-2xl shadow-orange-500/10">
                <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-orange-500/[0.04] blur-3xl" />
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
            <div className="lg:col-span-8 relative overflow-hidden rounded-3xl border border-white/10 hover:border-orange-500/30 bg-zinc-950/85 p-7 flex flex-col min-h-[540px] backdrop-blur-xl shadow-2xl transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/[0.03] blur-3xl" />
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
                  <svg viewBox="0 0 1000 440" preserveAspectRatio="xMidYMid meet" className="w-full h-full min-h-[440px]">
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
                            d={`M ${src.x * 10} ${src.y * 4.4} Q ${(src.x + dest.x) * 5} ${(src.y + dest.y) * 2.2 - 16} ${dest.x * 10} ${dest.y * 4.4}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.8" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.95 : 0.35}
                            className="transition-all duration-300 pointer-events-none"
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
                            d={`M ${src.x * 10} ${src.y * 4.4} Q ${(src.x + dest.x) * 5} ${(src.y + dest.y) * 2.2 + 14} ${dest.x * 10} ${dest.y * 4.4}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.8" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.95 : 0.35}
                            className="transition-all duration-300 pointer-events-none"
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
                            d={`M ${src.x * 10} ${src.y * 4.4} L ${dest.x * 10} ${dest.y * 4.4}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.8" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.95 : 0.35}
                            className="transition-all duration-300 pointer-events-none"
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
                            d={`M ${src.x * 10} ${src.y * 4.4} Q ${(src.x + dest.x) * 5} ${(src.y + dest.y) * 2.2 + 10} ${dest.x * 10} ${dest.y * 4.4}`}
                            fill="none"
                            stroke={isHighlighted ? "#f97316" : "#27272a"}
                            strokeWidth={isHighlighted ? "1.8" : "1"}
                            markerEnd={`url(#${isHighlighted ? "arrow-glow" : "arrow"})`}
                            opacity={isHighlighted ? 0.95 : 0.35}
                            className="transition-all duration-300 pointer-events-none"
                          />
                        );
                      })
                    )}

                    {/* Nodes Layer */}
                    {ATTACK_NODES.map(node => {
                      const isSelected = selectedNode?.id === node.id;
                      const cx = node.x * 10;
                      const cy = node.y * 4.4;
                      return (
                        <g
                          key={node.id}
                          onClick={() => setSelectedNode(node)}
                          className="cursor-pointer group"
                        >
                          {/* Large invisible hit area for immediate first-click responsiveness */}
                          <circle
                            cx={cx}
                            cy={cy}
                            r="32"
                            fill="transparent"
                            className="cursor-pointer"
                          />

                          {isSelected && (
                            <circle
                              cx={cx}
                              cy={cy}
                              r="18"
                              fill="none"
                              stroke="#f97316"
                              strokeWidth="2"
                              strokeDasharray="3 3"
                              className="animate-spin-slow pointer-events-none"
                            />
                          )}
                          <circle
                            cx={cx}
                            cy={cy}
                            r="10"
                            fill={isSelected ? "#f97316" : "#18181b"}
                            stroke={isSelected ? "#ea580c" : "#3f3f46"}
                            strokeWidth="2"
                            className="transition-all group-hover:stroke-orange-400 group-hover:scale-110 pointer-events-none"
                          />
                          <text
                            x={cx}
                            y={cy - 14}
                            textAnchor="middle"
                            fill={isSelected ? "#fb923c" : "#a1a1aa"}
                            fontSize="10px"
                            fontFamily="monospace"
                            className="font-bold pointer-events-none transition-colors group-hover:fill-zinc-100 select-none"
                          >
                            {node.id}
                          </text>
                          <text
                            x={cx}
                            y={cy + 19}
                            textAnchor="middle"
                            fill={isSelected ? "#fed7aa" : "#71717a"}
                            fontSize="9px"
                            className="pointer-events-none transition-colors group-hover:fill-zinc-200 select-none"
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

/** Signature Hero Visual: Concentric Counter-Rotating Defence Rings */
function ChakravyuhDefenceRings() {
  const [pulseCore, setPulseCore] = useState(false);
  const [fraudBlocked, setFraudBlocked] = useState(false);

  useEffect(() => {
    // Pulse intervals matching the particle timing
    const genuineInterval = setInterval(() => {
      setPulseCore(true);
      setTimeout(() => setPulseCore(false), 900);
    }, 4000);

    const fraudInterval = setInterval(() => {
      setTimeout(() => {
        setFraudBlocked(true);
        setTimeout(() => setFraudBlocked(false), 1200);
      }, 2000);
    }, 4000);

    return () => {
      clearInterval(genuineInterval);
      clearInterval(fraudInterval);
    };
  }, []);

  return (
    <div className="relative mx-auto flex w-full max-w-md items-center justify-center p-2">
      {/* Outer ambient glow */}
      <div className="pointer-events-none absolute inset-0 rounded-full bg-gradient-to-tr from-orange-500/15 via-amber-500/10 to-emerald-500/15 blur-2xl" />

      <div className="relative h-[340px] w-[340px] sm:h-[380px] sm:w-[380px]">
        <svg viewBox="0 0 380 380" className="h-full w-full select-none overflow-visible">
          <defs>
            <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="fraudFlash" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="ringGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f97316" stopOpacity="0.9" />
              <stop offset="50%" stopColor="#fb923c" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#f97316" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="ringGrad2" x1="100%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#ea580c" stopOpacity="0.8" />
              <stop offset="70%" stopColor="#f59e0b" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#ea580c" stopOpacity="0.9" />
            </linearGradient>
            <linearGradient id="ringGrad3" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#f97316" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#c2410c" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* Background Radar Grid Coordinates */}
          <circle cx="190" cy="190" r="172" fill="none" stroke="#27272a" strokeWidth="1" strokeDasharray="2 6" opacity="0.5" />
          <circle cx="190" cy="190" r="130" fill="none" stroke="#27272a" strokeWidth="1" strokeDasharray="3 6" opacity="0.4" />
          <circle cx="190" cy="190" r="85" fill="none" stroke="#27272a" strokeWidth="1" strokeDasharray="2 4" opacity="0.4" />

          {/* Coordinate Crosshairs */}
          <line x1="190" y1="10" x2="190" y2="370" stroke="#3f3f46" strokeWidth="1" strokeDasharray="4 8" opacity="0.25" />
          <line x1="10" y1="190" x2="370" y2="190" stroke="#3f3f46" strokeWidth="1" strokeDasharray="4 8" opacity="0.25" />

          {/* RING 1: L1 Edge Telemetry (Radius 150 - Slow Clockwise Counter-Rotation) */}
          <motion.g
            animate={{ rotate: 360 }}
            transition={{ duration: 32, repeat: Infinity, ease: "linear" }}
            style={{ originX: "190px", originY: "190px" }}
          >
            <circle
              cx="190"
              cy="190"
              r="150"
              fill="none"
              stroke="url(#ringGrad1)"
              strokeWidth="2.5"
              strokeDasharray="220 50 200 60 180 70"
              strokeLinecap="round"
            />
            {/* Satellite sensor nodes on Ring 1 */}
            <circle cx="190" cy="40" r="3.5" fill="#f97316" className="animate-pulse" />
            <circle cx="340" cy="190" r="3" fill="#fb923c" />
            <circle cx="70" cy="270" r="3" fill="#f97316" />
          </motion.g>

          {/* RING 2: L2 Behavioral Graph (Radius 108 - Counter-Clockwise Rotation) */}
          <motion.g
            animate={{ rotate: -360 }}
            transition={{ duration: 24, repeat: Infinity, ease: "linear" }}
            style={{ originX: "190px", originY: "190px" }}
          >
            <circle
              cx="190"
              cy="190"
              r="108"
              fill="none"
              stroke={fraudBlocked ? "#ef4444" : "url(#ringGrad2)"}
              strokeWidth={fraudBlocked ? "3.5" : "2.5"}
              strokeDasharray="160 45 140 50 120 40"
              strokeLinecap="round"
              className="transition-all duration-300"
            />
            {/* Nodes on Ring 2 */}
            <circle cx="190" cy="82" r="3" fill={fraudBlocked ? "#ef4444" : "#f59e0b"} />
            <circle cx="280" cy="245" r="3" fill="#ea580c" />
            <circle cx="100" cy="140" r="3" fill="#fb923c" />
          </motion.g>

          {/* RING 3: L3 Counterparty AI Shield (Radius 68 - Clockwise Rotation) */}
          <motion.g
            animate={{ rotate: 360 }}
            transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
            style={{ originX: "190px", originY: "190px" }}
          >
            <circle
              cx="190"
              cy="190"
              r="68"
              fill="none"
              stroke="url(#ringGrad3)"
              strokeWidth="2.5"
              strokeDasharray="110 30 90 35"
              strokeLinecap="round"
            />
            <circle cx="190" cy="122" r="3" fill="#f97316" />
            <circle cx="245" cy="225" r="3" fill="#f97316" />
          </motion.g>

          {/* Fraud Interception Barrier Shield Ripple */}
          {fraudBlocked && (
            <motion.circle
              cx="125"
              cy="235"
              r="22"
              fill="url(#fraudFlash)"
              stroke="#ef4444"
              strokeWidth="2"
              initial={{ scale: 0.6, opacity: 0.9 }}
              animate={{ scale: 1.4, opacity: 0 }}
              transition={{ duration: 0.8 }}
            />
          )}

          {/* Genuine Payment Particle (Green) traveling inward through ring gaps to the core */}
          <motion.g
            animate={{
              x: [130, 85, 45, 0],
              y: [-120, -75, -35, 0],
              opacity: [0, 1, 1, 0.9],
              scale: [0.8, 1, 1.1, 1.3],
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              times: [0, 0.35, 0.75, 1],
              ease: "easeInOut",
            }}
          >
            <circle cx="190" cy="190" r="4.5" fill="#10b981" className="shadow-lg shadow-emerald-500" />
            <circle cx="190" cy="190" r="8" fill="none" stroke="#10b981" strokeWidth="1.5" opacity="0.6" />
          </motion.g>

          {/* Fraudulent Payment Particle (Red/Orange) traveling inward and getting held at Barrier Ring 2 */}
          <motion.g
            animate={{
              x: [-130, -85, -65, -65, -65],
              y: [120, 75, 45, 45, 45],
              opacity: [0, 1, 1, 0.8, 0],
              scale: [0.8, 1, 1.2, 1, 0],
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              times: [0, 0.25, 0.5, 0.8, 1],
              ease: "easeOut",
            }}
          >
            <circle cx="190" cy="190" r="4.5" fill="#ef4444" className="shadow-lg shadow-red-500" />
            <circle cx="190" cy="190" r="8" fill="none" stroke="#ef4444" strokeWidth="1.5" opacity="0.7" />
          </motion.g>

          {/* Central Settlement Vault Core */}
          <circle
            cx="190"
            cy="190"
            r={pulseCore ? 34 : 28}
            fill="#090a0f"
            stroke={pulseCore ? "#10b981" : "#f97316"}
            strokeWidth="2"
            className="transition-all duration-300"
          />
          {pulseCore && (
            <circle cx="190" cy="190" r="46" fill="url(#coreGlow)" className="animate-ping" />
          )}
          <circle cx="190" cy="190" r="20" fill={pulseCore ? "#10b98120" : "#f9731615"} />

          {/* Core Symbol */}
          <g transform="translate(181, 181)">
            <path
              d="M9 2.5 L3 5.5 V10.5 C3 14.5 9 17.5 9 17.5 C9 17.5 15 14.5 15 10.5 V5.5 L9 2.5 Z"
              fill="none"
              stroke={pulseCore ? "#34d399" : "#fb923c"}
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </g>
        </svg>

        {/* Live HUD Badges around the rings */}
        <div className="pointer-events-none absolute -bottom-2 inset-x-0 flex items-center justify-between px-2 text-[10px] font-mono text-zinc-400">
          <span className="rounded-full border border-emerald-500/30 bg-emerald-950/70 px-2.5 py-1 text-emerald-300 backdrop-blur shadow">
            ● Genuine Pass (0.4ms)
          </span>
          <span className="rounded-full border border-red-500/30 bg-red-950/70 px-2.5 py-1 text-red-300 backdrop-blur shadow">
            ● Attack Intercepted
          </span>
        </div>

        <div className="pointer-events-none absolute -top-2 inset-x-0 flex justify-center text-[10px] font-mono font-bold tracking-widest uppercase text-orange-300">
          <span className="rounded-full border border-orange-500/30 bg-zinc-950/80 px-3 py-0.5 backdrop-blur">
            Multi-Layer Chakravyuh Perimeter
          </span>
        </div>
      </div>
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
    riskColor: "text-orange-400",
    riskBg: "border-orange-500/40 bg-orange-500/10",
    gaugeColor: "#f97316",
    action: "HOLD FOR REVIEW",
    actionBg: "bg-orange-500 text-zinc-950",
    glowColor: "from-orange-500/25 to-amber-500/10",
    signals: [
      "Active voice call during confirmation",
      "Screen share service detected",
      "Beneficiary matches mule network pattern",
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
    riskColor: "text-amber-400",
    riskBg: "border-amber-500/40 bg-amber-500/10",
    gaugeColor: "#f59e0b",
    action: "CHALLENGE (STEP-UP OTP)",
    actionBg: "bg-amber-400 text-zinc-950",
    glowColor: "from-amber-500/25 to-rose-500/10",
    signals: [
      "Sub-threshold fragmentation velocity",
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
    riskColor: "text-emerald-400",
    riskBg: "border-emerald-500/40 bg-emerald-500/10",
    gaugeColor: "#10b981",
    action: "INSTANT APPROVAL",
    actionBg: "bg-emerald-400 text-zinc-950",
    glowColor: "from-emerald-500/25 to-teal-500/10",
    signals: [
      "Known counterparty with 14 prior txns",
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
  const [timerProgress, setTimerProgress] = useState(0);
  const [displayedScore, setDisplayedScore] = useState(HERO_SCENARIOS[0].riskScore);
  const [activeAct, setActiveAct] = useState(0);

  const scoreRef = useRef(HERO_SCENARIOS[0].riskScore);

  // Smoothly interpolate displayed risk score on scenario change
  useEffect(() => {
    const target = HERO_SCENARIOS[activeScenarioIdx].riskScore;
    const start = scoreRef.current;
    const duration = 600;
    const startTime = performance.now();

    let animFrame: number;
    const animateNumber = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(1, elapsed / duration);
      const currentVal = Math.round(start + (target - start) * progress);
      scoreRef.current = currentVal;
      setDisplayedScore(currentVal);

      if (progress < 1) {
        animFrame = requestAnimationFrame(animateNumber);
      }
    };

    animFrame = requestAnimationFrame(animateNumber);
    return () => cancelAnimationFrame(animFrame);
  }, [activeScenarioIdx]);

  // Track global scroll
  useEffect(() => {
    const updateProgress = () => {
      const maximum = document.documentElement.scrollHeight - window.innerHeight;
      setScrollProgress(maximum > 0 ? Math.min(1, window.scrollY / maximum) : 0);
    };
    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    return () => window.removeEventListener("scroll", updateProgress);
  }, []);

  // 5-second auto-cycle with filling progress bar
  useEffect(() => {
    if (isPaused) return;

    const cycleDuration = 5000;
    const intervalTick = 50;
    let elapsed = 0;

    const timer = setInterval(() => {
      elapsed += intervalTick;
      setTimerProgress(Math.min(100, (elapsed / cycleDuration) * 100));

      if (elapsed >= cycleDuration) {
        elapsed = 0;
        setTimerProgress(0);
        setActiveScenarioIdx((prev) => (prev + 1) % HERO_SCENARIOS.length);
      }
    }, intervalTick);

    return () => clearInterval(timer);
  }, [isPaused, activeScenarioIdx]);

  const currentScenario = HERO_SCENARIOS[activeScenarioIdx];

  return (
    <main className="story-page min-h-screen overflow-x-hidden bg-[#08090b] text-zinc-100 selection:bg-orange-400/30">
      {/* Top Scroll Progress Line */}
      <div className="fixed inset-x-0 top-0 z-[60] h-1 bg-zinc-900">
        <motion.div
          className="h-full origin-left bg-gradient-to-r from-orange-500 via-amber-400 to-emerald-400 shadow-md shadow-orange-500/50"
          style={{ scaleX: scrollProgress }}
        />
      </div>

      {/* Header */}
      <header className="fixed inset-x-0 top-0 z-50 flex items-center justify-between px-5 py-4 md:px-10 backdrop-blur-xl bg-zinc-950/70 border-b border-white/5">
        <a href="#top" className="flex items-center gap-2.5 text-sm font-bold tracking-[0.18em] text-white" aria-label="Back to top">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-orange-400/40 bg-orange-500/10 shadow-sm">
            <Shield className="h-4 w-4 text-orange-300" />
          </span>
          CHAKRAVYUH
        </a>
        <Link
          href="/dashboard"
          className="group flex items-center gap-2 rounded-full border border-orange-400/40 bg-zinc-900/80 px-4 py-2 text-xs font-bold text-white backdrop-blur transition hover:border-orange-400 hover:bg-orange-500/15 shadow-sm"
        >
          Open live dashboard <ArrowUpRight className="h-3.5 w-3.5 text-orange-300 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </Link>
      </header>

      {/* HERO SECTION */}
      <section id="top" className="relative flex min-h-screen items-center px-5 pb-20 pt-28 md:px-10">
        <div className="story-grid pointer-events-none absolute inset-0 opacity-50" />
        <div className="pointer-events-none absolute left-[10%] top-[14%] h-96 w-96 rounded-full bg-orange-500/15 blur-[140px]" />
        <div className="pointer-events-none absolute bottom-[10%] right-[10%] h-80 w-80 rounded-full bg-emerald-500/10 blur-[140px]" />

        <div className="relative mx-auto grid w-full max-w-7xl items-center gap-12 lg:grid-cols-[1fr_1fr]">
          {/* Left Column: Copy & Value Proposition */}
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.75, ease: "easeOut" }}>
            <p className="mb-5 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-orange-300">
              <CircleDot className="h-3.5 w-3.5" /> Next-Generation Payment Defence
            </p>
            <h1 className="max-w-3xl text-5xl font-semibold leading-[0.98] tracking-[-0.055em] text-white sm:text-6xl md:text-7xl">
              Fraud evolves.<br /><span className="text-zinc-500">So should the defence.</span>
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-relaxed text-zinc-300">
              Chakravyuh simulates GenAI-enabled payment fraud, detects it in <strong className="text-orange-300 font-semibold">&lt; 8ms</strong> before authorization, and turns every blind spot into an unbreakable defence.
            </p>
            <div className="mt-9 flex flex-wrap gap-3.5">
              <a
                href="#story"
                className="group inline-flex items-center gap-2 rounded-full bg-orange-500 px-6 py-3.5 text-sm font-bold text-zinc-950 transition hover:bg-orange-400 shadow-lg shadow-orange-500/25"
              >
                Read the defence story <ArrowDown className="h-4 w-4 transition-transform group-hover:translate-y-1" />
              </a>
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-zinc-900/80 px-6 py-3.5 text-sm font-semibold text-zinc-200 transition hover:border-orange-400 hover:bg-orange-500/10"
              >
                Skip to dashboard <ArrowUpRight className="h-4 w-4 text-orange-300" />
              </Link>
            </div>
            <div className="mt-12 flex flex-wrap gap-x-8 gap-y-4 text-xs text-zinc-400 font-mono">
              <span className="flex items-center gap-1.5"><b className="text-white">16</b> Attack Families</span>
              <span className="flex items-center gap-1.5"><b className="text-orange-300">&lt; 8ms</b> Latency Window</span>
              <span className="flex items-center gap-1.5"><b className="text-emerald-400">Closed-Loop</b> Learning</span>
            </div>
          </motion.div>

          {/* Right Column: Signature Concentric Defence Rings + Live Authorisation Cockpit */}
          <div className="flex flex-col gap-6">
            {/* Signature Concentric Rings Visual */}
            <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-4 shadow-2xl backdrop-blur-xl transition-all duration-300">
              <ChakravyuhDefenceRings />
            </div>

            {/* Live Authorisation Engine Card (Auto-cycling every 5s with progress bar) */}
            <motion.div 
              initial={{ opacity: 0, scale: 0.96 }} 
              animate={{ opacity: 1, scale: 1 }} 
              transition={{ duration: 0.8 }} 
              className="relative w-full"
              onMouseEnter={() => setIsPaused(true)}
              onMouseLeave={() => setIsPaused(false)}
            >
              <div className={`absolute -inset-2 rounded-3xl bg-gradient-to-br ${currentScenario.glowColor} blur-xl transition-all duration-700`} />
              <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/90 p-6 shadow-2xl backdrop-blur-xl transition-all duration-300">
                {/* Card Header with Interactive Auto-Cycling Tabs */}
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-orange-400" />
                    <span className="text-xs font-bold uppercase tracking-[0.16em] text-orange-300">Live Authorisation Engine</span>
                    {isPaused && (
                      <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[9px] font-mono text-zinc-400">
                        Paused
                      </span>
                    )}
                  </div>

                  {/* 3 Tabs with Progress Bar */}
                  <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-zinc-900/90 p-1">
                    {HERO_SCENARIOS.map((sc, idx) => {
                      const isActive = activeScenarioIdx === idx;
                      return (
                        <button
                          key={sc.id}
                          onClick={() => {
                            setActiveScenarioIdx(idx);
                            setTimerProgress(0);
                          }}
                          className={`relative overflow-hidden rounded-full px-3 py-1.5 text-[11px] font-bold transition-all ${
                            isActive
                              ? "bg-zinc-800 text-white shadow"
                              : "text-zinc-400 hover:text-white"
                          }`}
                        >
                          {/* Active cycling progress bar filling over 5s */}
                          {isActive && (
                            <div
                              className="absolute inset-0 bg-orange-500/30 transition-all"
                              style={{ width: `${timerProgress}%` }}
                            />
                          )}
                          <span className="relative z-10">
                            {idx === 0 ? "Scam Push" : idx === 1 ? "Smurfing" : "Genuine QR"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Dynamic Transaction Display + Radial Gauge */}
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-zinc-400 font-medium">{currentScenario.rail}</span>
                      <span className="rounded-full bg-orange-500/15 border border-orange-500/30 px-2 py-0.5 text-[10px] font-bold text-orange-300 font-mono">
                        {currentScenario.tag}
                      </span>
                    </div>
                    <p className="mt-2 text-3xl sm:text-4xl font-bold tracking-tight text-white font-mono">
                      {currentScenario.amount}
                    </p>
                    <p className="mt-1.5 text-xs text-zinc-400">{currentScenario.subtitle}</p>
                  </div>

                  {/* Radial Gauge & Risk Score */}
                  <div className={`flex items-center gap-3 rounded-2xl border p-3 ${currentScenario.riskBg}`}>
                    <div className="relative h-14 w-14 flex items-center justify-center">
                      <svg className="absolute inset-0 h-full w-full -rotate-90">
                        <circle cx="28" cy="28" r="23" stroke="#27272a" strokeWidth="3.5" fill="transparent" />
                        <circle
                          cx="28"
                          cy="28"
                          r="23"
                          stroke={currentScenario.gaugeColor}
                          strokeWidth="3.5"
                          fill="transparent"
                          strokeDasharray={2 * Math.PI * 23}
                          strokeDashoffset={2 * Math.PI * 23 * (1 - displayedScore / 100)}
                          strokeLinecap="round"
                          className="transition-all duration-300"
                        />
                      </svg>
                      <div className="flex flex-col items-center z-10">
                        <span className="text-base font-black text-white font-mono leading-none">
                          {displayedScore}
                        </span>
                        <span className="text-[7px] font-mono text-zinc-400 uppercase">%</span>
                      </div>
                    </div>
                    <div className="text-left pr-1">
                      <p className="text-[9px] font-bold uppercase tracking-wider text-zinc-400">Risk Score</p>
                      <p className={`text-xs font-bold ${currentScenario.riskColor}`}>{currentScenario.riskLevel}</p>
                    </div>
                  </div>
                </div>

                <div className="my-5 h-px bg-white/10" />

                {/* Stamped Signal Rows (~80ms apart) */}
                <div className="space-y-2">
                  {currentScenario.signals.map((signal, index) => (
                    <motion.div 
                      key={`${currentScenario.id}-${signal}`} 
                      initial={{ opacity: 0, x: -14 }} 
                      animate={{ opacity: 1, x: 0 }} 
                      transition={{ duration: 0.22, delay: index * 0.08 }} 
                      className="flex items-center gap-3 rounded-xl border border-white/5 bg-zinc-900/60 p-2.5 text-xs text-zinc-200"
                    >
                      <ScanLine className={`h-4 w-4 shrink-0 ${currentScenario.riskColor}`} />
                      <span className="font-medium">{signal}</span>
                    </motion.div>
                  ))}
                </div>

                {/* Decision Chip Snapping In */}
                <div className="mt-5 flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
                  <motion.div 
                    key={currentScenario.action}
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.3, delay: 0.3 }}
                    className="flex flex-1 items-center justify-between rounded-xl border border-white/10 bg-zinc-900/90 p-3"
                  >
                    <span className="text-xs font-semibold text-zinc-400">Pre-Auth Decision</span>
                    <span className={`rounded-full px-3 py-1 text-xs font-black tracking-wide uppercase ${currentScenario.actionBg}`}>
                      {currentScenario.action}
                    </span>
                  </motion.div>
                  <Link 
                    href="/dashboard"
                    className="group flex items-center justify-center gap-1.5 rounded-xl border border-orange-500/40 bg-orange-500/10 px-4 py-3 text-xs font-bold text-orange-200 transition hover:border-orange-400 hover:bg-orange-500 hover:text-zinc-950 shadow-sm"
                  >
                    Inspect Studio <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </Link>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* FOUR ACTS WITH SCROLL SPINE */}
      <section id="story" className="relative px-5 pb-28 pt-10 md:px-10">
        <div className="mx-auto max-w-7xl">
          <div className="mb-16 max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-300 flex items-center gap-2">
              <BrainCircuit className="h-4 w-4 text-orange-400" />
              One payment. Four acts.
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-5xl">
              Scroll through the defence.
            </h2>
            <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
              Trace the end-to-end lifecycle of payment defense: from signal ingestion and multi-layer inference to human-in-the-loop validation and closed-loop retraining.
            </p>
          </div>

          <div className="grid gap-8 lg:grid-cols-[0.4fr_.6fr]">
            {/* Left Column: Interactive Scroll Spine Milestone Navigator */}
            <div className="hidden lg:block">
              <div className="sticky top-28 rounded-3xl border border-orange-500/20 bg-zinc-950/85 p-8 shadow-2xl backdrop-blur-xl">
                <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
                  <span className="text-xs font-bold uppercase tracking-widest text-orange-300">Defence Chronology</span>
                  <span className="text-[11px] font-mono text-zinc-400">Act {activeAct + 1} of 4</span>
                </div>

                {/* Vertical Scroll Spine Track */}
                <div className="relative pl-6 space-y-7 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-zinc-800">
                  {storySteps.map((step, idx) => {
                    const isCurrent = activeAct === idx;
                    return (
                      <div
                        key={step.number}
                        className={`relative cursor-pointer transition-all ${
                          isCurrent ? "opacity-100 translate-x-1" : "opacity-40 hover:opacity-75"
                        }`}
                        onClick={() => {
                          const el = document.getElementById(`act-${idx}`);
                          el?.scrollIntoView({ behavior: "smooth" });
                        }}
                      >
                        {/* Milestone node along the spine */}
                        <div
                          className={`absolute -left-6 top-1 h-4 w-4 rounded-full border-2 transition-all ${
                            isCurrent
                              ? "border-orange-400 bg-orange-500 shadow-md shadow-orange-500/50 scale-125"
                              : "border-zinc-700 bg-zinc-950"
                          }`}
                        />
                        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-orange-300 block mb-0.5">
                          Act {step.number} • {step.eyebrow}
                        </span>
                        <p className="text-xs font-semibold text-white truncate max-w-[220px]">
                          {step.title}
                        </p>
                      </div>
                    );
                  })}
                </div>

                <div className="mt-8 pt-4 border-t border-white/10">
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    A single payment is continuously analyzed and hardened against adversarial evasion.
                  </p>
                </div>
              </div>
            </div>

            {/* Right Column: Act Cards with Staggered Chip Animations */}
            <div className="space-y-6">
              {storySteps.map((step, index) => (
                <motion.article 
                  id={`act-${index}`}
                  key={step.number} 
                  initial={{ opacity: 0, y: 32 }} 
                  whileInView={{ opacity: 1, y: 0 }} 
                  onViewportEnter={() => setActiveAct(index)}
                  viewport={{ once: false, amount: 0.35 }} 
                  transition={{ duration: 0.55 }} 
                  className="group relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 shadow-2xl backdrop-blur-xl transition-all duration-300 md:p-9"
                >
                  <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                  <div className="flex items-start justify-between gap-5">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-300">
                        {step.number} / {step.eyebrow}
                      </p>
                      <h3 className="mt-3 max-w-xl text-2xl font-bold tracking-tight text-white md:text-3xl">
                        {step.title}
                      </h3>
                    </div>
                    <span className="text-5xl font-black text-white/10 select-none">
                      0{index + 1}
                    </span>
                  </div>
                  <p className="mt-4 max-w-2xl text-sm leading-relaxed text-zinc-300">
                    {step.copy}
                  </p>
                  
                  {/* Staggered Chips Animation */}
                  <div className="mt-6 flex flex-wrap gap-2.5">
                    {step.signals.map((signal, sIdx) => (
                      <motion.span 
                        key={signal} 
                        initial={{ opacity: 0, y: 8 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 + sIdx * 0.08 }}
                        className="rounded-full border border-white/10 bg-zinc-900/80 px-3.5 py-1.5 text-xs text-zinc-200 font-medium hover:border-orange-500/30 transition"
                      >
                        {signal}
                      </motion.span>
                    ))}
                  </div>
                </motion.article>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Operational Proof CTA Section */}
      <section className="relative border-y border-white/10 bg-gradient-to-br from-orange-500/15 via-zinc-950 to-emerald-500/10 px-5 py-24 md:px-10">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-300">
            The operational proof
          </p>
          <h2 className="mt-4 text-4xl font-bold tracking-tight text-white md:text-6xl">
            See the defence make a decision.
          </h2>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-zinc-300">
            Open the live workspace to inspect scenarios, alter payment signals, trace attack networks and record analyst feedback in real time.
          </p>
          <Link 
            href="/dashboard" 
            className="mt-9 inline-flex items-center gap-2 rounded-full bg-orange-500 hover:bg-orange-400 px-8 py-4 text-sm font-bold text-zinc-950 transition shadow-xl shadow-orange-500/25 tracking-wide"
          >
            Open live dashboard <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-5 py-12 md:px-10 bg-zinc-950 border-t border-white/10">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-8 md:flex-row">
          <div>
            <p className="text-sm font-bold tracking-[0.16em] text-white">CHAKRAVYUH</p>
            <p className="mt-2 max-w-sm text-sm text-zinc-400">
              Synthetic payment-fraud generation and explainable detection for the Mastercard Innovation Challenge 2026.
            </p>
          </div>
          <div className="flex flex-wrap gap-6">
            {profileLinks.map(profile => (
              <div key={profile.name} className="flex min-w-52 items-center gap-3">
                <TeamAvatar profile={profile} />
                <div>
                  <p className="text-sm font-semibold text-zinc-200">{profile.name}</p>
                  <p className="mb-2 text-xs text-zinc-500">{profile.role}</p>
                  <div className="flex gap-3">
                    <a href={profile.linkedin} target="_blank" rel="noreferrer" aria-label={`${profile.name} on LinkedIn`} className="text-zinc-500 transition hover:text-[#7ab8f5]">
                      <Linkedin className="h-4 w-4" />
                    </a>
                    <a href={profile.github} target="_blank" rel="noreferrer" aria-label={`${profile.name} on GitHub`} className="text-zinc-500 transition hover:text-white">
                      <Github className="h-4 w-4" />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </footer>
    </main>
  );
}

export default StoryPage;
