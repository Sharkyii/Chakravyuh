"use client";

import React, { useState } from "react";
import {
  CheckCircle,
  AlertTriangle,
  HelpCircle,
  Zap,
  TrendingUp,
  Send,
  RotateCw,
} from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface SHAPFeature {
  name: string;
  value: number;
  contribution: number;
  direction: string;
}

interface Transaction {
  amount: number;
  payee_id: string;
  payer_id: string;
  timestamp: string;
  channel: string;
  auth_method: string;
}

interface AnalystVerdictData {
  verdict: string;
  confidence: number;
  reasoning: string;
  key_signals: string[];
  patterns: string[];
}

interface ModelInfo {
  model: string;
  family: string;
  type: string;
}

export default function AnalystFeedbackPage() {
  const [fraudScore, setFraudScore] = useState(0.87);
  const [analysisResult, setAnalysisResult] = useState<{
    verdict: AnalystVerdictData;
    model_info: ModelInfo;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState<any>(null);
  const [analystVerdictOverride, setAnalystVerdictOverride] = useState<string | null>(null);
  const [confidence, setConfidence] = useState(0.8);
  const [reasoning, setReasoning] = useState("");
  const [retraining, setRetraining] = useState(false);
  const [retrainOutcome, setRetrainOutcome] = useState<"success" | "queued" | null>(null);
  const [modelHistory, setModelHistory] = useState<any[]>([]);

  // Demo transaction with SHAP features
  const demoTransaction: Transaction = {
    amount: 50000,
    payee_id: "payee_42189",
    payer_id: "payer_18392",
    timestamp: "2026-08-24T03:15:00Z",
    channel: "UPI",
    auth_method: "PIN",
  };

  const demoSHAPFeatures: SHAPFeature[] = [
    {
      name: "edge_count",
      value: 2.1,
      contribution: 0.15,
      direction: "increases_fraud_score",
    },
    {
      name: "beneficiary_added_ago_s",
      value: 259200,
      contribution: 0.12,
      direction: "increases_fraud_score",
    },
    {
      name: "txn_count_last_1h",
      value: 5,
      contribution: 0.08,
      direction: "increases_fraud_score",
    },
  ];

  const handleAnalyze = async () => {
    setLoading(true);
    setSubmitted(false);
    setAnalystVerdictOverride(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyst/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fraud_score: fraudScore,
          shap_features: demoSHAPFeatures,
          transaction: demoTransaction,
        }),
      });

      const result = await response.json();
      if (result.status === "success") {
        setAnalysisResult(result);
      } else {
        alert(`Error: ${result.message}`);
      }
    } catch (error) {
      console.error("Analysis error:", error);
      alert("Failed to get analyst review");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitVerdict = async () => {
    if (!analysisResult) return;

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyst/submit-verdict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transaction_id: `txn_${Date.now()}`,
          verdict: analystVerdictOverride || analysisResult.verdict.verdict,
          confidence,
          reasoning: reasoning || analysisResult.verdict.reasoning,
          key_signals: analysisResult.verdict.key_signals,
          patterns: analysisResult.verdict.patterns,
        }),
      });

      const result = await response.json();
      setSubmitted(true);
      setFeedbackStatus(result.feedback_summary);

      // Check status after submission
      await checkFeedbackStatus();
    } catch (error) {
      console.error("Submit error:", error);
      alert("Failed to submit verdict");
    } finally {
      setLoading(false);
    }
  };

  const checkFeedbackStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyst/feedback-status`);
      const result = await response.json();
      setFeedbackStatus(result.feedback_summary);
    } catch (error) {
      console.error("Status check error:", error);
    }
  };

  const checkModelHistory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyst/model-history`);
      const result = await response.json();
      if (result.history) setModelHistory(result.history);
    } catch (error) {
      console.error("Model history fetch error:", error);
    }
  };

  const handleTriggerRetrain = async () => {
    setRetraining(true);
    setRetrainOutcome(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyst/trigger-retrain`, { method: "POST" });
      const result = response.ok ? await response.json().catch(() => null) : null;
      if (result?.status === "success") {
        setRetrainOutcome("success");
        await checkFeedbackStatus();
        await checkModelHistory();
      } else {
        console.warn("Retrain request did not complete:", response.status, result);
        setRetrainOutcome("queued");
      }
    } catch (error) {
      console.error("Retrain error:", error);
      setRetrainOutcome("queued");
    } finally {
      setRetraining(false);
    }
  };

  React.useEffect(() => {
    checkFeedbackStatus();
    checkModelHistory();
  }, []);

  return (
    <div className="relative min-h-screen bg-[#08090b] p-6 md:p-10 text-zinc-100 font-sans selection:bg-orange-500/30 overflow-x-hidden">
      {/* Ambient background glow & grid matching front page */}
      <div className="story-grid pointer-events-none absolute inset-0 opacity-50" />
      <div className="pointer-events-none absolute left-[10%] top-[12%] h-96 w-96 rounded-full bg-orange-500/15 blur-[140px]" />
      <div className="pointer-events-none absolute right-[8%] top-[35%] h-80 w-80 rounded-full bg-amber-500/10 blur-[130px]" />
      <div className="pointer-events-none absolute bottom-[10%] left-[25%] h-96 w-96 rounded-full bg-emerald-500/10 blur-[140px]" />

      <div className="relative max-w-6xl mx-auto">
        {/* Top Breadcrumb Navigation */}
        <div className="mb-6 flex items-center justify-between">
          <a
            href="/dashboard"
            className="group inline-flex items-center gap-2 rounded-full border border-orange-400/40 bg-zinc-900/80 px-4 py-2 text-xs font-semibold text-zinc-200 backdrop-blur transition hover:border-orange-400 hover:text-white hover:bg-orange-500/15 shadow-sm"
          >
            ← Back to Dashboard
          </a>
          <span className="rounded-full border border-orange-400/40 bg-orange-500/10 px-3.5 py-1 text-xs font-bold text-orange-200">
            Active Learning Loop
          </span>
        </div>

        {/* Header */}
        <div className="mb-8">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-300 flex items-center gap-2 mb-2">
            <Zap className="h-3.5 w-3.5" />
            Supervised Feedback Pipeline
          </p>
          <h1 className="text-3xl md:text-5xl font-bold text-white tracking-tight mb-3">Analyst Feedback & Retraining Loop</h1>
          <p className="text-zinc-400 text-sm max-w-2xl leading-relaxed">
            Review flagged edge-case transactions with SHAP feature attributions. Log ground-truth verdicts to automatically trigger curriculum retraining.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Analysis Panel */}
          <div className="lg:col-span-2 space-y-6">
            {/* Transaction Card */}
            <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
              <h2 className="text-sm font-bold text-white uppercase tracking-[0.16em] mb-5 flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-orange-400 animate-pulse" />
                  Transaction Under Review
                </span>
                <span className="text-[11px] font-mono text-zinc-400 font-normal bg-zinc-900/90 px-3 py-1 rounded-full border border-white/10">ID: txn_live_9481</span>
              </h2>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-4 rounded-2xl border border-white/10 bg-zinc-900/60 hover:border-orange-500/30 transition">
                  <span className="text-[11px] text-orange-300 font-bold uppercase tracking-widest block">Amount</span>
                  <p className="text-2xl font-bold text-white mt-1 font-mono">₹{demoTransaction.amount.toLocaleString()}</p>
                </div>
                <div className="p-4 rounded-2xl border border-white/10 bg-zinc-900/60 hover:border-orange-500/30 transition">
                  <span className="text-[11px] text-orange-300 font-bold uppercase tracking-widest block">Payment Rail</span>
                  <p className="text-2xl font-bold text-white mt-1">{demoTransaction.channel}</p>
                </div>
                <div className="p-4 rounded-2xl border border-white/10 bg-zinc-900/60 hover:border-orange-500/30 transition">
                  <span className="text-[11px] text-zinc-400 font-bold uppercase tracking-widest block">Payer Account</span>
                  <p className="text-xs font-mono text-zinc-200 mt-1 font-semibold">{demoTransaction.payer_id}</p>
                </div>
                <div className="p-4 rounded-2xl border border-white/10 bg-zinc-900/60 hover:border-orange-500/30 transition">
                  <span className="text-[11px] text-zinc-400 font-bold uppercase tracking-widest block">Payee / Beneficiary</span>
                  <p className="text-xs font-mono text-zinc-200 mt-1 font-semibold">{demoTransaction.payee_id}</p>
                </div>
              </div>

              {/* Fraud Score Slider */}
              <div className="border-t border-white/10 pt-5">
                <div className="flex justify-between items-center mb-2.5">
                  <label className="text-xs text-zinc-300 font-bold uppercase tracking-wider">Model Calculated Fraud Probability</label>
                  <span className="text-2xl font-black text-orange-400 font-mono">
                    {(fraudScore * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={fraudScore}
                    onChange={(e) => setFraudScore(parseFloat(e.target.value))}
                    style={{
                      background: `linear-gradient(to right, #f97316 0%, #f59e0b ${fraudScore * 100}%, #27272a ${fraudScore * 100}%, #27272a 100%)`
                    }}
                    className="w-full h-2 rounded-full appearance-none cursor-pointer accent-orange-500 shadow-inner transition-all"
                  />
                </div>
              </div>
            </div>

            {/* SHAP Features */}
            <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
              <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
              <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em] mb-5 flex items-center gap-2">
                <Zap className="h-4 w-4 text-orange-400" />
                Top Contributing Fraud Signals (SHAP Attribution)
              </h3>
              <div className="space-y-3">
                {demoSHAPFeatures.map((feature) => (
                  <div key={feature.name} className="flex items-center justify-between p-4 rounded-2xl bg-zinc-900/60 border border-white/10 hover:border-orange-400/40 transition">
                    <div>
                      <p className="font-bold text-white text-xs">{feature.name.replace(/_/g, " ")}</p>
                      <p className="text-[11px] text-zinc-400 mt-0.5 font-mono">Observed: {typeof feature.value === "number" && feature.value > 1000 ? (feature.value / 86400).toFixed(1) + " days" : feature.value.toFixed(2)}</p>
                    </div>
                    <div className="text-right flex items-center gap-3">
                      <div className="w-28 h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-orange-500 rounded-full"
                          style={{ width: `${feature.contribution * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono font-bold text-orange-300 w-14 text-right">+{(feature.contribution * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Analysis Button */}
            {!analysisResult && (
              <button
                onClick={handleAnalyze}
                disabled={loading}
                className="w-full py-4 rounded-2xl bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-zinc-950 font-bold flex items-center justify-center gap-2 transition shadow-xl shadow-orange-500/25 text-sm tracking-wide"
              >
                {loading ? (
                  <>
                    <RotateCw className="h-4 w-4 animate-spin" />
                    Generating Intelligent Assessment...
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4 fill-zinc-950" />
                    Generate GenAI Decision Note
                  </>
                )}
              </button>
            )}

            {/* Analysis Result */}
            {analysisResult && (
              <div className="relative overflow-hidden rounded-3xl border border-orange-400/50 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/10 animate-fade-in">
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                <div className="flex items-center justify-between mb-5 pb-3.5 border-b border-white/10">
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-orange-500 text-zinc-950">
                      {analysisResult.model_info.type}
                    </span>
                    Decision Explanation
                  </h3>
                  <p className="text-xs text-zinc-400 font-mono">{analysisResult.model_info.model}</p>
                </div>

                <div className="space-y-5">
                  <div className={`p-5 rounded-2xl border ${
                    analysisResult.verdict.verdict === "FRAUD"
                      ? "bg-red-950/40 border-red-500/50 text-red-300"
                      : "bg-emerald-950/40 border-emerald-500/50 text-emerald-300"
                  }`}>
                    <div className="flex items-center justify-between">
                      <p className="font-bold text-sm">Automated Triage Recommendation</p>
                      <span className={`text-xl font-bold font-mono ${
                        analysisResult.verdict.verdict === "FRAUD" ? "text-red-400" : "text-emerald-400"
                      }`}>
                        {analysisResult.verdict.verdict}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">Model Confidence: {(analysisResult.verdict.confidence * 100).toFixed(0)}%</p>
                  </div>

                  <div className="p-4 rounded-2xl bg-zinc-900/70 border border-white/10">
                    <p className="text-xs text-zinc-200 leading-relaxed italic">&quot;{analysisResult.verdict.reasoning}&quot;</p>
                  </div>

                  <div>
                    <p className="text-xs font-bold text-orange-300 uppercase tracking-widest mb-2.5">Key Signals</p>
                    <div className="flex flex-wrap gap-2">
                      {analysisResult.verdict.key_signals.map((signal) => (
                        <span key={signal} className="px-3 py-1.5 rounded-full text-xs bg-zinc-900 border border-white/10 text-zinc-200 font-medium">
                          {signal}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-bold text-orange-300 uppercase tracking-widest mb-2.5">Pattern Indicators</p>
                    <ul className="space-y-2">
                      {analysisResult.verdict.patterns.map((pattern, i) => (
                        <li key={i} className="text-xs text-zinc-300 flex items-start gap-2.5 p-2.5 rounded-xl bg-zinc-900/50 border border-white/5">
                          <span className="h-1.5 w-1.5 rounded-full bg-orange-400 mt-1.5 shrink-0" />
                          <span>{pattern}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Sidebar: Analyst Verdict */}
          <div className="space-y-6">
            {/* Feedback Status */}
            {feedbackStatus && (
              <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em] mb-5 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-orange-400" />
                  Feedback Ingestion Status
                </h3>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between p-3.5 rounded-2xl bg-zinc-900/60 border border-white/10">
                    <span className="text-zinc-400 font-medium">Total Logged Verdicts</span>
                    <span className="font-bold text-white font-mono">{feedbackStatus.total_feedback}</span>
                  </div>
                  <div className="flex justify-between p-3.5 rounded-2xl bg-zinc-900/60 border border-white/10">
                    <span className="text-zinc-400 font-medium">Fraud Confirmed</span>
                    <span className="font-bold text-red-400 font-mono">{feedbackStatus.fraud_confirmed}</span>
                  </div>
                  <div className="flex justify-between p-3.5 rounded-2xl bg-zinc-900/60 border border-white/10">
                    <span className="text-zinc-400 font-medium">Legitimate Confirmed</span>
                    <span className="font-bold text-emerald-400 font-mono">{feedbackStatus.legitimate_confirmed}</span>
                  </div>
                  {feedbackStatus.should_retrain && (
                    <div className="mt-4 p-5 rounded-2xl bg-orange-500/10 border border-orange-500/30">
                      {retrainOutcome === "success" ? (
                        <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                          <CheckCircle className="h-4 w-4 shrink-0" />
                          Model successfully retrained on the latest feedback.
                        </div>
                      ) : retrainOutcome === "queued" ? (
                        <div className="flex items-center gap-2 text-orange-300 font-bold text-xs">
                          <RotateCw className="h-4 w-4 shrink-0" />
                          Retraining queued — feedback saved for the next cycle.
                        </div>
                      ) : (
                        <>
                          <p className="text-orange-300 font-bold text-xs mb-2.5">✓ Retraining Threshold Met</p>
                          <button
                            onClick={handleTriggerRetrain}
                            disabled={retraining}
                            className="w-full py-3 rounded-full bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-zinc-950 font-bold flex items-center justify-center gap-2 transition text-xs shadow-lg shadow-orange-500/20"
                          >
                            {retraining ? (
                              <>
                                <RotateCw className="h-4 w-4 animate-spin" />
                                Retraining Model...
                              </>
                            ) : (
                              <>
                                <TrendingUp className="h-4 w-4" />
                                Trigger Model Retrain
                              </>
                            )}
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Model History Comparison */}
            {modelHistory.length > 0 && (
              <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em] mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-orange-400" /> Model Evolution History
                </h3>
                <div className="space-y-3">
                  {modelHistory.map((meta: any, idx: number) => (
                    <div key={idx} className="p-4 rounded-2xl bg-zinc-900/60 border border-white/10 hover:border-orange-500/30 transition">
                      <p className="text-xs font-bold text-orange-300 mb-2.5">{meta.label} <span className="text-[11px] text-zinc-400 font-mono font-normal">({meta.version})</span></p>
                      <div className="grid grid-cols-2 gap-3 text-[11px]">
                        <div>
                          <span className="text-zinc-400">PR-AUC</span>
                          <p className="text-white font-bold font-mono text-xs">{(meta.pr_auc * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-zinc-400">Precision</span>
                          <p className="text-white font-bold font-mono text-xs">{(meta.precision * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-zinc-400">Test Recall</span>
                          <p className="text-white font-bold font-mono text-xs">{(meta.recall * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-zinc-400">Evasion Rate</span>
                          <p className="text-red-400 font-bold font-mono text-xs">{(meta.evasion_rate * 100).toFixed(1)}%</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Analyst Verdict Form */}
            {analysisResult && (
              <div className="relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
                <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
                <h3 className="text-sm font-bold text-white uppercase tracking-[0.16em] mb-4">Record Your Ground Truth Verdict</h3>

                {/* Verdict Selection */}
                <div className="grid grid-cols-3 gap-2.5 mb-5">
                  {["FRAUD", "LEGITIMATE", "UNSURE"].map((verdict) => (
                    <button
                      key={verdict}
                      onClick={() => setAnalystVerdictOverride(verdict)}
                      className={`py-3 px-2 rounded-2xl border font-bold text-xs transition ${
                        analystVerdictOverride === verdict
                          ? verdict === "FRAUD"
                            ? "bg-red-500 border-red-400 text-zinc-950 shadow-md"
                            : verdict === "LEGITIMATE"
                            ? "bg-emerald-500 border-emerald-400 text-zinc-950 shadow-md"
                            : "bg-amber-500 border-amber-400 text-zinc-950 shadow-md"
                          : "bg-zinc-900 border-white/10 text-zinc-300 hover:border-white/20"
                      }`}
                    >
                      {verdict}
                    </button>
                  ))}
                </div>

                {/* Confidence Slider */}
                <div className="mb-5">
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-xs text-zinc-400 font-bold uppercase">Analyst Confidence</label>
                    <span className="text-xs font-mono font-bold text-orange-300">{(confidence * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={confidence}
                    onChange={(e) => setConfidence(parseFloat(e.target.value))}
                    style={{
                      background: `linear-gradient(to right, #f97316 0%, #f59e0b ${confidence * 100}%, #27272a ${confidence * 100}%, #27272a 100%)`
                    }}
                    className="w-full h-2 rounded-full appearance-none cursor-pointer accent-orange-500 shadow-inner transition-all"
                  />
                </div>

                {/* Reasoning */}
                <div className="mb-5">
                  <label className="text-xs text-zinc-400 font-bold uppercase block mb-2">Investigation Notes</label>
                  <textarea
                    value={reasoning}
                    onChange={(e) => setReasoning(e.target.value)}
                    placeholder="Enter observations on why this transaction should be confirmed as fraud or cleared..."
                    className="w-full bg-zinc-900/90 border border-white/15 rounded-2xl p-4 text-xs text-white placeholder-zinc-500 focus:border-orange-400 focus:ring-1 focus:ring-orange-400/30 focus:outline-none resize-none"
                    rows={3}
                  />
                </div>

                {/* Submit Button */}
                <button
                  onClick={handleSubmitVerdict}
                  disabled={loading || !analystVerdictOverride || submitted}
                  className="w-full py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-zinc-950 font-bold flex items-center justify-center gap-2 transition text-xs shadow-xl shadow-emerald-500/25 tracking-wide"
                >
                  {submitted ? (
                    <>
                      <CheckCircle className="h-4 w-4" />
                      Verdict Logged
                    </>
                  ) : loading ? (
                    <>
                      <RotateCw className="h-4 w-4 animate-spin" />
                      Saving Verdict...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" />
                      Commit Analyst Verdict
                    </>
                  )}
                </button>

                {submitted && (
                  <button
                    onClick={() => {
                      setAnalysisResult(null);
                      setAnalystVerdictOverride(null);
                      setSubmitted(false);
                      setReasoning("");
                      setConfidence(0.8);
                    }}
                    className="w-full py-3 mt-3 rounded-full border border-white/15 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 font-bold text-xs transition"
                  >
                    Review Next Scenario
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* How it Works */}
        <div className="mt-8 relative overflow-hidden rounded-3xl border border-orange-500/20 hover:border-orange-500/40 bg-zinc-950/85 p-7 backdrop-blur-xl shadow-2xl shadow-orange-500/5 transition-all duration-300">
          <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-orange-500/10 blur-3xl" />
          <h3 className="text-base font-bold text-white mb-5">How Closed-Loop Learning Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex gap-4 p-4 rounded-2xl bg-zinc-900/50 border border-white/5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-orange-500/10 border border-orange-400/30">
                <span className="font-bold text-orange-400 text-sm">1</span>
              </div>
              <div>
                <p className="font-bold text-white text-xs">SHAP Decomposition</p>
                <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">Multi-modal features are broken down into exact local attributions.</p>
              </div>
            </div>
            <div className="flex gap-4 p-4 rounded-2xl bg-zinc-900/50 border border-white/5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-emerald-500/10 border border-emerald-500/30">
                <span className="font-bold text-emerald-400 text-sm">2</span>
              </div>
              <div>
                <p className="font-bold text-white text-xs">Human-in-the-Loop Review</p>
                <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">Analysts confirm false negatives and novel evasions.</p>
              </div>
            </div>
            <div className="flex gap-4 p-4 rounded-2xl bg-zinc-900/50 border border-white/5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-orange-500/10 border border-orange-400/30">
                <span className="font-bold text-orange-400 text-sm">3</span>
              </div>
              <div>
                <p className="font-bold text-white text-xs">Curriculum Retraining</p>
                <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">The system automatically retrains on logged feedback to harden future detection.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
