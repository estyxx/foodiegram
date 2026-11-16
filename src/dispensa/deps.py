import functools
from typing import Annotated, cast

from fastapi import Depends
from openai import OpenAI
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request

from dispensa.api_session import MIN_SECRET_LENGTH, LoginConfig
from dispensa.domain.errors import ConfigurationError
from dispensa.settings import Settings
from dispensa.storage.batches_db import BatchRepository
from dispensa.storage.db import create_db_engine, init_db
from dispensa.storage.exercise_log_db import ExerciseLogRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.pending_db import PendingLinkRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository


class Deps(BaseModel):
    """Repositories wired to one engine, shared across a running app."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    recipes: RecipeRepository
    extractions: ExtractionRepository
    user_state: UserStateRepository
    plans: PlanRepository
    pantry: PantryRepository
    targets: TargetRepository
    exercise_log: ExerciseLogRepository
    pending: PendingLinkRepository
    batches: BatchRepository


class AuthConfig(BaseModel):
    """HTTP Basic credentials; an empty username disables auth (dev)."""

    model_config = ConfigDict(frozen=True)

    username: str = ""
    password: str = ""


def build_deps(database_url: str) -> Deps:
    """Create an engine, initialise the schema, and wire every repository."""
    engine = create_db_engine(database_url)
    init_db(engine)
    return Deps(
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        user_state=UserStateRepository(engine),
        plans=PlanRepository(engine),
        pantry=PantryRepository(engine),
        targets=TargetRepository(engine),
        exercise_log=ExerciseLogRepository(engine),
        pending=PendingLinkRepository(engine),
        batches=BatchRepository(engine),
    )


def auth_from_settings(settings: Settings) -> AuthConfig:
    """Read Basic-auth credentials off the settings object."""
    return AuthConfig(
        username=settings.basic_auth_username,
        password=settings.basic_auth_password,
    )


def login_from_settings(settings: Settings) -> LoginConfig | None:
    """Return the web-login config, or None when the login is not configured.

    Raises ConfigurationError for a half-configured login, so a typo in one
    variable can never silently fall back to a weaker setup.
    """
    required = {
        "WORKOS_CLIENT_ID": settings.workos_client_id,
        "WORKOS_API_KEY": settings.workos_api_key,
        "WORKOS_REDIRECT_URI": settings.workos_redirect_uri,
        "SESSION_SECRET": settings.session_secret,
    }
    if not any(required.values()):
        return None
    missing = [name for name, value in required.items() if not value]
    if not settings.mcp_oauth_allowed_subjects.split():
        missing.append("MCP_OAUTH_ALLOWED_SUBJECTS")
    if missing:
        msg = f"{', '.join(missing)} required to enable the web login"
        raise ConfigurationError(msg)
    if len(settings.session_secret) < MIN_SECRET_LENGTH:
        msg = f"SESSION_SECRET must be at least {MIN_SECRET_LENGTH} characters"
        raise ConfigurationError(msg)
    return LoginConfig(
        client_id=settings.workos_client_id,
        api_key=settings.workos_api_key,
        redirect_uri=settings.workos_redirect_uri,
        session_secret=settings.session_secret,
        allowed_subjects=frozenset(settings.mcp_oauth_allowed_subjects.split()),
    )


def get_deps(request: Request) -> Deps:
    """Return the Deps bound to the running app (set in create_app)."""
    return cast("Deps", request.app.state.deps)


DepsDep = Annotated[Deps, Depends(get_deps)]


@functools.cache
def get_openai_client() -> OpenAI:
    """Create one OpenAI client per process, for endpoints that embed a query."""
    return OpenAI(api_key=Settings().require_openai_api_key())


OpenAIClientDep = Annotated[OpenAI, Depends(get_openai_client)]


@functools.cache
def get_settings() -> Settings:
    """Return the app settings, for endpoints that reach OpenAI (batch extraction)."""
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
