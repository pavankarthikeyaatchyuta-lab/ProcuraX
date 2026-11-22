"use client";
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
export type Row = Record<string, any>;
export const money = (v: unknown) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(v || 0));
export const number = (v: unknown) =>
  Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
export const today = () =>
  new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
export const date = (v: unknown) =>
  v
    ? new Date(
        String(v).includes("T") && !String(v).endsWith("Z")
          ? String(v) + "Z"
          : String(v),
      ).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "Asia/Kolkata",
      })
    : "—";
type Workspace = {
  me: Row | null;
  business: string;
  branch: string;
  branches: Row[];
  role: string;
  loading: boolean;
  notice: string;
  setNotice: (v: string) => void;
  setBusiness: (v: string) => void;
  setBranch: (v: string) => void;
  profile: () => Promise<void>;
  api: (path: string, method?: string, body?: unknown) => Promise<any>;
  base: string;
  refreshBranches: () => Promise<void>;
};
const Context = createContext<Workspace | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Row | null>(null),
    [business, setBusinessValue] = useState(""),
    [branch, setBranchValue] = useState(""),
    [branches, setBranches] = useState<Row[]>([]),
    [loading, setLoading] = useState(true),
    [notice, setNotice] = useState(""),
    [role, setRole] = useState("reviewer");
  const profile = useCallback(async () => {
    try {
      const r = await fetch("/api/v1/auth/me");
      if (!r.ok) {
        setMe(null);
        return;
      }
      const user = await r.json();
      setMe(user);
      setBusinessValue((current) =>
        user.businesses.some((b: Row) => b.id === current)
          ? current
          : user.businesses[0]?.id || "",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    profile();
  }, [profile]);
  const base = "/businesses/" + business;
  const api = useCallback(
    async (path: string, method = "GET", body?: unknown) => {
      const url =
        "/api/v1" +
        (path.startsWith("/auth") || path === "/businesses"
          ? path
          : base + path);
      const response = await fetch(url, {
        method,
        headers: {
          ...(body instanceof FormData
            ? {}
            : { "Content-Type": "application/json" }),
          "x-csrf-token": me?.csrf || "",
          ...(branch ? { "x-branch-id": branch } : {}),
        },
        ...(body !== undefined
          ? { body: body instanceof FormData ? body : JSON.stringify(body) }
          : {}),
      });
      const text = await response.text();
      let value;
      try {
        value = JSON.parse(text);
      } catch {
        throw new Error("The service is unavailable. Please retry.");
      }
      if (!response.ok) {
        const d = value.detail;
        throw new Error(
          typeof d === "string"
            ? d
            : Array.isArray(d)
              ? d
                  .map((x: Row | string) =>
                    typeof x === "string" ? x : x.msg || JSON.stringify(x),
                  )
                  .join("\n")
              : JSON.stringify(d || value),
        );
      }
      return value;
    },
    [base, branch, me?.csrf],
  );
  const refreshBranches = useCallback(async () => {
    if (!business || !me) return;
    const r = await fetch(
      "/api/v1/businesses/" + business + "/workspace/branches",
      { headers: { "x-csrf-token": me.csrf } },
    );
    if (r.ok) {
      const values = await r.json();
      setBranches(values);
      setBranchValue((current) =>
        current === "all" || values.some((b: Row) => b.id === current)
          ? current
              : values.find((b:Row)=>b.code==='MAIN')?.id || values[0]?.id || "",
      );
    }
  }, [business, me]);
  useEffect(() => {
    refreshBranches();
  }, [refreshBranches]);
  useEffect(() => {
    if (business && branch)
      api("/workspace/session")
        .then((v) => setRole(v.role))
        .catch(() => {});
  }, [api, business, branch]);
  function setBusiness(v: string) {
    setBranches([]);
    setBranchValue("");
    setBusinessValue(v);
    setNotice("");
  }
  function setBranch(v: string) {
    setBranchValue(v);
    setNotice("");
  }
  return (
    <Context.Provider
      value={{
        me,
        business,
        branch,
        branches,
        role,
        loading,
        notice,
        setNotice,
        setBusiness,
        setBranch,
        profile,
        api,
        base,
        refreshBranches,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useWorkspace() {
  const context = useContext(Context);
  if (!context) throw new Error("Workspace provider is missing");
  return context;
}
export function useResource(path: string | null) {
  const { api } = useWorkspace();
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    if (!path) return;
    setLoading(true);
    setError("");
    api(path)
      .then((v) => {
        if (live) setData(v);
      })
      .catch((e) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [path, api, tick]);
  return { data, error, loading, reload: () => setTick((v) => v + 1) };
}
