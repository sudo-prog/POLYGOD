"""Tests for Settings validators."""

import pytest
from pydantic import ValidationError


def test_database_url_defaults_to_sqlite():
    from src.backend.config import Settings

    s = Settings(
        POLYGOD_ADMIN_TOKEN="valid-token-for-test-abcdef",
        INTERNAL_API_KEY="valid-internal-key-abcdef",
        ENCRYPTION_KEY="",
    )
    assert "sqlite" in s.DATABASE_URL


def test_admin_token_rejects_sentinel():
    from src.backend.config import Settings

    with pytest.raises(ValidationError, match="POLYGOD_ADMIN_TOKEN"):
        Settings(POLYGOD_ADMIN_TOKEN="change-this-before-use")


def test_encryption_key_auto_generates_when_empty():
    from src.backend.config import Settings
    from cryptography.fernet import Fernet

    s = Settings(
        POLYGOD_ADMIN_TOKEN="valid-token-for-test-abcdef",
        INTERNAL_API_KEY="valid-internal-key-abcdef",
        ENCRYPTION_KEY="",
    )
    # Should have generated a valid Fernet key — verify it works
    key = s.ENCRYPTION_KEY.get_secret_value()
    Fernet(key.encode())  # raises if key is invalid


def test_internal_api_key_rejects_sentinel_in_production():
    from src.backend.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            DEBUG=False,
            POLYGOD_ADMIN_TOKEN="valid-token-for-test-abcdef",
            INTERNAL_API_KEY="change-this-before-use",
        )


def test_cors_origins_list_parses_correctly():
    from src.backend.config import Settings

    s = Settings(
        POLYGOD_ADMIN_TOKEN="valid-token-for-test-abcdef",
        INTERNAL_API_KEY="valid-internal-key-abcdef",
        CORS_ORIGINS="http://localhost:5173,https://example.com",
    )
    assert s.cors_origins_list == ["http://localhost:5173", "https://example.com"]
