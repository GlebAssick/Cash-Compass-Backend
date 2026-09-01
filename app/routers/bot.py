import os
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db, SessionLocal
from ..auth import get_current_user
from ..routers.budget import build_budget_context
from ..bot_phrases import find_matching_template, render_template
from ..claude_bot import generate_dynamic_comment

router = APIRouter(prefix="/bot", tags=["bot"])


def get_comment_for_context(context: dict) -> tuple[str, str]:
    """Возвращает (текст комментария, источник) для заданного контекста бюджета"""
    template = find_matching_template(context)
    if template:
        return render_template(template, context), "template"
    return generate_dynamic_comment(context), "claude_api"


@router.get("/comment")
def get_budget_comment(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    context = build_budget_context(db, current_user)
    if context is None:
        return {"comment": "Сначала задайте месячный бюджет, чтобы я мог давать советы.", "source": "static"}

    comment, source = get_comment_for_context(context)
    return {"comment": comment, "source": source}


@router.post("/broadcast-comments")
def broadcast_comments_to_all_users(x_admin_key: str = Header(...)):
    """
    Проходит по всем пользователям с заданным бюджетом и создаёт для каждого
    уведомление с комментарием бота. Защищено секретным ключом в заголовке,
    так как это не пользовательское, а системное/админское действие.
    """
    expected_key = os.getenv("ADMIN_TRIGGER_KEY")
    if not expected_key or x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Неверный админ-ключ")

    db = SessionLocal()
    try:
        users = db.query(models.User).all()
        created_count = 0

        for user in users:
            context = build_budget_context(db, user)
            if context is None:
                continue  # у пользователя ещё не задан бюджет — пропускаем

            comment, source = get_comment_for_context(context)

            notification = models.Notification(
                user_id=user.id,
                goal_id=None,
                message=comment,
                is_read=0,
            )
            db.add(notification)
            created_count += 1

        db.commit()
        return {"notified_users": created_count, "total_users": len(users)}
    finally:
        db.close()