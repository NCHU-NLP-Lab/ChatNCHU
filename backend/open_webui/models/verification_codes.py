import time
import uuid
import random
from typing import Optional

from open_webui.internal.db import Base, get_db

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, String


####################
# VerificationCode DB Schema
####################


class VerificationCode(Base):
    __tablename__ = "verification_code"

    id = Column(String, primary_key=True, unique=True)
    email = Column(String, index=True)
    code = Column(String(6))
    purpose = Column(String)  # "signup" or "password_reset"
    expires_at = Column(BigInteger)
    created_at = Column(BigInteger)
    used = Column(Boolean, default=False)


class VerificationCodeModel(BaseModel):
    id: str
    email: str
    code: str
    purpose: str
    expires_at: int
    created_at: int
    used: bool = False

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class SendCodeForm(BaseModel):
    email: str
    purpose: str = "signup"  # "signup" or "password_reset"


class CheckCodeForm(BaseModel):
    email: str
    code: str
    purpose: str = "signup"


class ForgotPasswordForm(BaseModel):
    email: str
    code: str
    new_password: str


####################
# CRUD
####################


class VerificationCodesTable:
    def create_code(
        self,
        email: str,
        purpose: str = "signup",
    ) -> Optional[VerificationCodeModel]:
        with get_db() as db:
            now = int(time.time())
            code_entry = VerificationCodeModel(
                id=str(uuid.uuid4()),
                email=email.lower(),
                code=f"{random.randint(0, 999999):06d}",
                purpose=purpose,
                expires_at=now + 900,  # 15 minutes
                created_at=now,
                used=False,
            )
            result = VerificationCode(**code_entry.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            return code_entry if result else None

    def get_latest_code(
        self,
        email: str,
        purpose: str = "signup",
    ) -> Optional[VerificationCodeModel]:
        try:
            with get_db() as db:
                code = (
                    db.query(VerificationCode)
                    .filter_by(email=email.lower(), purpose=purpose, used=False)
                    .order_by(VerificationCode.created_at.desc())
                    .first()
                )
                return VerificationCodeModel.model_validate(code) if code else None
        except Exception:
            return None

    def verify_code(
        self,
        email: str,
        code: str,
        purpose: str = "signup",
    ) -> bool:
        """Verify code is valid (correct, not expired, not used)."""
        with get_db() as db:
            now = int(time.time())
            entry = (
                db.query(VerificationCode)
                .filter_by(email=email.lower(), code=code, purpose=purpose, used=False)
                .filter(VerificationCode.expires_at > now)
                .first()
            )
            return entry is not None

    def mark_code_used(
        self,
        email: str,
        code: str,
        purpose: str = "signup",
    ) -> bool:
        try:
            with get_db() as db:
                entry = (
                    db.query(VerificationCode)
                    .filter_by(
                        email=email.lower(), code=code, purpose=purpose, used=False
                    )
                    .first()
                )
                if entry:
                    entry.used = True
                    db.commit()
                    return True
                return False
        except Exception:
            return False

    def check_cooldown(
        self,
        email: str,
        purpose: str = "signup",
        cooldown_seconds: int = 60,
    ) -> bool:
        """Return True if still in cooldown (should NOT send)."""
        with get_db() as db:
            now = int(time.time())
            latest = (
                db.query(VerificationCode)
                .filter_by(email=email.lower(), purpose=purpose)
                .order_by(VerificationCode.created_at.desc())
                .first()
            )
            if latest and (now - latest.created_at) < cooldown_seconds:
                return True
            return False


VerificationCodes = VerificationCodesTable()
