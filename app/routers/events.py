from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, timedelta
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/events", tags=["events"])

@router.get("/all", response_model=list[schemas.EventOut])
def get_all_events_for_country(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Все события, привязанные к стране текущего пользователя"""
    return db.query(models.Event).filter(models.Event.country == current_user.country).all()

@router.get("/upcoming", response_model=list[schemas.EventOut])
def get_upcoming_events(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """События в ближайшие 14 дней (год игнорируется, сравниваем только день и месяц)"""
    today = date.today()
    upcoming_window = [
        (today + timedelta(days=i)).strftime("%m-%d")
        for i in range(15)
    ]

    all_events = db.query(models.Event).filter(models.Event.country == current_user.country).all()

    upcoming = [
        event for event in all_events
        if event.event_date.strftime("%m-%d") in upcoming_window
    ]
    return upcoming