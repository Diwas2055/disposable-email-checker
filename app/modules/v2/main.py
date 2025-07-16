# app/main.py

import asyncio
import json
import time

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from app.modules.v2.routes import home,stats_page, check_email_endpoint, bulk_check_endpoint, stats_endpoint, health_endpoint, domains_endpoint, update_domains_endpoint
from app.modules.v2.helper import checker
from app.utils import logger

# Routes
routes = [
    # Home page
    Route("/", home, methods=["GET"]),
    Route("/stats-page", stats_page, methods=["GET"]),

    # API endpoints
    Route("/api/check", check_email_endpoint, methods=["POST"]),
    Route("/api/bulk-check", bulk_check_endpoint, methods=["POST"]),
    Route("/api/stats", stats_endpoint, methods=["GET"]),
    Route("/api/health", health_endpoint, methods=["GET"]),
    Route("/api/domains", domains_endpoint, methods=["GET"]),
    Route("/api/update-domains", update_domains_endpoint, methods=["POST"]),
]

# Enhanced middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    ),
    Middleware(GZipMiddleware, minimum_size=1000),
]

# Create Starlette app
app = Starlette(debug=False, routes=routes, middleware=middleware)
app.mount("/static", StaticFiles(directory="app/modules/v2/static"), name="static")

# Startup event
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
    print("🚀 Starting Advanced Disposable Email Checker API v2.0.0...")
    print("📧 API v2 Endpoints:")
    print("  POST /v2/api/check - Check single email")
    print("  POST /v2/api/bulk-check - Check multiple emails")
    print("  GET /v2/api/stats - Get detailed statistics")
    print("  GET /v2/api/health - Health check with diagnostics")
    print("  GET /v2/api/domains - Get domain lists with filtering")
    print("  POST /v2/api/update-domains - Force domain list update")
    print("\n📱 Web Interface:")
    print("  GET / - API documentation")
    print("  GET /demo - Interactive demo")
    print("  GET /stats-page - Statistics dashboard")
    print("\n🔄 Legacy Endpoints (v1) still supported for backward compatibility")
    print("\n💡 Example usage:")
    print('  curl -X POST http://localhost:8000/v2/api/check \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"email":"test@tempmail.org"}\'')
    print("\n⚡ Features:")
    print("  • Rate limiting (100 requests/hour per IP)")
    print("  • Enhanced error handling")
    print("  • Detailed statistics and analytics")
    print("  • Bulk processing with concurrency control")
    print("  • Domain list auto-updates")
    print("  • Health monitoring")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9999,
        reload=True,
        log_level="info",
        access_log=True
    )
