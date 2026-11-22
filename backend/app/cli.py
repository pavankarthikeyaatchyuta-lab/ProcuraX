from .db import today
import argparse
import getpass
import os
import secrets
from datetime import date, timedelta, datetime, time
from decimal import Decimal
from sqlalchemy import select
from .db import Base, engine, SessionLocal, now
from .models import *
from .security import hasher
from .domain import audit


def seed():
    with SessionLocal() as db:
        if db.scalar(select(Business).where(Business.demo == True)):
            print("Demo already exists. Existing credentials were not changed.")
            return
        password = os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(18)
        b = Business(name="Asha Daily Mart", demo=True)
        db.add(b)
        db.flush()
        u = User(email="owner@vyaya.local", password=hasher.hash(password))
        db.add(u)
        db.flush()
        db.add(Membership(business_id=b.id, user_id=u.id, role="owner"))
        suppliers = []
        for name, gst, minimum in [
            ("Metro Wholesale", "27AAACM1234A1Z5", 500),
            ("Sunrise Distributors", "27AAACS5678B1Z6", 0),
            ("Greenfield Traders", "27AAACG9012C1Z7", 0),
        ]:
            s = Supplier(
                business_id=b.id,
                name=name,
                gstin=gst,
                minimum_order=minimum,
                payment_terms="Net 14 days",
            )
            db.add(s)
            db.flush()
            suppliers.append(s)
        catalog = [
            (
                "AMUL-500",
                "Amul Taaza milk",
                "Amul",
                "Taaza",
                "500 ml",
                12,
                27,
                30,
                12,
                18,
            ),
            (
                "TATA-1KG",
                "Tata Salt · 1 kg",
                "Tata",
                "Iodised",
                "1 kg",
                10,
                22,
                28,
                5,
                0,
            ),
            (
                "FORT-1L",
                "Fortune sunflower oil",
                "Fortune",
                "Sunflower",
                "1 litre",
                12,
                118,
                145,
                4,
                9,
            ),
            (
                "PARLE-250",
                "Parle-G biscuits",
                "Parle",
                "Original",
                "250 g",
                24,
                24,
                32,
                7,
                14,
            ),
            (
                "AASH-5KG",
                "Aashirvaad atta",
                "Aashirvaad",
                "Whole wheat",
                "5 kg",
                4,
                220,
                280,
                3,
                35,
            ),
            (
                "SURF-1KG",
                "Surf Excel detergent",
                "Surf Excel",
                "Easy wash",
                "1 kg",
                6,
                156,
                190,
                2,
                7,
            ),
            ("MAGGI-70", "Maggi noodles", "Maggi", "Masala", "70 g", 48, 10, 14, 8, 40),
            (
                "BRU-50",
                "Bru instant coffee",
                "Bru",
                "Original",
                "50 g",
                12,
                110,
                140,
                0.35,
                4,
            ),
        ]
        for idx, (
            sku,
            name,
            brand,
            variant,
            size,
            pack,
            cost,
            sell,
            daily,
            current,
        ) in enumerate(catalog):
            p = Product(
                business_id=b.id,
                sku=sku,
                name=name,
                brand=brand,
                variant=variant,
                size=size,
                pack=pack,
                sell_price=sell,
                unit="unit",
                barcode=f"89010000000{idx}",
            )
            db.add(p)
            db.flush()
            total_sold = 0
            for day in range(84, 0, -1):
                occurred = today() - timedelta(days=day)
                qty = (
                    (0 if day % 5 else 2)
                    if daily < 1
                    else max(0, int(daily + (day * 7 + idx) % 5 - 2))
                )
                total_sold += qty
                tx = Transaction(
                    business_id=b.id,
                    source="demo",
                    source_key=f"sale-{idx}-{day}",
                    kind="sale",
                    invoice_no=f"S-{idx}-{day}",
                    date=occurred,
                    total=qty * sell,
                    raw={"demo": True},
                )
                db.add(tx)
                db.flush()
                if qty:
                    db.add(
                        Line(
                            business_id=b.id,
                            transaction_id=tx.id,
                            product_id=p.id,
                            qty=qty,
                            unit_cost=sell,
                            cash_unit=sell,
                            discount=0,
                            raw={"demo": True},
                        )
                    )
                    db.add(
                        Movement(
                            business_id=b.id,
                            product_id=p.id,
                            transaction_id=tx.id,
                            qty=-qty,
                            kind="sale",
                            reason="Demo sales import",
                            at=datetime.combine(occurred, time(12)),
                        )
                    )
                db.add(
                    Stock(
                        business_id=b.id,
                        product_id=p.id,
                        on_hand=current + qty + 20,
                        reserved=0,
                        on_order=0,
                        source="demo_availability",
                        at=datetime.combine(occurred, time(8)),
                    )
                )
            total_bought = 0
            for n in range(6):
                price = Decimal(cost) * (
                    Decimal("1.14") if n == 5 and idx in (0, 3) else Decimal("1")
                )
                qty = pack * 2
                total_bought += qty
                occurred = today() - timedelta(days=75 - n * 12)
                tx = Transaction(
                    business_id=b.id,
                    source="demo",
                    source_key=f"purchase-{idx}-{n}",
                    kind="purchase",
                    supplier_id=suppliers[0].id,
                    invoice_no=f"P-{idx}-{n}",
                    date=occurred,
                    total=price * qty,
                    raw={"demo": True},
                )
                db.add(tx)
                db.flush()
                db.add(
                    Line(
                        business_id=b.id,
                        transaction_id=tx.id,
                        product_id=p.id,
                        qty=qty,
                        unit_cost=price,
                        cash_unit=price,
                        discount=0,
                        raw={"demo": True},
                    )
                )
                db.add(
                    Movement(
                        business_id=b.id,
                        product_id=p.id,
                        transaction_id=tx.id,
                        qty=qty,
                        kind="purchase",
                        reason="Demo verified purchase",
                        at=datetime.combine(occurred, time(10)),
                    )
                )
            db.add(
                Movement(
                    business_id=b.id,
                    product_id=p.id,
                    qty=current + total_sold - total_bought,
                    kind="opening",
                    reason="Demo opening balance",
                    at=datetime.combine(today() - timedelta(days=90), time.min),
                )
            )
            for si, supplier in enumerate(suppliers):
                db.add(
                    Quote(
                        business_id=b.id,
                        product_id=p.id,
                        supplier_id=supplier.id,
                        supplier_sku=f"{si}-{sku}",
                        unit_cost=Decimal(cost)
                        * (
                            Decimal("1.03")
                            if si == 0
                            else Decimal(".97")
                            if si == 1
                            else Decimal("1")
                        ),
                        tax_pct=0,
                        freight_unit=0,
                        pack=pack,
                        moq=pack,
                        multiple=pack,
                        lead_days=3 + si,
                        observed=today() - timedelta(days=si),
                        valid_until=today() + timedelta(days=14),
                        tiers=[],
                    )
                )
            for si, supplier in enumerate(suppliers):
                for n in range(3):
                    ordered = today() - timedelta(days=25 + n * 7)
                    db.add(
                        Receipt(
                            business_id=b.id,
                            supplier_id=supplier.id,
                            product_id=p.id,
                            ordered_on=ordered,
                            expected=ordered + timedelta(days=4),
                            actual=ordered + timedelta(days=3 + (n == 2 and si == 2)),
                            ordered_qty=pack,
                            received_qty=pack,
                        )
                    )
            db.flush()
            db.add(
                Stock(
                    business_id=b.id,
                    product_id=p.id,
                    on_hand=current,
                    reserved=0,
                    on_order=0,
                    source="demo_count",
                    at=now(),
                )
            )
        audit(
            db,
            b.id,
            "seed",
            "demo.created",
            b.id,
            {"notice": "Synthetic data. Not evidence of live provider performance."},
        )
        db.commit()
        from .operations import ensure_payables
        ensure_payables(db,b.id);db.commit()
        print(f"Demo ready\nEmail: {u.email}\nPassword: {password}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["init", "seed", "create-user", "grant", "reset-mfa"]
    )
    parser.add_argument("--email")
    parser.add_argument("--business")
    parser.add_argument("--role", choices=["owner", "reviewer"], default="reviewer")
    args = parser.parse_args()
    if args.command == "init":
        from alembic.config import Config
        from alembic import command

        command.upgrade(Config("alembic.ini"), "head")
        return
    if args.command == "seed":
        seed()
        return
    with SessionLocal() as db:
        if not args.email:
            parser.error("--email required")
        email = args.email.strip().lower()
        u = db.scalar(select(User).where(User.email == email))
        if args.command == "create-user":
            if u:
                parser.error("User already exists")
            password = getpass.getpass("Password (12+ characters): ")
            if len(password) < 12:
                parser.error("Password too short")
            u = User(email=email, password=hasher.hash(password))
            db.add(u)
        elif args.command == "reset-mfa":
            if not u:
                parser.error("User not found")
            u.mfa_enabled = False
            u.totp_secret = None
            u.last_totp = 0
            db.execute(
                __import__("sqlalchemy").delete(Session).where(Session.user_id == u.id)
            )
            print("MFA reset and sessions revoked. Re-enroll before owner actions.")
        else:
            if not u or not args.business or not db.get(Business, args.business):
                parser.error("Valid --email and --business required")
            db.add(Membership(business_id=args.business, user_id=u.id, role=args.role))
            audit(
                db,
                args.business,
                "local-admin",
                "membership.granted",
                u.id,
                {"role": args.role},
            )
        db.commit()


if __name__ == "__main__":
    main()
