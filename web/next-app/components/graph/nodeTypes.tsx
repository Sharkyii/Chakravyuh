"use client";

import React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { ShieldAlert, User, Building2 } from "lucide-react";

export type ActorType = "payer" | "payee" | "attacker" | "payer_other";

export interface ActorNodeData {
  id: string;
  label: string;
  type: ActorType;
  risk: string;
  isSelected?: boolean;
  [key: string]: unknown;
}

export function ActorNode({ data }: NodeProps) {
  const nodeData = data as unknown as ActorNodeData;
  const isSelected = Boolean(nodeData.isSelected);
  const isCritical = nodeData.risk?.toLowerCase() === "critical" || nodeData.risk?.toLowerCase() === "high";
  const isAttacker = nodeData.type === "attacker";
  const isPayee = nodeData.type === "payee";

  const getBorderColor = () => {
    if (isSelected) return "border-orange-400 ring-2 ring-orange-500/40 shadow-[0_0_20px_rgba(249,115,22,0.3)]";
    if (isAttacker || isCritical) return "border-red-500/50 shadow-[0_0_15px_rgba(239,68,68,0.15)]";
    if (isPayee) return "border-emerald-500/40";
    return "border-orange-500/30";
  };

  const getBadgeColor = () => {
    if (isAttacker || isCritical) return "bg-red-950/70 text-red-300 border-red-500/40";
    if (isPayee) return "bg-emerald-950/70 text-emerald-300 border-emerald-500/40";
    return "bg-orange-950/70 text-orange-300 border-orange-500/40";
  };

  const getIcon = () => {
    if (isAttacker) return <ShieldAlert className="h-3.5 w-3.5 text-red-400 shrink-0" />;
    if (isPayee) return <Building2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />;
    return <User className="h-3.5 w-3.5 text-orange-400 shrink-0" />;
  };

  return (
    <div
      className={`relative px-3.5 py-2.5 rounded-2xl bg-zinc-950/95 border backdrop-blur-md transition-all duration-300 min-w-[155px] cursor-pointer select-none group ${getBorderColor()}`}
    >
      <Handle id="left" type="target" position={Position.Left} className="!w-2 !h-2 !bg-zinc-600 !border !border-white/20 !-left-1" />
      <Handle id="top" type="target" position={Position.Top} className="!w-2 !h-2 !bg-zinc-600 !border !border-white/20 !-top-1" />

      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5">
          {getIcon()}
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-zinc-400">
            {nodeData.type || "NODE"}
          </span>
        </div>
        <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-full border ${getBadgeColor()}`}>
          {nodeData.risk || "LOW"}
        </span>
      </div>

      <div className="text-xs font-bold text-white font-mono tracking-tight group-hover:text-orange-300 transition-colors">
        {nodeData.label}
      </div>

      <Handle id="right" type="source" position={Position.Right} className="!w-2 !h-2 !bg-orange-500 !border !border-white/20 !-right-1" />
      <Handle id="bottom" type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-orange-500 !border !border-white/20 !-bottom-1" />
    </div>
  );
}

export const nodeTypes = {
  actorNode: ActorNode,
};
