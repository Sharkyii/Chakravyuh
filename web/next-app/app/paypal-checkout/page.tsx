"use client";

import React, { useState } from "react";
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import Link from "next/link";

export default function PayPalCheckoutPage() {
  const [paymentStatus, setPaymentStatus] = useState<string>("Pending");
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);

  // Fake transaction mapping from PayPal to our fraud model's expected features
  const mapPayPalToFraudModel = (order: any, capture: any) => {
    return {
      amount: capture.purchase_units[0].payments.captures[0].amount.value,
      channel: "PAYPAL",
      rail: "paypal_checkout",
      device_is_known_for_payer: false, // Assume false for demo
      ip_is_proxy: false, // Could be randomized or extracted
      beneficiary_added_ago_s: 3600, 
      edge_count: 1,
      payee_id: capture.purchase_units[0].payee.email_address || "paypal_merchant",
      payer_id: capture.payer.email_address || "paypal_user",
      timestamp: capture.create_time,
      auth_method: "PAYPAL_LOGIN",
      // required by backend if call_active_during_txn is checked
      call_active_during_txn: false,
      screen_share_active: false
    };
  };

  const handleApprove = async (data: any, actions: any) => {
    setPaymentStatus("Processing Payment...");
    try {
      const capture = await actions.order.capture();
      setPaymentStatus("Payment Captured successfully!");
      
      setLoadingAnalysis(true);
      // Construct the transaction payload for our AI Fraud Model
      const txnData = mapPayPalToFraudModel(data, capture);
      
      // Call Chakravyuh Backend to score this PayPal transaction
      const response = await fetch("http://localhost:8000/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          transaction: txnData
        })
      });

      if (response.ok) {
        const result = await response.json();
        setAnalysisResult(result);
        if (result.risk_level === "CRITICAL" || result.risk_level === "HIGH") {
            setPaymentStatus("Payment Flagged as Fraud!");
        } else {
            setPaymentStatus("Payment Approved & Verified Secure.");
        }
      } else {
        console.error("Failed to analyze transaction");
        setPaymentStatus("Payment Captured, but Risk Analysis Failed.");
      }
    } catch (err) {
      console.error(err);
      setPaymentStatus("Payment Failed or Cancelled.");
    } finally {
      setLoadingAnalysis(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        
        <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-500">
            Chakravyuh + PayPal Integration
            </h1>
            <Link href="/" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-md text-sm font-medium transition-colors">
                Back to Dashboard
            </Link>
        </div>

        <p className="text-slate-400">
          This demo integrates the PayPal Developer Platform with our AI-powered Fraud Detection Engine.
          Make a sandbox payment below, and the transaction will be sent to the backend for real-time risk scoring and Gemini analysis.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Checkout Column */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6 shadow-xl">
            <h2 className="text-xl font-semibold text-slate-100 border-b border-slate-800 pb-2">Simulated Store Checkout</h2>
            <div className="flex items-center justify-between py-4 border-b border-slate-800">
                <div>
                    <h3 className="font-medium text-slate-200">Premium Subscription (1 Year)</h3>
                    <p className="text-sm text-slate-500">Access to all premium AI tools.</p>
                </div>
                <div className="font-bold text-lg text-slate-100">$99.00</div>
            </div>
            
            <div className="mt-6 z-0 relative">
              <PayPalScriptProvider options={{ clientId: "test", currency: "USD" }}>
                <PayPalButtons 
                  style={{ layout: "vertical", color: "blue", shape: "rect", label: "paypal" }} 
                  createOrder={(data, actions) => {
                    return actions.order.create({
                        intent: "CAPTURE",
                        purchase_units: [
                            {
                                amount: {
                                    value: "99.00",
                                    currency_code: "USD"
                                },
                                description: "Premium Subscription (1 Year)"
                            },
                        ],
                    });
                  }}
                  onApprove={handleApprove}
                />
              </PayPalScriptProvider>
            </div>
          </div>

          {/* Analysis Results Column */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4 shadow-xl">
            <h2 className="text-xl font-semibold text-slate-100 border-b border-slate-800 pb-2">AI Risk Analysis</h2>
            
            <div className="py-2">
                <span className="text-sm text-slate-500 uppercase tracking-wide font-medium">Status</span>
                <p className={`font-medium mt-1 ${paymentStatus.includes('Fraud') ? 'text-red-400' : paymentStatus.includes('Approved') ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {paymentStatus}
                </p>
            </div>

            {loadingAnalysis && (
                <div className="animate-pulse space-y-3 mt-4">
                    <div className="h-4 bg-slate-800 rounded w-3/4"></div>
                    <div className="h-4 bg-slate-800 rounded w-1/2"></div>
                    <div className="h-4 bg-slate-800 rounded w-5/6"></div>
                    <p className="text-xs text-indigo-400 mt-2">Running XGBoost Model & Gemini Analysis...</p>
                </div>
            )}

            {analysisResult && (
                <div className="space-y-4 mt-4 animate-in fade-in slide-in-from-bottom-2 duration-500">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-slate-950 border border-slate-800 p-3 rounded-md">
                            <div className="text-xs text-slate-500 mb-1">Risk Level</div>
                            <div className={`font-bold ${analysisResult.risk_level === 'LOW' ? 'text-emerald-400' : analysisResult.risk_level === 'MEDIUM' ? 'text-amber-400' : 'text-red-500'}`}>
                                {analysisResult.risk_level}
                            </div>
                        </div>
                        <div className="bg-slate-950 border border-slate-800 p-3 rounded-md">
                            <div className="text-xs text-slate-500 mb-1">Fraud Score</div>
                            <div className="font-bold text-slate-200">
                                {analysisResult.risk_score.toFixed(1)} / 100
                            </div>
                        </div>
                    </div>

                    <div className="bg-slate-950 border border-slate-800 p-4 rounded-md">
                        <h4 className="text-sm font-semibold text-slate-300 mb-2">Gemini Analyst Note</h4>
                        <p className="text-sm text-slate-400 leading-relaxed">
                            {analysisResult.explanation || "No AI explanation generated. Provide Gemini API Key in settings."}
                        </p>
                    </div>

                    <div className="bg-slate-950 border border-slate-800 p-4 rounded-md">
                        <h4 className="text-sm font-semibold text-slate-300 mb-2">Top SHAP Drivers</h4>
                        <ul className="space-y-1">
                            {analysisResult.shap_features?.slice(0, 3).map((f: any, idx: number) => (
                                <li key={idx} className="text-xs flex justify-between">
                                    <span className="text-slate-500">{f.name}</span>
                                    <span className={f.direction === "increases_fraud_score" ? "text-rose-400" : "text-emerald-400"}>
                                        {f.direction === "increases_fraud_score" ? "+" : "-"}{f.contribution.toFixed(2)}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
