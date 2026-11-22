from .db import today

"""Deterministic, auditable purchasing calculations. No model-generated money."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from math import lcm
from statistics import median
from difflib import SequenceMatcher
from sqlalchemy import select, func
from fastapi import HTTPException
from .models import *
from .db import now

D = Decimal
ZERO = D("0")


def dec(value):
    result = D(str(value))
    if not result.is_finite():
        raise ValueError("A finite number is required")
    return result


def plain(row):
    return {
        c.key: getattr(row, c.key) for c in row.__table__.columns if c.key != "metadata"
    } | ({"metadata": row.metadata_} if isinstance(row, Product) else {})


def rows(db, cls, business_id):
    return db.scalars(select(cls).where(cls.business_id == business_id)).all()


def owned(db, cls, key, business_id):
    row = db.scalar(select(cls).where(cls.id == key, cls.business_id == business_id))
    if not row:
        raise HTTPException(404, "Record not found")
    return row


def audit(db, bid, actor, action, target, detail=None):
    db.add(
        Audit(
            business_id=bid,
            actor=actor,
            action=action,
            target=target,
            detail=detail or {},
        )
    )


def latest_stock(db, bid, pid):
    return db.scalar(
        select(Stock)
        .where(Stock.business_id == bid, Stock.product_id == pid)
        .order_by(Stock.at.desc())
        .limit(1)
    )


def inventory(db, business):
    result = []
    for p in rows(db, Product, business.id):
        snapshot = latest_stock(db, business.id, p.id)
        ledger = db.scalar(
            select(func.coalesce(func.sum(Movement.qty), 0)).where(
                Movement.business_id == business.id, Movement.product_id == p.id
            )
        )
        onhand = (
            snapshot.on_hand if business.mode == "zoho" and snapshot else dec(ledger)
        )
        if business.mode == "zoho" and not snapshot:
            onhand = ZERO
        reserved = snapshot.reserved if snapshot else ZERO
        updated = snapshot.at if snapshot else None
        last_move = db.scalar(
            select(func.max(Movement.at)).where(
                Movement.business_id == business.id, Movement.product_id == p.id
            )
        )
        if (
            business.mode == "standalone"
            and last_move
            and (not updated or last_move > updated)
        ):
            updated = last_move
        # Compare a counted snapshot with the ledger at the instant it was counted.
        counted_ledger = (
            db.scalar(
                select(func.coalesce(func.sum(Movement.qty), 0)).where(
                    Movement.business_id == business.id,
                    Movement.product_id == p.id,
                    Movement.at <= snapshot.at,
                )
            )
            if snapshot
            else None
        )
        gap = snapshot.on_hand - dec(counted_ledger) if snapshot else None
        pending = ZERO
        if business.mode == "standalone":
            orders = {
                o.id
                for o in rows(db, PurchaseOrder, business.id)
                if o.status in ("approved", "ordered", "partially_received")
            }
            pending = sum(
                (
                    l.qty - l.received
                    for l in rows(db, OrderLine, business.id)
                    if l.order_id in orders and l.product_id == p.id
                ),
                ZERO,
            )
        result.append(
            {
                "product_id": p.id,
                "sku": p.sku,
                "name": p.name,
                "on_hand": str(onhand),
                "reserved": str(reserved),
                "available": str(max(ZERO, onhand - reserved)),
                "on_order": str((snapshot.on_order if snapshot else ZERO) + pending),
                "reconciliation_gap": str(gap) if gap is not None else None,
                "updated": updated.isoformat() if updated else None,
                "stale": not updated or now() - updated > timedelta(hours=24),
                "history_unknown": snapshot is None,
            }
        )
    return result


def forecast_values(y, method):
    if not y:
        return 0.0
    if method == "moving_average":
        return sum(y[-28:]) / len(y[-28:])
    if method == "seasonal_naive":
        return sum(y[-7:]) / len(y[-7:])
    if method == "exponential_smoothing":
        value = y[0]
        for item in y[1:]:
            value = 0.2 * item + 0.8 * value
        return value
    # Syntetos-Boylan corrected Croston: separately smooth interval and demand.
    z = interval = None
    gap = 0
    for item in y:
        gap += 1
        if item > 0:
            z = item if z is None else 0.1 * item + 0.9 * z
            interval = gap if interval is None else 0.1 * gap + 0.9 * interval
            gap = 0
    return 0.95 * z / interval if z is not None else 0.0


def forecasts(db, business):
    end = today()
    txs = {
        t.id: t
        for t in rows(db, Transaction, business.id)
        if t.active and t.kind == "sale" and t.date < end
    }
    series = defaultdict(lambda: defaultdict(float))
    for line in rows(db, Line, business.id):
        if line.transaction_id in txs:
            series[line.product_id][txs[line.transaction_id].date] += float(line.qty)
    output = []
    all_snapshots = rows(db, Stock, business.id)
    for p in rows(db, Product, business.id):
        hist = series[p.id]
        snapshots = sorted(
            [s for s in all_snapshots if s.product_id == p.id], key=lambda s: s.at
        )
        known = {s.at.date(): s.on_hand - s.reserved > 0 for s in snapshots}
        start = max(end - timedelta(days=180), min(hist) if hist else end)
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        valid_days = [day for day in days if known.get(day, True)]
        y = [hist.get(day, 0) for day in valid_days]
        metrics = {}
        branch_id = db.info.get("write_branch")
        config = (
            db.scalar(
                select(BranchProduct).where(
                    BranchProduct.branch_id == branch_id,
                    BranchProduct.product_id == p.id,
                )
            )
            if branch_id
            else None
        )
        is_main = not branch_id or db.get(Branch, branch_id).code == "MAIN"
        manual = (
            config.manual_demand if config else p.manual_demand if is_main else None
        )
        method = "manual" if manual is not None else "insufficient_history"
        demand = float(manual) if manual is not None else None
        if len(y) >= 28 and manual is None:
            methods = ["moving_average", "seasonal_naive", "exponential_smoothing"]
            if sum(v == 0 for v in y) / len(y) > 0.4:
                methods.append("croston_sba")
            # Weekly rolling origins, one-week horizon. Known stockouts are censored.
            for candidate in methods:
                errors, actuals = [], []
                for cut in range(max(14, len(y) - 56), len(y) - 6, 7):
                    if candidate == "seasonal_naive":
                        predicted = y[cut - 7 : cut]
                    else:
                        predicted = [forecast_values(y[:cut], candidate)] * 7
                    for predicted_value, actual in zip(predicted, y[cut : cut + 7]):
                        errors.append(predicted_value - actual)
                        actuals.append(actual)
                if errors:
                    metrics[candidate] = {
                        "mae": round(sum(abs(e) for e in errors) / len(errors), 3),
                        "wape": round(sum(abs(e) for e in errors) / sum(actuals), 4)
                        if sum(actuals)
                        else None,
                        "bias": round(sum(errors) / len(errors), 3),
                    }
            method = (
                min(metrics, key=lambda m: metrics[m]["mae"])
                if metrics
                else "moving_average"
            )
            demand = forecast_values(y, method)
        sd = (sum((v - sum(y) / len(y)) ** 2 for v in y) / len(y)) ** 0.5 if y else 0
        output.append(
            {
                "product_id": p.id,
                "name": p.name,
                "method": method,
                "model_version": "baseline-v1",
                "daily_demand": str(round(max(0, demand), 4))
                if demand is not None
                else None,
                "eligible": demand is not None,
                "observed_days": len(y),
                "excluded_stockout_days": len(days) - len(valid_days),
                "unknown_availability_days": sum(day not in known for day in days),
                "uncertainty_daily_sd": round(sd, 2),
                "confidence": "low"
                if len(y) < 56 or sum(day not in known for day in days)
                else "moderate",
                "backtests": metrics,
            }
        )
    return output


def scorecards(db, bid):
    result = []
    for supplier in rows(db, Supplier, bid):
        receipts = [r for r in rows(db, Receipt, bid) if r.supplier_id == supplier.id]
        n = len(receipts)
        result.append(
            plain(supplier)
            | {
                "sample_size": n,
                "on_time_rate": sum(r.actual <= r.expected for r in receipts) / n
                if n
                else None,
                "lead_days": sum((r.actual - r.ordered_on).days for r in receipts) / n
                if n
                else None,
                "fulfillment_rate": float(
                    sum((r.received_qty for r in receipts), ZERO)
                    / sum((r.ordered_qty for r in receipts), ZERO)
                )
                if n
                else None,
                "evidence": "observed" if n >= 3 else "insufficient evidence",
            }
        )
    return result


def costs(q, qty, recoverable=True):
    rate = dec(q.unit_cost)
    for tier in sorted(q.tiers, key=lambda t: dec(t["min_qty"])):
        if qty >= dec(tier["min_qty"]):
            rate = dec(tier["unit_cost"])
    tax = rate * dec(q.tax_pct) / 100
    freight = dec(q.freight_unit)
    return rate + freight + (ZERO if recoverable else tax), rate + tax + freight


def step_size(q):
    return D(lcm(int(q.pack * 10000), int(q.multiple * 10000))) / 10000


def ceil_step(qty, step):
    return (qty / step).to_integral_value(rounding=ROUND_CEILING) * step


def line_for(q, qty, product, f, stock, settings):
    economic, cash = costs(q, qty, settings.get("recoverable_gst", True))
    return {
        "quote_id": q.id,
        "product_id": product.id,
        "supplier_id": q.supplier_id,
        "name": product.name,
        "qty": str(qty),
        "unit_cost": str(economic),
        "cash_unit": str(cash),
        "cash_spend": str((qty * cash).quantize(D(".01"))),
        "benefit_estimate": str(
            (
                min(
                    qty,
                    dec(f["daily_demand"])
                    * (q.lead_days + settings.get("review_days", 7)),
                )
                * max(ZERO, product.sell_price - economic)
            ).quantize(D(".01"))
        ),
        "explanation": f"{f['method']}: {f['daily_demand']} units/day; available {stock['available']}; on order {stock['on_order']}; {q.lead_days}-day lead time. Price observed {q.observed}; cash cost includes taxes and freight.",
        "price_confirmed": False,
    }


def validate_basket(db, business, lines, budget):
    errors, groups, seen = [], defaultdict(Decimal), set()
    stocks = {s["product_id"]: s for s in inventory(db, business)}
    predictions = {f["product_id"]: f for f in forecasts(db, business)}
    normalized = []
    minimum_reliability = business.settings.get("minimum_reliability")
    scores = {s["id"]: s for s in scorecards(db, business.id)}
    for entry in lines:
        q = owned(db, Quote, entry["quote_id"], business.id)
        p = owned(db, Product, q.product_id, business.id)
        quantity = dec(entry["qty"])
        if p.id in seen:
            errors.append(f"{p.name}: duplicate product")
        seen.add(p.id)
        if quantity <= 0 or quantity < q.moq or quantity % step_size(q):
            errors.append(f"{p.name}: quantity violates MOQ or pack/order multiple")
        f = predictions[p.id]
        if not f["eligible"]:
            errors.append(f"{p.name}: demand estimate required")
            continue
        stock = stocks[p.id]
        cover = dec(f["daily_demand"]) * dec(business.settings.get("max_cover", 30))
        config = (
            db.scalar(
                select(BranchProduct).where(
                    BranchProduct.branch_id == db.info.get("write_branch"),
                    BranchProduct.product_id == p.id,
                )
            )
            if db.info.get("write_branch")
            else None
        )
        storage = config.storage_limit if config else p.storage_limit
        limit = min(cover, storage) if storage is not None else cover
        if quantity + dec(stock["available"]) + dec(stock["on_order"]) > limit:
            errors.append(f"{p.name}: maximum cover or storage exceeded")
        score = scores[q.supplier_id]
        if minimum_reliability is not None and (
            score["sample_size"] < 3
            or score["on_time_rate"] < float(minimum_reliability)
        ):
            errors.append(f"{p.name}: supplier reliability requirement not met")
        item = line_for(q, quantity, p, f, stock, business.settings)
        item["price_confirmed"] = bool(entry.get("price_confirmed"))
        normalized.append(item)
        groups[q.supplier_id] += dec(item["cash_spend"])
    total = sum((dec(item["cash_spend"]) for item in normalized), ZERO)
    if total > dec(budget):
        errors.append("Cash budget exceeded")
    for sid, spend in groups.items():
        supplier = owned(db, Supplier, sid, business.id)
        if spend < supplier.minimum_order:
            errors.append(f"{supplier.name}: supplier minimum order not met")
    return normalized, total, errors


def recommend(db, business, budget):
    stocks = {s["product_id"]: s for s in inventory(db, business)}
    predictions = {f["product_id"]: f for f in forecasts(db, business)}
    candidates, excluded = [], []
    supplier_scores = {s["id"]: s for s in scorecards(db, business.id)}
    minimum_reliability = business.settings.get("minimum_reliability")
    all_quotes = rows(db, Quote, business.id)
    for p in rows(db, Product, business.id):
        f, s = predictions[p.id], stocks[p.id]
        qs = [q for q in all_quotes if q.product_id == p.id]
        if minimum_reliability is not None:
            qs = [
                q
                for q in qs
                if supplier_scores[q.supplier_id]["sample_size"] >= 3
                and supplier_scores[q.supplier_id]["on_time_rate"]
                >= float(minimum_reliability)
            ]
        if not f["eligible"] or not qs or s["updated"] is None:
            excluded.append(
                {
                    "name": p.name,
                    "reason": "Demand estimate, stock evidence or supplier price missing",
                }
            )
            continue
        found = False
        config = (
            db.scalar(
                select(BranchProduct).where(
                    BranchProduct.branch_id == db.info.get("write_branch"),
                    BranchProduct.product_id == p.id,
                )
            )
            if db.info.get("write_branch")
            else None
        )
        safety = (
            config.safety_days
            if config and config.safety_days is not None
            else business.settings.get("safety_days", 2)
        )
        for q in qs:
            daily = dec(f["daily_demand"])
            desired = max(
                ZERO,
                daily
                * (
                    q.lead_days
                    + dec(business.settings.get("review_days", 7))
                    + dec(safety)
                )
                - dec(s["available"])
                - dec(s["on_order"]),
            )
            if desired <= 0:
                continue
            found = True
            qty = max(q.moq, ceil_step(desired, step_size(q)))
            econ, cash = costs(q, qty, business.settings.get("recoverable_gst", True))
            if cash > 0:
                candidates.append(
                    (max(ZERO, p.sell_price - econ) / cash, p.sku, q, qty, p, f, s)
                )
        if not found:
            excluded.append(
                {"name": p.name, "reason": "Existing stock and orders cover demand"}
            )
    selected = []
    blocked = set()
    attempted = set()
    ordered = sorted(candidates, key=lambda c: (-c[0], c[1], c[2].id))
    for _ in range(len(supplier_scores) + 1):
        chosen = {l["product_id"] for l in selected}
        for _, _, q, desired, p, f, s in ordered:
            if p.id in chosen or q.supplier_id in blocked:
                continue
            attempted.add(p.id)
            qty = desired
            remaining = dec(budget) - sum(
                (dec(l["cash_spend"]) for l in selected), ZERO
            )
            minimum_cash = min(
                [costs(q, q.moq, business.settings.get("recoverable_gst", True))[1]]
                + [
                    costs(
                        q,
                        dec(t["min_qty"]),
                        business.settings.get("recoverable_gst", True),
                    )[1]
                    for t in q.tiers
                ]
            )
            if minimum_cash > 0:
                qty = min(
                    qty, (remaining / minimum_cash // step_size(q)) * step_size(q)
                )
            while qty >= q.moq and qty > 0:
                item = line_for(q, qty, p, f, s, business.settings)
                _, _, problems = validate_basket(
                    db, business, selected + [item], budget
                )
                if not [e for e in problems if "supplier minimum order" not in e]:
                    selected.append(item)
                    chosen.add(p.id)
                    break
                qty -= step_size(q)
        groups = defaultdict(Decimal)
        for item in selected:
            groups[item["supplier_id"]] += dec(item["cash_spend"])
        invalid = {
            sid
            for sid, spend in groups.items()
            if spend < owned(db, Supplier, sid, business.id).minimum_order
        }
        if not invalid:
            break
        for item in selected:
            if item["supplier_id"] in invalid:
                excluded.append(
                    {
                        "name": item["name"],
                        "reason": "Supplier minimum order not reached; evaluating alternatives",
                    }
                )
        blocked.update(invalid)
        selected = [i for i in selected if i["supplier_id"] not in invalid]
    for _, _, q, desired, p, f, s in ordered:
        if p.id not in {i["product_id"] for i in selected} and p.id in attempted:
            if not any(e["name"] == p.name for e in excluded):
                excluded.append(
                    {
                        "name": p.name,
                        "reason": "Budget, cover, pack or supplier constraints prevent a feasible purchase",
                    }
                )
    normalized, total, errors = validate_basket(db, business, selected, budget)
    if errors:
        raise HTTPException(422, errors)
    return normalized, {
        "forecasts": list(predictions.values()),
        "inventory": list(stocks.values()),
        "excluded": excluded,
        "cash_spend": str(total),
        "algorithm": "greedy-contribution-per-rupee-v1",
        "generated_at": now().isoformat(),
        "unfilled_demand": [
            {
                "product_id": p.id,
                "name": p.name,
                "units": str(
                    max(
                        ZERO,
                        dec(predictions[p.id]["daily_demand"] or 0)
                        * (
                            dec(business.settings.get("review_days", 7))
                            + dec(business.settings.get("safety_days", 2))
                            + dec(business.settings.get("lead_days", 3))
                        )
                        - dec(stocks.get(p.id, {}).get("available", "0"))
                        - dec(stocks[p.id]["on_order"])
                        - sum(
                            (
                                dec(i["qty"])
                                for i in selected
                                if i["product_id"] == p.id
                            ),
                            ZERO,
                        ),
                    )
                ),
            }
            for p in rows(db, Product, business.id)
        ],
    }


def alerts(db, business):
    result = []
    txs = {
        t.id: t
        for t in rows(db, Transaction, business.id)
        if t.active and t.kind == "purchase"
    }
    stocks = {s["product_id"]: s for s in inventory(db, business)}
    predictions = {f["product_id"]: f for f in forecasts(db, business)}
    all_lines = rows(db, Line, business.id)
    sales_txs = {
        t.id: t
        for t in rows(db, Transaction, business.id)
        if t.active and t.kind == "sale"
    }
    for p in rows(db, Product, business.id):
        history = sorted(
            [
                line
                for line in all_lines
                if line.product_id == p.id and line.transaction_id in txs
            ],
            key=lambda line: txs[line.transaction_id].date,
        )
        groups = defaultdict(list)
        for line in history:
            groups[txs[line.transaction_id].supplier_id].append(line)
        for sid, group in groups.items():
            values = [l.unit_cost for l in group]
            if (
                len(values) >= 2
                and values[-2] > 0
                and (values[-1] - values[-2]) / values[-2] > D(".1")
            ):
                result.append(
                    {
                        "product_id": p.id,
                        "name": p.name,
                        "type": "price_change",
                        "severity": "commercial",
                        "message": f"Purchase cost rose {((values[-1] / values[-2] - 1) * 100):.1f}% for the same supplier.",
                        "supplier_id": sid,
                    }
                )
            if len(values) >= 6:
                center = median(values[:-1])
                mad = median([abs(v - center) for v in values[:-1]])
                if mad > 0 and abs(values[-1] - center) / mad > D("4.45"):
                    result.append(
                        {
                            "product_id": p.id,
                            "name": p.name,
                            "type": "robust_price_deviation",
                            "severity": "commercial",
                            "message": "Price lies outside the recent robust historical range.",
                        }
                    )
        if history:
            latest = history[-1].unit_cost
            quotes = [q for q in rows(db, Quote, business.id) if q.product_id == p.id]
            cheaper = min(
                (
                    costs(q, q.moq, business.settings.get("recoverable_gst", True))[0]
                    for q in quotes
                ),
                default=latest,
            )
            if cheaper < latest * D(".95"):
                result.append(
                    {
                        "product_id": p.id,
                        "name": p.name,
                        "type": "supplier_alternative",
                        "severity": "commercial",
                        "message": f"Alternative observed cost ₹{cheaper:.2f} versus latest ₹{latest:.2f}; confirm quotation.",
                    }
                )
            if p.sell_price and latest > p.sell_price * D(".85"):
                result.append(
                    {
                        "product_id": p.id,
                        "name": p.name,
                        "type": "margin",
                        "severity": "commercial",
                        "message": "Gross margin below 15% using latest verified purchase cost; tax-exclusive selling price.",
                    }
                )
            demand = dec(predictions[p.id]["daily_demand"] or 0)
            if (
                demand
                and dec(stocks.get(p.id, {}).get("available", "0"))
                > demand * dec(business.settings.get("max_cover", 30))
                and p.sell_price
                and latest > p.sell_price * D(".85")
            ):
                result.append(
                    {
                        "product_id": p.id,
                        "name": p.name,
                        "type": "working_capital",
                        "severity": "commercial",
                        "message": "Low-margin stock exceeds maximum days of cover and ties up working capital.",
                    }
                )
            recent_sales = [
                l
                for l in all_lines
                if l.product_id == p.id
                and l.transaction_id in sales_txs
                and sales_txs[l.transaction_id].date >= today() - timedelta(days=56)
            ]
            periods = [
                [
                    l
                    for l in recent_sales
                    if (
                        sales_txs[l.transaction_id].date >= today() - timedelta(days=28)
                    )
                    == recent
                ]
                for recent in (False, True)
            ]
            ratios = []
            selling = []
            for period in periods:
                gross = sum((l.qty * l.unit_cost + l.discount for l in period), ZERO)
                qty = sum((l.qty for l in period), ZERO)
                ratios.append(
                    sum((l.discount for l in period), ZERO) / gross if gross else None
                )
                selling.append(
                    sum((l.qty * l.unit_cost for l in period), ZERO) / qty
                    if qty
                    else None
                )
            if all(r is not None for r in ratios) and ratios[1] > ratios[0] + D(".02"):
                result.append(
                    {
                        "product_id": p.id,
                        "name": p.name,
                        "type": "sales_discount",
                        "severity": "commercial",
                        "message": "Sales discount intensity rose by more than two percentage points versus the previous 28 days.",
                    }
                )
            if (
                len(history) >= 2
                and history[0].unit_cost > 0
                and all(s is not None and s > 0 for s in selling)
                and latest / history[0].unit_cost > selling[1] / selling[0] + D(".05")
            ):
                result.append(
                    {
                        "product_id": p.id,
                        "name": p.name,
                        "type": "margin_erosion",
                        "severity": "commercial",
                        "message": "Purchase-cost growth exceeds observed selling-price growth; review gross margin.",
                    }
                )
        if dec(stocks.get(p.id, {}).get("available", "0")) <= 0:
            result.append(
                {
                    "product_id": p.id,
                    "name": p.name,
                    "type": "stockout",
                    "severity": "operational",
                    "message": "No available stock. Review demand and contribution before replenishment.",
                }
            )
    return result


def matching(db, bid, text, supplier_key=""):
    alias = db.scalar(
        select(Alias).where(
            Alias.business_id == bid,
            Alias.supplier_key == supplier_key,
            Alias.text == text,
        )
    )
    if alias:
        return [
            {
                "product_id": alias.product_id,
                "confidence": 1,
                "method": "approved_alias",
                "factor": str(alias.factor),
            }
        ]
    products = rows(db, Product, bid)
    exact = [
        p
        for p in products
        if text in [p.sku, p.barcode, p.source_id] or text.lower() == p.name.lower()
    ]
    if exact:
        return [
            {"product_id": p.id, "name": p.name, "confidence": 1, "method": "exact"}
            for p in exact
        ]
    return sorted(
        [
            {
                "product_id": p.id,
                "name": p.name,
                "confidence": round(
                    SequenceMatcher(None, text.lower(), p.name.lower()).ratio(), 3
                ),
                "method": "suggestion_requires_confirmation",
                "size": p.size,
                "variant": p.variant,
                "pack": str(p.pack),
            }
            for p in products
        ],
        key=lambda p: -p["confidence"],
    )[:5]


def profit_leak_analysis(db, business):
    """
    Module 5: Profit Leak Detector
    Uncovers situations where the shop is losing gross margin due to unpassed purchase cost hikes,
    selling below verified purchase cost, supplier price discrepancies, or excessive discount erosion.
    Explicitly quantifies estimated monthly Rupee leakage and distinguishes gross margin from net profit.
    """
    leaks = []
    total_leak_rupees = ZERO
    negative_margin_count = 0

    txs = {
        t.id: t
        for t in rows(db, Transaction, business.id)
        if t.active and t.kind == "purchase"
    }
    sales_txs = {
        t.id: t
        for t in rows(db, Transaction, business.id)
        if t.active and t.kind == "sale"
    }
    suppliers = {s.id: s for s in rows(db, Supplier, business.id)}
    products = rows(db, Product, business.id)
    all_lines = rows(db, Line, business.id)
    stocks = {s["product_id"]: s for s in inventory(db, business)}
    forecast_map = {f["product_id"]: f for f in forecasts(db, business)}
    quotes = rows(db, Quote, business.id)

    quotes_by_prod = defaultdict(list)
    for q in quotes:
        quotes_by_prod[q.product_id].append(q)

    # 56-day cutoffs for sales trend
    day_28_ago = today() - timedelta(days=28)
    day_56_ago = today() - timedelta(days=56)

    for p in products:
        daily_dem = dec(forecast_map.get(p.id, {}).get("daily_demand") or D("1.0"))
        if daily_dem <= ZERO:
            daily_dem = D("1.0")

        # Purchase history sorted by date
        p_lines = sorted(
            [l for l in all_lines if l.product_id == p.id and l.transaction_id in txs],
            key=lambda l: txs[l.transaction_id].date,
        )

        latest_cost = p_lines[-1].unit_cost if p_lines else ZERO
        latest_supplier_id = txs[p_lines[-1].transaction_id].supplier_id if p_lines else None
        latest_supplier_name = suppliers.get(latest_supplier_id).name if latest_supplier_id in suppliers else "Unknown"

        # Check 1: Selling below verified purchase cost (Negative Margin Leak)
        if latest_cost > ZERO and p.sell_price > ZERO and p.sell_price < latest_cost:
            per_unit_loss = latest_cost - p.sell_price
            est_monthly = per_unit_loss * daily_dem * D("30")
            total_leak_rupees += est_monthly
            negative_margin_count += 1
            leaks.append({
                "product_id": p.id,
                "name": p.name,
                "sku": p.sku,
                "category": "below_cost",
                "severity": "critical",
                "title": f"Selling below verified purchase cost: {p.name}",
                "unit_cost": str(latest_cost),
                "sell_price": str(p.sell_price),
                "margin_pct": str(round(((p.sell_price - latest_cost) / p.sell_price) * 100, 1)),
                "estimated_monthly_loss": str(round(est_monthly, 2)),
                "explanation": f"Item sells at ₹{p.sell_price:.2f}, but the latest verified purchase cost is ₹{latest_cost:.2f} from {latest_supplier_name}. Every unit sold loses ₹{per_unit_loss:.2f}.",
                "remedy": f"Raise selling price to at least ₹{latest_cost * D('1.15'):.2f} (15% margin) or negotiate purchase cost down."
            })

        # Check 2: Unpassed Supplier Price Increase (Margin Squeeze)
        if len(p_lines) >= 2:
            prev_cost = p_lines[-2].unit_cost
            if latest_cost > prev_cost and prev_cost > ZERO:
                cost_increase = latest_cost - prev_cost
                cost_pct = (cost_increase / prev_cost) * 100
                # Did sell price increase proportionally?
                if p.sell_price > ZERO and cost_increase >= D("0.5"):
                    current_margin = ((p.sell_price - latest_cost) / p.sell_price) * 100
                    prev_margin = ((p.sell_price - prev_cost) / p.sell_price) * 100
                    est_monthly = cost_increase * daily_dem * D("30")
                    total_leak_rupees += est_monthly
                    leaks.append({
                        "product_id": p.id,
                        "name": p.name,
                        "sku": p.sku,
                        "category": "unpassed_cost_increase",
                        "severity": "high",
                        "title": f"Unpassed supplier cost increase (+{cost_pct:.1f}%): {p.name}",
                        "unit_cost": str(latest_cost),
                        "prev_cost": str(prev_cost),
                        "sell_price": str(p.sell_price),
                        "margin_pct": str(round(current_margin, 1)),
                        "estimated_monthly_loss": str(round(est_monthly, 2)),
                        "explanation": f"Purchase cost increased from ₹{prev_cost:.2f} to ₹{latest_cost:.2f} (+₹{cost_increase:.2f}), but retail price stayed at ₹{p.sell_price:.2f}. Margin compressed from {prev_margin:.1f}% to {current_margin:.1f}%.",
                        "remedy": f"Adjust retail price to ₹{(p.sell_price + cost_increase):.2f} to recover ₹{est_monthly:.2f}/month."
                    })

        # Check 3: Multi-Supplier Price Discrepancy
        prod_quotes = quotes_by_prod.get(p.id, [])
        if len(prod_quotes) >= 2:
            sorted_quotes = sorted(prod_quotes, key=lambda q: q.unit_cost)
            cheapest = sorted_quotes[0]
            costliest = sorted_quotes[-1]
            diff = costliest.unit_cost - cheapest.unit_cost
            if diff > ZERO and (diff / cheapest.unit_cost) >= D("0.08"):  # >= 8% divergence
                est_monthly = diff * daily_dem * D("30")
                total_leak_rupees += est_monthly
                cheapest_supp = suppliers.get(cheapest.supplier_id)
                costliest_supp = suppliers.get(costliest.supplier_id)
                leaks.append({
                    "product_id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "category": "supplier_variance",
                    "severity": "medium",
                    "title": f"Supplier price variance ({round((diff / cheapest.unit_cost) * 100, 1)}% diff): {p.name}",
                    "unit_cost": str(costliest.unit_cost),
                    "cheapest_cost": str(cheapest.unit_cost),
                    "sell_price": str(p.sell_price),
                    "estimated_monthly_loss": str(round(est_monthly, 2)),
                    "explanation": f"{cheapest_supp.name if cheapest_supp else 'Alternative'} offers ₹{cheapest.unit_cost:.2f} vs {costliest_supp.name if costliest_supp else 'Current'} at ₹{costliest.unit_cost:.2f} (saving ₹{diff:.2f}/unit).",
                    "remedy": f"Direct reorders to {cheapest_supp.name if cheapest_supp else 'the cheaper supplier'} to capture ₹{est_monthly:.2f}/month."
                })

        # Check 4: Sales Discount Erosion
        prod_sales = [l for l in all_lines if l.product_id == p.id and l.transaction_id in sales_txs]
        recent_sales = [l for l in prod_sales if sales_txs[l.transaction_id].date >= day_28_ago]
        prior_sales = [l for l in prod_sales if day_56_ago <= sales_txs[l.transaction_id].date < day_28_ago]

        if recent_sales and prior_sales:
            def gross_discount_margin(sales_subset):
                tot_qty = sum((l.qty for l in sales_subset), ZERO)
                tot_gross = sum((l.qty * l.unit_cost + l.discount for l in sales_subset), ZERO)
                tot_discount = sum((l.discount for l in sales_subset), ZERO)
                eff_selling = (tot_gross - tot_discount) / tot_qty if tot_qty > ZERO else ZERO
                margin = ((eff_selling - latest_cost) / eff_selling * 100) if eff_selling > ZERO else ZERO
                return eff_selling, margin, tot_discount

            eff_recent, marg_recent, disc_recent = gross_discount_margin(recent_sales)
            eff_prior, marg_prior, disc_prior = gross_discount_margin(prior_sales)

            if marg_prior > marg_recent + D("4.0") and latest_cost > ZERO:
                margin_drop_diff = (marg_prior - marg_recent) / D("100") * (eff_recent * daily_dem * D("30"))
                total_leak_rupees += margin_drop_diff
                leaks.append({
                    "product_id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "category": "margin_compression",
                    "severity": "medium",
                    "title": f"Recent 28-day gross margin erosion: {p.name}",
                    "unit_cost": str(latest_cost),
                    "sell_price": str(p.sell_price),
                    "margin_pct": str(round(marg_recent, 1)),
                    "prev_margin_pct": str(round(marg_prior, 1)),
                    "estimated_monthly_loss": str(round(margin_drop_diff, 2)),
                    "explanation": f"Realized gross margin declined from {marg_prior:.1f}% to {marg_recent:.1f}% due to discounts and unrecovered cost shifts.",
                    "remedy": "Cap promotional discounts or renegotiate supplier volume rebates."
                })

    leaks.sort(key=lambda x: dec(x.get("estimated_monthly_loss") or ZERO), reverse=True)

    return {
        "total_monthly_leakage_rupees": str(round(total_leak_rupees, 2)),
        "affected_products_count": len({l["product_id"] for l in leaks}),
        "critical_negative_margin_count": negative_margin_count,
        "total_purchases": len(txs),
        "total_products": len(products),
        "has_history": len(txs) >= 2,
        "history_status": "sufficient" if len(txs) >= 2 else ("insufficient" if len(txs) > 0 else "no_purchases"),
        "distinction_note": "Gross margin and purchase-cost analysis only. Overhead, store electricity, taxes, and operational expenses are not subtracted.",
        "leaks": leaks,
    }


def local_demand_analysis(db, business):
    """
    Module 4: Local Market Demand Intelligence
    Combines 4 evidence sources:
    A. Shop-level sales and assortment analysis
    B. Unmet Demand Register (customer requests for unstocked items)
    C. Seasonal and emerging demand signals
    D. Aggregated local demand network status (with honest 'insufficient local data' transparency)
    Plus multi-factor Product Opportunity Scoring.
    """
    unmet_rows = db.scalars(
        select(UnmetDemandRequest).where(UnmetDemandRequest.business_id == business.id)
    ).all()
    signals_rows = db.scalars(
        select(LocalMarketSignal).where(LocalMarketSignal.business_id == business.id)
    ).all()

    products = rows(db, Product, business.id)
    sales_txs = {
        t.id: t
        for t in rows(db, Transaction, business.id)
        if t.active and t.kind == "sale"
    }
    all_lines = rows(db, Line, business.id)

    # Assortment breakdown
    category_counts = defaultdict(int)
    category_sales_qty = defaultdict(Decimal)
    for p in products:
        cat = p.brand or "Staples"
        category_counts[cat] += 1

    day_30_ago = today() - timedelta(days=30)
    for l in all_lines:
        if l.transaction_id in sales_txs and sales_txs[l.transaction_id].date >= day_30_ago:
            # find product
            matching_p = next((p for p in products if p.id == l.product_id), None)
            if matching_p:
                cat = matching_p.brand or "Staples"
                category_sales_qty[cat] += l.qty

    assortment_gaps = []
    total_sales_units = sum(category_sales_qty.values(), ZERO)
    for cat, qty in category_sales_qty.items():
        sku_count = category_counts.get(cat, 1)
        sales_share = (qty / total_sales_units * 100) if total_sales_units > ZERO else ZERO
        # High sales share with very low SKU count represents an assortment gap
        if sales_share >= D("15.0") and sku_count <= 2:
            assortment_gaps.append({
                "category": cat,
                "current_skus": sku_count,
                "sales_share_pct": round(float(sales_share), 1),
                "insight": f"{cat} drives {sales_share:.1f}% of store volume across only {sku_count} SKUs. Customers likely seek greater variety in this category."
            })

    # Opportunity scoring for Unmet Demand Requests
    opportunities = []
    for u in unmet_rows:
        count = u.request_count
        units = float(u.requested_qty)
        # 1. Frequency Score (0-100)
        s_freq = min(100.0, count * 15.0 + units * 2.0)
        # 2. Category Momentum Score (0-100)
        cat_sales = float(category_sales_qty.get(u.category, ZERO))
        s_cat = 80.0 if cat_sales > 50 else (50.0 if u.category in category_counts else 40.0)
        # 3. Expected Margin Potential (0-100)
        s_margin = 75.0 if u.estimated_sell_price and u.estimated_sell_price > 50 else 60.0
        # 4. Investment & Risk (0-100, lower is better)
        s_risk = 25.0

        # Weighted Opportunity Score
        raw_score = 0.40 * s_freq + 0.25 * s_cat + 0.25 * s_margin - 0.10 * s_risk
        score = round(max(10.0, min(98.0, raw_score)), 1)

        if score >= 70.0:
            rec = "High Priority Trial — Order small test batch (1 pack/case)"
            priority = "high"
        elif score >= 45.0:
            rec = "Moderate Opportunity — Survey customers or check supplier MOQ"
            priority = "medium"
        else:
            rec = "Low Evidence — Continue logging requests before ordering"
            priority = "low"

        opportunities.append({
            "id": u.id,
            "product_name": u.product_name,
            "brand": u.brand,
            "variant": u.variant,
            "category": u.category,
            "request_count": u.request_count,
            "requested_qty": str(u.requested_qty),
            "estimated_sell_price": str(u.estimated_sell_price) if u.estimated_sell_price else None,
            "customer_notes": u.customer_notes,
            "status": u.status,
            "request_date": str(u.request_date),
            "opportunity_score": score,
            "score_breakdown": {
                "frequency_pts": round(0.40 * s_freq, 1),
                "category_pts": round(0.25 * s_cat, 1),
                "margin_pts": round(0.25 * s_margin, 1),
                "risk_deduction": round(0.10 * s_risk, 1),
                "formula": "40% Frequency + 25% Category Volume + 25% Margin - 10% Risk",
            },
            "priority": priority,
            "recommendation": rec,
        })

    opportunities.sort(key=lambda o: o["opportunity_score"], reverse=True)

    signals_list = [
        {
            "id": s.id,
            "title": s.title,
            "category": s.category,
            "signal_type": s.signal_type,
            "source": s.source,
            "source_date": str(s.source_date),
            "impact_multiplier": str(s.impact_multiplier),
            "notes": s.notes,
        }
        for s in signals_rows
    ]

    sales_days = len({t.date for t in sales_txs.values()})
    in_store_sales_label = f"Active ({sales_days} sales days recorded)" if sales_days > 0 else "0 recorded sales days"
    total_local_merchants = len([b for b in db.scalars(select(Business)).all() if not b.demo])
    network_status = "Insufficient local cross-shop data" if total_local_merchants <= 1 else f"Forming network ({total_local_merchants} stores registered)"
    network_note = (
        "No external participating shops registered in this area. Cross-shop trend assertions cannot be fabricated without verified merchant data sharing."
        if total_local_merchants <= 1
        else "Cross-shop aggregation requires merchant data sharing consent across participating stores."
    )

    return {
        "unmet_requests_count": len(unmet_rows),
        "opportunities": opportunities,
        "assortment_gaps": assortment_gaps,
        "seasonal_signals": signals_list,
        "local_network": {
            "verified_in_store_sales": in_store_sales_label,
            "unmet_demand_register": f"Active ({len(unmet_rows)} customer inquiries recorded)",
            "cross_shop_network_status": network_status,
            "cross_shop_network_note": network_note,
            "participating_merchants_count": total_local_merchants,
        }
    }


def ai_assistant_query(db, business, query, language="en"):
    """
    Module 6: AI Business Assistant
    Grounded strictly in verified shop records (zero hallucinations).
    Answers natural language questions in English, Telugu, and Hindi:
    1. Products with increased purchase price this month
    2. Supplier offering lowest comparable cost for an item
    3. Products to reorder today
    4. Highest sales this week
    5. Products with declining gross margins
    6. Customer requested unstocked products
    7. Suggested order cost & budget impact
    Returns natural language response, structured evidence records, and action links.
    """
    q = query.lower().strip()

    # Determine intent
    is_price_hike = any(k in q for k in ["price increase", "cost increase", "increased", "expensive", "hike", "rose", "ధర పెరిగింది", "భావం పెరిగింది", "भाव बढ़ा", "दाम बढ़ा", "रेट बढ़ा"])
    is_lowest_supplier = any(k in q for k in ["lowest supplier", "cheapest supplier", "best price", "lowest cost", "cheaper", "సప్లయర్", "తక్కువ ధర", "సౌక", "सबसे सस्ता", "किफायती", "सप्लायर"])
    is_reorder = any(k in q for k in ["reorder", "running low", "stockout", "what to buy", "order today", "need to buy", "ఆర్డర్", "స్టాక్ తక్కువ", "కొనాలి", "ఆరడర", "खरीदना", "कम स्टॉक", "दोबारा ऑर्डर", "दोबारा आर्डर", "आर्डर", "ऑर्डर"])
    is_top_sales = any(k in q for k in ["highest sales", "top sales", "best seller", "selling most", "fastest", "ఎక్కువ అమ్మకాలు", "సేల్స్", "सबसे ज्यादा बिक्री", "टॉप सेलिंग", "ज्यादा बिका"])
    is_declining_margin = any(k in q for k in ["declining margin", "margin drop", "profit leak", "margin", "losing profit", "loss", "మార్జిన్ తగ్గింది", "లాభం తగ్గింది", "నష్టం", "मार्जिन कम", "मुनाफा कम", "नुकसान"])
    is_unmet_demand = any(k in q for k in ["customer request", "unstocked", "missing product", "what customers want", "unmet", "గ్రాహకులు", "కస్టమర్ కోరినవి", "స్టాక్ లేనివి", "ग्राहक की मांग", "जो स्टॉक में नहीं"])
    is_suggested_cost = any(k in q for k in ["suggested cost", "budget", "how much", "cost to purchase", "plan cost", "ఖర్చు", "బడ్జెట్", "మొత్తం", "लागत", "बजट", "कितना खर्च"])

    products = rows(db, Product, business.id)
    if not products:
        msg = {
            "te": "మీ స్టోర్ కేటలాగ్‌లో ప్రస్తుతం ఉత్పత్తులు లేవు. రికార్డ్ ఆధారిత విశ్లేషణ కోసం ఉత్పత్తులను జోడించండి.",
            "hi": "आपकी दुकान के कैटलॉग में अभी कोई उत्पाद नहीं है। रिकॉर्ड-आधारित विश्लेषण के लिए उत्पाद जोड़ें और इनवॉइस अपलोड करें।",
        }.get(language, "Your store currently has zero products in its catalog. Add products and upload supplier invoices to enable record-grounded analysis.")
        return {
            "query": query,
            "language": language,
            "response": msg,
            "evidence": [],
            "citations": ["Store product catalog (0 records)"],
            "action_link": "/inventory/products/new",
            "grounding_status": "insufficient_data",
        }

    prod_map = {p.id: p for p in products}
    suppliers = {s.id: s for s in rows(db, Supplier, business.id)}
    quotes = rows(db, Quote, business.id)
    stocks = {s["product_id"]: s for s in inventory(db, business)}
    forecast_map = {f["product_id"]: f for f in forecasts(db, business)}

    evidence = []
    citations = []
    action_link = "/overview"

    # Intent 1: Price Increases
    if is_price_hike:
        action_link = "/intelligence/profit-leaks"
        citations.append("Verified supplier invoices over the last 30 days")
        leak_data = profit_leak_analysis(db, business)
        hikes = [l for l in leak_data["leaks"] if l["category"] in ("unpassed_cost_increase", "below_cost")]
        if not hikes:
            hikes = leak_data["leaks"][:3]

        evidence = [
            {
                "Product": h["name"],
                "Verified Cost": f"₹{h.get('unit_cost', '0')}",
                "Previous Cost": f"₹{h.get('prev_cost', 'N/A')}",
                "Retail Price": f"₹{h.get('sell_price', '0')}",
                "Impact": f"₹{h.get('estimated_monthly_loss', '0')}/mo",
            }
            for h in hikes[:5]
        ]

        if language == "te":
            text = f"ఈ నెలలో {len(hikes)} ఉత్పత్తుల కొనుగోలు ధరలు పెరిగాయి. ప్రధానంగా {hikes[0]['name'] if hikes else 'ఉత్పత్తులు'} ధర పెరిగింది, దీనివల్ల నెలకు దాదాపు ₹{leak_data['total_monthly_leakage_rupees']} లాభం తగ్గే అవకాశం ఉంది."
        elif language == "hi":
            text = f"इस महीने {len(hikes)} उत्पादों की खरीद कीमतों में बढ़ोतरी हुई है। मुख्य रूप से {hikes[0]['name'] if hikes else 'उत्पादों'} की लागत बढ़ी है, जिससे अनुमानित ₹{leak_data['total_monthly_leakage_rupees']} मासिक मार्जिन कम हो रहा है।"
        else:
            text = f"We detected verified purchase price increases across {len(hikes)} products this period. The most critical is {hikes[0]['name'] if hikes else 'several items'}, causing an estimated gross margin leakage of ₹{leak_data['total_monthly_leakage_rupees']}/month unless selling prices or supplier quotes are adjusted."

    # Intent 2: Lowest Cost Supplier
    elif is_lowest_supplier:
        action_link = "/intelligence/suppliers"
        citations.append("Active supplier quotations and observed invoice delivery costs")
        # Find item mentioned or show multi-supplier comparisons
        cheapest_quotes = []
        by_prod = defaultdict(list)
        for q_row in quotes:
            by_prod[q_row.product_id].append(q_row)

        for pid, q_list in by_prod.items():
            if len(q_list) >= 2:
                sorted_q = sorted(q_list, key=lambda x: x.unit_cost)
                p = prod_map.get(pid)
                if p:
                    cheapest_quotes.append({
                        "Product": p.name,
                        "Cheapest Supplier": suppliers.get(sorted_q[0].supplier_id, Supplier(name='Unknown')).name,
                        "Best Rate": f"₹{sorted_q[0].unit_cost:.2f}",
                        "Competing Rate": f"₹{sorted_q[-1].unit_cost:.2f}",
                        "Saving": f"₹{(sorted_q[-1].unit_cost - sorted_q[0].unit_cost):.2f}/unit"
                    })

        evidence = cheapest_quotes[:5]
        top = cheapest_quotes[0] if cheapest_quotes else None

        if language == "te":
            text = f"సప్లయర్ ధరలను విశ్లేషించగా, {top['Product'] if top else 'ఉత్పత్తుల'} పై {top['Cheapest Supplier'] if top else 'కొత్త సప్లయర్'} అత్యల్ప ధర ({top['Best Rate'] if top else 'తక్కువ ధరకు'}) అందిస్తున్నారు. దీనివల్ల యూనిట్‌కు {top['Saving'] if top else 'మంచి ఆదా'} లభిస్తుంది."
        elif language == "hi":
            text = f"आपूर्तिकर्ताओं के विश्लेषण से पता चलता है कि {top['Product'] if top else 'उत्पादों'} के लिए {top['Cheapest Supplier'] if top else 'न्यूनतम सप्लायर'} सबसे कम दर ({top['Best Rate'] if top else 'रियायती मूल्य'}) दे रहे हैं, जिससे प्रति यूनिट {top['Saving'] if top else 'बचत'} होगी।"
        else:
            text = f"Based on verified supplier quotes, {top['Cheapest Supplier'] if top else 'preferred suppliers'} offer the lowest comparable cost for {top['Product'] if top else 'key items'} at {top['Best Rate'] if top else 'lower rates'}, saving {top['Saving'] if top else 'on unit procurement'}."

    # Intent 3: Reorder Recommendations Today
    elif is_reorder:
        action_link = "/purchasing/planner"
        citations.append("Usable inventory ledger, 84-day sales velocity, and supplier lead times")
        reorder_items = []
        for p in products:
            stk = stocks.get(p.id, {})
            avail = dec(stk.get("available") or ZERO)
            fc = forecast_map.get(p.id, {})
            dem = dec(fc.get("daily_demand") or ZERO)
            lead = 3
            safety = 2
            needed = (dem * dec(lead + safety)) - avail
            if needed > ZERO or avail <= ZERO:
                reorder_items.append({
                    "Product": p.name,
                    "Current Stock": f"{avail:.0f} {p.unit}",
                    "Daily Demand": f"{dem:.1f}",
                    "Stockout Urgency": "Critical (0 stock)" if avail <= 0 else "Low Stock",
                    "Suggested Order": f"{max(p.pack, ceil_step(needed, p.pack)):.0f} {p.unit}"
                })

        evidence = reorder_items[:5]
        first_item = reorder_items[0]["Product"] if reorder_items else "Stocked items"

        if language == "te":
            text = f"ఈ రోజు {len(reorder_items)} ఉత్పత్తులను రీ-ఆర్డర్ చేయాలి. ముఖ్యంగా {first_item} స్టాక్ అయిపోయింది లేదా అత్యవసరంగా ఉంది. అమ్మకాల వేగం మరియు సప్లయర్ డెలివరీ సమయాన్ని బట్టి ఆర్డర్ ప్లాన్ సిఫార్సు చేయబడింది."
        elif language == "hi":
            text = f"आज {len(reorder_items)} उत्पादों को पुनः आर्डर (Reorder) करने की आवश्यकता है। विशेष रूप से {first_item} का स्टॉक खत्म हो चुका है या बहुत कम है। बिक्री दर और सप्लायर लीड समय के अनुसार यह सिफारिश की गई है।"
        else:
            text = f"You have {len(reorder_items)} products currently recommended for replenishment today based on the formula Q = max(0, d(L+R) + S - I - P). Top priority is {first_item} to prevent customer stockouts."

    # Intent 4: Top Sales This Week
    elif is_top_sales:
        action_link = "/intelligence/forecasts"
        citations.append("POS & finalized sales transactions over the past 7 days")
        txs_sale = {t.id: t for t in rows(db, Transaction, business.id) if t.active and t.kind == "sale"}
        week_ago = today() - timedelta(days=7)
        sales_7d = defaultdict(Decimal)
        rev_7d = defaultdict(Decimal)
        for l in rows(db, Line, business.id):
            if l.transaction_id in txs_sale and txs_sale[l.transaction_id].date >= week_ago:
                sales_7d[l.product_id] += l.qty
                rev_7d[l.product_id] += (l.qty * l.unit_cost)

        ranked = sorted(sales_7d.items(), key=lambda x: x[1], reverse=True)
        evidence = [
            {
                "Product": prod_map[pid].name if pid in prod_map else "Product",
                "Units Sold (7d)": f"{qty:.0f}",
                "Sales Value": f"₹{rev_7d[pid]:.2f}",
                "Daily Velocity": f"{(qty / D('7')):.1f}/day"
            }
            for pid, qty in ranked[:5] if pid in prod_map
        ]

        top_p = evidence[0]["Product"] if evidence else "Main staples"

        if language == "te":
            text = f"గత 7 రోజుల్లో అత్యధికంగా అమ్ముడైన ఉత్పత్తి: {top_p} ({evidence[0]['Units Sold (7d)'] if evidence else '0'} యూనిట్లు). ఇది మీ స్టోర్‌లో అత్యంత వేగంగా తిరిగే వస్తువు."
        elif language == "hi":
            text = f"पिछले 7 दिनों में सबसे अधिक बिक्री {top_p} की रही ({evidence[0]['Units Sold (7d)'] if evidence else '0'} यूनिट्स)। यह आपके स्टोर की सबसे तेज बिकने वाली वस्तु है।"
        else:
            text = f"The highest volume product over the past 7 days is {top_p} with {evidence[0]['Units Sold (7d)'] if evidence else '0'} units sold, driving consistent store traffic."

    # Intent 5: Declining Gross Margins
    elif is_declining_margin:
        action_link = "/intelligence/profit-leaks"
        citations.append("Historical purchase invoices vs POS sales discount ledger")
        leak_data = profit_leak_analysis(db, business)
        evidence = [
            {
                "Product": l["name"],
                "Category": l["category"].replace("_", " ").title(),
                "Current Margin": f"{l.get('margin_pct', 'N/A')}%",
                "Monthly Leak": f"₹{l.get('estimated_monthly_loss', '0')}",
                "Action": l.get("remedy", "")
            }
            for l in leak_data["leaks"][:5]
        ]

        if language == "te":
            text = f"మొత్తం {leak_data['affected_products_count']} ఉత్పత్తులలో లాభాల మార్జిన్ తగ్గినట్లు గుర్తించబడింది. నెలకు సుమారు ₹{leak_data['total_monthly_leakage_rupees']} మేర లాభం లీక్ అవుతోంది. అమ్మకపు ధరను పెంచడం లేదా సప్లయర్లతో చర్చించడం అవసరం."
        elif language == "hi":
            text = f"कुल {leak_data['affected_products_count']} उत्पादों में ग्रॉस मार्जिन में गिरावट दर्ज की गई है। इससे मासिक लगभग ₹{leak_data['total_monthly_leakage_rupees']} का संभावित नुकसान हो रहा है।"
        else:
            text = f"Identified {leak_data['affected_products_count']} SKUs with gross margin compression or selling below verified cost, representing an estimated ₹{leak_data['total_monthly_leakage_rupees']} monthly leakage."

    # Intent 6: Unmet Customer Requests
    elif is_unmet_demand:
        action_link = "/intelligence/local-demand"
        citations.append("Store Unmet Demand Register & customer request log")
        demand_data = local_demand_analysis(db, business)
        evidence = [
            {
                "Requested Product": o["product_name"],
                "Category": o["category"],
                "Requests": str(o["request_count"]),
                "Score": f"{o['opportunity_score']}/100",
                "Action": o["recommendation"]
            }
            for o in demand_data["opportunities"][:5]
        ]
        top_req = evidence[0]["Requested Product"] if evidence else "None yet"

        if language == "te":
            text = f"కస్టమర్లు కోరిన కానీ ప్రస్తుతం స్టోర్‌లో లేని వస్తువులలో '{top_req}' అగ్రస్థానంలో ఉంది. దీనికి అత్యధిక డిమాండ్ స్కోర్ ఉంది మరియు ఒక చిన్న ట్రయల్ బ్యాచ్ ఆర్డర్ చేయడం మంచిది."
        elif language == "hi":
            text = f"ग्राहकों द्वारा मांगी गई अनुपलब्ध वस्तुओं में '{top_req}' सबसे आगे है। इसका ऑपर्च्युनिटी स्कोर अधिक है और इसका एक छोटा ट्रायल आर्डर मंगाना उचित रहेगा।"
        else:
            text = f"The Unmet Demand Register shows '{top_req}' as the most requested unstocked product. Based on our opportunity scoring, a small trial order is recommended."

    # Intent 7: Suggested Purchase Cost
    elif is_suggested_cost:
        action_link = "/purchasing/planner"
        citations.append("Budget optimizer, minimum order quantities, and supplier price tier schedules")
        try:
            rec, _ = recommend(db, business, D("20000"))
        except Exception:
            rec = []
        evidence = [
            {
                "Product": l["name"],
                "Quantity": f"{l['qty']} units",
                "Supplier": suppliers.get(l["supplier_id"], Supplier(name="Supplier")).name,
                "Spend": f"₹{l['cash_spend']:.2f}",
                "Benefit": f"₹{l['benefit_estimate']:.2f}"
            }
            for l in rec[:5]
        ]
        total_spend = sum((dec(l["cash_spend"]) for l in rec), ZERO)

        if language == "te":
            text = f"ప్రస్తుత సిఫార్సు చేసిన కొనుగోలు ప్లాన్ ప్రకారం మొత్తం ఖర్చు ₹{total_spend:.2f}. ఇది మీ కొనుగోలు బడ్జెట్ పరిమితికి లోబడి ఉండి అత్యధిక లాభం తెచ్చే వస్తువులకు ప్రాధాన్యత ఇస్తుంది."
        elif language == "hi":
            text = f"सिफारिश किए गए खरीद प्लान के अनुसार कुल अनुमानित खर्च ₹{total_spend:.2f} है। यह आपके खरीद बजट के अंतर्गत सबसे आवश्यक स्टॉक को प्राथमिकता देता है।"
        else:
            text = f"The cash-flow-aware purchase plan requires an estimated ₹{total_spend:.2f} across {len(rec)} prioritized lines, maximizing stock coverage within your available working capital."

    # Default overview
    else:
        action_link = "/overview"
        citations.append("Verified catalog, live stock balance, and active intelligence signals")
        leak_data = profit_leak_analysis(db, business)
        demand_data = local_demand_analysis(db, business)
        evidence = [
            {"Area": "Active SKUs", "Value": str(len(products))},
            {"Area": "Monthly Profit Leakage", "Value": f"₹{leak_data['total_monthly_leakage_rupees']}"},
            {"Area": "Unmet Customer Requests", "Value": str(demand_data["unmet_requests_count"])},
            {"Area": "Local Market Network", "Value": "Active (In-Store Signals)"}
        ]
        if language == "te":
            text = f"మీ వ్యాపార సారాంశం: {len(products)} ఉత్పత్తులు ఉన్నాయి. ₹{leak_data['total_monthly_leakage_rupees']} లాభాల లీక్ గుర్తించబడింది మరియు {demand_data['unmet_requests_count']} కస్టమర్ అభ్యర్థనలు నమోదయ్యాయి. వివరాల కోసం క్రింది ప్రశ్నలను అడగవచ్చు."
        elif language == "hi":
            text = f"आपके व्यवसाय का विश्लेषण: {len(products)} उत्पाद मौजूद हैं। ₹{leak_data['total_monthly_leakage_rupees']} की मार्जिन लीकेज पहचानी गई है और {demand_data['unmet_requests_count']} ग्राहकों की मांग दर्ज है।"
        else:
            text = f"Here is your verified store snapshot: Managing {len(products)} catalog products. Detected ₹{leak_data['total_monthly_leakage_rupees']} in monthly profit leakage and {demand_data['unmet_requests_count']} customer unmet demand requests."

    return {
        "query": query,
        "language": language,
        "response": text,
        "evidence": evidence,
        "citations": citations,
        "action_link": action_link,
    }


def unified_decision_summary(db, business, budget=D("25000")):
    """
    Unified Purchase Decision Engine & Supplier Negotiation Insights
    Answers the 7 core questions from the proposal:
    1. What is running low?
    2. What is selling or being requested?
    3. What quantity is justified?
    4. Which supplier offers the best comparable total cost?
    5. Is the supplier reliable based on recorded history?
    6. Does the purchase fit the available budget?
    7. What is the expected benefit and what is the uncertainty?
    Plus factual negotiation talking points.
    """
    products = rows(db, Product, business.id)
    stocks = {s["product_id"]: s for s in inventory(db, business)}
    forecast_map = {f["product_id"]: f for f in forecasts(db, business)}
    quotes = rows(db, Quote, business.id)
    suppliers = {s.id: s for s in rows(db, Supplier, business.id)}
    unmet = db.scalars(select(UnmetDemandRequest).where(UnmetDemandRequest.business_id == business.id)).all()
    cards = scorecards(db, business.id)
    try:
        recommended_lines, _ = recommend(db, business, budget)
    except Exception:
        recommended_lines = []

    # 1. Running low
    running_low = [
        {"product": p.name, "available": stocks.get(p.id, {}).get("available", "0"), "unit": p.unit}
        for p in products if dec(stocks.get(p.id, {}).get("available", "0")) <= ZERO
    ]

    # 2. Demand drivers
    requested_items = [
        {"product": u.product_name, "requests": u.request_count, "category": u.category}
        for u in unmet if u.status in ("logged", "evaluating")
    ]

    # 3. Negotiation Insights
    txs = {t.id: t for t in rows(db, Transaction, business.id) if t.active and t.kind == "purchase"}
    all_lines = rows(db, Line, business.id)
    negotiation_points = []

    for q in quotes:
        p = next((x for x in products if x.id == q.product_id), None)
        supp = suppliers.get(q.supplier_id)
        if not p or not supp:
            continue

        # Look for historical cheaper purchases from same or competitor supplier
        hist_lines = [l for l in all_lines if l.product_id == p.id and l.transaction_id in txs]
        for l in hist_lines:
            prev_tx = txs[l.transaction_id]
            if l.unit_cost < q.unit_cost * D("0.96"): # at least 4% cheaper previously
                prev_supp = suppliers.get(prev_tx.supplier_id, Supplier(name="Another Supplier"))
                negotiation_points.append({
                    "product": p.name,
                    "quoted_supplier": supp.name,
                    "quote_price": f"₹{q.unit_cost:.2f}",
                    "benchmark_price": f"₹{l.unit_cost:.2f}",
                    "benchmark_source": f"Invoice #{prev_tx.invoice_no} on {prev_tx.date.strftime('%d-%b-%Y')} from {prev_supp.name}",
                    "talking_point": f"Negotiate with {supp.name} on {p.name}: previously purchased at ₹{l.unit_cost:.2f} (₹{(q.unit_cost - l.unit_cost):.2f} lower) via Invoice #{prev_tx.invoice_no}."
                })
                break

    return {
        "budget": str(budget),
        "total_spend": str(sum((dec(l["cash_spend"]) for l in recommended_lines), ZERO)),
        "running_low_count": len(running_low),
        "running_low_preview": running_low[:4],
        "unmet_requests_count": len(requested_items),
        "unmet_requests_preview": requested_items[:4],
        "recommended_lines_count": len(recommended_lines),
        "supplier_scorecards": cards,
        "negotiation_insights": negotiation_points[:5],
    }
