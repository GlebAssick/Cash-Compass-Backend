from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from datetime import date, timedelta


router = APIRouter(prefix="/goals", tags=["goals"])

MILESTONES = [25, 50, 75, 100]

def check_and_create_milestone_notifications(db: Session, goal: models.Goal, old_percent: float, new_percent: float):
    for milestone in MILESTONES:
        if old_percent < milestone <= new_percent:
            if milestone == 100:
                message = f'Поздравляем! Цель "{goal.name}" достигнута! 🎉'
            else:
                message = f'Вы прошли {milestone}% пути к цели "{goal.name}"!'

            notification = models.Notification(
                user_id=goal.user_id,
                goal_id=goal.id,
                message=message,
                is_read=0,
            )
            db.add(notification)

def build_goal_out(goal: models.Goal) -> schemas.GoalOut:
    percent = float(goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0.0
    return schemas.GoalOut(
        id=goal.id,
        name=goal.name,
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        target_date=goal.target_date,
        is_completed=goal.is_completed,
        progress_percent=round(min(percent, 100.0), 1),
    )

@router.get("/", response_model=list[schemas.GoalOut])
def get_goals(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    goals = db.query(models.Goal).filter(models.Goal.user_id == current_user.id).all()
    return [build_goal_out(g) for g in goals]

@router.post("/", response_model=schemas.GoalOut)
def create_goal(payload: schemas.GoalCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_goal = models.Goal(
        user_id=current_user.id,
        name=payload.name,
        target_amount=payload.target_amount,
        current_amount=Decimal("0"),
        target_date=payload.target_date,
        is_completed=0,
    )
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)
    return build_goal_out(new_goal)

@router.post("/{goal_id}/contribute", response_model=schemas.GoalOut)
def contribute_to_goal(goal_id: int, payload: schemas.GoalContributionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id, models.Goal.user_id == current_user.id
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    if goal.is_completed:
        raise HTTPException(status_code=400, detail="Цель уже достигнута")

    old_percent = float(goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0.0

    contribution = models.GoalContribution(goal_id=goal.id, amount=payload.amount)
    db.add(contribution)

    goal.current_amount += payload.amount
    if goal.current_amount >= goal.target_amount:
        goal.is_completed = 1

    new_percent = float(goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0.0
    check_and_create_milestone_notifications(db, goal, old_percent, new_percent)

    db.commit()
    db.refresh(goal)
    return build_goal_out(goal)

@router.get("/{goal_id}/monthly-needed")
def calculate_monthly_needed(goal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Сколько нужно откладывать в месяц, чтобы успеть к target_date"""
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id, models.Goal.user_id == current_user.id
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    if not goal.target_date:
        raise HTTPException(status_code=400, detail="У цели не указан срок (target_date)")

    from datetime import date
    today = date.today()
    remaining_amount = goal.target_amount - goal.current_amount

    if remaining_amount <= 0:
        return {"monthly_needed": 0, "months_left": 0}

    months_left = max(1, (goal.target_date.year - today.year) * 12 + (goal.target_date.month - today.month))
    monthly_needed = remaining_amount / months_left

    return {
        "monthly_needed": round(float(monthly_needed), 2),
        "months_left": months_left,
        "remaining_amount": remaining_amount,
    }

@router.delete("/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id, models.Goal.user_id == current_user.id
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    db.delete(goal)
    db.commit()
    return {"detail": "Цель удалена"}

@router.get("/{goal_id}/forecast")
def get_goal_forecast(goal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Прогноз: раньше или позже срока будет достигнута цель, при текущем темпе накоплений"""
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id, models.Goal.user_id == current_user.id
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")

    contributions = db.query(models.GoalContribution).filter(
        models.GoalContribution.goal_id == goal.id
    ).order_by(models.GoalContribution.created_at).all()

    if len(contributions) < 2:
        return {"status": "not_enough_data", "message": "Нужно минимум 2 пополнения для прогноза темпа."}

    from datetime import date
    first_date = contributions[0].created_at.date()
    days_saving = (date.today() - first_date).days or 1

    daily_rate = float(goal.current_amount) / days_saving
    remaining_amount = float(goal.target_amount - goal.current_amount)

    if daily_rate <= 0 or remaining_amount <= 0:
        return {"status": "completed_or_no_progress"}

    days_needed = remaining_amount / daily_rate
    estimated_date = date.today() + timedelta(days=int(days_needed))

    result = {
        "status": "forecast_ready",
        "estimated_completion_date": str(estimated_date),
        "daily_rate": round(daily_rate, 2),
    }

    if goal.target_date:
        if estimated_date < goal.target_date:
            days_earlier = (goal.target_date - estimated_date).days
            result["message"] = f"При текущем темпе вы достигнете цели на {days_earlier} дн. раньше срока!"
        elif estimated_date > goal.target_date:
            days_later = (estimated_date - goal.target_date).days
            result["message"] = f"При текущем темпе вы опоздаете к сроку на {days_later} дн."
        else:
            result["message"] = "Вы идёте точно по графику."

    return result