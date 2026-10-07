"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { NODE_TYPES, type AgentFlowNodeData, type FlowNodeStatus } from "./AgentFlowNode";
import { NodeDetailModal } from "./NodeDetailModal";
import type { ICONS } from "@/components/pixel/icons";
import type { InvestigationStep } from "@/lib/types";

type IconName = keyof typeof ICONS;

interface StageDef {
  id: string;
  agent: string;
  label: string;
  icon: IconName;
  x: number;
  y: number;
}

// Mirrors the real DAG in backend/app/agents/orchestrator.py::_run_pipeline —
// Spatial and Relationship are independent analyses that both depend on
// Statistics and both feed into the robustness check, so they're drawn as a
// genuine branch/merge rather than flattened into one line.
const STAGES: StageDef[] = [
  { id: "orchestrator", agent: "ORCHESTRATOR", label: "Orchestrator", icon: "compass", x: 0, y: 90 },
  { id: "nasa_data", agent: "NASA_DATA_AGENT", label: "NASA Data", icon: "satellite", x: 210, y: 90 },
  { id: "quality", agent: "DATA_QUALITY_AGENT", label: "Data Quality", icon: "magnifier", x: 420, y: 90 },
  { id: "trend", agent: "TREND_AGENT", label: "Trend", icon: "chart", x: 630, y: 90 },
  { id: "statistics", agent: "STATISTICS_AGENT", label: "Statistics", icon: "scales", x: 840, y: 90 },
  { id: "spatial", agent: "SPATIAL_AGENT", label: "Spatial", icon: "pin", x: 1050, y: 10 },
  { id: "relationship", agent: "RELATIONSHIP_AGENT", label: "Relationship", icon: "link", x: 1050, y: 170 },
  { id: "investigation", agent: "INVESTIGATION_AGENT", label: "Robustness", icon: "telescope", x: 1270, y: 90 },
  { id: "skeptic", agent: "SKEPTIC_AGENT", label: "Skeptic", icon: "flag", x: 1480, y: 90 },
  { id: "report", agent: "REPORT_AGENT", label: "Report", icon: "scroll", x: 1690, y: 90 },
];

const EDGES: [string, string][] = [
  ["orchestrator", "nasa_data"],
  ["nasa_data", "quality"],
  ["quality", "trend"],
  ["trend", "statistics"],
  ["statistics", "spatial"],
  ["statistics", "relationship"],
  ["spatial", "investigation"],
  ["relationship", "investigation"],
  ["investigation", "skeptic"],
  ["skeptic", "report"],
];

function latestFor(agent: string, steps: InvestigationStep[]) {
  const relevant = steps.filter((s) => s.agent === agent);
  return relevant.length ? relevant[relevant.length - 1] : null;
}

function statusOf(agent: string, steps: InvestigationStep[]): FlowNodeStatus {
  const last = latestFor(agent, steps);
  if (!last) return "pending";
  if (last.status === "running" || last.status === "done" || last.status === "error" || last.status === "skipped") {
    return last.status;
  }
  return "pending";
}

const CANDIDATE_LABEL = /^\[([^\]]+)\]/;

/**
 * Single-run mode (used by /investigate): one status per node, driven
 * directly by the live SSE step stream.
 *
 * Aggregate mode (used by /discover): ~16 candidates run this graph
 * concurrently, so each node instead shows a count of how many candidates
 * have reached it — an honest representation of a fan-out, not a fake
 * single run.
 */
export function AgentFlowGraph({ steps, mode = "single" }: { steps: InvestigationStep[]; mode?: "single" | "aggregate" }) {
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);

  const { nodes: builtNodes, edges } = useMemo(() => {
    const nodes: Node<AgentFlowNodeData>[] = STAGES.map((stage) => {
      let status: FlowNodeStatus = "pending";
      let message: string | undefined;
      let count: number | undefined;

      if (mode === "single") {
        status = statusOf(stage.agent, steps);
        message = latestFor(stage.agent, steps)?.message;
      } else {
        const seen = new Set<string>();
        let lastMsg: string | undefined;
        for (const s of steps) {
          if (s.agent !== stage.agent) continue;
          const m = CANDIDATE_LABEL.exec(s.message);
          if (m) seen.add(m[1]);
          lastMsg = s.message;
        }
        count = seen.size;
        status = count > 0 ? "running" : "pending";
        message = lastMsg;
      }

      return {
        id: stage.id,
        type: "agentNode",
        position: { x: stage.x, y: stage.y },
        data: { label: stage.label, icon: stage.icon, status, message, count },
        draggable: false,
        selectable: false,
      };
    });

    const edges: Edge[] = EDGES.map(([from, to]) => {
      const fromNode = nodes.find((n) => n.id === from)!;
      const active = fromNode.data.status === "done" || (fromNode.data.count ?? 0) > 0;
      const color = active ? "var(--app-accent-cyan)" : "var(--app-border)";
      return {
        id: `${from}-${to}`,
        source: from,
        target: to,
        animated: active,
        style: { stroke: color, strokeWidth: active ? 2 : 1.5 },
      };
    });

    return { nodes, edges };
  }, [steps, mode]);

  // React Flow drops a node's measured size and handle positions whenever it
  // receives a new node object, and only re-measures nodes whose DOM size then
  // changes — the rest stay hidden with their edges gone. So keep the nodes in
  // React Flow state (onNodesChange records the measurements) and swap only
  // `data` as SSE steps arrive.
  const [nodes, setNodes, onNodesChange] = useNodesState(builtNodes);
  useEffect(() => {
    setNodes((prev) =>
      builtNodes.map((node) => {
        const existing = prev.find((p) => p.id === node.id);
        return existing ? { ...existing, data: node.data } : node;
      }),
    );
  }, [builtNodes, setNodes]);

  const onNodeClick: NodeMouseHandler = (_, node) => setSelectedStageId(node.id);
  const selectedStage = STAGES.find((s) => s.id === selectedStageId);
  const selectedSteps = selectedStage ? steps.filter((s) => s.agent === selectedStage.agent) : [];

  return (
    <div className="hud-panel overflow-hidden p-0" style={{ height: 320 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.4}
        maxZoom={1.2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        onNodeClick={onNodeClick}
        panOnScroll
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--app-hud-line)" />
        <Controls showInteractive={false} className="!bottom-2 !left-2" />
      </ReactFlow>
      {selectedStage && (
        <NodeDetailModal
          agentLabel={selectedStage.label}
          icon={selectedStage.icon}
          steps={selectedSteps}
          onClose={() => setSelectedStageId(null)}
        />
      )}
    </div>
  );
}
