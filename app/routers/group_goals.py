from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/group-goals", tags=["group-goals"])


def build_group_goal_out(db: Session, goal: models.GroupGoal) -> schemas.GroupGoalOut:
    percent = float(goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0.0

    members = db.query(models.GroupGoalMember).filter(
        models.GroupGoalMember.group_goal_id == goal.id
    ).all()

    members_out = []
    for member in members:
        user = db.query(models.User).filter(models.User.id == member.user_id).first()
        contributed = db.query(models.GroupGoalContribution).filter(
            models.GroupGoalContribution.group_goal_id == goal.id,
            models.GroupGoalContribution.user_id == member.user_id,
        ).all()
        total_contributed = sum((c.amount for c in contributed), Decimal("0"))
        members_out.append(schemas.GroupGoalMemberOut(
            user_id=user.id, email=user.email, contributed=total_contributed
        ))

    return schemas.GroupGoalOut(
        id=goal.id,
        name=goal.name,
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        invite_code=goal.invite_code,
        is_completed=goal.is_completed,
        progress_percent=round(min(percent, 100.0), 1),
        members=members_out,
    )


def ensure_membership(db: Session, group_goal_id: int, user_id: int) -> models.GroupGoalMember:
    membership = db.query(models.GroupGoalMember).filter(
        models.GroupGoalMember.group_goal_id == group_goal_id,
        models.GroupGoalMember.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Вы не состоите в этой групповой цели")
    return membership


@router.get("/", response_model=list[schemas.GroupGoalOut])
def get_my_group_goals(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    memberships = db.query(models.GroupGoalMember).filter(
        models.GroupGoalMember.user_id == current_user.id
    ).all()
    goal_ids = [m.group_goal_id for m in memberships]

    goals = db.query(models.GroupGoal).filter(models.GroupGoal.id.in_(goal_ids)).all()
    return [build_group_goal_out(db, g) for g in goals]


@router.post("/", response_model=schemas.GroupGoalOut)
def create_group_goal(payload: schemas.GroupGoalCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_goal = models.GroupGoal(
        name=payload.name,
        target_amount=payload.target_amount,
        current_amount=Decimal("0"),
        created_by=current_user.id,
    )
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)

    # создатель автоматически становится первым участником
    membership = models.GroupGoalMember(group_goal_id=new_goal.id, user_id=current_user.id)
    db.add(membership)
    db.commit()

    return build_group_goal_out(db, new_goal)


@router.post("/join", response_model=schemas.GroupGoalOut)
def join_group_goal(payload: schemas.GroupGoalJoin, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    goal = db.query(models.GroupGoal).filter(models.GroupGoal.invite_code == payload.invite_code).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Групповая цель с таким кодом не найдена")

    existing_membership = db.query(models.GroupGoalMember).filter(
        models.GroupGoalMember.group_goal_id == goal.id,
        models.GroupGoalMember.user_id == current_user.id,
    ).first()
    if existing_membership:
        raise HTTPException(status_code=400, detail="Вы уже состоите в этой групповой цели")

    membership = models.GroupGoalMember(group_goal_id=goal.id, user_id=current_user.id)
    db.add(membership)
    db.commit()

    return build_group_goal_out(db, goal)


@router.post("/{goal_id}/contribute", response_model=schemas.GroupGoalOut)
def contribute_to_group_goal(goal_id: int, payload: schemas.GroupGoalContributeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    ensure_membership(db, goal_id, current_user.id)

    goal = db.query(models.GroupGoal).filter(models.GroupGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Групповая цель не найдена")
    if goal.is_completed:
        raise HTTPException(status_code=400, detail="Цель уже достигнута")

    contribution = models.GroupGoalContribution(
        group_goal_id=goal.id, user_id=current_user.id, amount=payload.amount
    )
    db.add(contribution)

    goal.current_amount += payload.amount
    if goal.current_amount >= goal.target_amount:
        goal.is_completed = 1

    db.commit()
    db.refresh(goal)

    return build_group_goal_out(db, goal)


@router.get("/{goal_id}", response_model=schemas.GroupGoalOut)
def get_group_goal_detail(goal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    ensure_membership(db, goal_id, current_user.id)

    goal = db.query(models.GroupGoal).filter(models.GroupGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Групповая цель не найдена")

    return build_group_goal_out(db, goal)