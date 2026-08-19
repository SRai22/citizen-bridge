import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import type { Task } from "@/types/api";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock @xyflow/react to avoid canvas/DOM measurement issues in jsdom
vi.mock("@xyflow/react", () => {
  const actual: Record<string, unknown> = {};
  return {
    ...actual,
    ReactFlow: ({ nodes, edges }: { nodes: unknown[]; edges: unknown[] }) => (
      <div data-testid="react-flow" data-nodes={nodes.length} data-edges={edges.length} />
    ),
    Background: () => null,
    Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
    useNodesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
    useEdgesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
  };
});

// Must import after mocks
import { DependencyGraph } from "./dependency-graph";

function makeTask(overrides: Partial<Task> & { id: string; title: string }): Task {
  return {
    case_id: "case-1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    workflow_id: "wf",
    task_type: "test",
    status: "ready",
    input_data: {},
    output_data: {},
    completed_at: null,
    dependencies: [],
    external_applications: [],
    approval_requests: [],
    ...overrides,
  };
}

describe("DependencyGraph", () => {
  const caseId = "case-1";

  const tasks: Task[] = [
    makeTask({ id: "t1", title: "Death Certificate", status: "completed" }),
    makeTask({
      id: "t2",
      title: "Family Pension",
      status: "ready",
      dependencies: [{ id: "d1", created_at: "", updated_at: "", task_id: "t2", depends_on_task_id: "t1", dependency_type: "document" }],
    }),
    makeTask({
      id: "t3",
      title: "BESCOM Transfer",
      status: "blocked",
      dependencies: [{ id: "d2", created_at: "", updated_at: "", task_id: "t3", depends_on_task_id: "t1", dependency_type: "document" }],
    }),
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders ReactFlow with correct node and edge count", () => {
    render(<DependencyGraph tasks={tasks} caseId={caseId} />);
    const flow = screen.getByTestId("react-flow");
    expect(flow).toHaveAttribute("data-nodes", "3");
    expect(flow).toHaveAttribute("data-edges", "2");
  });

  test("renders without crashing when tasks is empty", () => {
    render(<DependencyGraph tasks={[]} caseId={caseId} />);
    const flow = screen.getByTestId("react-flow");
    expect(flow).toHaveAttribute("data-nodes", "0");
    expect(flow).toHaveAttribute("data-edges", "0");
  });

  test("renders the graph container element", () => {
    const { container } = render(<DependencyGraph tasks={tasks} caseId={caseId} />);
    expect(container.querySelector(".h-\\[360px\\]")).toBeInTheDocument();
  });
});
