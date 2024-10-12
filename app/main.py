from app.routes.auth import github_auth, google_auth
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import secrets

from app.config import FRONTEND_URL, FIREBASE_DATABASE_URL, get_sdk_secret
from app.routes import github_utils, repository_utils
from app import orchestrator
from app.routes import nodes_utils as nodes

import logging
import firebase_admin
import uvicorn

load_dotenv()

app = FastAPI()

logging.basicConfig(
    filename="app.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(32),
    max_age=3600,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Adding the routers to main
app.include_router(github_auth.router)
app.include_router(github_utils.router)
app.include_router(google_auth.router)
app.include_router(repository_utils.router)
app.include_router(orchestrator.router)
app.include_router(nodes.router)

# Initialize firebase admin and add realtime DB
logger.info("Initializing Firebase Admin SDK")
cred = credentials.Certificate(get_sdk_secret())
firebase_admin.initialize_app(cred, {
    'databaseURL': FIREBASE_DATABASE_URL
})
logger.info("Firebase Admin SDK initialized successfully")

@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Hello from FastAPI!"}

if __name__ == "__main__":
    logger.info("Starting the FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000)