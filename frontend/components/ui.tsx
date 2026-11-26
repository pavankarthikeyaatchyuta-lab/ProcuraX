"use client";
import Link from "next/link";
import { useState, type ReactNode, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Search,
  Inbox,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { useResource, useWorkspace, type Row } from "./workspace";
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Status({ value }: { value: string }) {
  const tone = [
    "approved",
    "received",
    "paid",
    "awarded",
    "healthy",
    "completed",
    "connected",
  ].includes(value)
    ? "green"
    : ["rejected", "cancelled", "failed", "overdue", "stockout"].includes(value)
      ? "red"
      : [
            "awaiting_approval",
            "pending",
            "partially_received",
            "reorder",
            "returned",
            "dispatched",
          ].includes(value)
        ? "amber"
        : "neutral";
  return <Badge tone={tone}>{value?.replaceAll("_", " ")}</Badge>;
}
export function PageHeader({
  title,
  description,
  action,
  back,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  back?: string;
}) {
  return (
    <div className="page-header">
      <div>
        {back && (
          <Link className="back-link" href={back}>
            <ArrowLeft size={16} />
            Back
          </Link>
        )}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="page-actions">{action}</div>}
    </div>
  );
}
export function Panel({
  title,
  description,
  action,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={"panel " + className}>
      {title && (
        <header className="panel-header">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
export function Empty({
  title = "No records yet",
  detail = "Your records will appear here.",
  action,
}: {
  title?: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span>
        <Inbox size={26} />
      </span>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}
export function ErrorBox({ error }: { error?: string }) {
  return error ? (
    <div className="error" role="alert">
      <AlertCircle size={18} />
      <span>{error}</span>
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <Loader2 className="spin" size={22} />
      Loading your workspace…
    </div>
  );
}
export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: string;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      className={"button " + variant}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
export function ActionLink({
  href,
  children,
  secondary = false,
}: {
  href: string;
  children: ReactNode;
  secondary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={"button " + (secondary ? "secondary" : "primary")}
    >
      {children}
    </Link>
  );
}
export function Stat({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
  icon?: ReactNode;
}) {
  return (
    <section className="stat">
      <div className="stat-label">
        {label}
        {icon}
      </div>
      <strong>{value}</strong>
      {detail && <p>{detail}</p>}
    </section>
  );
}
export type Column = {
  key: string;
  label: string;
  render?: (row: Row) => ReactNode;
  numeric?: boolean;
};
export function Table({
  heads,
  children,
}: {
  heads: string[];
  children: ReactNode;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {heads.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
export function DataTable({
  columns,
  rows,
  empty = "No matching records",
  searchable = true,
  pageSize = 10,
}: {
  columns: Column[];
  rows: Row[];
  empty?: string;
  searchable?: boolean;
  pageSize?: number;
}) {
  const [query, setQuery] = useState(""),
    [sort, setSort] = useState(""),
    [desc, setDesc] = useState(false),
    [page, setPage] = useState(1);
  let values = rows.filter((r) =>
    JSON.stringify(r).toLowerCase().includes(query.toLowerCase()),
  );
  if (sort)
    values = [...values].sort((a, b) => {
      const av = a[sort],
        bv = b[sort];
      return (
        (typeof av === "number" || !Number.isNaN(Number(av))
          ? Number(av) - Number(bv)
          : String(av ?? "").localeCompare(String(bv ?? ""))) * (desc ? -1 : 1)
      );
    });
  const visible = values.slice((page - 1) * pageSize, page * pageSize);
  return (
    <>
      {searchable && (
        <div className="table-toolbar">
          <label className="search">
            <Search size={17} />
            <input
              aria-label="Search records"
              placeholder="Search records…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <span className="muted">
            {values.length} {values.length === 1 ? "record" : "records"}
          </span>
        </div>
      )}
      {values.length ? (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c.key} className={c.numeric ? "numeric" : ""}>
                      <button
                        onClick={() => {
                          setSort(c.key);
                          setDesc(sort === c.key ? !desc : false);
                        }}
                      >
                        {c.label}
                        {sort === c.key ? (
                          desc ? (
                            <ChevronDown size={13} />
                          ) : (
                            <ChevronUp size={13} />
                          )
                        ) : null}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((r, i) => (
                  <tr key={r.id || i}>
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={c.numeric ? "numeric" : ""}
                        data-label={c.label}
                      >
                        {c.render ? c.render(r) : String(r[c.key] ?? "—")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            total={values.length}
            size={pageSize}
            setPage={setPage}
          />
        </>
      ) : (
        <Empty
          title={empty}
          detail="Try a different search or add a new record."
        />
      )}
    </>
  );
}
export function Pagination({
  page,
  total,
  size,
  setPage,
}: {
  page: number;
  total: number;
  size: number;
  setPage: (v: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {total
          ? `${(page - 1) * size + 1}–${Math.min(page * size, total)} of ${total}`
          : "0 records"}
      </span>
      <div>
        <button
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => setPage(page - 1)}
        >
          <ArrowLeft size={16} />
        </button>
        <span>Page {page}</span>
        <button
          aria-label="Next page"
          disabled={page * size >= total}
          onClick={() => setPage(page + 1)}
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
export function RecordsTable({
  path,
  columns,
  statusOptions,
}: {
  path: string;
  columns: Column[];
  statusOptions?: string[];
}) {
  const [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [status, setStatus] = useState("");
  const parts=path.split('?');const params=new URLSearchParams(parts[1]);params.set('page',String(page));params.set('page_size','20');if(q)params.set('q',q);if(statusOptions)params.set('status',status);
  const { data, error, loading } = useResource(parts[0]+'?'+params.toString());
  return (
    <>
      <div className="table-toolbar">
        <label className="search">
          <Search size={17} />
          <input
            aria-label="Search records"
            placeholder="Search records…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
        {statusOptions && (
          <select
            aria-label="Filter status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        )}
      </div>
      <ErrorBox error={error} />
      {loading && !data ? (
        <Loading />
      ) : data?.items.length ? (
        <>
          <DataTable rows={data.items} columns={columns} searchable={false} pageSize={200} />
          <Pagination
            page={page}
            total={data.total}
            size={20}
            setPage={setPage}
          />
        </>
      ) : (
        <Empty />
      )}
    </>
  );
}
export type Field = {
  key: string;
  label: string;
  type?: string;
  value?: any;
  required?: boolean;
  help?: string;
  options?: { value: string; label: string }[];
};
export function Form({
  fields,
  onSubmit,
  button = "Save changes",
  children,
}: {
  fields: Field[];
  onSubmit: (v: Row) => Promise<unknown>;
  button?: string;
  children?: ReactNode;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <form
      onSubmit={async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        const values = Object.fromEntries(new FormData(e.currentTarget));
        try {
          await onSubmit(values);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="form-grid">
        {fields.map((f) => (
          <label key={f.key}>
            {f.label}
            {f.options ? (
              <select
                name={f.key}
                required={f.required}
                defaultValue={f.value ?? ""}
              >
                <option value="">Select…</option>
                {f.options.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : f.type === "textarea" ? (
              <textarea
                name={f.key}
                defaultValue={f.value ?? ""}
                required={f.required}
              />
            ) : (
              <input
                name={f.key}
                type={f.type || "text"}
                step="any"
                defaultValue={f.value ?? ""}
                required={f.required}
                autoComplete={f.type === "password" ? "new-password" : "off"}
              />
            )}{" "}
            {f.help && <small>{f.help}</small>}
          </label>
        ))}
      </div>
      {children}
      <ErrorBox error={error} />
      <div className="form-actions">
        <Button type="submit" disabled={busy}>
          {busy ? <Loader2 size={16} className="spin" /> : null}
          {busy ? "Saving…" : button}
        </Button>
      </div>
    </form>
  );
}
export function useAction(reload?: () => void) {
  const { api, setNotice } = useWorkspace();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function run(
    path: string,
    method = "POST",
    body?: unknown,
    message = "Saved successfully",
  ) {
    setBusy(true);
    setError("");
    try {
      const value = await api(path, method, body);
      setNotice(message);
      reload?.();
      return value;
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setBusy(false);
    }
  }
  return { run, error, busy };
}
