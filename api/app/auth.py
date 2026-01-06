"""HTTP Basic Authentication middleware."""
import os
import secrets
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify HTTP Basic Auth credentials.

    Credentials are set via environment variables:
    - BASIC_AUTH_USERNAME
    - BASIC_AUTH_PASSWORD

    If not set, defaults to 'admin' / 'changeme' (for development only).
    """
    correct_username = os.getenv("BASIC_AUTH_USERNAME", "admin")
    correct_password = os.getenv("BASIC_AUTH_PASSWORD", "changeme")

    # Use constant-time comparison to prevent timing attacks
    is_username_correct = secrets.compare_digest(
        credentials.username.encode("utf8"),
        correct_username.encode("utf8")
    )
    is_password_correct = secrets.compare_digest(
        credentials.password.encode("utf8"),
        correct_password.encode("utf8")
    )

    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
