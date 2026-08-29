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
    <div className="relative min-h-screen bg-[#0B0B0C] p-6 md:p-10 text-[#EDEDEF] font-sans selection:bg-[#D9500B]/30 overflow-x-hidden">
      <div className="relative max-w-6xl mx-auto">
        {/* Top Breadcrumb Navigation */}
        <div className="mb-6 flex items-center justify-between">
          <a
            href="/dashboard"
            className="group inline-flex items-center gap-2 rounded-md border border-[#2E2E33] bg-[#18181B] px-3.5 py-1.5 text-xs font-medium text-[#EDEDEF] transition-colors hover:border-[#D9500B]/60 hover:text-white shadow-sm"
          >
            ← Back to Dashboard
          </a>
          <span className="rounded-sm border border-[#2E2E33] bg-[#18181B] px-2.5 py-1 text-xs font-mono font-medium text-[#D9500B]">
            Active Learning Loop
          </span>
        </div>

        {/* Header */}
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#A0A0A8] flex items-center gap-2 mb-1.5">
            <Zap className="h-3.5 w-3.5 text-[#D9500B]" />
            Supervised Feedback Pipeline
          </p>
          <h1 className="text-2xl md:text-4xl font-semibold text-white tracking-tight mb-2">Analyst Feedback & Retraining Loop</h1>
          <p className="text-[#A0A0A8] text-xs max-w-2xl leading-relaxed">
            Review flagged edge-case transactions with SHAP feature attributions. Log ground-truth verdicts to automatically trigger curriculum retraining.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Main Analysis Panel */}
          <div className="lg:col-span-2 space-y-5">
            {/* Transaction Card */}
            <div className="rounded-lg border border-[#232326] bg-[#121214] p-5 transition-colors hover:border-[#2E2E33]">
              <h2 className="text-xs font-semibold text-white uppercase tracking-[0.08em] mb-4 flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#D9500B]" />
                  Transaction Under Review
                </span>
                <span className="text-[11px] font-mono text-[#A0A0A8] font-normal bg-[#08080A] px-2.5 py-0.5 rounded-sm border border-[#232326]">ID: txn_live_9481</span>
              </h2>
              <div className="grid grid-cols-2 gap-3 mb-5">
                <div className="p-3.5 rounded-md border border-[#232326] bg-[#08080A] transition-colors hover:border-[#2E2E33]">
                  <span className="text-[11px] text-[#A0A0A8] font-medium uppercase tracking-wider block">Amount</span>
                  <p className="text-xl font-semibold text-white mt-0.5 font-mono tabular-nums">₹{demoTransaction.amount.toLocaleString()}</p>
                </div>
                <div className="p-3.5 rounded-md border border-[#232326] bg-[#08080A] transition-colors hover:border-[#2E2E33]">
                  <span className="text-[11px] text-[#A0A0A8] font-medium uppercase tracking-wider block">Payment Rail</span>
                  <p className="text-xl font-semibold text-white mt-0.5">{demoTransaction.channel}</p>
                </div>
                <div className="p-3.5 rounded-md border border-[#232326] bg-[#08080A] transition-colors hover:border-[#2E2E33]">
                  <span className="text-[11px] text-[#6E6E76] font-medium uppercase tracking-wider block">Payer Account</span>
                  <p className="text-xs font-mono text-[#EDEDEF] mt-0.5 font-medium">{demoTransaction.payer_id}</p>
                </div>
                <div className="p-3.5 rounded-md border border-[#232326] bg-[#08080A] transition-colors hover:border-[#2E2E33]">
                  <span className="text-[11px] text-[#6E6E76] font-medium uppercase tracking-wider block">Payee / Beneficiary</span>
                  <p className="text-xs font-mono text-[#EDEDEF] mt-0.5 font-medium">{demoTransaction.payee_id}</p>
                </div>
              </div>

              {/* Fraud Score Slider */}
              <div className="border-t border-[#232326] pt-4">
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs text-[#A0A0A8] font-medium uppercase tracking-wider">Model Calculated Fraud Probability</label>
                  <span className="text-xl font-semibold text-[#D9500B] font-mono tabular-nums">
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
                      background: `linear-gradient(to right, #D9500B 0%, #D9A420 ${fraudScore * 100}%, #232326 ${fraudScore * 100}%, #232326 100%)`
                    }}
                    className="w-full h-1.5 rounded-full appearance-none cursor-pointer accent-[#D9500B] transition-all"
                  />
                </div>
              </div>
            </div>

            {/* SHAP Features */}
            <div className="rounded-lg border border-[#232326] bg-[#121214] p-5 transition-colors hover:border-[#2E2E33]">
              <h3 className="text-xs font-semibold text-white uppercase tracking-[0.08em] mb-4 flex items-center gap-2">
                <Zap className="h-3.5 w-3.5 text-[#D9500B]" />
                Top Contributing Fraud Signals (SHAP Attribution)
              </h3>
              <div className="space-y-2">
                {demoSHAPFeatures.map((feature) => (
                  <div key={feature.name} className="flex items-center justify-between p-3 rounded-md bg-[#08080A] border border-[#232326] transition-colors hover:border-[#2E2E33]">
                    <div>
                      <p className="font-medium text-[#EDEDEF] text-xs font-mono">{feature.name.replace(/_/g, " ")}</p>
                      <p className="text-[11px] text-[#A0A0A8] mt-0.5 font-mono">Observed: {typeof feature.value === "number" && feature.value > 1000 ? (feature.value / 86400).toFixed(1) + " days" : feature.value.toFixed(2)}</p>
                    </div>
                    <div className="text-right flex items-center gap-3">
                      <div className="w-24 h-1.5 bg-[#18181B] rounded-sm overflow-hidden border border-[#232326]">
                        <div
                          className="h-full bg-[#D9500B] rounded-sm"
                          style={{ width: `${feature.contribution * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono font-medium text-[#D9500B] w-14 text-right tabular-nums">+{(feature.contribution * 100).toFixed(1)}%</span>
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
                className="w-full py-3 rounded-md bg-[#D9500B] hover:bg-[#EB6018] disabled:opacity-50 text-white font-medium flex items-center justify-center gap-2 transition-colors shadow-sm text-xs tracking-wide"
              >
                {loading ? (
                  <>
                    <RotateCw className="h-3.5 w-3.5 animate-spin" />
                    Generating Intelligent Assessment...
                  </>
                ) : (
                  <>
                    <Zap className="h-3.5 w-3.5 fill-white" />
                    Generate GenAI Decision Note
                  </>
                )}
              </button>
            )}

            {/* Analysis Result */}
            {analysisResult && (
              <div className="rounded-lg border border-[#2E2E33] bg-[#121214] p-5 shadow-sm animate-fade-in">
                <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#232326]">
                  <h3 className="text-xs font-semibold text-white uppercase tracking-[0.08em] flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-medium bg-[#18181B] border border-[#2E2E33] text-[#D9500B]">
                      {analysisResult.model_info.type}
                    </span>
                    Decision Explanation
                  </h3>
                  <p className="text-xs text-[#A0A0A8] font-mono">{analysisResult.model_info.model}</p>
                </div>

                <div className="space-y-4">
                  <div className={`p-4 rounded-md border ${
                    analysisResult.verdict.verdict === "FRAUD"
                      ? "bg-[#2C1214] border-[#5E2326] text-[#E5484D]"
                      : "bg-[#0E2A1D] border-[#1C5138] text-[#3FBF7F]"
                  }`}>
                    <div className="flex items-center justify-between">
                      <p className="font-semibold text-xs">Automated Triage Recommendation</p>
                      <span className={`text-sm font-semibold font-mono ${
                        analysisResult.verdict.verdict === "FRAUD" ? "text-[#E5484D]" : "text-[#3FBF7F]"
                      }`}>
                        {analysisResult.verdict.verdict}
                      </span>
                    </div>
                    <p className="text-xs text-[#A0A0A8] mt-1 font-mono">Model Confidence: {(analysisResult.verdict.confidence * 100).toFixed(0)}%</p>
                  </div>

                  <div className="p-3.5 rounded-md bg-[#08080A] border border-[#232326]">
                    <p className="text-xs text-[#EDEDEF] leading-relaxed italic font-sans">&quot;{analysisResult.verdict.reasoning}&quot;</p>
                  </div>

                  <div>
                    <p className="text-[11px] font-medium text-[#A0A0A8] uppercase tracking-wider mb-2">Key Signals</p>
                    <div className="flex flex-wrap gap-1.5">
                      {analysisResult.verdict.key_signals.map((signal) => (
                        <span key={signal} className="px-2.5 py-1 rounded-sm text-xs bg-[#08080A] border border-[#232326] text-[#EDEDEF] font-mono">
                          {signal}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-[11px] font-medium text-[#A0A0A8] uppercase tracking-wider mb-2">Pattern Indicators</p>
                    <ul className="space-y-1.5">
                      {analysisResult.verdict.patterns.map((pattern, i) => (
                        <li key={i} className="text-xs text-[#EDEDEF] flex items-start gap-2 p-2 rounded-md bg-[#08080A] border border-[#232326]">
                          <span className="h-1.5 w-1.5 rounded-full bg-[#D9500B] mt-1 shrink-0" />
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
          <div className="space-y-5">
            {/* Feedback Status */}
            {feedbackStatus && (
              <div className="rounded-lg border border-[#232326] bg-[#121214] p-5 transition-colors hover:border-[#2E2E33]">
                <h3 className="text-xs font-semibold text-white uppercase tracking-[0.08em] mb-4 flex items-center gap-2">
                  <TrendingUp className="h-3.5 w-3.5 text-[#D9500B]" />
                  Feedback Ingestion Status
                </h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between p-3 rounded-md bg-[#08080A] border border-[#232326]">
                    <span className="text-[#A0A0A8] font-medium">Total Logged Verdicts</span>
                    <span className="font-semibold text-white font-mono tabular-nums">{feedbackStatus.total_feedback}</span>
                  </div>
                  <div className="flex justify-between p-3 rounded-md bg-[#08080A] border border-[#232326]">
                    <span className="text-[#A0A0A8] font-medium">Fraud Confirmed</span>
                    <span className="font-semibold text-[#E5484D] font-mono tabular-nums">{feedbackStatus.fraud_confirmed}</span>
                  </div>
                  <div className="flex justify-between p-3 rounded-md bg-[#08080A] border border-[#232326]">
                    <span className="text-[#A0A0A8] font-medium">Legitimate Confirmed</span>
                    <span className="font-semibold text-[#3FBF7F] font-mono tabular-nums">{feedbackStatus.legitimate_confirmed}</span>
                  </div>
                  {feedbackStatus.should_retrain && (
                    <div className="mt-3.5 p-3.5 rounded-md bg-[#18181B] border border-[#2E2E33]">
                      {retrainOutcome === "success" ? (
                        <div className="flex items-center gap-2 text-[#3FBF7F] font-medium text-xs">
                          <CheckCircle className="h-4 w-4 shrink-0" />
                          Model successfully retrained on the latest feedback.
                        </div>
                      ) : retrainOutcome === "queued" ? (
                        <div className="flex items-center gap-2 text-[#D9A420] font-medium text-xs">
                          <RotateCw className="h-4 w-4 shrink-0" />
                          Retraining queued — feedback saved for next cycle.
                        </div>
                      ) : (
                        <>
                          <p className="text-[#D9A420] font-medium text-xs mb-2">Retraining Threshold Met</p>
                          <button
                            onClick={handleTriggerRetrain}
                            disabled={retraining}
                            className="w-full py-2.5 rounded-md bg-[#D9500B] hover:bg-[#EB6018] disabled:opacity-50 text-white font-medium flex items-center justify-center gap-2 transition-colors text-xs shadow-sm"
                          >
                            {retraining ? (
                              <>
                                <RotateCw className="h-3.5 w-3.5 animate-spin" />
                                Retraining Model...
                              </>
                            ) : (
                              <>
                                <TrendingUp className="h-3.5 w-3.5" />
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
              <div className="rounded-lg border border-[#232326] bg-[#121214] p-5 transition-colors hover:border-[#2E2E33]">
                <h3 className="text-xs font-semibold text-white uppercase tracking-[0.08em] mb-3 flex items-center gap-2">
                  <TrendingUp className="h-3.5 w-3.5 text-[#D9500B]" /> Model Evolution History
                </h3>
                <div className="space-y-2">
                  {modelHistory.map((meta: any, idx: number) => (
                    <div key={idx} className="p-3.5 rounded-md bg-[#08080A] border border-[#232326] transition-colors hover:border-[#2E2E33]">
                      <p className="text-xs font-medium text-[#D9500B] mb-2">{meta.label} <span className="text-[11px] text-[#6E6E76] font-mono font-normal">({meta.version})</span></p>
                      <div className="grid grid-cols-2 gap-2 text-[11px]">
                        <div>
                          <span className="text-[#6E6E76]">PR-AUC</span>
                          <p className="text-white font-semibold font-mono text-xs tabular-nums">{(meta.pr_auc * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-[#6E6E76]">Precision</span>
                          <p className="text-white font-semibold font-mono text-xs tabular-nums">{(meta.precision * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-[#6E6E76]">Test Recall</span>
                          <p className="text-white font-semibold font-mono text-xs tabular-nums">{(meta.recall * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-[#6E6E76]">Evasion Rate</span>
                          <p className="text-[#E5484D] font-semibold font-mono text-xs tabular-nums">{(meta.evasion_rate * 100).toFixed(1)}%</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Analyst Verdict Form */}
            {analysisResult && (
              <div className="rounded-lg border border-[#232326] bg-[#121214] p-5 transition-colors hover:border-[#2E2E33]">
                <h3 className="text-xs font-semibold text-white uppercase tracking-[0.08em] mb-3">Record Your Ground Truth Verdict</h3>

                {/* Verdict Selection */}
                <div className="grid grid-cols-3 gap-2 mb-4">
                  {["FRAUD", "LEGITIMATE", "UNSURE"].map((verdict) => (
                    <button
                      key={verdict}
                      onClick={() => setAnalystVerdictOverride(verdict)}
                      className={`py-2 px-1.5 rounded-md border font-medium text-xs transition-colors ${
                        analystVerdictOverride === verdict
                          ? verdict === "FRAUD"
                            ? "bg-[#2C1214] border-[#5E2326] text-[#E5484D]"
                            : verdict === "LEGITIMATE"
                            ? "bg-[#0E2A1D] border-[#1C5138] text-[#3FBF7F]"
                            : "bg-[#2B2009] border-[#5C4413] text-[#D9A420]"
                          : "bg-[#08080A] border-[#232326] text-[#A0A0A8] hover:border-[#2E2E33]"
                      }`}
                    >
                      {verdict}
                    </button>
                  ))}
                </div>

                {/* Confidence Slider */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs text-[#A0A0A8] font-medium uppercase">Analyst Confidence</label>
                    <span className="text-xs font-mono font-medium text-[#D9500B] tabular-nums">{(confidence * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={confidence}
                    onChange={(e) => setConfidence(parseFloat(e.target.value))}
                    style={{
                      background: `linear-gradient(to right, #D9500B 0%, #D9A420 ${confidence * 100}%, #232326 ${confidence * 100}%, #232326 100%)`
                    }}
                    className="w-full h-1.5 rounded-full appearance-none cursor-pointer accent-[#D9500B] transition-all"
                  />
                </div>

                {/* Reasoning */}
                <div className="mb-4">
                  <label className="text-xs text-[#A0A0A8] font-medium uppercase block mb-1.5">Investigation Notes</label>
                  <textarea
                    value={reasoning}
                    onChange={(e) => setReasoning(e.target.value)}
                    placeholder="Enter observations on why this transaction should be confirmed as fraud or cleared..."
                    className="w-full bg-[#08080A] border border-[#232326] rounded-md p-3 text-xs text-white placeholder-[#6E6E76] focus:border-[#D9500B] focus:outline-none resize-none"
                    rows={3}
                  />
                </div>

                {/* Submit Button */}
                <button
                  onClick={handleSubmitVerdict}
                  disabled={loading || !analystVerdictOverride || submitted}
                  className="w-full py-2.5 rounded-md bg-[#1C5138] border border-[#3FBF7F]/40 text-[#3FBF7F] hover:bg-[#236446] disabled:opacity-50 font-medium flex items-center justify-center gap-2 transition-colors text-xs tracking-wide"
                >
                  {submitted ? (
                    <>
                      <CheckCircle className="h-3.5 w-3.5" />
                      Verdict Logged
                    </>
                  ) : loading ? (
                    <>
                      <RotateCw className="h-3.5 w-3.5 animate-spin" />
                      Saving Verdict...
                    </>
                  ) : (
                    <>
                      <Send className="h-3.5 w-3.5" />
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
                    className="w-full py-2 mt-2.5 rounded-md border border-[#232326] bg-[#08080A] hover:bg-[#18181B] text-[#EDEDEF] font-medium text-xs transition-colors"
                  >
                    Review Next Scenario
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* How it Works */}
        <div className="mt-6 rounded-lg border border-[#232326] bg-[#121214] p-5 transition-colors hover:border-[#2E2E33]">
          <h3 className="text-xs font-semibold text-white uppercase tracking-[0.08em] mb-4">How Closed-Loop Learning Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex gap-3 p-3.5 rounded-md bg-[#08080A] border border-[#232326]">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#18181B] border border-[#2E2E33]">
                <span className="font-mono font-medium text-[#D9500B] text-xs">1</span>
              </div>
              <div>
                <p className="font-semibold text-white text-xs">SHAP Decomposition</p>
                <p className="text-[11px] text-[#A0A0A8] mt-0.5 leading-relaxed">Multi-modal features are broken down into exact local attributions.</p>
              </div>
            </div>
            <div className="flex gap-3 p-3.5 rounded-md bg-[#08080A] border border-[#232326]">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#18181B] border border-[#2E2E33]">
                <span className="font-mono font-medium text-[#3FBF7F] text-xs">2</span>
              </div>
              <div>
                <p className="font-semibold text-white text-xs">Human-in-the-Loop Review</p>
                <p className="text-[11px] text-[#A0A0A8] mt-0.5 leading-relaxed">Analysts confirm false negatives and novel evasions.</p>
              </div>
            </div>
            <div className="flex gap-3 p-3.5 rounded-md bg-[#08080A] border border-[#232326]">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#18181B] border border-[#2E2E33]">
                <span className="font-mono font-medium text-[#D9500B] text-xs">3</span>
              </div>
              <div>
                <p className="font-semibold text-white text-xs">Curriculum Retraining</p>
                <p className="text-[11px] text-[#A0A0A8] mt-0.5 leading-relaxed">The system automatically retrains on logged feedback to harden future detection.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
