"""Authentication utilities for JWT-based authentication.

Handles password hashing, token generation/verification, and authentication middleware.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_session
from core.models.user import User
from core.models.session import Session

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.
    
    Args:
        plain_password: The plain text password
        hashed_password: The hashed password to verify against
        
    Returns:
        Whether the password is correct
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.
    
    Args:
        password: The plain text password
        
    Returns:
        The hashed password
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.
    
    Args:
        data: The data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        The encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token.
    
    Args:
        data: The data to encode in the token
        
    Returns:
        The encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT token.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        The decoded token payload
        
    Raises:
        HTTPException: If the token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_session)
) -> User:
    """Get the current authenticated user from JWT token.
    
    Args:
        credentials: The HTTP authorization credentials
        db: Database session
        
    Returns:
        The authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    
    # Decode the token
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get the user from database
    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get the current active user.
    
    Args:
        current_user: The current authenticated user
        
    Returns:
        The active user
        
    Raises:
        HTTPException: If the user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def create_user_session(
    user: User,
    db: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Session:
    """Create a new session for a user.
    
    Args:
        user: The user to create a session for
        db: Database session
        ip_address: Optional IP address of the request
        user_agent: Optional user agent string
        
    Returns:
        The created session
    """
    import secrets
    
    # Generate a random session identifier
    session_token = secrets.token_urlsafe(32)
    
    # Hash the token for storage
    token_hash = get_password_hash(session_token)
    
    # Create session record
    session = Session(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # Store the unhashed token on the session object for return (not persisted)
    session._token = session_token
    
    return session


async def revoke_session(session_id: UUID, db: AsyncSession) -> bool:
    """Revoke a user session.
    
    Args:
        session_id: The ID of the session to revoke
        db: Database session
        
    Returns:
        Whether the session was revoked
    """
    stmt = select(Session).where(Session.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if session:
        await db.delete(session)
        await db.commit()
        return True
    
    return False


async def revoke_all_user_sessions(user_id: UUID, db: AsyncSession) -> int:
    """Revoke all sessions for a user.
    
    Args:
        user_id: The ID of the user
        db: Database session
        
    Returns:
        Number of sessions revoked
    """
    stmt = select(Session).where(Session.user_id == user_id)
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    
    count = len(sessions)
    for session in sessions:
        await db.delete(session)
    
    if count > 0:
        await db.commit()
    
    return count


async def clean_expired_sessions(db: AsyncSession) -> int:
    """Clean up expired sessions from the database.
    
    Args:
        db: Database session
        
    Returns:
        Number of sessions cleaned
    """
    stmt = select(Session).where(Session.expires_at <= datetime.now(timezone.utc))
    result = await db.execute(stmt)
    expired_sessions = result.scalars().all()
    
    count = len(expired_sessions)
    for session in expired_sessions:
        await db.delete(session)
    
    if count > 0:
        await db.commit()
    
    return count


async def get_current_company(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
) -> "Company":
    """Get the current user's company for the active semester.
    
    Args:
        current_user: The current authenticated user
        db: Database session
        
    Returns:
        The user's company for the current semester
        
    Raises:
        HTTPException: If no company found for user in current semester
    """
    from core.models.company import Company
    
    # Get the user's company for their current semester
    stmt = select(Company).where(
        Company.user_id == current_user.id,
        Company.semester_id == current_user.semester_id
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No company found for current semester. Please create a company first."
        )
    
    return company 