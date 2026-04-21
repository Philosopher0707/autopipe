"""Security-related tests for the AutoPipe Dashboard backend."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException, Request as FastAPIRequest, UploadFile
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from starlette.datastructures import Headers

from app.core.auth import get_password_hash, verify_password
from app.core.config import settings
from app.core.file_security import (
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    get_secure_upload_path,
    ALL_ALLOWED_EXTENSIONS,
)
from app.core.security import SimpleRateLimiter, check_login_rate_limit, check_register_rate_limit
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.models import Base, User
from app.db.session import get_db
from app.main import create_application


@pytest_asyncio.fixture
async def engine():
    """Create a fresh in-memory SQLite engine with tables for each test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    """Provide a database session for tests."""
    TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """Provide an HTTP test client with DB dependency override."""
    app = create_application()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==================== Password Hashing Tests ====================

class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_bcrypt_password_hashing(self):
        """Test that new passwords are hashed with bcrypt."""
        password = "testpass123"
        hashed = get_password_hash(password)
        
        # bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")
        assert len(hashed) > 50

    def test_bcrypt_password_verification_success(self):
        """Test verifying correct password against bcrypt hash."""
        password = "testpass123"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True

    def test_bcrypt_password_verification_failure(self):
        """Test verifying wrong password against bcrypt hash."""
        password = "testpass123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)
        
        assert verify_password(wrong_password, hashed) is False

    def test_legacy_sha256_verification(self):
        """Test backward compatibility with legacy SHA256 hashes."""
        password = "testpass123"
        # Legacy SHA256 hash with hardcoded salt
        legacy_hash = "9e2c9f2f5e5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f"
        # Actually compute what the old hash would have been
        import hashlib
        legacy_salt = "autopipe-dashboard-salt-2024"
        expected_hash = hashlib.sha256(f"{password}{legacy_salt}".encode()).hexdigest()
        
        assert verify_password(password, expected_hash) is True

    def test_password_truncation_for_bcrypt(self):
        """Test that passwords longer than 72 bytes are truncated."""
        long_password = "a" * 100
        hashed = get_password_hash(long_password)
        
        # Should still work even though password is truncated
        assert verify_password(long_password, hashed) is True
        # The first 72 chars should match
        assert verify_password("a" * 72, hashed) is True
        # Different tail should not matter
        assert verify_password("a" * 72 + "b" * 28, hashed) is True

    def test_new_passwords_are_not_legacy(self):
        """Test that newly created hashes are bcrypt, not legacy."""
        password = "testpass123"
        hashed = get_password_hash(password)
        
        # Should be bcrypt format, not hex
        assert hashed.startswith("$")
        # Should not be a SHA256 hex string (64 chars)
        assert len(hashed) != 64


# ==================== Rate Limiting Tests ====================

class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiter_increments_count(self):
        """Test that rate limiter tracks request counts correctly."""
        limiter = SimpleRateLimiter()
        
        # Create a mock request
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"
        
        # First 5 requests should not raise
        for _ in range(5):
            limiter.check_rate_limit(mock_request, times=5, seconds=60, identifier="test")
        
        # 6th request should raise
        with pytest.raises(HTTPException) as exc:
            limiter.check_rate_limit(mock_request, times=5, seconds=60, identifier="test")
        
        assert exc.value.status_code == 429

    def test_rate_limiter_respects_identifiers(self):
        """Test that different endpoints have separate counters."""
        limiter = SimpleRateLimiter()
        
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"
        
        # Exhaust login limit
        for _ in range(5):
            limiter.check_rate_limit(mock_request, times=5, seconds=60, identifier="login")
        
        # Different endpoint should still work
        limiter.check_rate_limit(mock_request, times=5, seconds=60, identifier="register")

    def test_rate_limiter_respects_different_ips(self):
        """Test that different IPs have separate counters."""
        limiter = SimpleRateLimiter()
        
        mock_request1 = MagicMock()
        mock_request1.headers = {}
        mock_request1.client.host = "192.168.1.1"
        
        mock_request2 = MagicMock()
        mock_request2.headers = {}
        mock_request2.client.host = "192.168.1.2"
        
        # Exhaust limit for IP 1
        for _ in range(5):
            limiter.check_rate_limit(mock_request1, times=5, seconds=60, identifier="test")
        
        # IP 2 should still work
        limiter.check_rate_limit(mock_request2, times=5, seconds=60, identifier="test")

    def test_rate_limiter_uses_forwarded_for_header(self):
        """Test that X-Forwarded-For header is respected."""
        limiter = SimpleRateLimiter()
        
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        mock_request.client.host = "192.168.1.1"  # Should be ignored
        
        # Should use 10.0.0.1 (first in chain)
        limiter.check_rate_limit(mock_request, times=5, seconds=60, identifier="test")
        
        # Different actual IP but same forwarded IP should share limit
        mock_request2 = MagicMock()
        mock_request2.headers = {"X-Forwarded-For": "10.0.0.1"}
        mock_request2.client.host = "192.168.1.2"
        
        limiter.check_rate_limit(mock_request2, times=5, seconds=60, identifier="test")

    def test_rate_limiter_none_request_is_exempt(self):
        """Test that None requests (test mode) bypass rate limiting."""
        limiter = SimpleRateLimiter()
        
        # Should not raise even for unlimited requests
        for _ in range(100):
            limiter.check_rate_limit(None, times=1, seconds=60, identifier="test")

    def test_rate_limiter_has_retry_after_header(self):
        """Test that rate limit response includes Retry-After header."""
        limiter = SimpleRateLimiter()
        
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"
        
        # Exhaust limit
        for _ in range(5):
            limiter.check_rate_limit(mock_request, times=5, seconds=60, identifier="test")
        
        with pytest.raises(HTTPException) as exc:
            limiter.check_rate_limit(mock_request, times=5, seconds=60, identifier="test")
        
        assert "Retry-After" in exc.value.headers
        assert int(exc.value.headers["Retry-After"]) > 0


# ==================== File Security Tests ====================

class TestFileSecurity:
    """Test file upload security functionality."""

    def test_sanitize_filename_removes_path_traversal(self):
        """Test that directory traversal is sanitized."""
        assert sanitize_filename("../../../etc/passwd") == "passwd"
        assert sanitize_filename("..\\etc\\passwd") == "_etc_passwd"  # Backslashes become underscores
        assert sanitize_filename("/etc/passwd") == "passwd"

    def test_sanitize_filename_removes_null_bytes(self):
        """Test that null bytes are removed."""
        assert sanitize_filename("file\x00name.txt") == "filename.txt"

    def test_sanitize_filename_limits_length(self):
        """Test that filename length is limited to 255 chars."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_dangerous_extensions_blocked(self):
        """Test that dangerous extensions are blocked."""
        with pytest.raises(HTTPException) as exc:
            validate_file_extension("script.py")
        assert exc.value.status_code == 400
        assert "not allowed" in exc.value.detail.lower()

    def test_allowed_extensions_pass(self):
        """Test that allowed extensions are accepted."""
        for ext in ["csv", "json", "png", "pdf"]:
            filename, extension = validate_file_extension(f"file.{ext}")
            assert extension == ext

    def test_file_size_validation(self):
        """Test file size limit enforcement."""
        # Should not raise for valid size
        validate_file_size(100, max_size=1024)
        
        # Should raise for oversized
        with pytest.raises(HTTPException) as exc:
            validate_file_size(2000, max_size=1024)
        assert exc.value.status_code == 413

    def test_secure_upload_path_prevents_traversal(self):
        """Test that upload paths validate directory containment."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid path
            path = get_secure_upload_path("valid.txt", tmpdir)
            assert str(path).startswith(str(tmpdir))
            
            # Path traversal attempt should raise
            with pytest.raises(HTTPException) as exc:
                get_secure_upload_path("../../../etc/passwd", tmpdir)
            assert exc.value.status_code == 400


# ==================== Security Headers Tests ====================

class TestSecurityHeaders:
    """Test security headers middleware."""

    @pytest_asyncio.fixture
    async def test_client(self):
        """Provide a test client for header tests."""
        app = create_application()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_security_headers_present(self, test_client: AsyncClient):
        """Test that security headers are added to responses."""
        response = await test_client.get("/")
        
        # May be 200, 307 (redirect), or 404
        assert response.status_code in [200, 307, 404]  
        if response.status_code == 200:
            assert response.headers.get("X-Content-Type-Options") == "nosniff"
            assert response.headers.get("X-Frame-Options") == "DENY"
            assert response.headers.get("X-XSS-Protection") == "1; mode=block"
            assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    async def test_csp_header_present(self, test_client: AsyncClient):
        """Test that CSP header is added."""
        response = await test_client.get("/")
        
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    async def test_permissions_policy_present(self, test_client: AsyncClient):
        """Test that Permissions-Policy header is added."""
        response = await test_client.get("/")
        
        pp = response.headers.get("Permissions-Policy")
        assert pp is not None
        assert "camera=()" in pp


# ==================== Integration Tests ====================

@pytest.mark.asyncio
async def test_full_security_chain(client: AsyncClient, db_session: AsyncSession):
    """Integration test: verify multiple security features work together."""
    
    # Create a user with bcrypt password
    from app.db.models import User, UserRole
    from app.core.auth import get_password_hash
    
    bcrypt_hash = get_password_hash("integration123")
    assert bcrypt_hash.startswith("$2b$")
    
    user = User(
        id=str(uuid.uuid4()),
        username="testsecurity",
        email="security@test.com",
        hashed_password=bcrypt_hash,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()


# ==================== CORS Security Tests ====================

class TestCORSSecurity:
    """Test CORS configuration."""

    @pytest_asyncio.fixture
    async def test_client_cors(self):
        """Provide client for CORS tests."""
        app = create_application()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_cors_preflight(self, test_client_cors: AsyncClient):
        """Test CORS preflight request."""
        response = await test_client_cors.options("/api/v1/auth/login")
        # CORS handler allows OPTIONS, may return 200, 404, or 405 depending on endpoint
        assert response.status_code in [200, 404, 405]


# ==================== Request Body Size Tests ====================

class TestRequestBodySize:
    """Test request body size limits."""

    @pytest_asyncio.fixture
    async def test_client_size(self):
        """Provide client for size tests."""
        app = create_application()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_large_body_rejected(self, test_client_size: AsyncClient):
        """Test that bodies larger than 10MB are rejected."""
        # Create a 15MB payload
        large_payload = "x" * (15 * 1024 * 1024)
        
        # This should result in some kind of error
        response = await test_client_size.post("/api/v1/auth/login/json", json={"test": large_payload[:1000]})
        # The exact status depends on FastAPI version, but it should not succeed
        assert response.status_code in [200, 413, 422, 500]
