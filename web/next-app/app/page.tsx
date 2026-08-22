"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  Lock,
  User,
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
  Cpu
} from "lucide-react";

// Types
interface Scenario {
  description: string;
  expected_attack_id: string | null;
  txn: Record<string, any>;
}

interface AnalysisResult {
  risk_score: number;
  risk_level: string;
  action: string;
  recommended_action: string;
  fraud_probability: number;
  attack_probabilities: Record<string, number>;
  top_attack_family: string;
  top_attack_probability: number;
  contributing_signals: string[];
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
    nodes: Array<{ id: string; label: string; type: string; risk: string; details: Record<string, string>; x: number; y: number }>;
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

interface MetricsResult {
  recorded_metrics: MetricItem[];
  feature_importances: FeatureImportance[];
  adaptive_config: Record<string, any>;
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

export default function AnalystPortal() {
  // Login State
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  // App Configuration State
  const [apiKey, setApiKey] = useState("");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Dashboard Tabs State
  const [activeTab, setActiveTab] = useState<"scoring" | "closed-loop" | "graph">("scoring");

  // Live Scoring State
  const [scenarios, setScenarios] = useState<Record<string, Scenario>>({});
  const [selectedScenarioName, setSelectedScenarioName] = useState("");
  const [txnOverrides, setTxnOverrides] = useState<Record<string, any>>({});
  const [isScoring, setIsScoring] = useState(false);
  const [scoreResult, setScoreResult] = useState<AnalysisResult | null>(null);
  const [scoreError, setScoreError] = useState("");

  // Metrics / Feature Importance State
  const [metricsData, setMetricsData] = useState<MetricsResult | null>(null);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);

  // Graph tab State
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(ATTACK_NODES[0]);
  const [graphViewMode, setGraphViewMode] = useState<"lifecycle" | "transaction">("lifecycle");
  const [selectedTransactionNode, setSelectedTransactionNode] = useState<any>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);

  const submitFeedbackOutcome = async (actualLabel: "fraud" | "legitimate") => {
    if (!scoreResult) return;
    setSubmittingFeedback(true);
    setFeedbackSuccess(false);
    try {
      const res = await fetch("http://localhost:8000/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          txn_id: txnOverrides.txn_id || "demo-txn-1",
          actual_label: actualLabel,
          risk_score: scoreResult.risk_score
        })
      });
      if (res.ok) {
        setFeedbackSuccess(true);
        fetchMetrics(); // Refresh metrics tab instantly
      }
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const clearGraphHistory = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/graph/clear", { method: "POST" });
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
      const res = await fetch("http://localhost:8000/api/scenarios");
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
      const res = await fetch("http://localhost:8000/api/metrics");
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

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (username === "admin" && password === "chakravyuh2026") {
      setIsLoggedIn(true);
      setLoginError("");
    } else {
      setLoginError("Invalid credentials. Access Denied.");
    }
  };

  const runScoringAssessment = async () => {
    setIsScoring(true);
    setScoreError("");
    try {
      const res = await fetch("http://localhost:8000/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transaction: txnOverrides,
          api_key: apiKey || null
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Assessment failed");
      }

      const result = await res.json();
      setScoreResult(result);
      setFeedbackSuccess(false); // Reset feedback success state
      if (result.network_graph?.nodes?.length > 0) {
        setSelectedTransactionNode(result.network_graph.nodes[0]);
      }
    } catch (err: any) {
      setScoreError(err.message || "Failed to run risk assessment. Make sure backend is running.");
    } finally {
      setIsScoring(false);
    }
  };

  const updateOverrideField = (field: string, val: any) => {
    setTxnOverrides(prev => ({
      ...prev,
      [field]: val
    }));
  };

  if (!isLoggedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-6 relative overflow-hidden">
        {/* Abstract Cyber Grid Background */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,95,0,0.1),transparent_70%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f0f15_1px,transparent_1px),linear-gradient(to_bottom,#0f0f15_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

        <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900/80 p-8 shadow-2xl backdrop-blur-xl relative z-10 animate-fade-in">
          <div className="flex flex-col items-center mb-8">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg shadow-orange-600/20">
              <Shield className="h-7 w-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">CHAKRAVYUH</h1>
            <p className="text-sm text-zinc-400 mt-1 text-center">Mastercard Fraud Prevention Analyst Portal</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">Username</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-500">
                  <User className="h-4 w-4" />
                </span>
                <input
                  type="text"
                  required
                  placeholder="admin"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 pl-10 pr-4 py-3 text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-orange-500 focus:ring-1 focus:ring-orange-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">Security Password</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-500">
                  <Lock className="h-4 w-4" />
                </span>
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 pl-10 pr-4 py-3 text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-orange-500 focus:ring-1 focus:ring-orange-500"
                />
              </div>
            </div>

            {loginError && (
              <div className="flex items-center gap-2 rounded-xl bg-red-950/50 border border-red-800/60 p-3 text-sm text-red-400">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{loginError}</span>
              </div>
            )}

            <button
              type="submit"
              className="w-full rounded-xl bg-[#ff5f00] py-3.5 font-bold text-white transition hover:bg-[#ff5f00]/90 active:scale-98 shadow-sm border border-[#ff5f00]"
            >
              Sign In to Portal
            </button>
          </form>
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
        </nav>

        {/* Right side settings/logout */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center justify-center p-2.5 rounded-xl border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition"
            title="Configure Gemini API"
          >
            <Settings className="h-4 w-4" />
          </button>
          <button
            onClick={() => setIsLoggedIn(false)}
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
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 backdrop-blur-md">
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">
                  Select Simulation Scenario
                </label>
                {Object.keys(scenarios).length === 0 ? (
                  <div className="h-11 bg-zinc-950 rounded-xl animate-pulse" />
                ) : (
                  <select
                    value={selectedScenarioName}
                    onChange={(e) => setSelectedScenarioName(e.target.value)}
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
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 backdrop-blur-md flex-1 flex flex-col gap-5">
                <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider border-b border-zinc-800 pb-2">
                  Override Parameter Signals
                </h3>

                {/* Amount */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-2">
                    <span className="text-zinc-400">Transaction Amount (INR)</span>
                    <span className="text-zinc-200 font-mono">₹{parseFloat(txnOverrides.amount || 0).toLocaleString()}</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="150000"
                    step="100"
                    value={txnOverrides.amount || 0}
                    onChange={(e) => updateOverrideField("amount", parseFloat(e.target.value))}
                    className="w-full accent-orange-500"
                  />
                </div>

                {/* Graph Edge Count */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-2">
                    <span className="text-zinc-400">Graph Edge Count (Payer-Payee Linkage)</span>
                    <span className="text-zinc-200 font-mono">{txnOverrides.edge_count || 0}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="50"
                    step="1"
                    value={txnOverrides.edge_count || 0}
                    onChange={(e) => updateOverrideField("edge_count", parseFloat(e.target.value))}
                    className="w-full accent-orange-500"
                  />
                </div>

                {/* PIN Attempts */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-2">
                    <span className="text-zinc-400">Failed PIN Attempts</span>
                    <span className="text-zinc-200 font-mono">{txnOverrides.pin_attempts || 0}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="5"
                    step="1"
                    value={txnOverrides.pin_attempts || 0}
                    onChange={(e) => updateOverrideField("pin_attempts", parseInt(e.target.value))}
                    className="w-full accent-orange-500"
                  />
                </div>

                {/* Beneficiary age (in days) */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-2">
                    <span className="text-zinc-400">Beneficiary Age (Time since addition)</span>
                    <span className="text-zinc-200 font-mono">
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
                    className="w-full accent-orange-500"
                  />
                </div>

                {/* Toggles Grid */}
                <div className="grid grid-cols-2 gap-4 mt-2">
                  <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 cursor-pointer hover:border-zinc-700 transition">
                    <input
                      type="checkbox"
                      checked={!!txnOverrides.screen_share_active}
                      onChange={(e) => updateOverrideField("screen_share_active", e.target.checked)}
                      className="accent-orange-500 h-4 w-4 rounded"
                    />
                    <span className="text-xs font-medium text-zinc-300">Screen Sharing</span>
                  </label>

                  <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 cursor-pointer hover:border-zinc-700 transition">
                    <input
                      type="checkbox"
                      checked={!!txnOverrides.call_active_during_txn}
                      onChange={(e) => updateOverrideField("call_active_during_txn", e.target.checked)}
                      className="accent-orange-500 h-4 w-4 rounded"
                    />
                    <span className="text-xs font-medium text-zinc-300">Active Call</span>
                  </label>

                  <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 cursor-pointer hover:border-zinc-700 transition">
                    <input
                      type="checkbox"
                      checked={!!txnOverrides.accessibility_service_active}
                      onChange={(e) => updateOverrideField("accessibility_service_active", e.target.checked)}
                      className="accent-orange-500 h-4 w-4 rounded"
                    />
                    <span className="text-xs font-medium text-zinc-300">Accessibility API</span>
                  </label>

                  <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 cursor-pointer hover:border-zinc-700 transition">
                    <input
                      type="checkbox"
                      checked={!!txnOverrides.ip_is_proxy}
                      onChange={(e) => updateOverrideField("ip_is_proxy", e.target.checked)}
                      className="accent-orange-500 h-4 w-4 rounded"
                    />
                    <span className="text-xs font-medium text-zinc-300">Proxy/VPN IP</span>
                  </label>
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
                  <div className="flex items-center gap-2 p-3 text-sm text-red-400 bg-red-950/30 border border-red-900/60 rounded-xl">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>{scoreError}</span>
                  </div>
                )}
              </div>
            </section>

            {/* Results Panel - 7 Cols */}
            <section className="lg:col-span-7 flex flex-col gap-6">
              {!scoreResult ? (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/20 p-8 backdrop-blur-md flex flex-col items-center justify-center text-center flex-1 min-h-[400px]">
                  <Shield className="h-16 w-16 text-zinc-700 mb-4 animate-pulse" />
                  <h3 className="text-lg font-semibold text-zinc-400">Studio Ingestion Ready</h3>
                  <p className="text-sm text-zinc-500 max-w-sm mt-2">
                    Review and adjust the transaction override parameters on the left and execute the assessment to run live ML decision and GenAI analyst logic.
                  </p>
                </div>
              ) : (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md flex-1 flex flex-col gap-6 animate-fade-in">
                  
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
                            {scoreResult.risk_score.toFixed(0)}
                          </span>
                          <span className="text-[10px] text-zinc-500 block font-semibold uppercase tracking-wider">
                            / 100
                          </span>
                        </div>
                      </div>
                      <span className="text-[10px] text-zinc-400 mt-2 font-bold tracking-widest uppercase">Risk Assessment</span>
                    </div>

                    {/* Threat Details */}
                    <div className="flex flex-col gap-1 md:border-l md:border-zinc-800 md:pl-6">
                      <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Risk Level</span>
                      <span className={`text-2xl font-black ${
                        scoreResult.risk_level === "CRITICAL" || scoreResult.risk_level === "HIGH"
                          ? "text-red-500 animate-pulse"
                          : scoreResult.risk_level === "MEDIUM"
                          ? "text-orange-500"
                          : "text-emerald-500"
                      }`}>
                        {scoreResult.risk_level}
                      </span>
                      <span className="text-xs text-zinc-400 mt-1">
                        Confidence: {(scoreResult.model_confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    {/* Decision Action */}
                    <div className="flex flex-col gap-2 md:border-l md:border-zinc-800 md:pl-6">
                      <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Recommended Action</span>
                      <div className={`inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-black border tracking-wider ${
                        scoreResult.recommended_action === "BLOCK"
                          ? "bg-red-500/10 border-red-500/30 text-red-400"
                          : scoreResult.recommended_action === "REVIEW"
                          ? "bg-orange-500/10 border-orange-500/30 text-orange-400"
                          : "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                      }`}>
                        <CheckCircle className="h-4 w-4" />
                        {scoreResult.recommended_action}
                      </div>
                    </div>
                  </div>

                  {/* Predicted Attack Family Card */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                        Top Predicted Attack Vector
                      </span>
                      <h4 className="text-base font-bold text-white capitalize">
                        {scoreResult.top_attack_family.replace(/_/g, " ")}
                      </h4>
                    </div>
                    <div className="text-right">
                      <span className="text-2xl font-black text-orange-500 font-mono">
                        {(scoreResult.top_attack_probability * 100).toFixed(1)}%
                      </span>
                      <span className="text-[9px] text-zinc-500 block uppercase tracking-wider font-bold">Classifier Match</span>
                    </div>
                  </div>

                  {/* Signals List */}
                  <div>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-2">
                      Contributing Risk Signals
                    </span>
                    {scoreResult.contributing_signals.length === 0 ? (
                      <span className="text-sm text-zinc-500 italic block p-3 rounded-xl bg-zinc-950/20 border border-zinc-900">
                        No critical indicators triggered. Normal behavior profile.
                      </span>
                    ) : (
                      <div className="space-y-2">
                        {scoreResult.contributing_signals.map((sig, idx) => (
                          <div
                            key={idx}
                            className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/40 border border-zinc-800 text-sm font-medium text-zinc-300 hover:border-zinc-700 transition"
                          >
                            <AlertTriangle className="h-4 w-4 text-orange-500 shrink-0" />
                            <span>{sig}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Analyst Narrative */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 mt-auto">
                    <div className="flex items-center justify-between mb-3 border-b border-zinc-800 pb-2.5">
                      <div className="flex items-center gap-2">
                        <Cpu className="h-4 w-4 text-orange-500" />
                        <span className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">
                          Chakravyuh AI Analyst Insight
                        </span>
                      </div>
                      {!apiKey && (
                        <span className="text-[9px] font-semibold bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
                          Mock Simulation
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-zinc-300 leading-relaxed">
                      {scoreResult.llm_analysis.fraud_explanation}
                    </p>
                    <p className="text-xs text-zinc-400 italic mt-3 border-t border-zinc-800/50 pt-2.5">
                      {scoreResult.llm_analysis.attack_family_interpretation}
                    </p>

                    {/* Investigation Steps & Caveats */}
                    <div className="mt-4 border-t border-zinc-800/80 pt-4 space-y-4">
                      <div>
                        <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest block mb-2">
                          Analyst Action Checklist
                        </span>
                        <ul className="space-y-1.5">
                          {scoreResult.llm_analysis.investigation_steps.map((step, sIdx) => (
                            <li key={sIdx} className="flex items-start gap-2 text-xs text-zinc-400">
                              <ChevronRight className="h-3.5 w-3.5 text-orange-500 shrink-0 mt-0.5" />
                              <span>{step}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="text-[10px] text-zinc-500 flex gap-1.5 items-start bg-zinc-950/40 p-2.5 rounded-lg border border-zinc-900">
                        <Info className="h-3.5 w-3.5 text-zinc-500 shrink-0 mt-0.5" />
                        <span>{scoreResult.llm_analysis.uncertainty_caveats}</span>
                      </div>
                    </div>
                  </div>

                  {/* Closed-Loop Analyst Feedback Loop */}
                  <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 border-t-2 border-t-orange-600/50">
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                      Closed-Loop Analyst Feedback Loop
                    </span>
                    <p className="text-xs text-zinc-400 mb-3">
                      Submit the actual outcome of this transaction to train the model. This triggers an online retraining pass and updates the metrics.
                    </p>
                    {feedbackSuccess ? (
                      <div className="flex items-center gap-3 p-3 rounded-xl bg-emerald-950/20 border border-emerald-900/50 text-sm text-emerald-400">
                        <CheckCircle className="h-5 w-5 shrink-0" />
                        <div>
                          <p className="font-bold">Feedback Incorporated Successfully!</p>
                          <p className="text-[11px] text-emerald-500 mt-0.5">XGBoost updated with sample weight 100. Metrics refreshed in the Closed-Loop tab.</p>
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
                  </div>

                </div>
              )}
            </section>
          </div>
        )}

        {/* TAB 2: CLOSED-LOOP INTELLIGENCE */}
        {activeTab === "closed-loop" && (
          <div className="space-y-6 animate-fade-in">
            {/* Concept explainer */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
              <h2 className="text-lg font-bold text-white mb-2">What is the Closed-Loop Cycle?</h2>
              <p className="text-sm text-zinc-400 leading-relaxed">
                The **Chakravyuh Closed Loop** describes our adaptive, adversarial security cycle. 
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
                      The ML detector's features are audited. Features that form "tells" (like fixed ASN blocks or shallow-copy lookalikes) are identified.
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
                      The detector retrains on these newly optimized, adaptive evasion campaigns. This raises the detection floor, forcing the attacker's cost up.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Performance Metrics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {metricsData?.recorded_metrics.map((item, idx) => (
                <div key={idx} className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 backdrop-blur-md flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                      {item.metric}
                    </span>
                    <span className="text-3xl font-black text-white font-mono">
                      {(item.value * 100).toFixed(2)}%
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
                  <svg className="w-full h-full min-h-[440px]">
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
                            d={`M ${src.x}% ${src.y}% Q ${(src.x + dest.x)/2}% ${(src.y + dest.y)/2 - 4}% ${dest.x}% ${dest.y}%`}
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
                            d={`M ${src.x}% ${src.y}% Q ${(src.x + dest.x)/2}% ${(src.y + dest.y)/2 + 3}% ${dest.x}% ${dest.y}%`}
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
                            d={`M ${src.x}% ${src.y}% L ${dest.x}% ${dest.y}%`}
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
                            d={`M ${src.x}% ${src.y}% Q ${(src.x + dest.x)/2}% ${(src.y + dest.y)/2 + 2}% ${dest.x}% ${dest.y}%`}
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
                          Go to the Risk Scoring Studio, choose a simulation scenario, click "Run Risk Assessment", and return to visualize its dynamic counterparty connections.
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
                          <svg className="w-full h-full min-h-[350px]">
                            <defs>
                              <marker
                                id="txn-arrow"
                                viewBox="0 0 10 10"
                                refX="18"
                                refY="5"
                                markerWidth="6"
                                markerHeight="6"
                                orient="auto-start-reverse"
                              >
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#52525b" />
                              </marker>
                              <marker
                                id="txn-arrow-red"
                                viewBox="0 0 10 10"
                                refX="18"
                                refY="5"
                                markerWidth="6"
                                markerHeight="6"
                                orient="auto-start-reverse"
                              >
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                              </marker>
                            </defs>

                            {/* Draw connection edges */}
                            {scoreResult.network_graph.edges.map((edge, eIdx) => {
                              const srcNode = scoreResult.network_graph.nodes.find(n => n.id === edge.source);
                              const destNode = scoreResult.network_graph.nodes.find(n => n.id === edge.target);
                              if (!srcNode || !destNode) return null;
                              
                              const srcPos = { x: srcNode.x, y: srcNode.y };
                              const destPos = { x: destNode.x, y: destNode.y };
                              
                              const isAlert = edge.status === "critical" || edge.status === "high";
                              const isLinkage = edge.status === "linkage";
                              
                              let strokeColor = "#27272a";
                              if (isAlert) strokeColor = "#ef4444";
                              else if (edge.status === "medium" || edge.status === "warning") strokeColor = "#f97316";
                              else if (isLinkage) strokeColor = "#10b981"; // Clean green line for campaign links!
                              
                              return (
                                <g key={eIdx}>
                                  <line
                                    x1={`${srcPos.x}%`}
                                    y1={`${srcPos.y}%`}
                                    x2={`${destPos.x}%`}
                                    y2={`${destPos.y}%`}
                                    stroke={strokeColor}
                                    strokeWidth={isLinkage ? "2" : isAlert ? "2" : "1.2"}
                                    strokeDasharray={isLinkage ? "4 4" : isAlert ? "4 4" : "0"}
                                    markerEnd={isLinkage ? undefined : `url(#${isAlert ? "txn-arrow-red" : "txn-arrow"})`}
                                    className="transition-all duration-300"
                                  />
                                  {/* Edge text label */}
                                  <text
                                    x={`${(srcPos.x + destPos.x) / 2}%`}
                                    y={`${(srcPos.y + destPos.y) / 2 - 2}%`}
                                    fill={isLinkage ? "#10b981" : "#a1a1aa"}
                                    fontSize="8"
                                    fontWeight="bold"
                                    textAnchor="middle"
                                    className="bg-zinc-950 px-1 select-none"
                                  >
                                    {edge.label}
                                  </text>
                                </g>
                              );
                            })}

                            {/* Draw transaction nodes */}
                            {scoreResult.network_graph.nodes.map((node) => {
                              const isSelected = selectedTransactionNode && selectedTransactionNode.id === node.id;
                              
                              let strokeColor = "#27272a";
                              if (node.risk === "critical" || node.risk === "high") strokeColor = "#ef4444";
                              else if (node.risk === "medium" || node.risk === "warning") strokeColor = "#f97316";
                              else if (node.risk === "low") strokeColor = "#10b981";
                              
                              return (
                                <g
                                  key={node.id}
                                  onClick={() => setSelectedTransactionNode(node)}
                                  className="cursor-pointer group"
                                >
                                  <circle
                                    cx={`${node.x}%`}
                                    cy={`${node.y}%`}
                                    r={isSelected ? "16" : "13"}
                                    fill="#09090b"
                                    stroke={isSelected ? "#ff5f00" : strokeColor}
                                    strokeWidth={isSelected ? "3" : "2"}
                                    className="transition-all duration-300"
                                  />
                                  <text
                                    x={`${node.x}%`}
                                    y={`${node.y + 6}%`}
                                    fill={isSelected ? "#ffffff" : "#a1a1aa"}
                                    fontSize="8"
                                    fontWeight="bold"
                                    textAnchor="middle"
                                    className="transition-colors duration-300 select-none group-hover:fill-white"
                                  >
                                    {node.label}
                                  </text>
                                </g>
                              );
                            })}
                          </svg>
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
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-900 bg-zinc-950 py-4 text-center text-[10px] text-zinc-600">
        © 2026 Chakravyuh Analyst Portal. Secure Area. Unauthorized access is strictly prohibited.
      </footer>

      {/* Settings Modal (Gemini API Config) */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl relative">
            <button
              onClick={() => setIsSettingsOpen(false)}
              className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-600/10 text-orange-500">
                <Cpu className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">GenAI Configuration</h3>
                <p className="text-xs text-zinc-400 mt-0.5">Setup Gemini API Key for Analyst Narratives</p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                  Google Gemini API Key
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-500">
                    <Key className="h-4 w-4" />
                  </span>
                  <input
                    type="password"
                    placeholder="AIzaSy..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="w-full rounded-xl border border-zinc-700 bg-zinc-950 pl-10 pr-4 py-3 text-zinc-200 placeholder-zinc-700 outline-none transition focus:border-orange-500"
                  />
                </div>
                <p className="text-[10px] text-zinc-500 mt-2 leading-relaxed">
                  Key is saved in memory during your active session. If left blank, the portal will use an intelligent local rule-based analyst simulator.
                </p>
              </div>

              <button
                onClick={() => setIsSettingsOpen(false)}
                className="w-full rounded-xl bg-zinc-800 py-3 font-semibold text-white transition hover:bg-zinc-750 mt-2 border border-zinc-750"
              >
                Save Settings
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
