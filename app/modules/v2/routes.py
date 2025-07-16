import asyncio
import time
import json

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from app.utils import logger
from app.modules.v2.schemas import EmailRequest
from app.modules.v2.helper import get_client_ip,check_rate_limit,checker,RATE_LIMIT_REQUESTS,RATE_LIMIT_WINDOW

templates = Jinja2Templates(directory="app/modules/v2/templates")

# HTML endpoints
async def home(request: Request):
    """Home page with API documentation"""
    return templates.TemplateResponse("index.html", {"request": request})


async def stats_page(request: Request):
    """Statistics dashboard page"""
    try:
        stats = checker.get_stats()
        return templates.TemplateResponse(
            "stats.html", {"request": request, "stats": stats}
        )
    except Exception as e:
        logger.error(f"Error in stats_page: {str(e)}")
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": str(e)}
        )


async def demo_page(request: Request):
    """Demo page for testing the API"""
    return templates.TemplateResponse("demo.html", {"request": request})


async def check_email_endpoint(request: Request):
    """Single email check endpoint with rate limiting"""
    client_ip = get_client_ip(request)

    if not check_rate_limit(client_ip):
        return JSONResponse(
            {"error": "Rate limit exceeded. Try again later."},
            status_code=429
        )

    try:
        body = await request.json()
        email = body.get("email", "").strip()

        try:
            validated_email = EmailRequest(email=email)
            email = validated_email.email  # normalized email
        except ValueError as ve:
            return JSONResponse({"error": str(ve)}, status_code=400)

        # Validate email length
        if len(email) > 254:
            return JSONResponse(
                {"error": "Email address too long"},
                status_code=400
            )

        result = await checker.check_email(email)

        # Convert to dict first
        result_dict = result.to_dict()

        # Add additional metadata
        result_dict.update({
            "api_version": "2.0.0",
            "processing_time_ms": result_dict.get("processing_time_ms", 0),
            "client_ip": client_ip[:8] + "..." if len(client_ip) > 8 else client_ip
        })
        return JSONResponse(result_dict)

    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Invalid JSON in request body"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Error in check_email_endpoint: {str(e)}")
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500
        )


async def bulk_check_endpoint(request: Request):
    """Bulk email check endpoint with enhanced processing"""
    client_ip = get_client_ip(request)

    if not check_rate_limit(client_ip):
        return JSONResponse(
            {"error": "Rate limit exceeded. Try again later."},
            status_code=429
        )

    try:
        body = await request.json()
        emails = body.get("emails", [])
        options = body.get("options", {})

        if not isinstance(emails, list) or not emails:
            return JSONResponse(
                {"error": "emails field must be a non-empty array"},
                status_code=400
            )

        # Configurable batch size
        max_batch_size = options.get("max_batch_size", 100)
        if len(emails) > max_batch_size:
            return JSONResponse(
                {"error": f"Maximum {max_batch_size} emails per request"},
                status_code=400
            )

        start_time = time.time()
        semaphore = asyncio.Semaphore(10)  # Limit concurrent processing

        async def process_email(email):
            async with semaphore:
                try:
                    if not email or not isinstance(email, str):
                        raise ValueError("Empty or invalid email")

                    validated = EmailRequest(email=email.strip())
                    clean_email = validated.email
                    result = await checker.check_email(clean_email)
                    return result.to_dict()

                except ValueError as ve:
                    # Email validation issue
                    return {
                        "email": email,
                        "error": f"Validation error: {str(ve)}",
                        "is_disposable": None,
                        "risk_score": None,
                        "risk_level": None,
                        "checks": {}
                    }

                except Exception as e:
                    # Any other internal/external error
                    return {
                        "email": email,
                        "error": f"Processing error: {str(e)}",
                        "is_disposable": None,
                        "risk_score": None,
                        "risk_level": None,
                        "checks": {}
                    }

        results = await asyncio.gather(*[process_email(email) for email in emails])
        processing_time = (time.time() - start_time) * 1000

        # Statistics
        disposable_count = sum(1 for r in results if r.get("is_disposable") is True)
        valid_count = sum(1 for r in results if r.get("is_disposable") is False)
        invalid_count = sum(1 for r in results if r.get("error", "").startswith("Validation error"))
        error_count = sum(1 for r in results if r.get("error"))

        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        for result in results:
            risk_score = result.get("risk_score")
            if isinstance(risk_score, (int, float)):
                if risk_score < 30:
                    risk_distribution["low"] += 1
                elif risk_score < 70:
                    risk_distribution["medium"] += 1
                else:
                    risk_distribution["high"] += 1

        return JSONResponse({
            "results": results,
            "summary": {
                "total_checked": len(emails),
                "disposable_count": disposable_count,
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "error_count": error_count,
                "risk_distribution": risk_distribution,
                "processing_time_ms": round(processing_time, 2),
                "average_time_per_email_ms": round(processing_time / len(emails), 2)
            },
            "metadata": {
                "api_version": "2.0.0",
                "timestamp": time.time(),
                "client_ip": client_ip[:8] + "..." if len(client_ip) > 8 else client_ip
            }
        })

    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Invalid JSON in request body"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Error in bulk_check_endpoint: {str(e)}")
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500
        )


async def stats_endpoint(request: Request):
    """Enhanced statistics endpoint"""
    try:
        stats = checker.get_stats()
        # Add system information
        stats.update({
            "system_info": {
                "api_version": "2.0.0",
                "uptime_seconds": time.time() - checker.start_time,
                "rate_limit_info": {
                    "requests_per_hour": RATE_LIMIT_REQUESTS,
                    "window_seconds": RATE_LIMIT_WINDOW
                }
            },
            "performance": {
                "avg_response_time_ms": stats.get("avg_response_time_ms", 0),
                "cache_hit_rate": stats.get("cache_hit_rate", 0),
                "total_requests": stats.get("total_requests", 0)
            }
        })

        return JSONResponse(stats)
    except Exception as e:
        logger.error(f"Error in stats_endpoint: {str(e)}")
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500
        )


async def health_endpoint(request: Request):
    """Enhanced health check endpoint"""
    try:
        health_status = await checker.health_check()

        return JSONResponse({
            "status": "healthy" if health_status["healthy"] else "unhealthy",
            "timestamp": time.time(),
            "version": "2.0.0",
            "uptime_seconds": time.time() - checker.start_time,
            "checks": health_status["checks"]
        })
    except Exception as e:
        logger.error(f"Error in health_endpoint: {str(e)}")
        return JSONResponse(
            {"status": "unhealthy", "error": str(e)},
            status_code=500
        )


async def domains_endpoint(request: Request):
    """Enhanced domains endpoint with filtering"""
    try:
        limit = min(int(request.query_params.get("limit", 100)), 1000)
        offset = int(request.query_params.get("offset", 0))
        search = request.query_params.get("search", "").lower()
        domain_type = request.query_params.get("type", "disposable")  # disposable or whitelist

        if domain_type == "whitelist":
            domains_set = checker.whitelist_domains
        else:
            domains_set = checker.disposable_domains

        # Filter domains if search query provided
        if search:
            filtered_domains = [d for d in domains_set if search in d]
        else:
            filtered_domains = list(domains_set)

        domains_list = sorted(filtered_domains)
        total = len(domains_list)
        paginated_domains = domains_list[offset:offset + limit]

        return JSONResponse({
            "domains": paginated_domains,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_next": offset + limit < total,
                "has_previous": offset > 0
            },
            "filters": {
                "type": domain_type,
                "search": search
            },
            "metadata": {
                "api_version": "2.0.0",
                "timestamp": time.time()
            }
        })

    except ValueError:
        return JSONResponse(
            {"error": "limit and offset must be integers"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Error in domains_endpoint: {str(e)}")
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500
        )


async def update_domains_endpoint(request: Request):
    """Endpoint to manually trigger domain list update"""
    try:
        success = await checker.force_update_domains()

        if success:
            return JSONResponse({
                "message": "Domain lists updated successfully",
                "timestamp": time.time(),
                "stats": checker.get_stats()
            })
        else:
            return JSONResponse(
                {"error": "Failed to update domain lists"},
                status_code=500
            )
    except Exception as e:
        logger.error(f"Error in update_domains_endpoint: {str(e)}")
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500
        )
