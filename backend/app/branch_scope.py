"""One request scope for legacy and expanded operational records."""

from sqlalchemy import event, select, or_
from sqlalchemy.orm import Session as OrmSession, with_loader_criteria
from fastapi import HTTPException
from .db import uid
from .models import Branch, BranchScoped, Transfer, Audit


def default_branch(db, bid):
    branch = db.scalar(
        select(Branch).where(Branch.business_id == bid, Branch.code == "MAIN")
    )
    if not branch:
        branch = Branch(id=uid(), business_id=bid, code="MAIN", name="Main Store")
        db.add(branch)
        db.flush()
    return branch


@event.listens_for(OrmSession, "do_orm_execute")
def scoped_select(state):
    ids = state.session.info.get("branch_ids")
    if ids is None or not state.is_select or state.execution_options.get("unscoped"):
        return
    # Transfer visibility includes incoming goods at the destination branch.
    entities={d.get('entity') for d in state.statement.column_descriptions}
    for cls in entities:
        if isinstance(cls,type) and issubclass(cls, BranchScoped):
            if cls is Transfer:
                state.statement = state.statement.options(
                    with_loader_criteria(
                        cls,
                        or_(cls.branch_id.in_(ids), cls.destination_id.in_(ids)),
                        include_aliases=True,
                    )
                )
            elif cls.__name__ in ("UnmetDemandRequest", "LocalMarketSignal"):
                state.statement = state.statement.options(
                    with_loader_criteria(
                        cls,
                        or_(cls.branch_id.in_(ids), cls.branch_id.is_(None)),
                        include_aliases=True,
                    )
                )
            else:
                state.statement = state.statement.options(
                    with_loader_criteria(
                        cls, cls.branch_id.in_(ids), include_aliases=True
                    )
                )


@event.listens_for(OrmSession, "before_flush")
def assign_branch(db, context, instances):
    pending = {b.business_id: b for b in db.new if isinstance(b, Branch)}
    for row in list(db.new):
        if not isinstance(row, BranchScoped) or row.branch_id is not None:
            continue
        selected = db.info.get("write_branch")
        if selected:
            row.branch_id = selected
            continue
        branch = pending.get(row.business_id)
        if branch is None:
            branch = db.scalar(
                select(Branch).where(
                    Branch.business_id == row.business_id, Branch.code == "MAIN"
                )
            )
            if branch is None:
                branch = Branch(
                    id=uid(),
                    business_id=row.business_id,
                    code="MAIN",
                    name="Main Store",
                )
                db.add(branch)
            pending[row.business_id] = branch
        row.branch_id = branch.id
