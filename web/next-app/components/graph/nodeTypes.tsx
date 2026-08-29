import React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { riskColor } from "@/lib/graphColors";

const hiddenHandleStyle: React.CSSProperties = {
  opacity: 0,
  width: 1,
  height: 1,
  border: "none",
  background: "transparent",
};

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
  const stroke = riskColor(nodeData.risk);
  return (
    <div className="flex flex-col items-center gap-1 select-none cursor-pointer group">
      <Handle type="target" position={Position.Left} style={hiddenHandleStyle} />
      <div
        className="rounded-full flex items-center justify-center transition-all duration-300"
        style={{
          width: isSelected ? 32 : 26,
          height: isSelected ? 32 : 26,
          background: "#09090b",
          border: `${isSelected ? 3 : 2}px solid ${isSelected ? "#ff5f00" : stroke}`,
        }}
      />
      <span
        className="text-[8px] font-bold whitespace-nowrap transition-colors duration-300 group-hover:text-white"
        style={{ color: isSelected ? "#ffffff" : "#a1a1aa" }}
      >
        {nodeData.label}
      </span>
      <Handle type="source" position={Position.Right} style={hiddenHandleStyle} />
    </div>
  );
}

export const nodeTypes = {
  actorNode: ActorNode,
};
