from starlette.requests import Request
import time

from app.modules.v2.email_checker import DisposableEmailChecker
from app.modules.v2.schemas import EmailRequest

# Initialize the checker
checker = DisposableEmailChecker()

# Rate limiting storage (in production, use Redis)
rate_limit_storage = {}
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600  # 1 hour


def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "localhost"


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    current_time = time.time()

    # Clean old entries
    rate_limit_storage[client_ip] = [
        timestamp for timestamp in rate_limit_storage.get(client_ip, [])
        if current_time - timestamp < RATE_LIMIT_WINDOW
    ]

    # Check if limit exceeded
    if len(rate_limit_storage.get(client_ip, [])) >= RATE_LIMIT_REQUESTS:
        return False

    # Add current request
    rate_limit_storage.setdefault(client_ip, []).append(current_time)
    return True
