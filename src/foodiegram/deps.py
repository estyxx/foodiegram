import functools
from typing import Annotated, cast

from fastapi import Depends
from openai import OpenAI
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request

from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.pantry_db import PantryRepository
from foodiegram.storage.plans_db import PlanRepository
from foodiegram.storage.recipes_db import RecipeRepository
from foodiegram.storage.targets_db import TargetRepository
from foodiegram.storage.user_state_db import UserStateRepository


class Deps(BaseModel):
    """Repositories wired to one engine, shared across a running app."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    recipes: RecipeRepository
    extractions: ExtractionRepository
    user_state: UserStateRepository
    plans: PlanRepository
    pantry: PantryRepository
    targets: TargetRepository


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
    )


def auth_from_settings(settings: Settings) -> AuthConfig:
    """Read Basic-auth credentials off the settings object."""
    return AuthConfig(
        username=settings.basic_auth_username,
        password=settings.basic_auth_password,
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
