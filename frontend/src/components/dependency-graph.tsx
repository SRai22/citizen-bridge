"use client";

import {
  Background,
  type Edge,
  type Node,
  type NodeProps,
  Panel,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo } from "react";

import type { TaskStatus } from "@/types/api";

export interface DependencyGraphTask {
  id: string;
  title: string;
  status: TaskStatus;
  dependencies: Array<{ depends_on_task_id: string }>;
}

// -- Status → visual mapping ---------------------------------------------------

const STATUS_COLORS: Record<TaskStatus, { bg: string; border: string; text: string }> = {
  pending: { bg: "#f8fafc", border: "#cbd5e1", text: "#475569" },
  ready: { bg: "#ecfdf5", border: "#6ee7b7", text: "#065f46" },
  in_progress: { bg: "#f5f3ff", border: "#a78bfa", text: "#5b21b6" },
  awaiting_approval: { bg: "#fffbeb", border: "#fbbf24", text: "#92400e" },
  submitted: { bg: "#eff6ff", border: "#60a5fa", text: "#1e40af" },
  completed: { bg: "#ecfdf5", border: "#34d399", text: "#065f46" },
  failed: { bg: "#fff1f2", border: "#fb7185", text: "#9f1239" },
  blocked: { bg: "#fff1f2", border: "#fda4af", text: "#9f1239" },
  cancelled: { bg: "#f8fafc", border: "#cbd5e1", text: "#475569" },
};

const STATUS_ICONS: Record<TaskStatus, string> = {
  pending: "☐",
  ready: "☐",
  in_progress: "⏳",
  awaiting_approval: "⏳",
  submitted: "⏳",
  completed: "✅",
  failed: "🔴",
  blocked: "🔴",
  cancelled: "—",
};

// -- Custom node component -----------------------------------------------------

function TaskNode({ data }: NodeProps<Node<{ label: string; status: TaskStatus; caseId: string; taskId: string }>>) {
  const router = useRouter();
  const colors = STATUS_COLORS[data.status];
  const icon = STATUS_ICONS[data.status];

  return (
    <button
      onClick={() => router.push(`/life-events/${data.caseId}/task/${data.taskId}`)}
      className="cursor-pointer rounded-xl px-4 py-3 text-left shadow-sm transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2"
      style={{ background: colors.bg, border: `2px solid ${colors.border}`, minWidth: 160 }}
    >
      <div className="flex items-center gap-2">
        {icon && (
          <span className="text-sm font-bold" style={{ color: colors.text }}>
            {icon}
          </span>
        )}
        <span className="text-sm font-semibold leading-tight" style={{ color: colors.text }}>
          {data.label}
        </span>
      </div>
    </button>
  );
}

const nodeTypes = { task: TaskNode };

// -- Dagre layout --------------------------------------------------------------

const NODE_WIDTH = 200;
const NODE_HEIGHT = 60;

function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 80, nodesep: 60 });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    };
  });
}

// -- Main component ------------------------------------------------------------

interface DependencyGraphProps {
  tasks: DependencyGraphTask[];
  caseId: string;
}

export function DependencyGraph({ tasks, caseId }: DependencyGraphProps) {
  const { initialNodes, initialEdges } = useMemo(() => {
    const nodes: Node[] = tasks.map((task) => ({
      id: task.id,
      type: "task",
      position: { x: 0, y: 0 },
      data: { label: task.title, status: task.status, caseId, taskId: task.id },
    }));

    const edges: Edge[] = tasks.flatMap((task) =>
      task.dependencies.map((dep) => ({
        id: `${dep.depends_on_task_id}-${task.id}`,
        source: dep.depends_on_task_id,
        target: task.id,
        animated: task.status === "blocked" || task.status === "pending",
        style: { stroke: task.status === "blocked" ? "#fb7185" : "#94a3b8", strokeWidth: 2 },
      })),
    );

    const laid = layoutGraph(nodes, edges);
    return { initialNodes: laid, initialEdges: edges };
  }, [tasks, caseId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const onNodeClick = useCallback(() => {
    // Navigation handled inside the TaskNode button
  }, []);

  return (
    <div className="h-[360px] w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        zoomOnScroll
        minZoom={0.5}
        maxZoom={1.5}
      >
        <Background gap={20} size={1} color="#e2e8f0" />
        <Panel position="top-right">
          <span className="rounded-md bg-white/80 px-2 py-1 text-[10px] font-medium text-slate-400 shadow-sm backdrop-blur">
            Scroll to zoom · Drag to pan
          </span>
        </Panel>
      </ReactFlow>
    </div>
  );
}
