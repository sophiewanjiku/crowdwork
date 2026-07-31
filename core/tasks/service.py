"""
Task engine: claiming, submitting, and reviewing tasks.

This is core business logic - no FastAPI imports here. The API layer
(api/routers/assignments.py) just calls these functions and translates
their exceptions into HTTP responses. That separation means this logic
would work identically if called from a web app instead of Telegram.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import (
    Task, TaskAssignment, AssignmentStatus, TaskStatus,
    Submission, Review, User, TransactionType,
)
from core.wallet.service import credit


class TaskEngineError(Exception):
    """Base class for expected business-rule violations (not bugs)."""
    pass


class TaskNotAvailable(TaskEngineError):
    pass


class AlreadyClaimed(TaskEngineError):
    pass


class NotYourAssignment(TaskEngineError):
    pass


class InvalidAssignmentState(TaskEngineError):
    pass


def claim_task(db: Session, task: Task, worker: User) -> TaskAssignment:
    if task.status != TaskStatus.active:
        raise TaskNotAvailable("This task isn't open for claims.")

    existing = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.task_id == task.id, TaskAssignment.worker_id == worker.id)
        .first()
    )
    if existing:
        raise AlreadyClaimed("You've already claimed this task.")

    claimed_count = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.task_id == task.id)
        .filter(TaskAssignment.status != AssignmentStatus.rejected)
        .count()
    )
    if claimed_count >= task.max_assignments:
        raise TaskNotAvailable("This task has no open slots left.")

    assignment = TaskAssignment(task_id=task.id, worker_id=worker.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def submit_answer(
    db: Session,
    assignment: TaskAssignment,
    worker: User,
    answer_text: str | None,
    answer_file_url: str | None,
) -> Submission:
    if assignment.worker_id != worker.id:
        raise NotYourAssignment("This assignment doesn't belong to you.")
    if assignment.status != AssignmentStatus.assigned:
        raise InvalidAssignmentState(f"Can't submit - assignment is '{assignment.status.value}'.")

    submission = Submission(
        assignment_id=assignment.id,
        answer_text=answer_text,
        answer_file_url=answer_file_url,
    )
    assignment.status = AssignmentStatus.submitted
    assignment.submitted_at = datetime.now(timezone.utc)

    db.add(submission)
    db.add(assignment)
    db.commit()
    db.refresh(submission)
    return submission


def review_submission(
    db: Session,
    submission: Submission,
    reviewer: User,
    decision: AssignmentStatus,
    accuracy_score: float | None,
    notes: str | None,
) -> Review:
    if decision not in (AssignmentStatus.approved, AssignmentStatus.rejected):
        raise InvalidAssignmentState("Decision must be 'approved' or 'rejected'.")

    assignment = submission.assignment
    if assignment.status != AssignmentStatus.submitted:
        raise InvalidAssignmentState(f"Can't review - assignment is '{assignment.status.value}'.")

    review = Review(
        submission_id=submission.id,
        reviewer_id=reviewer.id,
        is_automatic=False,
        accuracy_score=accuracy_score,
        decision=decision,
        notes=notes,
    )
    assignment.status = decision
    db.add(review)
    db.add(assignment)
    db.commit()
    db.refresh(review)

    if decision == AssignmentStatus.approved:
        worker = assignment.worker  # requires the relationship below
        credit(
            db,
            worker.wallet,
            assignment.task.reward_amount,
            TransactionType.task_reward,
            reference_id=assignment.id,
        )

    return review