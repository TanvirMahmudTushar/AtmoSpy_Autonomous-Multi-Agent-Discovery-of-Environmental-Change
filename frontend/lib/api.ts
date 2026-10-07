import type {
  AuthResponse,
  DatasetInfo,
  FindingDetail,
  FindingSummary,
  Investigation,
  RegionInfo,
  User,
  VariableInfo,
  Watch,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "etd-token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private browsing / blocked storage */
  }
}

/** An HTTP error from the API. `status` is 0 when the request never got a
 * response (network down, backend asleep, CORS-blocked). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Could not reach the server. Please try again in a moment.", 0);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail || JSON.stringify(body);
    } catch {
      detail = await res.text().catch(() => "");
    }
    throw new ApiError(detail || `API ${path} failed: ${res.status}`, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  createInvestigation: (question: string) =>
    request<{ investigation_id: string }>("/api/investigations", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  getInvestigation: (id: string) => request<Investigation>(`/api/investigations/${id}`),

  listMyInvestigations: (limit = 20) => request<Investigation[]>(`/api/investigations?limit=${limit}`),

  startDiscovery: () =>
    request<{ investigation_id: string }>("/api/discover", { method: "POST", body: JSON.stringify({}) }),

  listFindings: (params?: {
    variable_code?: string;
    region_code?: string;
    significance?: string;
    investigation_id?: string;
    mine?: boolean;
    /** Only the newest finding per region/variable/period (hides repeat runs). */
    unique?: boolean;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.variable_code) qs.set("variable_code", params.variable_code);
    if (params?.region_code) qs.set("region_code", params.region_code);
    if (params?.significance) qs.set("significance", params.significance);
    if (params?.investigation_id) qs.set("investigation_id", params.investigation_id);
    if (params?.mine) qs.set("mine", "true");
    if (params?.unique) qs.set("unique", "true");
    if (params?.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<FindingSummary[]>(`/api/findings${suffix}`);
  },

  getFinding: (id: string) => request<FindingDetail>(`/api/findings/${id}`),

  getDatasets: () => request<DatasetInfo[]>("/api/datasets"),
  getVariables: () => request<VariableInfo[]>("/api/variables"),
  getRegions: () => request<RegionInfo[]>("/api/regions"),

  getHealth: () =>
    request<{ status: string; app: string; database: boolean; llm_available: boolean; nasa_power: boolean }>(
      "/api/health"
    ),

  signup: (email: string, password: string, display_name?: string) =>
    request<AuthResponse>("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password, display_name }) }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  guestLogin: () => request<AuthResponse>("/api/auth/guest", { method: "POST" }),

  me: () => request<User>("/api/auth/me"),

  listWatches: () => request<Watch[]>("/api/watches"),
  createWatch: (region_code: string, variable_code: string, frequency_days: number) =>
    request<Watch>("/api/watches", {
      method: "POST",
      body: JSON.stringify({ region_code, variable_code, frequency_days }),
    }),
  deleteWatch: (id: string) => request<void>(`/api/watches/${id}`, { method: "DELETE" }),
  toggleWatch: (id: string) => request<Watch>(`/api/watches/${id}/toggle`, { method: "POST" }),
  checkWatchNow: (id: string) =>
    request<{ investigation_id: string }>(`/api/watches/${id}/check-now`, { method: "POST" }),
};

export function eventsUrl(kind: "investigations" | "discover", id: string): string {
  return `${API_URL}/api/${kind}/${id}/events`;
}

export { API_URL };
