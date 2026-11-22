"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, ArrowRight, Wallet, Download } from "lucide-react";
import {
  useResource,
  useWorkspace,
  money,
  number,
  date,
  today,
  type Row,
} from "./workspace";
import {
  PageHeader,
  Panel,
  RecordsTable,
  DataTable,
  Form,
  ActionLink,
  Loading,
  ErrorBox,
  Status,
  Stat,
} from "./ui";
export function Payables() {
  return (
    <>
      <PageHeader
        title="Supplier payables"
        description="Track verified bills, payment records, and supplier credits. No money is transferred by this application."
      />
      <Panel>
        <RecordsTable
          path="/workspace/payables"
          statusOptions={[
            "open",
            "overdue",
            "partially_paid",
            "paid",
            "inactive",
          ]}
          columns={[
            {
              key: "invoice_no",
              label: "Invoice",
              render: (p) => (
                <Link
                  href={"/purchasing/payables/" + p.id}
                  className="record-link"
                >
                  {p.invoice_no}
                  <small>{p.supplier_name}</small>
                </Link>
              ),
            },
            { key: "due", label: "Due date", render: (p) => date(p.due) },
            {
              key: "amount",
              label: "Invoice amount",
              numeric: true,
              render: (p) => money(p.amount),
            },
            {
              key: "paid",
              label: "Recorded payments",
              numeric: true,
              render: (p) => money(p.paid),
            },
            {
              key: "outstanding",
              label: "Outstanding",
              numeric: true,
              render: (p) => <strong>{money(p.outstanding)}</strong>,
            },
            {
              key: "status",
              label: "Status",
              render: (p) => <Status value={p.status} />,
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function PayableDetail() {
  const { id } = useParams<{ id: string }>(),
    resource = useResource("/workspace/payables/" + id);
  const p = resource.data;
  if (!p)
    return (
      <>
        <ErrorBox error={resource.error} />
        <Loading />
      </>
    );
  return (
    <>
      <PageHeader
        title={p.invoice_no}
        description={p.supplier_name + " · Supplier payable"}
        back="/purchasing/payables"
        action={
          <>
            <ActionLink
              href={"/purchasing/payables/" + id + "/credit"}
              secondary
            >
              Record supplier credit
            </ActionLink>
            <ActionLink href={"/purchasing/payables/" + id + "/payment"}>
              <Plus size={16} />
              Record payment
            </ActionLink>
          </>
        }
      />
      <div className="stats-grid">
        <Stat
          label="Invoice amount"
          value={money(p.amount)}
          detail={"Invoice date " + date(p.invoice_date)}
        />
        <Stat label="Recorded payments" value={money(p.paid)} />
        <Stat label="Supplier credits" value={money(p.credited)} />
        <Stat
          label="Outstanding balance"
          value={money(p.outstanding)}
          detail={"Due " + date(p.due)}
        />
      </div>
      <Panel title="Recorded payment history">
        <DataTable
          rows={p.payments}
          columns={[
            { key: "date", label: "Date", render: (r) => date(r.date) },
            {
              key: "amount",
              label: "Amount",
              numeric: true,
              render: (r) => money(r.amount),
            },
            { key: "method", label: "Method" },
            { key: "reference", label: "Payment reference" },
          ]}
        />
      </Panel>
      <Panel title="Supplier credit evidence">
        <DataTable
          rows={p.credits}
          columns={[
            { key: "date", label: "Date", render: (r) => date(r.date) },
            { key: "reference", label: "Credit reference" },
            {
              key: "amount",
              label: "Amount",
              numeric: true,
              render: (r) => money(r.amount),
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function PaymentForm() {
  const { id } = useParams<{ id: string }>(),
    w = useWorkspace(),
    router = useRouter(),
    resource = useResource("/workspace/payables/" + id),
    [key] = useState(() => crypto.randomUUID());
  const p = resource.data;
  if (!p) return <Loading />;
  return (
    <>
      <PageHeader
        title="Record supplier payment"
        description={`${p.invoice_no} · ${p.supplier_name} · Outstanding ${money(p.outstanding)}`}
        back={"/purchasing/payables/" + id}
      />
      <Panel title="Payment evidence" className="form-panel">
        <div className="info">
          This records a payment you made outside Vyaya. It does not move money,
          access a bank account, or initiate a UPI transfer.
        </div>
        <Form
          button="Record payment"
          fields={[
            {
              key: "amount",
              label: "Amount paid (₹)",
              type: "number",
              required: true,
              value: p.outstanding,
            },
            {
              key: "date",
              label: "Payment date",
              type: "date",
              required: true,
              value: today(),
            },
            {
              key: "method",
              label: "Payment method",
              required: true,
              options: ["bank_transfer", "upi", "cash", "cheque", "other"].map(
                (v) => ({ value: v, label: v.replaceAll("_", " ") }),
              ),
            },
            {
              key: "reference",
              label: "External transaction / receipt reference",
              required: true,
            },
          ]}
          onSubmit={async (v) => {
            await w.api("/workspace/payables/" + id + "/payments", "POST", {
              ...v,
              version: p.version,
              idempotency_key: key,
            });
            w.setNotice("Payment recorded. No funds were moved by Vyaya.");
            router.push("/purchasing/payables/" + id);
          }}
        />
      </Panel>
    </>
  );
}
export function CreditForm() {
  const { id } = useParams<{ id: string }>(),
    w = useWorkspace(),
    router = useRouter(),
    resource = useResource("/workspace/payables/" + id),
    returns = useResource("/workspace/returns");
  const p = resource.data;
  if (!p) return <Loading />;
  return (
    <>
      <PageHeader
        title="Record supplier credit"
        description="Link an acknowledged supplier credit to a return and a verified invoice."
        back={"/purchasing/payables/" + id}
      />
      <Panel title="Credit evidence" className="form-panel">
        <Form
          button="Record supplier credit"
          fields={[
            {
              key: "return_id",
              label: "Supplier return",
              required: true,
              options: (returns.data || [])
                .filter((r: Row) => r.supplier_id === p.supplier_id)
                .map((r: Row) => ({
                  value: r.id,
                  label: `${r.order_number} · ${date(r.created)} · ${r.id.slice(0, 8)}`,
                })),
            },
            {
              key: "amount",
              label: "Acknowledged credit amount (₹)",
              type: "number",
              required: true,
            },
            {
              key: "reference",
              label: "Supplier credit-note reference",
              required: true,
            },
            {
              key: "date",
              label: "Credit-note date",
              type: "date",
              required: true,
              value: today(),
            },
          ]}
          onSubmit={async (v) => {
            await w.api("/workspace/payables/" + id + "/credits", "POST", {
              ...v,
              version: p.version,
            });
            w.setNotice("Supplier credit linked");
            router.push("/purchasing/payables/" + id);
          }}
        />
      </Panel>
    </>
  );
}
