import os
import secrets
from datetime import timedelta
from hashlib import sha256
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from .db import get_db, now
from .models import Session, User, Membership, Branch, BranchGrant
from . import branch_scope

hasher = PasswordHasher()


def cipher():
    key = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key:
        raise HTTPException(
            503, "Set TOKEN_ENCRYPTION_KEY to enable MFA and external credentials"
        )
    return Fernet(key.encode())


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    return cipher().decrypt(value.encode()).decode()


def current(request: Request, db=Depends(get_db)):
    cookie = request.cookies.get("procure_session", "")
    session = db.get(Session, sha256(cookie.encode()).hexdigest()) if cookie else None
    if not session or session.expires < now():
        raise HTTPException(401, "Sign in required")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        token = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(token, session.csrf):
            raise HTTPException(403, "CSRF token missing or invalid")
    request.state.session = session
    return db.get(User, session.user_id)


def access(
    business_id: str, request: Request, user=Depends(current), db=Depends(get_db)
):
    membership = db.scalar(
        select(Membership).where(
            Membership.business_id == business_id, Membership.user_id == user.id
        )
    )
    if not membership:
        raise HTTPException(404, "Business not found")
    request.state.role = membership.role
    branches = db.scalars(select(Branch).where(Branch.business_id == business_id)).all()
    if not branches:
        branches = [branch_scope.default_branch(db, business_id)]
    grants = db.scalars(
        select(BranchGrant).where(
            BranchGrant.business_id == business_id, BranchGrant.user_id == user.id
        )
    ).all()
    allowed = (
        [b.id for b in branches]
        if membership.role == "owner"
        else [g.branch_id for g in grants]
    )
    # Existing test/CLI memberships without grants are limited to the main branch.
    if not allowed and membership.role in ("reviewer", "receiving", "manager"):
        allowed = [next((b.id for b in branches if b.code=='MAIN'),branches[0].id)]
    default_id=next((b.id for b in branches if b.code=='MAIN' and b.id in allowed),allowed[0] if allowed else None)
    chosen = (
        request.headers.get("x-branch-id")
        or request.query_params.get("branch_id")
        or default_id
        if allowed
        else None
    )
    if chosen == "all":
        selected = allowed
    elif chosen in allowed:
        selected = [chosen]
    else:
        raise HTTPException(404, "Branch not found or access not granted")
    db.info["branch_ids"] = selected
    db.info["write_branch"] = selected[0] if len(selected) == 1 else None
    request.state.branch_ids = selected
    request.state.branch_id = selected[0] if len(selected) == 1 else None
    request.state.business_owner = membership.role == "owner"
    db.info["business_owner"] = membership.role == "owner"
    if (
        len(selected) != 1
        and request.method not in ("GET", "HEAD")
        and "/workspace/" not in request.url.path
        and any(
            "/" + p in request.url.path
            for p in (
                "documents",
                "imports",
                "inventory",
                "baskets",
                "receipts",
                "movements",
                "lost-sales",
                "jobs",
            )
        )
    ):
        raise HTTPException(
            422, "Select one branch before changing operational records"
        )
    if membership.role != "owner":
        roles = [g.role for g in grants if g.branch_id in selected]
        request.state.role = (
            roles[0] if roles and len(set(roles)) == 1 else membership.role
        )
    if request.state.role == "receiving" and request.method not in ("GET", "HEAD"):
        if not any(p in request.url.path for p in ("/receive", "/read", "/auth/")):
            raise HTTPException(
                403, "Receiving staff can receive goods and read records only"
            )
    return user


def owner(request: Request, user=Depends(access), db=Depends(get_db)):
    if request.state.role != "owner":
        raise HTTPException(403, "Owner access required")
    # Demo owners can exercise workflows; real owners must enroll MFA first.
    if (
        not user.mfa_enabled or not request.state.session.mfa_verified
    ) and request.method not in ("GET", "HEAD"):
        from .models import Business

        business = db.get(Business, request.path_params["business_id"])
        if business and not business.demo:
            raise HTTPException(
                403, "Enable owner MFA in Settings before changing real business data"
            )
    return user
