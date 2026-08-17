from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import PromptIn, PromptOut

router = APIRouter(prefix="/projects/{project_id}/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptOut])
def list_prompts(project_id: str, db: Session = Depends(get_db)):
    return [PromptOut(id=item.id, project_id=item.project_id, name=item.name, content=item.content) for item in db.scalars(select(models.PromptTemplate).where(models.PromptTemplate.project_id == project_id))]


@router.post("", response_model=PromptOut)
def save_prompt(project_id: str, payload: PromptIn, db: Session = Depends(get_db)):
    prompt = models.PromptTemplate(project_id=project_id, name=payload.name, content=payload.content)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return PromptOut(id=prompt.id, project_id=prompt.project_id, name=prompt.name, content=prompt.content)


@router.put("/{prompt_id}", response_model=PromptOut)
def update_prompt(project_id: str, prompt_id: int, payload: PromptIn, db: Session = Depends(get_db)):
    prompt = db.get(models.PromptTemplate, prompt_id)
    if not prompt or prompt.project_id != project_id:
        raise HTTPException(404, "Prompt 不存在")
    prompt.name = payload.name
    prompt.content = payload.content
    db.commit()
    return PromptOut(id=prompt.id, project_id=prompt.project_id, name=prompt.name, content=prompt.content)
