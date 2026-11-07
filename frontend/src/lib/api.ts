/**
 * API client configuration and communication layer with the FastAPI backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("cra_auth_token");
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("cra_auth_token", token);
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("cra_auth_token");
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = `${API_BASE_URL.replace(/\/$/, "")}/${endpoint.replace(/^\//, "")}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      clearStoredToken();
      throw new ApiError("Authentication credentials expired or invalid", 401);
    }

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = await response.text();
      }
      const message =
        typeof errorData === "object" && errorData?.detail
          ? errorData.detail
          : `HTTP error ${response.status}: ${response.statusText}`;
      throw new ApiError(message, response.status, errorData);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(err?.message || "Network request failed", 0, err);
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestInit) =>
    request<T>(endpoint, { ...options, method: "GET" }),

  post: <T>(endpoint: string, body?: any, options?: RequestInit) =>
    request<T>(endpoint, {
      ...options,
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: <T>(endpoint: string, body?: any, options?: RequestInit) =>
    request<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(endpoint: string, body?: any, options?: RequestInit) =>
    request<T>(endpoint, {
      ...options,
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(endpoint: string, options?: RequestInit) =>
    request<T>(endpoint, { ...options, method: "DELETE" }),

  // Domain-specific backend endpoints
  auth: {
    me: () => apiClient.get<any>("/api/auth/me"),
    login: (email: string) =>
      apiClient.post<any>("/api/auth/cli-login", { email }),
    tokens: () => apiClient.get<any[]>("/api/auth/tokens"),
    createToken: (name: string, days?: number) =>
      apiClient.post<any>("/api/auth/tokens", {
        name,
        expires_in_days: days,
      }),
    revokeToken: (id: string) => apiClient.delete<any>(`/api/auth/tokens/${id}`),
  },

  reviews: {
    list: (limit = 20) => apiClient.get<any[]>(`/api/reviews?limit=${limit}`),
    history: (params: {
      page?: number;
      page_size?: number;
      search?: string;
      source?: string;
      status?: string;
      severity?: string;
      repository?: string;
      team_id?: string;
      sort_by?: string;
      sort_order?: string;
    } = {}) => {
      const q = new URLSearchParams();
      if (params.page) q.set("page", String(params.page));
      if (params.page_size) q.set("page_size", String(params.page_size));
      if (params.search) q.set("search", params.search);
      if (params.source && params.source !== "all") q.set("source", params.source);
      if (params.status && params.status !== "all") q.set("status", params.status);
      if (params.severity && params.severity !== "all") q.set("severity", params.severity);
      if (params.repository && params.repository !== "all") q.set("repository", params.repository);
      if (params.team_id) q.set("team_id", params.team_id);
      if (params.sort_by) q.set("sort_by", params.sort_by);
      if (params.sort_order) q.set("sort_order", params.sort_order);
      return apiClient.get<any>(`/api/reviews/history?${q.toString()}`);
    },
    get: (id: string) => apiClient.get<any>(`/api/reviews/${id}`),
    submit: (codeDiff: string, teamId?: string) =>
      apiClient.post<any>("/api/review", {
        code_diff: codeDiff,
        team_id: teamId,
        source: "Web",
      }),
  },

  memories: {
    activeBank: (teamId?: string) =>
      apiClient.get<any>(
        teamId ? `/api/memories/active-bank?team_id=${teamId}` : "/api/memories/active-bank"
      ),
    facts: (teamId?: string, limit = 50) =>
      apiClient.get<any[]>(
        teamId
          ? `/api/memories/facts?team_id=${teamId}&limit=${limit}`
          : `/api/memories/facts?limit=${limit}`
      ),
    search: (query: string, limit = 5, teamId?: string) => {
      const q = new URLSearchParams({ query, limit: String(limit) });
      if (teamId) q.set("team_id", teamId);
      return apiClient.post<any>(`/api/memories/search?${q.toString()}`);
    },
    reviewTrace: (reviewId: string) =>
      apiClient.get<any>(`/api/memories/review-trace/${reviewId}`),
    retain: (rule: string, tags: string[] = [], teamId?: string) =>
      apiClient.post<any>("/api/retain", {
        rule,
        tags,
        team_id: teamId,
      }),
    recall: (query: string, topK = 5) =>
      apiClient.post<any>("/api/memories/recall", {
        query,
        top_k: topK,
      }),
  },

  teamRules: {
    list: (teamId?: string) =>
      apiClient.get<any[]>(
        teamId ? `/api/rules?team_id=${teamId}` : "/api/rules"
      ),
    create: (ruleText: string, teamId?: string) =>
      apiClient.post<any>("/api/rules", {
        rule: ruleText,
        team_id: teamId,
      }),
    delete: (ruleId: string) => apiClient.delete<any>(`/api/rules/${ruleId}`),
  },

  teams: {
    list: () => apiClient.get<any[]>("/api/teams"),
    settings: (teamId: string) => apiClient.get<any>(`/api/teams/${teamId}/settings`),
    updateSettings: (teamId: string, payload: { name?: string; hindsight_bank_id?: string; default_model?: string }) =>
      apiClient.put<any>(`/api/teams/${teamId}/settings`, payload),
    inviteMember: (teamId: string, payload: { email: string; role: string }) =>
      apiClient.post<any>(`/api/teams/${teamId}/members/invite`, payload),
    updateMemberRole: (teamId: string, userId: string, role: string) =>
      apiClient.put<any>(`/api/teams/${teamId}/members/${userId}/role`, { role }),
    removeMember: (teamId: string, userId: string) =>
      apiClient.delete<any>(`/api/teams/${teamId}/members/${userId}`),
    deleteRule: (teamId: string, ruleId: string) =>
      apiClient.delete<any>(`/api/teams/${teamId}/rules/${ruleId}`),
  },

  dashboard: {
    stats: (teamId?: string) =>
      apiClient.get<any>(
        teamId ? `/api/dashboard/stats?team_id=${teamId}` : "/api/dashboard/stats"
      ),
  },

  github: {
    status: () => apiClient.get<any>("/api/github/status"),
    connect: (accessToken: string) =>
      apiClient.post<any>("/api/github/connect", { access_token: accessToken }),
    disconnect: () => apiClient.delete<any>("/api/github/disconnect"),
    repositories: () => apiClient.get<any[]>("/api/github/repositories"),
    branches: (owner: string, repo: string) =>
      apiClient.get<any[]>(`/api/github/repositories/${owner}/${repo}/branches`),
    tree: (owner: string, repo: string, ref = "main", recursive = false) =>
      apiClient.get<any[]>(
        `/api/github/repositories/${owner}/${repo}/tree?ref=${ref}&recursive=${recursive}`
      ),
    reviewResource: (payload: {
      owner: string;
      repo: string;
      ref?: string;
      file_path?: string;
      commit_sha?: string;
      base?: string;
      head?: string;
      team_id?: string;
    }) => apiClient.post<any>("/api/github/review", payload),
  },

  pullRequests: {
    list: (
      owner: string,
      repo: string,
      filters: { language?: string; framework?: string; state?: string; team_id?: string } = {}
    ) => {
      const q = new URLSearchParams();
      if (filters.language) q.set("language", filters.language);
      if (filters.framework) q.set("framework", filters.framework);
      if (filters.state) q.set("state", filters.state);
      if (filters.team_id) q.set("team_id", filters.team_id);
      const queryStr = q.toString() ? `?${q.toString()}` : "";
      return apiClient.get<any[]>(`/api/pull-requests/${owner}/${repo}${queryStr}`);
    },
    review: (owner: string, repo: string, prNumber: number, teamId?: string) =>
      apiClient.post<any>("/api/pull-requests/review", {
        owner,
        repo,
        pr_number: prNumber,
        team_id: teamId,
      }),
  },
};

