import dagre from "@dagrejs/dagre";

export interface LayoutOptions {
  rankdir?: "LR" | "TB";
  nodeWidth?: number;
  nodeHeight?: number;
  nodesep?: number;
  ranksep?: number;
}

const DEFAULT_OPTIONS: Required<LayoutOptions> = {
  rankdir: "LR",
  nodeWidth: 140,
  nodeHeight: 40,
  nodesep: 60,
  ranksep: 160,
};

export function layoutWithDagre<
  N extends { id: string },
  E extends { source: string; target: string }
>(nodes: N[], edges: E[], options?: LayoutOptions): Array<N & { position: { x: number; y: number } }> {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: opts.rankdir, nodesep: opts.nodesep, ranksep: opts.ranksep });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of nodes) {
    g.setNode(node.id, { width: opts.nodeWidth, height: opts.nodeHeight });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: {
        x: pos.x - opts.nodeWidth / 2,
        y: pos.y - opts.nodeHeight / 2,
      },
    };
  });
}
