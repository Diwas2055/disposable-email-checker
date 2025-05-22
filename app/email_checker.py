import asyncio
import re
import socket
import time
from typing import Dict, Optional, Set

import httpx

from utils import load_domains, logger, write_domains

DISPOSABLE_DOMAINS_FILE = "disposable_domains.json"
WHITELIST_DOMAINS_FILE = "whitelist_domains.json"
DISPOSABLE_DOMAINS_URLS = [
    "https://raw.githubusercontent.com/martenson/disposable-email-domains/master/disposable_email_blocklist.conf",
    "https://raw.githubusercontent.com/disposable/disposable-email-domains/master/domains.txt",
]


class DisposableEmailChecker:
    def __init__(self):
        self.disposable_domains: Set[str] = set()
        self.whitelist_domains: Set[str] = set()
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 3600  # 1 hour
        self.last_update = 0
        self.update_interval = 86400  # 24 hours

        self._initialize_domains()

    def _initialize_domains(self):
        logger.info("Initializing domain lists...")
        self.disposable_domains.update(load_domains(DISPOSABLE_DOMAINS_FILE))
        self.whitelist_domains.update(load_domains(WHITELIST_DOMAINS_FILE))

        if not self.disposable_domains:
            logger.warning(
                "Disposable domain list is empty. Fetching from external sources."
            )
            try:
                asyncio.run(self._fetch_external_lists())
            except Exception as e:
                logger.error(f"Failed to fetch external domain lists: {e}")

    def _is_cache_valid(self, email: str) -> bool:
        return email in self.cache and (
            time.time() - self.cache[email]["timestamp"] < self.cache_ttl
        )

    def _extract_domain(self, email: str) -> Optional[str]:
        if "@" not in email:
            return None
        return email.split("@")[1].lower().strip()

    def _is_valid_email_format(self, email: str) -> bool:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    def _check_suspicious_patterns(self, email: str) -> Dict[str, bool]:
        username = email.split("@")[0]
        patterns = {
            "has_numbers_only_username": re.match(r"^[0-9]+$", username) is not None,
            "has_random_username": len(re.findall(r"[a-zA-Z0-9]{10,}", username)) > 0,
            "has_temp_keywords": any(
                kw in email.lower()
                for kw in [
                    "temp",
                    "temporary",
                    "disposable",
                    "throw",
                    "fake",
                    "test",
                    "spam",
                    "trash",
                    "dummy",
                    "delete",
                    "remove",
                ]
            ),
            "has_suspicious_tld": email.lower().endswith((".tk", ".ml", ".ga", ".cf")),
            "has_multiple_dots": email.count(".") > 2,
            "has_plus_addressing": "+" in username,
        }
        return patterns

    async def _fetch_from_url(self, client, url, retries=3, delay=2) -> Set[str]:
        for attempt in range(1, retries + 1):
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    content = response.text
                    return {
                        line.strip().lower()
                        for line in content.splitlines()
                        if line.strip() and not line.startswith("#")
                    }
                logger.warning(f"Non-200 response from {url}: {response.status_code}")
                break
            except httpx.HTTPError as e:
                logger.warning(f"[Attempt {attempt}] Error fetching {url}: {e}")
                await asyncio.sleep(delay)
        return set()

    async def _fetch_external_lists(self) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=10, headers={"User-Agent": "DisposableEmailChecker/1.0"}
            ) as client:
                tasks = [
                    self._fetch_from_url(client, url) for url in DISPOSABLE_DOMAINS_URLS
                ]
                results = await asyncio.gather(*tasks)

            for domains in results:
                self.disposable_domains.update(domains)

            self.last_update = time.time()
            logger.info(
                f"Updated disposable domains list with {len(self.disposable_domains)} entries."
            )
            write_domains(DISPOSABLE_DOMAINS_FILE, self.disposable_domains)
            return True
        except Exception as e:
            logger.error(f"Failed to update external domain lists: {e}")
            return False

    async def update_domains_if_needed(self):
        if time.time() - self.last_update > self.update_interval:
            logger.info("Domain list is outdated. Updating...")
            await self._fetch_external_lists()

    async def check_email(self, email: str) -> Dict:
        if self._is_cache_valid(email):
            return self.cache[email]["result"]

        await self.update_domains_if_needed()

        result = {
            "email": email,
            "is_disposable": False,
            "is_valid_format": self._is_valid_email_format(email),
            "domain": None,
            "risk_score": 0,
            "checks": {
                "domain_blacklist": False,
                "domain_whitelist": False,
                "suspicious_patterns": {},
                "mx_record_exists": None,
            },
            "timestamp": time.time(),
        }

        if not result["is_valid_format"]:
            result["risk_score"] = 100
            self._cache_result(email, result)
            return result

        domain = self._extract_domain(email)
        result["domain"] = domain

        if not domain:
            result["risk_score"] = 100
            self._cache_result(email, result)
            return result

        if domain in self.whitelist_domains:
            result["checks"]["domain_whitelist"] = True
            result["risk_score"] = 0
            self._cache_result(email, result)
            return result

        if domain in self.disposable_domains:
            result["is_disposable"] = True
            result["checks"]["domain_blacklist"] = True
            result["risk_score"] = 95

        patterns = self._check_suspicious_patterns(email)
        result["checks"]["suspicious_patterns"] = patterns

        pattern_score = sum(
            [
                patterns["has_numbers_only_username"] * 15,
                patterns["has_random_username"] * 10,
                patterns["has_temp_keywords"] * 25,
                patterns["has_suspicious_tld"] * 20,
                patterns["has_multiple_dots"] * 5,
                patterns["has_plus_addressing"] * 3,
            ]
        )

        if not result["is_disposable"]:
            result["risk_score"] = min(pattern_score, 90)

        try:
            result["checks"]["mx_record_exists"] = await self._check_mx_record(domain)
            if not result["checks"]["mx_record_exists"]:
                result["risk_score"] = min(result["risk_score"] + 30, 100)
        except Exception:
            result["checks"]["mx_record_exists"] = None

        if result["risk_score"] >= 70:
            result["is_disposable"] = True

        self._cache_result(email, result)
        return result

    async def _check_mx_record(self, domain: str) -> bool:
        try:
            socket.getaddrinfo(domain, None)
            return True
        except socket.gaierror:
            return False

    def _cache_result(self, email: str, result: Dict):
        self.cache[email] = {"result": result, "timestamp": time.time()}
        if len(self.cache) > 10000:
            cutoff = time.time() - self.cache_ttl
            self.cache = {
                k: v for k, v in self.cache.items() if v["timestamp"] > cutoff
            }

    def get_stats(self) -> Dict:
        return {
            "disposable_domains_count": len(self.disposable_domains),
            "whitelist_domains_count": len(self.whitelist_domains),
            "cache_size": len(self.cache),
            "last_update": self.last_update,
            "cache_ttl": self.cache_ttl,
        }
