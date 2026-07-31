"""
Assignment endpoints: claiming a task, submitting an answer, reviewing a submission.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.base import get_db
from db.models import Task, TaskAssignment, Submission, AssignmentStatus, User
from core.auth.dependencies import get_current_user
from core.tasks.service import claim_task, submit_answer, review_submission, TaskEngineError

router = APIRouter(tags=["assignments"])


class AssignmentOut(BaseModel):
    id: int
    task_id: int
    worker_id: int
    status: AssignmentStatus

    class Config:
        from_attributes = True


class SubmitIn(BaseModel):
    answer_text: str | None = None
    answer_file_url: str | None = None


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    answer_text: str | None
    answer_file_url: str | None

    class Config:
        from_attributes = True


class ReviewIn(BaseModel):
    decision: AssignmentStatus  # "approved" or "rejected"
    accuracy_score: float | None = None
    notes: str | None = None


class ReviewOut(BaseModel):
    id: int
    submission_id: int
    decision: AssignmentStatus
    accuracy_score: float | None
    notes: str | None

    class Config:
        from_attributes = True


@router.post("/tasks/{task_id}/claim", response_model=AssignmentOut)
def claim(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return claim_task(db, task, current_user)
    except TaskEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assignments/{assignment_id}/submit", response_model=SubmissionOut)
def submit(
    assignment_id: int,
    submission_in: SubmitIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = db.query(TaskAssignment).filter(TaskAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    try:
        return submit_answer(
            db, assignment, current_user, submission_in.answer_text, submission_in.answer_file_url
        )
    except TaskEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/submissions/{submission_id}/review", response_model=ReviewOut)
def review(
    submission_id: int,
    review_in: ReviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can review submissions")

    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    try:
        return review_submission(
            db, submission, current_user, review_in.decision, review_in.accuracy_score, review_in.notes
        )
    except TaskEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))