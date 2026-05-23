from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.containers.auth_container import router as auth_router
from app.containers.course_container import router as course_router
from app.containers.dashboard_container import router as dashboard_router
from app.containers.draft_container import router as draft_router
from app.containers.review_container import router as review_router
from app.containers.user_container import router as user_router
from app.database import Base, engine
from app.services.seed_service import seed_demo_data


load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RPD-AI Prototype")

app.add_middleware(
    SessionMiddleware,
    secret_key="rpd-ai-demo-secret-key-change-in-production",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(dashboard_router)
app.include_router(course_router)
app.include_router(draft_router)
app.include_router(review_router)

seed_demo_data()