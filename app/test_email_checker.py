import pytest
from modules.v1.email_checker import DisposableEmailChecker
from modules.v2.email_checker import DisposableEmailChecker as DisposableEmailCheckerV2



@pytest.mark.asyncio
async def test_valid_email():
    checker = DisposableEmailChecker()
    result = await checker.check_email("john.doe@gmail.com")
    assert result["is_valid_format"] is True
    assert result["is_disposable"] is False
    assert result["risk_score"] < 70


@pytest.mark.asyncio
async def test_disposable_email():
    checker = DisposableEmailChecker()
    # Add a fake disposable domain for test
    checker.disposable_domains.add("mailinator.com")
    result = await checker.check_email("fake@mailinator.com")
    assert result["is_disposable"] is True
    assert result["checks"]["domain_blacklist"] is True
    assert result["risk_score"] >= 70


@pytest.mark.asyncio
async def test_whitelisted_email():
    checker = DisposableEmailChecker()
    checker.whitelist_domains.add("example.com")
    result = await checker.check_email("admin@example.com")
    assert result["is_disposable"] is False
    assert result["checks"]["domain_whitelist"] is True
    assert result["risk_score"] == 0


@pytest.mark.asyncio
async def test_invalid_email():
    checker = DisposableEmailChecker()
    result = await checker.check_email("invalid-email")
    assert result["is_valid_format"] is False
    assert result["risk_score"] == 100


@pytest.mark.asyncio
async def test_mx_record_check():
    checker = DisposableEmailChecker()
    result = await checker.check_email("support@openai.com")
    # Cannot guarantee MX check result; ensure no crash and risk_score in bounds
    assert "mx_record_exists" in result["checks"]
    assert 0 <= result["risk_score"] <= 100


@pytest.mark.asyncio
async def test_cache_mechanism():
    checker = DisposableEmailChecker()
    email = "cached@example.com"
    checker.whitelist_domains.add("example.com")
    result1 = await checker.check_email(email)
    result2 = await checker.check_email(email)
    assert result1 == result2  # Cache hit should return identical result



@pytest.mark.asyncio
async def test_valid_email_v2():
    checker = DisposableEmailCheckerV2()
    result = await checker.check_email("john.doe@gmail.com")
    result = result.to_dict()
    assert result["is_valid_format"] is True
    assert result["is_disposable"] is False
    assert result["risk_score"] < 70


@pytest.mark.asyncio
async def test_disposable_email_v2():
    checker = DisposableEmailCheckerV2()
    # Add a fake disposable domain for test
    checker.disposable_domains.add("mailinator.com")
    result = await checker.check_email("fake@mailinator.com")
    result = result.to_dict()
    assert result["is_disposable"] is True
    assert result["checks"]["domain_blacklist"] is True
    assert result["risk_score"] >= 70


@pytest.mark.asyncio
async def test_whitelisted_email_v2():
    checker = DisposableEmailCheckerV2()
    checker.whitelist_domains.add("example.com")
    result = await checker.check_email("admin@example.com")
    result = result.to_dict()
    assert result["is_disposable"] is False
    assert result["checks"]["domain_whitelist"] is True
    assert result["risk_score"] == 0


@pytest.mark.asyncio
async def test_invalid_email_v2():
    checker = DisposableEmailCheckerV2()
    result = await checker.check_email("invalid-email")
    result = result.to_dict()
    assert result["is_valid_format"] is False
    assert result["risk_score"] == 100


@pytest.mark.asyncio
async def test_mx_record_check_v2():
    checker = DisposableEmailCheckerV2()
    result = await checker.check_email("support@openai.com")
    result = result.to_dict()
    # Cannot guarantee MX check result; ensure no crash and risk_score in bounds
    assert "mx_record_exists" in result["checks"]
    assert 0 <= result["risk_score"] <= 100


@pytest.mark.asyncio
async def test_cache_mechanism_v2():
    checker = DisposableEmailCheckerV2()
    email = "cached@example.com"
    checker.whitelist_domains.add("example.com")
    result1 = await checker.check_email(email)
    result2 = await checker.check_email(email)
    result1 = result1.to_dict()
    result2 = result2.to_dict()
    assert result1 == result2  # Cache hit should return identical result
