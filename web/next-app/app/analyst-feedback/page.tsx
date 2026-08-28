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
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyst/trigger-retrain`, { method: "POST" });
      const result = await response.json();
      if (result.status === "success") {
        await checkFeedbackStatus();
        await checkModelHistory();
        alert("Model successfully retrained!");
      } else {
        alert("Failed to retrain: " + result.message);
      }
    } catch (error) {
      console.error("Retrain error:", error);
      alert("Error triggering retrain");
    } finally {
      setRetraining(false);
    }
  };

  React.useEffect(() => {
    checkFeedbackStatus();
    checkModelHistory();
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-black text-white mb-2">Analyst Feedback Loop</h1>
          <p className="text-zinc-400">
            Review flagged transactions. Claude Sonnet 5 provides intelligent analysis.
            Your verdicts improve the detector over time.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Analysis Panel */}
          <div className="lg:col-span-2 space-y-6">
            {/* Transaction Card */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
              <h2 className="text-lg font-bold text-white mb-4">Transaction Under Review</h2>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <span className="text-xs text-zinc-500 uppercase">Amount</span>
                  <p className="text-2xl font-bold text-white">₹{demoTransaction.amount.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 uppercase">Channel</span>
                  <p className="text-2xl font-bold text-white">{demoTransaction.channel}</p>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 uppercase">Payer</span>
                  <p className="text-sm font-mono text-zinc-300">{demoTransaction.payer_id}</p>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 uppercase">Payee</span>
                  <p className="text-sm font-mono text-zinc-300">{demoTransaction.payee_id}</p>
                </div>
              </div>

              {/* Fraud Score Slider */}
              <div className="border-t border-zinc-700/30 pt-4">
                <label className="text-xs text-zinc-500 uppercase">Model Fraud Score</label>
                <div className="flex items-center gap-4 mt-2">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={fraudScore}
                    onChange={(e) => setFraudScore(parseFloat(e.target.value))}
                    className="flex-1"
                  />
                  <span className="text-2xl font-bold text-orange-400 w-16 text-right">
                    {(fraudScore * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            {/* SHAP Features */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <Zap className="h-4 w-4 text-orange-500" />
                Top Fraud Signals (SHAP Explanability)
              </h3>
              <div className="space-y-3">
                {demoSHAPFeatures.map((feature) => (
                  <div key={feature.name} className="flex items-center justify-between p-3 rounded-lg bg-zinc-950/50 border border-zinc-700/30">
                    <div>
                      <p className="font-semibold text-white">{feature.name.replace(/_/g, " ")}</p>
                      <p className="text-xs text-zinc-500">Value: {typeof feature.value === "number" && feature.value > 1000 ? (feature.value / 86400).toFixed(1) + " days" : feature.value.toFixed(2)}</p>
                    </div>
                    <div className="text-right">
                      <div className="w-16 h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-orange-500"
                          style={{ width: `${feature.contribution * 100}%` }}
                        />
                      </div>
                      <p className="text-xs text-zinc-400 mt-1">{(feature.contribution * 100).toFixed(1)}%</p>
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
                className="w-full py-3 rounded-xl bg-orange-600 hover:bg-orange-500 disabled:bg-zinc-700 text-white font-bold flex items-center justify-center gap-2 transition"
              >
                {loading ? (
                  <>
                    <RotateCw className="h-4 w-4 animate-spin" />
                    Analyzing with Claude Sonnet 5...
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4" />
                    Get Claude Analyst Opinion
                  </>
                )}
              </button>
            )}

            {/* Claude Analysis Result */}
            {analysisResult && (
              <div className="rounded-2xl border border-orange-500/30 bg-orange-950/10 p-6 backdrop-blur-md">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <span className="px-2 py-1 rounded text-xs font-bold bg-orange-600 text-white">
                      {analysisResult.model_info.type}
                    </span>
                    Analysis
                  </h3>
                  <p className="text-xs text-zinc-500">{analysisResult.model_info.model}</p>
                </div>

                <div className="space-y-4">
                  <div className={`p-4 rounded-lg border ${
                    analysisResult.verdict.verdict === "FRAUD"
                      ? "bg-red-950/30 border-red-500/30"
                      : "bg-emerald-950/30 border-emerald-500/30"
                  }`}>
                    <div className="flex items-center justify-between">
                      <p className="font-semibold text-white">Verdict</p>
                      <span className={`text-xl font-bold ${
                        analysisResult.verdict.verdict === "FRAUD" ? "text-red-400" : "text-emerald-400"
                      }`}>
                        {analysisResult.verdict.verdict}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-2">Confidence: {(analysisResult.verdict.confidence * 100).toFixed(0)}%</p>
                  </div>

                  <div>
                    <p className="text-sm text-zinc-400 italic">&quot;{analysisResult.verdict.reasoning}&quot;</p>
                  </div>

                  <div>
                    <p className="text-xs text-zinc-500 uppercase mb-2">Key Signals</p>
                    <div className="flex flex-wrap gap-2">
                      {analysisResult.verdict.key_signals.map((signal) => (
                        <span key={signal} className="px-2 py-1 rounded text-xs bg-zinc-800 text-zinc-200">
                          {signal}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-zinc-500 uppercase mb-2">Patterns</p>
                    <ul className="space-y-1">
                      {analysisResult.verdict.patterns.map((pattern, i) => (
                        <li key={i} className="text-xs text-zinc-400">• {pattern}</li>
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
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 backdrop-blur-md">
                <h3 className="text-sm font-bold text-white mb-3">Feedback Status</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Total Verdicts</span>
                    <span className="font-bold text-white">{feedbackStatus.total_feedback}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Fraud Confirmed</span>
                    <span className="font-bold text-red-400">{feedbackStatus.fraud_confirmed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Legitimate</span>
                    <span className="font-bold text-emerald-400">{feedbackStatus.legitimate_confirmed}</span>
                  </div>
                  {feedbackStatus.should_retrain && (
                    <div className="mt-3 p-3 rounded-lg bg-orange-500/20 border border-orange-500/30">
                      <p className="text-orange-300 font-semibold mb-2">✓ Ready to Retrain</p>
                      <button
                        onClick={handleTriggerRetrain}
                        disabled={retraining}
                        className="w-full py-2 rounded-lg bg-orange-600 hover:bg-orange-500 disabled:bg-zinc-700 text-white font-bold flex items-center justify-center gap-2 transition text-xs"
                      >
                        {retraining ? (
                          <>
                            <RotateCw className="h-4 w-4 animate-spin" />
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
              </div>
            )}

            {/* Model History Comparison */}
            {modelHistory.length > 0 && (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 backdrop-blur-md">
                <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-blue-400" /> Model Evolution
                </h3>
                <div className="space-y-4">
                  {modelHistory.map((meta: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-lg bg-zinc-950/50 border border-zinc-700/50">
                      <p className="text-xs font-bold text-blue-300 mb-2">{meta.label} <span className="text-[10px] text-zinc-500 font-mono font-normal">({meta.version})</span></p>
                      <div className="grid grid-cols-2 gap-2 text-[10px]">
                        <div>
                          <span className="text-zinc-500">PR-AUC</span>
                          <p className="text-white font-semibold">{(meta.pr_auc * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-zinc-500">Precision</span>
                          <p className="text-white font-semibold">{(meta.precision * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-zinc-500">Test Recall</span>
                          <p className="text-white font-semibold">{(meta.recall * 100).toFixed(2)}%</p>
                        </div>
                        <div>
                          <span className="text-zinc-500">Evasion Rate</span>
                          <p className="text-red-400 font-semibold">{(meta.evasion_rate * 100).toFixed(1)}%</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Analyst Verdict Form */}
            {analysisResult && (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
                <h3 className="text-lg font-bold text-white mb-4">Your Verdict</h3>

                {/* Verdict Selection */}
                <div className="space-y-3 mb-6">
                  {["FRAUD", "LEGITIMATE", "UNSURE"].map((verdict) => (
                    <button
                      key={verdict}
                      onClick={() => setAnalystVerdictOverride(verdict)}
                      className={`w-full py-2 px-3 rounded-lg border font-semibold text-sm transition ${
                        analystVerdictOverride === verdict
                          ? verdict === "FRAUD"
                            ? "bg-red-600 border-red-500 text-white"
                            : verdict === "LEGITIMATE"
                            ? "bg-emerald-600 border-emerald-500 text-white"
                            : "bg-yellow-600 border-yellow-500 text-white"
                          : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-500"
                      }`}
                    >
                      {verdict === "FRAUD" && <AlertTriangle className="h-4 w-4 inline mr-2" />}
                      {verdict === "LEGITIMATE" && <CheckCircle className="h-4 w-4 inline mr-2" />}
                      {verdict === "UNSURE" && <HelpCircle className="h-4 w-4 inline mr-2" />}
                      {verdict}
                    </button>
                  ))}
                </div>

                {/* Confidence Slider */}
                <div className="mb-6">
                  <label className="text-xs text-zinc-500 uppercase block mb-2">Confidence</label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={confidence}
                    onChange={(e) => setConfidence(parseFloat(e.target.value))}
                    className="w-full"
                  />
                  <p className="text-xs text-zinc-400 mt-1 text-right">{(confidence * 100).toFixed(0)}%</p>
                </div>

                {/* Reasoning */}
                <div className="mb-6">
                  <label className="text-xs text-zinc-500 uppercase block mb-2">Your Reasoning</label>
                  <textarea
                    value={reasoning}
                    onChange={(e) => setReasoning(e.target.value)}
                    placeholder="Why do you agree/disagree with Claude&rsquo;s assessment?"
                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg p-2 text-xs text-white placeholder-zinc-600 focus:border-orange-500 focus:outline-none resize-none"
                    rows={4}
                  />
                </div>

                {/* Submit Button */}
                <button
                  onClick={handleSubmitVerdict}
                  disabled={loading || !analystVerdictOverride || submitted}
                  className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white font-bold flex items-center justify-center gap-2 transition"
                >
                  {submitted ? (
                    <>
                      <CheckCircle className="h-4 w-4" />
                      Verdict Submitted
                    </>
                  ) : loading ? (
                    <>
                      <RotateCw className="h-4 w-4 animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" />
                      Submit Verdict
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
                    className="w-full py-2 mt-3 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white font-semibold text-sm"
                  >
                    Review Another Transaction
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* How it Works */}
        <div className="mt-12 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 backdrop-blur-md">
          <h3 className="text-lg font-bold text-white mb-4">How This Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-orange-500/20 border border-orange-500/30">
                <span className="font-bold text-orange-400 text-sm">1</span>
              </div>
              <div>
                <p className="font-semibold text-white text-sm">Claude Analyzes</p>
                <p className="text-xs text-zinc-500 mt-1">Claude Sonnet 5 (non-hallucinating) reviews SHAP features</p>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/20 border border-emerald-500/30">
                <span className="font-bold text-emerald-400 text-sm">2</span>
              </div>
              <div>
                <p className="font-semibold text-white text-sm">You Review</p>
                <p className="text-xs text-zinc-500 mt-1">Agree or disagree with Claude&rsquo;s verdict</p>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-500/20 border border-blue-500/30">
                <span className="font-bold text-blue-400 text-sm">3</span>
              </div>
              <div>
                <p className="font-semibold text-white text-sm">Model Improves</p>
                <p className="text-xs text-zinc-500 mt-1">At 50+ verdicts, model retrains on human feedback</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
