from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aifun.api.routes import router
from aifun.db.session import init_db
from aifun.processing import reconcile_orphaned_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Phase 1's in-process thread pool has no durable queue — a row still
    # "processing" from before this restart is orphaned, not in-flight.
    # See aifun.processing.reconcile_orphaned_jobs.
    reconcile_orphaned_jobs()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
