
from starlette.responses import JSONResponse, RedirectResponse
import uvicorn
from starlette.routing import Route,Mount
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

from starlette.requests import Request
from app.modules.v1.main import app as v1_app
from app.modules.v2.main import app as v2_app
from app.modules.v2.helper import checker
from app.utils import logger

# Middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ),
    Middleware(GZipMiddleware, minimum_size=1000),
]

async def home(request: Request):
   """Home page"""
    return RedirectResponse("/v2")



# Mount v1 and v2 routes
routes = [
    Route("/", home, methods=["GET"]),
    # Route("/stats-page", stats_page, methods=["GET"]),
    Mount("/v1/",app=v1_app,name="Disposable Email Checker v1.0"),
    Mount("/v2/",app=v2_app,name="Disposable Email Checker v2.0"),
]

app = Starlette(debug=True, routes=routes, middleware=middleware)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("🚀 Starting Advanced Disposable Email Checker API v2.0.0")
    await checker.initialize()


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("🛑 Shutting down Advanced Disposable Email Checker API")
    await checker.cleanup()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
