from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import APP_DIR, Settings, settings
from app.routes import auth, course, dashboard, draft, review, user
from app.database import Base, engine
from app.services.seed_service import seed_demo_data

def create_app(config: Settings = settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Prototype schema setup; replace with migrations before deployment.
        Base.metadata.create_all(bind=engine)
        if config.seed_demo:
            seed_demo_data()
        yield

    application = FastAPI(title='RPD-AI Prototype', lifespan=lifespan)
    application.add_middleware(
        SessionMiddleware,
        secret_key=config.session_secret,
        https_only=config.secure_cookies,
    )
    application.mount('/static', StaticFiles(directory=str(APP_DIR / 'static')), name='static')
    for module in (auth, user, dashboard, course, draft, review):
        application.include_router(module.router)
    return application

app = create_app()
