import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet

os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base, get_db, now
from app.models import (
    Business,
    User,
    Membership,
    Product,
    Supplier,
    Quote,
    Movement,
    Stock,
)
from app.security import hasher
from app.main import app


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        b = Business(name="Test shop", demo=True)
        other = Business(name="Other tenant", demo=True)
        db.add_all([b, other])
        db.flush()
        owner = User(
            email="owner@test.local", password=hasher.hash("correct-test-password")
        )
        reviewer = User(
            email="review@test.local", password=hasher.hash("review-test-password")
        )
        db.add_all([owner, reviewer])
        db.flush()
        db.add_all(
            [
                Membership(business_id=b.id, user_id=owner.id, role="owner"),
                Membership(business_id=b.id, user_id=reviewer.id, role="reviewer"),
            ]
        )
        p = Product(
            business_id=b.id,
            sku="MILK",
            name="Milk 500 ml",
            size="500 ml",
            pack=12,
            sell_price=30,
            manual_demand=10,
        )
        s = Supplier(business_id=b.id, name="Supplier A", minimum_order=0)
        db.add_all([p, s])
        db.flush()
        q = Quote(
            business_id=b.id,
            product_id=p.id,
            supplier_id=s.id,
            unit_cost=20,
            tax_pct=5,
            freight_unit=1,
            pack=12,
            moq=24,
            multiple=12,
            lead_days=3,
            tiers=[],
        )
        db.add(q)
        db.add_all(
            [
                Movement(
                    business_id=b.id,
                    product_id=p.id,
                    qty=12,
                    kind="opening",
                    reason="Test opening",
                ),
                Stock(
                    business_id=b.id,
                    product_id=p.id,
                    on_hand=12,
                    reserved=0,
                    on_order=0,
                    source="count",
                ),
            ]
        )
        db.commit()
        ids = {
            "business": b.id,
            "other": other.id,
            "product": p.id,
            "supplier": s.id,
            "quote": q.id,
            "owner": owner.id,
        }

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@test.local", "password": "correct-test-password"},
        )
        assert r.status_code == 200, r.text
        client.headers["x-csrf-token"] = r.json()["csrf"]
        yield client, factory, ids
    app.dependency_overrides.clear()
    engine.dispose()
