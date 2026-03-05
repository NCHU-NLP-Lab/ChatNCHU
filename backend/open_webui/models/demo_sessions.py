import time
import uuid
from typing import Optional, List

from open_webui.internal.db import Base, get_db

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, String


####################
# DemoSession DB Schema
####################


class DemoSession(Base):
    __tablename__ = "demo_session"

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, index=True)
    login_date = Column(String)  # "YYYY-MM-DD"
    login_at = Column(BigInteger)
    expires_at = Column(BigInteger)
    logged_out = Column(Boolean, default=False)
    logged_out_at = Column(BigInteger, nullable=True)


class DemoSessionModel(BaseModel):
    id: str
    user_id: str
    login_date: str
    login_at: int
    expires_at: int
    logged_out: bool = False
    logged_out_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


####################
# CRUD
####################


class DemoSessionsTable:
    def get_today_sessions(
        self,
        user_id: str,
    ) -> List[DemoSessionModel]:
        """Return all sessions for today."""
        try:
            with get_db() as db:
                today = time.strftime("%Y-%m-%d")
                sessions = (
                    db.query(DemoSession)
                    .filter_by(user_id=user_id, login_date=today)
                    .all()
                )
                return [DemoSessionModel.model_validate(s) for s in sessions]
        except Exception:
            return []

    def count_today_sessions(
        self,
        user_id: str,
    ) -> int:
        """Return the number of sessions created today."""
        try:
            with get_db() as db:
                today = time.strftime("%Y-%m-%d")
                return (
                    db.query(DemoSession)
                    .filter_by(user_id=user_id, login_date=today)
                    .count()
                )
        except Exception:
            return 0

    def get_active_session(
        self,
        user_id: str,
    ) -> Optional[DemoSessionModel]:
        """Return the current active session (not expired, not logged out), or None."""
        try:
            with get_db() as db:
                today = time.strftime("%Y-%m-%d")
                now = int(time.time())
                session = (
                    db.query(DemoSession)
                    .filter_by(user_id=user_id, login_date=today, logged_out=False)
                    .filter(DemoSession.expires_at > now)
                    .first()
                )
                return DemoSessionModel.model_validate(session) if session else None
        except Exception:
            return None

    def get_today_session(
        self,
        user_id: str,
    ) -> Optional[DemoSessionModel]:
        """Return the most recent session for today (for backward compat)."""
        try:
            with get_db() as db:
                today = time.strftime("%Y-%m-%d")
                session = (
                    db.query(DemoSession)
                    .filter_by(user_id=user_id, login_date=today)
                    .order_by(DemoSession.login_at.desc())
                    .first()
                )
                return DemoSessionModel.model_validate(session) if session else None
        except Exception:
            return None

    def create_session(
        self,
        user_id: str,
        duration: int = 7200,
    ) -> Optional[DemoSessionModel]:
        with get_db() as db:
            now = int(time.time())
            today = time.strftime("%Y-%m-%d")
            session_entry = DemoSessionModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                login_date=today,
                login_at=now,
                expires_at=now + duration,
                logged_out=False,
                logged_out_at=None,
            )
            result = DemoSession(**session_entry.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            return session_entry if result else None

    def mark_logged_out(
        self,
        user_id: str,
    ) -> bool:
        """Mark the active session as logged out."""
        try:
            with get_db() as db:
                today = time.strftime("%Y-%m-%d")
                now = int(time.time())
                session = (
                    db.query(DemoSession)
                    .filter_by(user_id=user_id, login_date=today, logged_out=False)
                    .filter(DemoSession.expires_at > now)
                    .first()
                )
                if session:
                    session.logged_out = True
                    session.logged_out_at = int(time.time())
                    db.commit()
                    return True
                return False
        except Exception:
            return False

    def is_session_expired(
        self,
        user_id: str,
    ) -> bool:
        """Return True if user has no active session (all expired or logged out)."""
        active = self.get_active_session(user_id)
        return active is None

    def get_remaining_time(
        self,
        user_id: str,
    ) -> Optional[int]:
        """Return remaining seconds for the active session, or None/0."""
        active = self.get_active_session(user_id)
        if active is None:
            return 0
        now = int(time.time())
        remaining = active.expires_at - now
        return max(0, remaining)

    def reset_today_session(
        self,
        user_id: str,
    ) -> bool:
        """Delete ALL today's sessions so the user can log in again."""
        try:
            with get_db() as db:
                today = time.strftime("%Y-%m-%d")
                deleted = (
                    db.query(DemoSession)
                    .filter_by(user_id=user_id, login_date=today)
                    .delete()
                )
                db.commit()
                return deleted > 0
        except Exception:
            return False


DemoSessions = DemoSessionsTable()
