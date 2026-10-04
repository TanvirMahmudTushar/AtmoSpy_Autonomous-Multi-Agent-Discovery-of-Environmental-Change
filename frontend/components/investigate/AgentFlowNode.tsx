import { Handle, Position } from "@xyflow/react";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { ICONS } from "@/components/pixel/icons";

export type FlowNodeStatus = "pending" | "running" | "done" | "error" | "skipped";

export interface AgentFlowNodeData {
  label: string;
  icon: keyof typeof ICONS;
  status: FlowNodeStatus;
  message?: string;
  count?: number; // discovery aggregate mode: candidates that reached this stage
  [key: string]: unknown;
}

const STATUS_COLOR: Record<FlowNodeStatus, string> = {
  pending: "var(--app-muted)",
  running: "var(--app-accent-cyan)",
  done: "var(--chart-good)",
  error: "var(--chart-critical)",
  skipped: "var(--app-muted)",
};

export function AgentFlowNode({ data }: { data: AgentFlowNodeData }) {
  const color = STATUS_COLOR[data.status];
  const pulsing = data.status === "running";

  return (
    <div
      className="hud-panel group flex w-[188px] cursor-pointer flex-col gap-1.5 !rounded-md p-3 transition-transform hover:-translate-y-0.5"
      title="Click for this agent's raw data"
      style={{
        borderColor: color,
        boxShadow: pulsing
          ? `0 0 0 1px ${color}, 0 0 18px -2px ${color}`
          : data.status === "done"
            ? `0 0 0 1px ${color}, 0 0 10px -4px ${color}`
            : undefined,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color, border: "none", width: 6, height: 6 }} />
      <div className="flex items-center gap-2">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 bg-[var(--app-panel-alt)] ${pulsing ? "animate-pulse" : ""}`}
          style={{ borderColor: color }}
        >
          <PixelSprite name={data.icon} size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-[8px] leading-tight text-[var(--app-ink)]">{data.label}</div>
          <div className="font-mono-data text-[9px] uppercase tracking-wide" style={{ color }}>
            {data.count !== undefined ? `${data.count} active` : data.status}
          </div>
        </div>
      </div>
      {data.message && (
        <div className="line-clamp-2 text-[9px] leading-tight text-[var(--app-ink-soft)]" title={data.message}>
          {data.message}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: color, border: "none", width: 6, height: 6 }} />
    </div>
  );
}

export const NODE_TYPES = { agentNode: AgentFlowNode };
