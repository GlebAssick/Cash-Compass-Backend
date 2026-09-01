from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=list[schemas.CategoryOut])
def get_categories(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Category).filter(
        or_(models.Category.is_default == 1, models.Category.user_id == current_user.id)
    ).all()

@router.post("/", response_model=schemas.CategoryOut)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_category = models.Category(name=category.name, user_id=current_user.id, is_default=0)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category