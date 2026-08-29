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
  const risk = (nodeData.risk || "LOW").toLowerCase();
  const isCritical = risk === "critical" || risk === "high";
  const isWarning = risk === "medium" || risk === "warning";
  const isAttacker = nodeData.type === "attacker";
  const isPayee = nodeData.type === "payee";

  const getBorderColor = () => {
    if (isSelected) return "border-[#D9500B] ring-1 ring-[#D9500B]/50";
    if (isAttacker || isCritical) return "border-[#5E2326] hover:border-[#E5484D]/70";
    if (isWarning) return "border-[#5C4413] hover:border-[#D9A420]/70";
    if (isPayee) return "border-[#1C5138] hover:border-[#3FBF7F]/70";
    return "border-[#232326] hover:border-[#2E2E33]";
  };

  const getBadgeColor = () => {
    if (isAttacker || isCritical) return "bg-[#2C1214] text-[#E5484D] border-[#5E2326]";
    if (isWarning) return "bg-[#2B2009] text-[#D9A420] border-[#5C4413]";
    if (isPayee) return "bg-[#0E2A1D] text-[#3FBF7F] border-[#1C5138]";
    return "bg-[#18181B] text-[#A0A0A8] border-[#232326]";
  };

  const getIcon = () => {
    if (isAttacker) return <ShieldAlert className="h-3.5 w-3.5 text-[#E5484D] shrink-0" />;
    if (isPayee) return <Building2 className="h-3.5 w-3.5 text-[#3FBF7F] shrink-0" />;
    return <User className="h-3.5 w-3.5 text-[#D9500B] shrink-0" />;
  };

  return (
    <div
      className={`relative px-3.5 py-2.5 rounded-lg bg-[#121214] border transition-colors duration-200 min-w-[155px] cursor-pointer select-none group ${getBorderColor()}`}
    >
      <Handle id="left" type="target" position={Position.Left} className="!w-1.5 !h-1.5 !bg-[#2E2E33] !border-none !-left-0.5" />
      <Handle id="top" type="target" position={Position.Top} className="!w-1.5 !h-1.5 !bg-[#2E2E33] !border-none !-top-0.5" />

      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5">
          {getIcon()}
          <span className="text-[10px] font-mono font-medium uppercase tracking-wider text-[#A0A0A8]">
            {nodeData.type || "NODE"}
          </span>
        </div>
        <span className={`text-[9px] font-mono font-medium px-1.5 py-0.5 rounded-sm border ${getBadgeColor()}`}>
          {nodeData.risk || "LOW"}
        </span>
      </div>

      <div className="text-xs font-medium text-[#EDEDEF] font-mono tracking-tight group-hover:text-white transition-colors">
        {nodeData.label}
      </div>

      <Handle id="right" type="source" position={Position.Right} className="!w-1.5 !h-1.5 !bg-[#D9500B] !border-none !-right-0.5" />
      <Handle id="bottom" type="source" position={Position.Bottom} className="!w-1.5 !h-1.5 !bg-[#D9500B] !border-none !-bottom-0.5" />
    </div>
  );
}

export const nodeTypes = {
  actorNode: ActorNode,
};
