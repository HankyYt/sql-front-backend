from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from src.models.achievement import Achievement, UsersAchievements
from src.models.progress import UserProgress
from src.models.user import User
from src.schemas.user import UserPublic
from src.utils.auth import get_current_user

router = APIRouter(prefix="/api/profile", tags=["Профиль"])


@router.get("/me", summary="Логин и баллы", response_model=UserPublic)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/tasks_progress", summary="Прогресс по задачам")
async def get_my_progress(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import func
    from src.models.task import Task, TaskSolved
    
    result = await db.execute(
        select(Task.mission_id, func.count(TaskSolved.task_global_id))
        .join(TaskSolved, Task.task_global_id == TaskSolved.task_global_id)
        .where(TaskSolved.user_id == current_user.user_id)
        .group_by(Task.mission_id)
    )
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for mission_id, count in result.all():
        counts[mission_id] = count
        
    return {
        "easy_solved": counts[0],
        "medium_solved": counts[1],
        "hard_solved": counts[2],
        "mission3_solved": counts[3],
        "mission4_solved": counts[4],
        "mission5_solved": counts[5],
    }


@router.get("/achievements", summary="Имеющиеся ачивки")
async def get_my_achievements(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(
            Achievement.category_name,
            Achievement.icon,
            Achievement.name,
            Achievement.description,
            Achievement.historical_info,
        )
        .join(UsersAchievements)
        .where(UsersAchievements.user_id == current_user.user_id)
    )
    achievements = result.all()
    grouped_achievements: Dict[str, List] = {}
    for ach in achievements:
        category = ach.category_name
        achievement_data = {
            "icon": ach.icon,
            "name": ach.name,
            "description": ach.description,
            "historical_info": ach.historical_info,
        }

        if category not in grouped_achievements:
            grouped_achievements[category] = []

        grouped_achievements[category].append(achievement_data)

    return grouped_achievements
