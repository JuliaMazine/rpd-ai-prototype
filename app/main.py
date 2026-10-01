from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.localization import translate
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
    @application.exception_handler(HTTPException)
    async def russian_http_error(request, error):
        detail = translate(error.detail) if isinstance(error.detail, str) else error.detail
        return JSONResponse({"detail": detail}, status_code=error.status_code, headers=error.headers)

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
