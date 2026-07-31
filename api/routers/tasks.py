from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.base import get_db
from db.models import Task, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


# --- Pydantic schemas: these define what JSON goes in and out of the API.
# They're deliberately separate from the SQLAlchemy models in db/models.py -
# the API's public shape and the database's internal shape are allowed to
# differ, and keeping them separate means changing one doesn't force a
# change in the other.

class TaskCreate(BaseModel):
    title: str
    instructions: str
    task_type: str
    payload: dict = {}
    reward_amount: Decimal
    max_assignments: int = 1


class TaskOut(BaseModel):
    id: int
    title: str
    instructions: str
    task_type: str
    payload: dict
    reward_amount: Decimal
    max_assignments: int
    status: TaskStatus

    class Config:
        from_attributes = True  # lets Pydantic read straight from a SQLAlchemy object


@router.post("", response_model=TaskOut)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    task = Task(
        title=task_in.title,
        instructions=task_in.instructions,
        task_type=task_in.task_type,
        payload=task_in.payload,
        reward_amount=task_in.reward_amount,
        max_assignments=task_in.max_assignments,
        status=TaskStatus.draft,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(Task).all()


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.patch("/{task_id}/activate", response_model=TaskOut)
def activate_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.active
    db.commit()
    db.refresh(task)
    return task