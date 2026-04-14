const toNumber = (value, fallback = 0) => {
  if (value === null || value === undefined) return fallback;
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

export const filterEdgesData = (edgesData, { minValue = 0, maxEdges } = {}) => {
  const min = Math.max(0, toNumber(minValue, 0));
  let filtered = edgesData.filter((tx) => toNumber(tx.amount, 0) >= min);

  if (maxEdges && filtered.length > maxEdges) {
    filtered = [...filtered].sort((a, b) => {
      const blockA = toNumber(a.blockNumber, 0);
      const blockB = toNumber(b.blockNumber, 0);
      if (blockA !== blockB) return blockB - blockA;
      return toNumber(b.amount, 0) - toNumber(a.amount, 0);
    }).slice(0, maxEdges);
  }

  return filtered;
};

const buildAdjacency = (edges) => {
  const adjacency = new Map();
  edges.forEach((edge) => {
    if (!edge.source || !edge.target) return;
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set());
    adjacency.get(edge.source).add(edge.target);
    adjacency.get(edge.target).add(edge.source);
  });
  return adjacency;
};

const buildDegreeMap = (edges) => {
  const degree = {};
  edges.forEach((edge) => {
    if (!edge.source || !edge.target) return;
    degree[edge.source] = (degree[edge.source] || 0) + 1;
    degree[edge.target] = (degree[edge.target] || 0) + 1;
  });
  return degree;
};

export const collapseLowActivityNodes = ({
  nodes,
  edges,
  centerId,
  maxNodes,
  leafDegree = 1,
  createSummaryNode,
  createSummaryEdge,
} = {}) => {
  if (!nodes.length) {
    return { nodes, edges, meta: { collapsed: 0, summaryNodes: 0, dropped: 0 } };
  }

  const degree = buildDegreeMap(edges);
  const adjacency = buildAdjacency(edges);
  const nodeIds = nodes.map((node) => node.id);

  const keep = new Set();
  if (centerId && nodeIds.includes(centerId)) keep.add(centerId);

  const sorted = [...nodeIds].sort((a, b) => (degree[b] || 0) - (degree[a] || 0));
  const target = maxNodes ? Math.max(1, maxNodes) : nodeIds.length;
  for (const id of sorted) {
    if (keep.size >= target) break;
    keep.add(id);
  }

  const leafNodes = nodeIds.filter(
    (id) => !keep.has(id) && (degree[id] || 0) <= leafDegree,
  );

  const summaryCounts = new Map();
  let dropped = 0;
  leafNodes.forEach((id) => {
    const neighbors = adjacency.get(id) || new Set();
    const hub = [...neighbors].find((nodeId) => keep.has(nodeId));
    if (hub) {
      summaryCounts.set(hub, (summaryCounts.get(hub) || 0) + 1);
    } else {
      dropped += 1;
    }
  });

  const summaryEntries = [...summaryCounts.entries()].filter(([, count]) => count > 0);

  const summaryNodes = [];
  const summaryEdges = [];
  summaryEntries.forEach(([hub, count]) => {
    const summaryId = `summary:${hub}`;
    if (createSummaryNode) summaryNodes.push(createSummaryNode(summaryId, hub, count));
    if (createSummaryEdge) summaryEdges.push(createSummaryEdge(summaryId, hub, count));
  });

  const keptNodes = nodes.filter((node) => keep.has(node.id));
  const keptEdges = edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target));

  return {
    nodes: [...keptNodes, ...summaryNodes],
    edges: [...keptEdges, ...summaryEdges],
    meta: {
      collapsed: leafNodes.length,
      summaryNodes: summaryNodes.length,
      dropped,
    },
  };
};

export const applyRadialLayout = (nodes, edges, centerId, options = {}) => {
  if (!nodes.length) return nodes;

  const ringSpacing = options.ringSpacing || 220;
  const minRadius = options.minRadius || 80;

  const adjacency = buildAdjacency(edges);
  const nodeIds = nodes.map((node) => node.id);
  const center = centerId && nodeIds.includes(centerId) ? centerId : nodeIds[0];

  const depth = {};
  const visited = new Set([center]);
  const queue = [center];
  depth[center] = 0;

  while (queue.length) {
    const current = queue.shift();
    (adjacency.get(current) || []).forEach((neighbor) => {
      if (visited.has(neighbor)) return;
      visited.add(neighbor);
      depth[neighbor] = (depth[current] || 0) + 1;
      queue.push(neighbor);
    });
  }

  const maxDepth = Math.max(...Object.values(depth));
  nodeIds.forEach((id) => {
    if (depth[id] === undefined) depth[id] = maxDepth + 1;
  });

  const levels = new Map();
  nodeIds.forEach((id) => {
    const level = depth[id] || 0;
    if (!levels.has(level)) levels.set(level, []);
    levels.get(level).push(id);
  });

  const nodeIndex = new Map(nodes.map((node, idx) => [node.id, idx]));
  const nextNodes = nodes.map((node) => ({ ...node }));

  [...levels.entries()].sort((a, b) => a[0] - b[0]).forEach(([level, ids]) => {
    const radius = level === 0 ? 0 : minRadius + (level - 1) * ringSpacing;
    const sortedIds = [...ids].sort();
    const count = sortedIds.length;
    sortedIds.forEach((id, index) => {
      const angle = count === 1 ? 0 : (2 * Math.PI * index) / count;
      const x = radius * Math.cos(angle);
      const y = radius * Math.sin(angle);
      const idx = nodeIndex.get(id);
      if (idx !== undefined) nextNodes[idx] = { ...nextNodes[idx], position: { x, y } };
    });
  });

  return nextNodes;
};
