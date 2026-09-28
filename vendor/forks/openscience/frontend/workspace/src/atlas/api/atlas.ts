/** Atlas graph client backed by the selected OpenScience server's bridge. */

import type { ProjectRequest } from "@/utils/openscience-fetch"

export interface AtlasNode {
  node_id: string
  title: string | null
  summary: string
  hypothesis: string
  content: string
  kind: string
  lifecycle: "staged" | "committed" | string
  outcome: string | null
  parent_ids: string[]
  child_ids: string[]
  graph_tags: string[]
  tag_ids: string[]
  sharing_mode: "public" | "private" | "unlisted" | string
  slug_name: string | null
  repo_url: string | null
  branch_name: string | null
  head_commit_sha: string | null
  revision: number
  created_at: string
  updated_at: string
  updated_by: string | null
  no_artifacts_reason: string | null
}

export interface NodesListResponse {
  nodes: AtlasNode[]
  total: number
  page: number
  per_page: number
  has_more: boolean
}

export interface AtlasArtifact {
  artifact_id: string
  node_id: string
  kind: string
  name?: string
  uri?: string
  bytes?: number
  created_at?: string
  [key: string]: unknown
}

export interface ArtifactsListResponse {
  artifacts: AtlasArtifact[]
  has_more?: boolean
}

export interface InitProjectResponse {
  project_id: string | null
  error?: "unauthenticated" | "unreachable" | "plan" | "backend"
  status?: number
  message?: string
  host?: string
}

async function requestJSON<T>(
  request: ProjectRequest,
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await request(`/api/atlas${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = ""
    try {
      detail = (await res.json())?.detail ?? ""
    } catch {}
    throw new Error(`atlas ${method} ${path} failed: ${res.status}${detail ? ` — ${detail}` : ""}`)
  }
  if (!res.headers.get("content-type")?.includes("application/json")) {
    throw new Error(`atlas ${method} ${path} returned a non-JSON response`)
  }
  return res.json()
}

export interface GraphTreeResponse {
  anchor_node_id?: string
  root_node_ids?: string[]
  nodes: AtlasNode[]
  node_count?: number
}

export function createAtlasAPI(request: ProjectRequest) {
  const get = <T>(path: string) => requestJSON<T>(request, "GET", path)
  const post = <T>(path: string, body: unknown) => requestJSON<T>(request, "POST", path, body)

  return {
    /** The user's graphs = root nodes; the canvas shows one at a time. */
    listGraphs: () => get<NodesListResponse>("/graphs"),
    /** Full subgraph for a single graph/root. */
    getGraphTree: (id: string) => get<GraphTreeResponse>(`/graphs/${id}/tree`),
    createNode: (input: { title: string; projectID: string; parentID: string }) =>
      post<AtlasNode>("/nodes", {
        title: input.title,
        projectID: input.projectID,
        parent_id: input.parentID,
      }),
    /** Resolve the opened project's root without creating one. */
    resolveProject: () => get<{ project_id: string | null }>("/project"),
    /** Find or create the opened project's root after explicit user action. */
    initProject: () => post<InitProjectResponse>("/project/init", {}),
    listArtifacts: (nodeID: string) => get<ArtifactsListResponse | AtlasArtifact[]>(`/nodes/${nodeID}/artifacts`),
  }
}
