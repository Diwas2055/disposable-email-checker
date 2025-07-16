# app/email_checker.py

import asyncio
import re
import socket
import time
from typing import Dict, Optional, Set, List
from dataclasses import dataclass
from enum import Enum

import httpx
try:
    from utils import load_domains, logger, write_domains
except ImportError:
    from app.utils import load_domains, logger, write_domains

DISPOSABLE_DOMAINS_FILE = "app/disposable_domains.json"
WHITELIST_DOMAINS_FILE = "app/whitelist_domains.json"
DISPOSABLE_DOMAINS_URLS = [
    "https://raw.githubusercontent.com/martenson/disposable-email-domains/master/disposable_email_blocklist.conf",
    "https://raw.githubusercontent.com/disposable/disposable-email-domains/master/domains.txt",
    "https://raw.githubusercontent.com/wesbos/burner-email-providers/master/emails.txt",
    "https://raw.githubusercontent.com/ivolo/disposable-email-domains/master/index.json",
]
class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EmailCheckResult:
    email: str
    is_disposable: bool
    is_valid_format: bool
    risk_score: int
    risk_level: RiskLevel
    checks: Dict
    timestamp: float
    domain: Optional[str]

    def to_dict(self) -> Dict:
        return {
            "email": self.email,
            "is_disposable": self.is_disposable,
            "is_valid_format": self.is_valid_format,
            "domain": self.domain,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else self.risk_level,
            "checks": self.checks,
            "timestamp": self.timestamp,
        }


class DisposableEmailChecker:
    def __init__(self, cache_ttl: int = 3600, update_interval: int = 86400, max_cache_size: int = 10000):
        self.disposable_domains: Set[str] = set()
        self.whitelist_domains: Set[str] = set()
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = cache_ttl
        self.last_update = 0
        self.update_interval = update_interval
        self.max_cache_size = max_cache_size

        # Email validation pattern (more comprehensive)
        self.email_pattern = re.compile(
            r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
        )

        # Suspicious keywords for better detection
        self.suspicious_keywords = {
            "temp", "temporary", "disposable", "throw", "fake", "test", "spam",
            "trash", "dummy", "delete", "remove", "noemail", "nomail", "tempmail",
            "guerrillamail", "mailinator", "10minute", "minute", "hour", "day"
        }

        # High-risk TLDs
        self.suspicious_tlds = {
            ".tk", ".ml", ".ga", ".cf", ".tk", ".pw", ".cc", ".ws", ".info"
        }

        # Initialize domains synchronously (without external fetch)
        self._initialize_domains()

    def _initialize_domains(self):
        """Initialize domain lists from local files only"""
        logger.info("Initializing domain lists from local files...")

        try:
            self.disposable_domains.update(load_domains(DISPOSABLE_DOMAINS_FILE))
            self.whitelist_domains.update(load_domains(WHITELIST_DOMAINS_FILE))

            logger.info(f"Loaded {len(self.disposable_domains)} disposable domains")
            logger.info(f"Loaded {len(self.whitelist_domains)} whitelist domains")

            # Note: External fetch will be handled by initialize() method
            if not self.disposable_domains:
                logger.warning("Disposable domain list is empty. Will fetch from external sources during initialization.")

        except Exception as e:
            logger.error(f"Error initializing domains: {e}")

    def _is_cache_valid(self, email: str) -> bool:
        """Check if cached result is still valid"""
        return (
            email in self.cache and
            (time.time() - self.cache[email]["timestamp"]) < self.cache_ttl
        )

    def _extract_domain(self, email: str) -> Optional[str]:
        """Extract domain from email with better validation"""
        if "@" not in email:
            return None

        parts = email.split("@")
        if len(parts) != 2:
            return None

        domain = parts[1].lower().strip()

        # Additional domain validation
        if not domain or domain.startswith(".") or domain.endswith("."):
            return None

        return domain

    def _is_valid_email_format(self, email: str) -> bool:
        """Validate email format using comprehensive regex"""
        if not email or len(email) > 254:  # RFC 5321 limit
            return False

        return bool(self.email_pattern.match(email))

    def _check_suspicious_patterns(self, email: str) -> Dict[str, bool]:
        """Enhanced suspicious pattern detection"""
        username = email.split("@")[0]
        domain = self._extract_domain(email)

        patterns = {
            "has_numbers_only_username": re.match(r"^[0-9]+$", username) is not None,
            "has_random_username": len(re.findall(r"[a-zA-Z0-9]{15,}", username)) > 0,
            "has_temp_keywords": any(kw in email.lower() for kw in self.suspicious_keywords),
            "has_suspicious_tld": any(email.lower().endswith(tld) for tld in self.suspicious_tlds),
            "has_multiple_dots": email.count(".") > 3,
            "has_plus_addressing": "+" in username,
            "has_consecutive_dots": ".." in email,
            "has_short_domain": domain and len(domain) < 4,
            "has_long_username": len(username) > 50,
            "has_special_chars_excess": len(re.findall(r"[._%+-]", username)) > 3,
        }

        return patterns

    def _calculate_risk_level(self, risk_score: int) -> RiskLevel:
        """Calculate risk level based on score"""
        if risk_score >= 90:
            return RiskLevel.CRITICAL
        elif risk_score >= 70:
            return RiskLevel.HIGH
        elif risk_score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    async def _fetch_from_url(self, client: httpx.AsyncClient, url: str, retries: int = 3, delay: int = 2) -> Set[str]:
        """Fetch domains from URL with improved error handling"""
        for attempt in range(1, retries + 1):
            try:
                response = await client.get(url, timeout=15)
                if response.status_code == 200:
                    content = response.text
                    domains = {
                        line.strip().lower()
                        for line in content.splitlines()
                        if line.strip() and not line.startswith("#") and "." in line
                    }
                    logger.info(f"Successfully fetched {len(domains)} domains from {url}")
                    return domains
                else:
                    logger.warning(f"Non-200 response from {url}: {response.status_code}")

            except httpx.TimeoutException:
                logger.warning(f"[Attempt {attempt}] Timeout fetching {url}")
            except httpx.HTTPError as e:
                logger.warning(f"[Attempt {attempt}] HTTP error fetching {url}: {e}")
            except Exception as e:
                logger.error(f"[Attempt {attempt}] Unexpected error fetching {url}: {e}")

            if attempt < retries:
                await asyncio.sleep(delay * attempt)  # Exponential backoff

        return set()

    async def _fetch_external_lists(self) -> bool:
        """Fetch external domain lists with improved concurrency"""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "DisposableEmailChecker/2.0"},
                limits=httpx.Limits(max_connections=5)
            ) as client:
                tasks = [
                    self._fetch_from_url(client, url) for url in DISPOSABLE_DOMAINS_URLS
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            domains_added = 0
            for result in results:
                if isinstance(result, set):
                    initial_size = len(self.disposable_domains)
                    self.disposable_domains.update(result)
                    domains_added += len(self.disposable_domains) - initial_size
                else:
                    logger.error(f"Error in fetch task: {result}")

            self.last_update = time.time()
            logger.info(f"Updated disposable domains list. Added {domains_added} new domains. Total: {len(self.disposable_domains)}")

            # Save to file
            write_domains(DISPOSABLE_DOMAINS_FILE, self.disposable_domains)
            return True

        except Exception as e:
            logger.error(f"Failed to update external domain lists: {e}")
            return False

    async def update_domains_if_needed(self) -> bool:
        """Update domains if needed with better timing logic"""
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            logger.info("Domain list is outdated. Updating...")
            return await self._fetch_external_lists()
        return True

    async def _check_mx_record(self, domain: str) -> Optional[bool]:
        """Check MX record with improved DNS lookup"""
        try:
            # First check if domain resolves
            await asyncio.get_event_loop().run_in_executor(
                None, socket.getaddrinfo, domain, None
            )
            return True
        except socket.gaierror:
            return False
        except Exception as e:
            logger.debug(f"MX record check failed for {domain}: {e}")
            return None

    def _cache_result(self, email: str, result: EmailCheckResult):
        """Cache result with size management"""
        self.cache[email] = {
            "result": result.to_dict(),
            "timestamp": time.time()
        }

        # Manage cache size
        if len(self.cache) > self.max_cache_size:
            self._clean_cache()

    def _clean_cache(self):
        """Clean expired cache entries"""
        current_time = time.time()
        cutoff = current_time - self.cache_ttl

        old_size = len(self.cache)
        self.cache = {
            k: v for k, v in self.cache.items()
            if v["timestamp"] > cutoff
        }

        # If still too large, remove oldest entries
        if len(self.cache) > self.max_cache_size:
            sorted_cache = sorted(
                self.cache.items(),
                key=lambda x: x[1]["timestamp"],
                reverse=True
            )
            self.cache = dict(sorted_cache[:self.max_cache_size])

        logger.debug(f"Cache cleaned: {old_size} -> {len(self.cache)} entries")

    async def check_email(self, email: str) -> EmailCheckResult:
        """Main email checking method with enhanced logic"""
        # Check cache first
        if self._is_cache_valid(email):
            cached_result = self.cache[email]["result"]
            return EmailCheckResult(**cached_result)

        # Update domains if needed
        await self.update_domains_if_needed()

        # Initialize result
        current_time = time.time()
        result = EmailCheckResult(
            email=email,
            is_disposable=False,
            is_valid_format=self._is_valid_email_format(email),
            domain=None,
            risk_score=0,
            risk_level=RiskLevel.LOW,
            checks={
                "domain_blacklist": False,
                "domain_whitelist": False,
                "suspicious_patterns": {},
                "mx_record_exists": None,
            },
            timestamp=current_time,
        )

        # Basic format validation
        if not result.is_valid_format:
            result.risk_score = 100
            result.risk_level = RiskLevel.CRITICAL
            self._cache_result(email, result)
            return result

        # Extract domain
        domain = self._extract_domain(email)
        result.domain = domain

        if not domain:
            result.risk_score = 100
            result.risk_level = RiskLevel.CRITICAL
            self._cache_result(email, result)
            return result

        # Check whitelist first
        if domain in self.whitelist_domains:
            result.checks["domain_whitelist"] = True
            result.risk_score = 0
            result.risk_level = RiskLevel.LOW
            self._cache_result(email, result)
            return result

        # Check disposable domains
        if domain in self.disposable_domains:
            result.is_disposable = True
            result.checks["domain_blacklist"] = True
            result.risk_score = 95

        # Check suspicious patterns
        patterns = self._check_suspicious_patterns(email)
        result.checks["suspicious_patterns"] = patterns

        # Calculate pattern-based risk score
        pattern_weights = {
            "has_numbers_only_username": 20,
            "has_random_username": 15,
            "has_temp_keywords": 30,
            "has_suspicious_tld": 25,
            "has_multiple_dots": 10,
            "has_plus_addressing": 5,
            "has_consecutive_dots": 20,
            "has_short_domain": 10,
            "has_long_username": 8,
            "has_special_chars_excess": 7,
        }

        pattern_score = sum(
            patterns.get(pattern, False) * weight
            for pattern, weight in pattern_weights.items()
        )

        # Update risk score if not already marked as disposable
        if not result.is_disposable:
            result.risk_score = min(pattern_score, 90)

        # Check MX record
        try:
            mx_exists = await self._check_mx_record(domain)
            result.checks["mx_record_exists"] = mx_exists

            if mx_exists is False:
                result.risk_score = min(result.risk_score + 35, 100)

        except Exception as e:
            logger.debug(f"MX check failed for {domain}: {e}")
            result.checks["mx_record_exists"] = None

        # Final disposable determination
        if result.risk_score >= 70:
            result.is_disposable = True

        # Set risk level
        result.risk_level = self._calculate_risk_level(result.risk_score)

        # Cache and return
        self._cache_result(email, result)
        return result

    async def check_emails_batch(self, emails: List[str]) -> List[EmailCheckResult]:
        """Check multiple emails concurrently"""
        tasks = [self.check_email(email) for email in emails]
        return await asyncio.gather(*tasks)

    def add_to_whitelist(self, domains: Set[str]):
        """Add domains to whitelist"""
        self.whitelist_domains.update(domains)
        write_domains(WHITELIST_DOMAINS_FILE, self.whitelist_domains)
        logger.info(f"Added {len(domains)} domains to whitelist")

    def add_to_blacklist(self, domains: Set[str]):
        """Add domains to blacklist"""
        self.disposable_domains.update(domains)
        write_domains(DISPOSABLE_DOMAINS_FILE, self.disposable_domains)
        logger.info(f"Added {len(domains)} domains to blacklist")

    def get_stats(self) -> Dict:
        """Get checker statistics"""
        return {
            "disposable_domains_count": len(self.disposable_domains),
            "whitelist_domains_count": len(self.whitelist_domains),
            "cache_size": len(self.cache),
            "last_update": self.last_update,
            "cache_ttl": self.cache_ttl,
            "update_interval": self.update_interval,
            "max_cache_size": self.max_cache_size,
        }

    def clear_cache(self):
        """Clear the entire cache"""
        self.cache.clear()
        logger.info("Cache cleared")

    async def force_update_domains(self) -> bool:
        """Force update of domain lists"""
        self.last_update = 0  # Force update
        return await self._fetch_external_lists()

    async def initialize(self):
        """Initialize the checker - called on startup"""
        logger.info("Initializing DisposableEmailChecker...")
        self.start_time = time.time()

        # Load initial domains (already done in __init__)
        # But fetch external lists if needed
        if not self.disposable_domains:
            logger.info("No disposable domains loaded, fetching from external sources...")
            await self._fetch_external_lists()

        # Update domains if needed
        await self.update_domains_if_needed()

        logger.info("DisposableEmailChecker initialized successfully")

    async def cleanup(self):
        """Cleanup resources - called on shutdown"""
        logger.info("Cleaning up DisposableEmailChecker...")

        # Clear cache
        self.clear_cache()

        # Save current domain lists
        try:
            write_domains(DISPOSABLE_DOMAINS_FILE, self.disposable_domains)
            write_domains(WHITELIST_DOMAINS_FILE, self.whitelist_domains)
            logger.info("Domain lists saved successfully")
        except Exception as e:
            logger.error(f"Error saving domain lists during cleanup: {e}")

        logger.info("DisposableEmailChecker cleanup completed")

    async def health_check(self) -> Dict:
        """Perform health check and return status"""
        checks = {}
        healthy = True

        try:
            # Check if domain lists are loaded
            checks["disposable_domains"] = {
                "status": "healthy" if len(self.disposable_domains) > 0 else "warning",
                "count": len(self.disposable_domains),
                "message": f"Loaded {len(self.disposable_domains)} disposable domains"
            }

            # Check if whitelist is loaded
            checks["whitelist_domains"] = {
                "status": "healthy" if len(self.whitelist_domains) > 0 else "warning",
                "count": len(self.whitelist_domains),
                "message": f"Loaded {len(self.whitelist_domains)} whitelist domains"
            }

            # Check cache status
            checks["cache_status"] = {
                "status": "healthy",
                "size": len(self.cache),
                "max_size": self.max_cache_size,
                "message": f"Cache: {len(self.cache)}/{self.max_cache_size} entries"
            }

            # Check last update time
            time_since_update = time.time() - self.last_update
            update_status = "healthy" if time_since_update < self.update_interval else "warning"
            # Convert seconds into a human-readable time
            if time_since_update < 60:
                time_ago = f"{int(time_since_update)} seconds ago"
            elif time_since_update < 3600:
                minutes = int(time_since_update // 60)
                time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                hours = int(time_since_update // 3600)
                time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"

            checks["domain_updates"] = {
                "status": update_status,
                "last_update": self.last_update,
                "time_since_update": time_since_update,
                "message": f"Last update: {time_ago}"
            }

            # Test basic functionality
            try:
                test_result = await self.check_email("test@example.com")
                checks["basic_functionality"] = {
                    "status": "healthy",
                    "message": "Basic email checking is working"
                }
            except Exception as e:
                checks["basic_functionality"] = {
                    "status": "unhealthy",
                    "message": f"Basic email checking failed: {str(e)}"
                }
                healthy = False

            # Overall health status
            if any(check["status"] == "unhealthy" for check in checks.values()):
                healthy = False

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            healthy = False
            checks["health_check_error"] = {
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}"
            }

        return {
            "healthy": healthy,
            "checks": checks,
            "timestamp": time.time()
        }
