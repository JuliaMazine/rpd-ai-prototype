from fastapi.templating import Jinja2Templates
from app.config import APP_DIR
from app.constants import ROLE_LABELS, STATUS_LABELS
from app.localization import translate
from app.services.course_service import ASSESSMENT_LABELS

def russian_context(request):
    return {
        "t": translate,
        "role_labels": ROLE_LABELS,
        "status_labels": STATUS_LABELS,
        "assessment_labels": ASSESSMENT_LABELS,
    }

templates = Jinja2Templates(directory=str(APP_DIR / "templates"), context_processors=[russian_context])
