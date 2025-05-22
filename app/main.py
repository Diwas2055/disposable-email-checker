import asyncio
import json
import time

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.email_checker import DisposableEmailChecker

templates = Jinja2Templates(directory="app/templates")


# Initialize the checker
checker = DisposableEmailChecker()


async def check_email_endpoint(request):
    """Single email check endpoint"""
    try:
        body = await request.json()
        email = body.get("email", "").strip().lower()

        if not email:
            return JSONResponse({"error": "Email address is required"}, status_code=400)

        result = await checker.check_email(email)
        return JSONResponse(result)

    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON in request body"}, status_code=400)
    except Exception as e:
        return JSONResponse(
            {"error": f"Internal server error: {str(e)}"}, status_code=500
        )


async def bulk_check_endpoint(request):
    """Bulk email check endpoint"""
    try:
        body = await request.json()
        emails = body.get("emails", [])

        if not isinstance(emails, list) or not emails:
            return JSONResponse(
                {"error": "emails field must be a non-empty array"}, status_code=400
            )

        if len(emails) > 100:
            return JSONResponse(
                {"error": "Maximum 100 emails per request"}, status_code=400
            )

        # Process emails concurrently
        tasks = [checker.check_email(email.strip().lower()) for email in emails]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {"email": emails[i], "error": str(result), "is_disposable": None}
                )
            else:
                processed_results.append(result)

        return JSONResponse(
            {
                "results": processed_results,
                "total_checked": len(emails),
                "disposable_count": sum(
                    1 for r in processed_results if r.get("is_disposable")
                ),
                "timestamp": time.time(),
            }
        )

    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON in request body"}, status_code=400)
    except Exception as e:
        return JSONResponse(
            {"error": f"Internal server error: {str(e)}"}, status_code=500
        )


async def stats_endpoint(request):
    """Statistics endpoint"""
    stats = checker.get_stats()
    return JSONResponse(stats)


async def health_endpoint(request):
    """Health check endpoint"""
    return JSONResponse(
        {"status": "healthy", "timestamp": time.time(), "version": "1.0.0"}
    )


async def domains_endpoint(request):
    """Get disposable domains list"""
    try:
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))

        domains_list = sorted(list(checker.disposable_domains))
        total = len(domains_list)

        paginated_domains = domains_list[offset : offset + limit]

        return JSONResponse(
            {
                "domains": paginated_domains,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_next": offset + limit < total,
            }
        )

    except ValueError:
        return JSONResponse(
            {"error": "limit and offset must be integers"}, status_code=400
        )


# HTML endpoints
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


async def stats_page(request: Request):
    stats = checker.get_stats()
    return templates.TemplateResponse(
        "stats.html", {"request": request, "stats": stats}
    )


# Routes
routes = [
    Route("/check", check_email_endpoint, methods=["POST"]),
    Route("/bulk-check", bulk_check_endpoint, methods=["POST"]),
    Route("/stats", stats_endpoint, methods=["GET"]),
    Route("/health", health_endpoint, methods=["GET"]),
    # Route("/domains", domains_endpoint, methods=["GET"]),
    Route("/", home, methods=["GET"]),
    Route("/stats-page", stats_page, methods=["GET"]),
]

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

# Create Starlette app
app = Starlette(debug=True, routes=routes, middleware=middleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

if __name__ == "__main__":
    print("🚀 Starting Advanced Disposable Email Checker API...")
    print("📧 Endpoints available:")
    print("  POST /check - Check single email")
    print("  POST /bulk-check - Check multiple emails")
    print("  GET /stats - Get checker statistics")
    print("  GET /health - Health check")
    print("  GET / - Home page")
    print("  GET /stats-page - Stats page")
    print("\n💡 Example usage:")
    print(
        '  curl -X POST http://localhost:8000/check -H "Content-Type: application/json" -d \'{"email":"test@tempmail.org"}\''
    )

    uvicorn.run("main:app", host="0.0.0.0", port=9999, reload=True, log_level="info")
