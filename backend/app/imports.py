from .db import today
import csv
import io
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from sqlalchemy import select
from fastapi import HTTPException
from openpyxl import load_workbook
from .models import *
from .domain import dec, owned, audit, rows
from .schemas import ProductInput, SupplierInput, PurchaseLine

TEMPLATES = {
    "products": [
        "sku",
        "name",
        "brand",
        "variant",
        "size",
        "unit",
        "barcode",
        "pack",
        "sell_price",
        "manual_demand",
    ],
    "suppliers": ["name", "gstin", "minimum_order", "payment_terms"],
    "opening_stock": ["source_key", "sku", "date", "qty", "reason"],
    "purchases": [
        "source_key",
        "invoice_no",
        "supplier_gstin",
        "date",
        "sku",
        "qty",
        "factor",
        "rate",
        "discount",
        "tax_pct",
        "freight",
    ],
    "sales": [
        "source_key",
        "invoice_no",
        "date",
        "sku",
        "qty",
        "factor",
        "rate",
        "discount",
        "tax_pct",
    ],
    "returns": [
        "source_key",
        "invoice_no",
        "supplier_gstin",
        "date",
        "sku",
        "qty",
        "factor",
        "rate",
        "return_type",
    ],
    "adjustments": ["source_key", "sku", "date", "qty", "reason"],
}


def read_table(content, name):
    if name.lower().endswith(".csv"):
        return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    if name.lower().endswith(".xlsx"):
        import zipfile

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(f.file_size for f in archive.infolist()) > 50_000_000:
                raise ValueError("Spreadsheet uncompressed size exceeds 50 MB")
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        cells = sheet.iter_rows(values_only=True)
        headers = [str(v or "") for v in next(cells)]
        result = []
        for row in cells:
            if len(result) >= 10000:
                raise ValueError("Maximum 10,000 rows per import")
            result.append(
                {
                    h: v.isoformat()[:10]
                    if isinstance(v, (date, datetime))
                    else str(v)
                    if v is not None
                    else ""
                    for h, v in zip(headers, row)
                }
            )
        return result
    raise ValueError("Use CSV or XLSX")


def post_transaction(
    db,
    business,
    *,
    source,
    source_key,
    kind,
    invoice_no,
    occurred,
    supplier_id,
    total,
    lines,
    raw,
    actor,
):
    linked_order = raw.get("order_id") if isinstance(raw, dict) else None
    if linked_order:
        from .operations import get_order

        order = get_order(
            db, business.id, linked_order, db.info.get("branch_ids") or []
        )
        if order.supplier_id != supplier_id:
            raise HTTPException(422, "Invoice supplier differs from order")
    existing = db.scalar(
        select(Transaction).where(
            Transaction.business_id == business.id,
            Transaction.source == source,
            Transaction.source_key == source_key,
        )
    )
    if existing:
        return existing
    if kind == "purchase" and supplier_id:
        duplicate = db.scalar(
            select(Transaction).where(
                Transaction.business_id == business.id,
                Transaction.kind == kind,
                Transaction.supplier_id == supplier_id,
                Transaction.invoice_no == invoice_no,
                Transaction.date == occurred,
                Transaction.active == True,
            )
        )
        if duplicate:
            if abs(duplicate.total - total) > Decimal(".02"):
                raise HTTPException(
                    409,
                    "Invoice identity already exists with a different total; resolve conflict",
                )
            return duplicate
    tx = Transaction(
        business_id=business.id,
        source=source,
        source_key=source_key,
        kind=kind,
        supplier_id=supplier_id,
        invoice_no=invoice_no,
        date=occurred,
        total=total,
        raw=raw,
    )
    db.add(tx)
    db.flush()
    for line in lines:
        p = owned(db, Product, line.product_id, business.id)
        units = line.qty * line.factor
        if units != units.quantize(Decimal(".0001")):
            raise HTTPException(
                422, "Normalized base quantity supports at most four decimal places"
            )
        net = line.qty * line.rate - line.discount
        if net < 0:
            raise HTTPException(422, "Discount exceeds line amount")
        tax = net * line.tax_pct / 100
        economic = (
            net
            + line.freight
            + (Decimal(0) if business.settings.get("recoverable_gst", True) else tax)
        ) / units
        cash = (net + line.freight + tax) / units
        db.add(
            Line(
                business_id=business.id,
                transaction_id=tx.id,
                product_id=p.id,
                qty=units,
                unit_cost=economic,
                cash_unit=cash,
                discount=line.discount,
                raw=line.model_dump(mode="json"),
            )
        )
        if business.mode == "standalone" and source != "zoho" and not linked_order:
            sign = 1 if kind in ("purchase", "customer_return") else -1
            db.add(
                Movement(
                    business_id=business.id,
                    product_id=p.id,
                    transaction_id=tx.id,
                    qty=units * sign,
                    kind=kind,
                    reason=f"{source}: {invoice_no}",
                    at=datetime.combine(occurred, time(23, 59))
                    if occurred < today()
                    else now(),
                )
            )
    audit(
        db,
        business.id,
        actor,
        "transaction.posted",
        tx.id,
        {"source": source, "kind": kind},
    )
    if kind=='purchase' and supplier_id:
        db.add(Payable(business_id=business.id,branch_id=tx.branch_id,transaction_id=tx.id,supplier_id=supplier_id,due=occurred+timedelta(days=14)))
    if linked_order:
        db.flush()
        from .operations import link_invoice

        link_invoice(db, business.id, order, tx, db.info.get("branch_ids") or [], actor)
    return tx


def commit_import(db, business, job, mapping, actor):
    # Python sqlite's legacy transaction mode otherwise commits released savepoints.
    connection = db.connection()
    if (
        connection.dialect.name == "sqlite"
        and not connection.connection.driver_connection.in_transaction
    ):
        connection.exec_driver_sql("BEGIN")
    kind = job.payload["import_kind"]
    entries = [
        {target: row.get(column, "") for target, column in mapping.items() if column}
        for row in job.payload["rows"]
    ]
    errors, created = [], []
    grouped = {}
    for number, row in enumerate(entries, 2):
        try:
            with db.begin_nested():
                if kind == "products":
                    values = ProductInput.model_validate(
                        {k: v for k, v in row.items() if v != ""}
                    )
                    if db.scalar(
                        select(Product).where(
                            Product.business_id == business.id,
                            Product.sku == values.sku,
                        )
                    ):
                        continue
                    obj = Product(business_id=business.id, **values.model_dump())
                    db.add(obj)
                    db.flush()
                    created.append(obj.id)
                elif kind == "suppliers":
                    values = SupplierInput.model_validate(
                        {k: v for k, v in row.items() if v != ""}
                    )
                    obj = Supplier(business_id=business.id, **values.model_dump())
                    db.add(obj)
                    db.flush()
                    created.append(obj.id)
                else:
                    source_key = row.get("source_key", "").strip()
                    if not source_key:
                        raise ValueError("source_key is required for idempotency")
                    p = db.scalar(
                        select(Product).where(
                            Product.business_id == business.id,
                            Product.sku == row.get("sku"),
                        )
                    )
                    if not p:
                        raise ValueError("SKU not found; import products first")
                    day = date.fromisoformat(row["date"][:10])
                    if day > today():
                        raise ValueError("Future transaction dates are not supported")
                    if kind in ("opening_stock", "adjustments"):
                        if business.mode != "standalone":
                            raise ValueError(
                                "Stock imports are disabled in Zoho-authoritative mode"
                            )
                        if not row.get("reason"):
                            raise ValueError("Reason is required")
                        key = f"{kind}:{source_key}"
                        if db.scalar(
                            select(Transaction).where(
                                Transaction.business_id == business.id,
                                Transaction.source == "file",
                                Transaction.source_key == key,
                            )
                        ):
                            continue
                        if kind == "opening_stock" and db.scalar(
                            select(Movement).where(
                                Movement.business_id == business.id,
                                Movement.product_id == p.id,
                                Movement.kind == "opening",
                            )
                        ):
                            raise ValueError(
                                "Opening balance already exists; use adjustment"
                            )
                        tx = Transaction(
                            business_id=business.id,
                            source="file",
                            source_key=key,
                            kind=kind,
                            invoice_no=source_key,
                            date=day,
                            total=0,
                            raw=row,
                        )
                        db.add(tx)
                        db.flush()
                        db.add(
                            Movement(
                                business_id=business.id,
                                product_id=p.id,
                                transaction_id=tx.id,
                                qty=dec(row["qty"]),
                                kind="opening"
                                if kind == "opening_stock"
                                else "adjustment",
                                reason=row["reason"],
                                at=datetime.combine(day, time.min),
                            )
                        )
                        db.flush()
                        created.append(tx.id)
                    else:
                        group_key = f"{kind}:{source_key}"
                        group = grouped.setdefault(
                            group_key,
                            {"row": row, "date": day, "lines": [], "number": number},
                        )
                        if (
                            group["date"] != day
                            or group["row"].get("supplier_gstin", "")
                            != row.get("supplier_gstin", "")
                            or group["row"].get("invoice_no", "")
                            != row.get("invoice_no", "")
                        ):
                            raise ValueError(
                                "Rows sharing source_key must share date, supplier and invoice number"
                            )
                        line = PurchaseLine(
                            product_id=p.id,
                            raw_description=p.name,
                            **{
                                k: row[k]
                                for k in (
                                    "qty",
                                    "factor",
                                    "rate",
                                    "discount",
                                    "tax_pct",
                                    "freight",
                                )
                                if row.get(k) not in ("", None)
                            },
                        )
                        group["lines"].append(line)
        except Exception as exc:
            errors.append(
                {
                    "row": number,
                    "message": str(exc.detail)
                    if isinstance(exc, HTTPException)
                    else str(exc)[:500],
                }
            )
    for key, group in grouped.items():
        try:
            with db.begin_nested():
                row = group["row"]
                supplier = None
                tx_kind = {
                    "purchases": "purchase",
                    "sales": "sale",
                    "returns": row.get("return_type", ""),
                }[kind]
                if tx_kind not in (
                    "purchase",
                    "sale",
                    "customer_return",
                    "supplier_return",
                ):
                    raise ValueError(
                        "return_type must be customer_return or supplier_return"
                    )
                if tx_kind in ("purchase", "supplier_return"):
                    supplier = db.scalar(
                        select(Supplier).where(
                            Supplier.business_id == business.id,
                            Supplier.gstin == row.get("supplier_gstin"),
                        )
                    )
                    if not supplier:
                        raise ValueError("Supplier GSTIN not found")
                total = sum(
                    (
                        (l.qty * l.rate - l.discount) * (1 + l.tax_pct / 100)
                        + l.freight
                        for l in group["lines"]
                    ),
                    Decimal(0),
                )
                tx = post_transaction(
                    db,
                    business,
                    source="file",
                    source_key=key,
                    kind=tx_kind,
                    invoice_no=row.get("invoice_no", key),
                    occurred=group["date"],
                    supplier_id=supplier.id if supplier else None,
                    total=total,
                    lines=group["lines"],
                    raw={"rows": [l.model_dump(mode="json") for l in group["lines"]]},
                    actor=actor,
                )
                db.flush()
                created.append(tx.id)
        except Exception as exc:
            errors.append(
                {
                    "row": group["number"],
                    "message": str(exc.detail)
                    if isinstance(exc, HTTPException)
                    else str(exc)[:500],
                }
            )
    if errors:
        # Caller rolls back the entire batch; valid rows are not partially posted.
        raise HTTPException(
            422,
            {"message": "Nothing imported; fix these rows and retry", "errors": errors},
        )
    job.status = "completed"
    job.result = {"created": len(created)}
    audit(db, business.id, actor, "import.committed", job.id, job.result)
    return job.result


def einvoice(raw):
    seller, doc = raw.get("SellerDtls", {}), raw.get("DocDtls", {})
    return {
        "supplier_name": seller.get("LglNm", ""),
        "supplier_gstin": seller.get("Gstin", ""),
        "invoice_no": doc.get("No", ""),
        "date": datetime.strptime(doc["Dt"], "%d/%m/%Y").date().isoformat()
        if doc.get("Dt")
        else "",
        "total": str(raw.get("ValDtls", {}).get("TotInvVal", 0)),
        "irn": raw.get("Irn"),
        "acknowledgement": {"AckNo": raw.get("AckNo"), "AckDt": raw.get("AckDt")},
        "source_json": raw,
        "lines": [
            {
                "raw_description": l.get("PrdDesc", ""),
                "qty": str(l.get("Qty", 0)),
                "unit": l.get("Unit", ""),
                "rate": str(l.get("UnitPrice", 0)),
                "discount": str(l.get("Discount", 0)),
                "tax_pct": str(l.get("GstRt", 0)),
                "freight": "0",
                "confidence": 1,
                "product_id": "",
            }
            for l in raw.get("ItemList", [])
        ],
    }
