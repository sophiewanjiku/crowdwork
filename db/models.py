"""
Core data models.

These are the nouns of the platform. Nothing here knows Telegram exists -
that's the whole point of the architecture. If a model needs to change to
support a new client (web, WhatsApp, an enterprise API), something has gone
wrong with the design.
"""

import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    String, Text, ForeignKey, DateTime, Numeric, JSON, Enum, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Identity & auth
# ---------------------------------------------------------------------------

class User(Base):
    """
    The core identity. One row per human, regardless of how many channels
    (Telegram, web, WhatsApp...) they connect through.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    identities: Mapped[list["Identity"]] = relationship(back_populates="user")
    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False)


class Identity(Base):
    """
    Links a User to one login channel. This is the piece that makes the
    system multi-client: a Telegram user and a future web user with the same
    email both point at the same User row.

    channel: "telegram", "web", "whatsapp", "api_key", etc.
    external_id: the ID that channel uses - e.g. the Telegram numeric user id,
                 as a string (so we don't have to special-case formats).
    """
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_identity_channel_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="identities")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class TaskStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"


class AssignmentStatus(str, enum.Enum):
    assigned = "assigned"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class Task(Base):
    """
    A task template. Deliberately generic: `task_type` is just a string tag
    (e.g. "text_answer", "multiple_choice", "photo_upload") and `payload` is
    free-form JSON holding whatever that task type needs (a question, a set
    of choices, a file to review, etc).

    This means adding a brand new kind of task later is a data change, not a
    schema migration.
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    # Optional - only set for tasks that can be auto-graded (e.g. multiple
    # choice with one right answer). Left null for tasks that need a human
    # reviewer.
    correct_answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    reward_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max_assignments: Mapped[int] = mapped_column(default=1)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.draft)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignments: Mapped[list["TaskAssignment"]] = relationship(back_populates="task")


class TaskAssignment(Base):
    """
    One worker's claim on one task. Tracks the lifecycle: assigned -> 
    submitted -> approved/rejected.
    """
    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus), default=AssignmentStatus.assigned
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship(back_populates="assignments")
    submission: Mapped["Submission | None"] = relationship(back_populates="assignment", uselist=False)


class Submission(Base):
    """
    The actual answer a worker submitted for one assignment.
    Supports both a text answer and/or a file - a task can require either,
    both, or neither depending on task_type.
    """
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("task_assignments.id"), unique=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped["TaskAssignment"] = relationship(back_populates="submission")
    review: Mapped["Review | None"] = relationship(back_populates="submission", uselist=False)


class Review(Base):
    """
    The verdict on a submission - either from an automatic check (comparing
    against Task.correct_answer) or a human reviewer (reviewer_id set).
    """
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), unique=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_automatic: Mapped[bool] = mapped_column(default=False)
    accuracy_score: Mapped[float | None] = mapped_column(nullable=True)  # 0.0 - 1.0
    decision: Mapped[AssignmentStatus] = mapped_column(Enum(AssignmentStatus))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submission: Mapped["Submission"] = relationship(back_populates="review")


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------

class TransactionType(str, enum.Enum):
    task_reward = "task_reward"
    adjustment = "adjustment"
    withdrawal = "withdrawal"


class Wallet(Base):
    """
    One wallet per user. `balance` is a denormalized cache for fast reads -
    the real source of truth is the sum of Transaction rows below. Never
    edit `balance` directly from application code; always go through the
    wallet service (built later), which writes a Transaction and updates
    the cache in the same operation.
    """
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    user: Mapped["User"] = relationship(back_populates="wallet")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="wallet")


class Transaction(Base):
    """
    An immutable ledger entry. Positive amount = credit (money in),
    negative = debit (money out). Never deleted or edited - if a reward was
    wrong, you add a correcting Transaction, you don't rewrite history.
    reference_id points at whatever caused this transaction, e.g. a
    TaskAssignment.id for a task_reward entry.
    """
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    wallet: Mapped["Wallet"] = relationship(back_populates="transactions")