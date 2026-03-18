import os
import re
import uuid
import time
import datetime
import logging
from aiohttp import ClientSession

from open_webui.models.auths import (
    AddUserForm,
    ApiKey,
    Auths,
    Token,
    LdapForm,
    SigninForm,
    SigninResponse,
    SignupForm,
    UpdatePasswordForm,
    UpdateProfileForm,
    UserResponse,
)
from open_webui.models.users import Users
from open_webui.models.verification_codes import (
    VerificationCodes,
    SendCodeForm,
    CheckCodeForm,
    ForgotPasswordForm,
)
from open_webui.models.demo_sessions import DemoSessions
from open_webui.models.groups import Groups

from open_webui.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from open_webui.env import (
    WEBUI_AUTH,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_AUTH_TRUSTED_NAME_HEADER,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_COOKIE_SECURE,
    SRC_LOG_LEVELS,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from open_webui.config import OPENID_PROVIDER_URL, ENABLE_OAUTH_SIGNUP, ENABLE_LDAP
from pydantic import BaseModel
from open_webui.utils.misc import parse_duration, validate_email_format
from open_webui.utils.auth import (
    create_api_key,
    create_token,
    get_admin_user,
    get_verified_user,
    get_current_user,
    get_password_hash,
)
from open_webui.utils.webhook import post_webhook
from open_webui.utils.access_control import get_permissions
from open_webui.utils.email import send_verification_email

from typing import Optional, List

from ssl import CERT_REQUIRED, PROTOCOL_TLS

if ENABLE_LDAP.value:
    from ldap3 import Server, Connection, NONE, Tls
    from ldap3.utils.conv import escape_filter_chars

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


def parse_allowed_domains(config_value: str) -> list[str]:
    """Parse ALLOWED_EMAIL_DOMAINS config and return list of enabled domain strings.
    Supports both legacy comma-separated format and new JSON format.
    """
    if not config_value:
        return []
    config_value = config_value.strip()
    if config_value.startswith("["):
        import json
        try:
            entries = json.loads(config_value)
            return [e["domain"] for e in entries if e.get("enabled", True)]
        except (json.JSONDecodeError, KeyError):
            return []
    else:
        return [d.strip() for d in config_value.split(",") if d.strip()]

############################
# GetSessionUser
############################


class SessionUserResponse(Token, UserResponse):
    expires_at: Optional[int] = None
    permissions: Optional[dict] = None


@router.get("/", response_model=SessionUserResponse)
async def get_session_user(
    request: Request, response: Response, user=Depends(get_current_user)
):
    expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
    expires_at = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())

    token = create_token(
        data={"id": user.id},
        expires_delta=expires_delta,
    )

    datetime_expires_at = (
        datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
        if expires_at
        else None
    )

    # Set the cookie token
    response.set_cookie(
        key="token",
        value=token,
        expires=datetime_expires_at,
        httponly=True,  # Ensures the cookie is not accessible via JavaScript
        samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
        secure=WEBUI_AUTH_COOKIE_SECURE,
    )

    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "profile_image_url": user.profile_image_url,
        "permissions": user_permissions,
    }


############################
# Update Profile
############################


@router.post("/update/profile", response_model=UserResponse)
async def update_profile(
    form_data: UpdateProfileForm, session_user=Depends(get_verified_user)
):
    if session_user:
        user = Users.update_user_by_id(
            session_user.id,
            {"profile_image_url": form_data.profile_image_url, "name": form_data.name},
        )
        if user:
            return user
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.DEFAULT())
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# Update Password
############################


@router.post("/update/password", response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm, session_user=Depends(get_current_user)
):
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)
    if session_user:
        user = Auths.authenticate_user(session_user.email, form_data.password)

        if user:
            hashed = get_password_hash(form_data.new_password)
            return Auths.update_user_password_by_id(user.id, hashed)
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_PASSWORD)
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# LDAP Authentication
############################
@router.post("/ldap", response_model=SessionUserResponse)
async def ldap_auth(request: Request, response: Response, form_data: LdapForm):
    ENABLE_LDAP = request.app.state.config.ENABLE_LDAP
    LDAP_SERVER_LABEL = request.app.state.config.LDAP_SERVER_LABEL
    LDAP_SERVER_HOST = request.app.state.config.LDAP_SERVER_HOST
    LDAP_SERVER_PORT = request.app.state.config.LDAP_SERVER_PORT
    LDAP_ATTRIBUTE_FOR_MAIL = request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL
    LDAP_ATTRIBUTE_FOR_USERNAME = request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME
    LDAP_SEARCH_BASE = request.app.state.config.LDAP_SEARCH_BASE
    LDAP_SEARCH_FILTERS = request.app.state.config.LDAP_SEARCH_FILTERS
    LDAP_APP_DN = request.app.state.config.LDAP_APP_DN
    LDAP_APP_PASSWORD = request.app.state.config.LDAP_APP_PASSWORD
    LDAP_USE_TLS = request.app.state.config.LDAP_USE_TLS
    LDAP_CA_CERT_FILE = request.app.state.config.LDAP_CA_CERT_FILE
    LDAP_CIPHERS = (
        request.app.state.config.LDAP_CIPHERS
        if request.app.state.config.LDAP_CIPHERS
        else "ALL"
    )

    if not ENABLE_LDAP:
        raise HTTPException(400, detail="LDAP authentication is not enabled")

    try:
        tls = Tls(
            validate=CERT_REQUIRED,
            version=PROTOCOL_TLS,
            ca_certs_file=LDAP_CA_CERT_FILE,
            ciphers=LDAP_CIPHERS,
        )
    except Exception as e:
        log.error(f"TLS configuration error: {str(e)}")
        raise HTTPException(400, detail="Failed to configure TLS for LDAP connection.")

    try:
        server = Server(
            host=LDAP_SERVER_HOST,
            port=LDAP_SERVER_PORT,
            get_info=NONE,
            use_ssl=LDAP_USE_TLS,
            tls=tls,
        )
        connection_app = Connection(
            server,
            LDAP_APP_DN,
            LDAP_APP_PASSWORD,
            auto_bind="NONE",
            authentication="SIMPLE" if LDAP_APP_DN else "ANONYMOUS",
        )
        if not connection_app.bind():
            raise HTTPException(400, detail="Application account bind failed")

        search_success = connection_app.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=f"(&({LDAP_ATTRIBUTE_FOR_USERNAME}={escape_filter_chars(form_data.user.lower())}){LDAP_SEARCH_FILTERS})",
            attributes=[
                f"{LDAP_ATTRIBUTE_FOR_USERNAME}",
                f"{LDAP_ATTRIBUTE_FOR_MAIL}",
                "cn",
            ],
        )

        if not search_success:
            raise HTTPException(400, detail="User not found in the LDAP server")

        entry = connection_app.entries[0]
        username = str(entry[f"{LDAP_ATTRIBUTE_FOR_USERNAME}"]).lower()
        email = entry[f"{LDAP_ATTRIBUTE_FOR_MAIL}"].value  # retrive the Attribute value
        if not email:
            raise HTTPException(400, "User does not have a valid email address.")
        elif isinstance(email, str):
            email = email.lower()
        elif isinstance(email, list):
            email = email[0].lower()
        else:
            email = str(email).lower()

        cn = str(entry["cn"])
        user_dn = entry.entry_dn

        if username == form_data.user.lower():
            connection_user = Connection(
                server,
                user_dn,
                form_data.password,
                auto_bind="NONE",
                authentication="SIMPLE",
            )
            if not connection_user.bind():
                raise HTTPException(400, "Authentication failed.")

            user = Users.get_user_by_email(email)
            if not user:
                try:
                    user_count = Users.get_num_users()

                    role = (
                        "admin"
                        if user_count == 0
                        else request.app.state.config.DEFAULT_USER_ROLE
                    )

                    user = Auths.insert_new_auth(
                        email=email,
                        password=str(uuid.uuid4()),
                        name=cn,
                        role=role,
                    )

                    if not user:
                        raise HTTPException(
                            500, detail=ERROR_MESSAGES.CREATE_USER_ERROR
                        )

                except HTTPException:
                    raise
                except Exception as err:
                    log.error(f"LDAP user creation error: {str(err)}")
                    raise HTTPException(
                        500, detail="Internal error occurred during LDAP user creation."
                    )

            user = Auths.authenticate_user_by_trusted_header(email)

            if user:
                token = create_token(
                    data={"id": user.id},
                    expires_delta=parse_duration(
                        request.app.state.config.JWT_EXPIRES_IN
                    ),
                )

                # Set the cookie token
                response.set_cookie(
                    key="token",
                    value=token,
                    httponly=True,  # Ensures the cookie is not accessible via JavaScript
                )

                user_permissions = get_permissions(
                    user.id, request.app.state.config.USER_PERMISSIONS
                )

                return {
                    "token": token,
                    "token_type": "Bearer",
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                    "profile_image_url": user.profile_image_url,
                    "permissions": user_permissions,
                }
            else:
                raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        else:
            raise HTTPException(400, "User record mismatch.")
    except Exception as e:
        log.error(f"LDAP authentication error: {str(e)}")
        raise HTTPException(400, detail="LDAP authentication failed.")


############################
# ChatNCHU: Verification Code
############################


@router.post("/verify/send-code")
async def send_verification_code(
    request: Request,
    form_data: SendCodeForm,
):
    email = form_data.email.lower()
    purpose = form_data.purpose

    # Validate email format
    if not validate_email_format(email):
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT)

    # ChatNCHU: Email local part validation (only alphanumeric)
    local_part = email.split("@")[0]
    if not re.match(r'^[a-zA-Z0-9]+$', local_part):
        raise HTTPException(400, detail="Email username can only contain letters and numbers.")

    # For signup: check domain whitelist and if email is already registered
    if purpose == "signup":
        domains = parse_allowed_domains(request.app.state.config.ALLOWED_EMAIL_DOMAINS)
        if domains:
            email_domain = email.split("@")[-1]
            if email_domain not in domains:
                raise HTTPException(
                    400,
                    detail=f"Email domain @{email_domain} is not allowed. Allowed domains: {', '.join(domains)}",
                )
        if Users.get_user_by_email(email):
            raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    # For password_reset: check if email exists
    if purpose == "password_reset":
        if not Users.get_user_by_email(email):
            raise HTTPException(400, detail="No account found with this email.")

    # Check cooldown (1 minute)
    if VerificationCodes.check_cooldown(email, purpose, cooldown_seconds=60):
        raise HTTPException(429, detail="Please wait 60 seconds before requesting a new code.")

    # Create verification code
    code_entry = VerificationCodes.create_code(email, purpose)
    if not code_entry:
        raise HTTPException(500, detail="Failed to create verification code.")

    # Send email
    smtp_host = request.app.state.config.SMTP_HOST
    smtp_port = request.app.state.config.SMTP_PORT
    smtp_user = request.app.state.config.SMTP_USER
    smtp_password = request.app.state.config.SMTP_PASSWORD
    smtp_from = request.app.state.config.SMTP_FROM
    smtp_use_tls = request.app.state.config.SMTP_USE_TLS

    if not smtp_host:
        raise HTTPException(500, detail="SMTP is not configured. Please contact the administrator.")

    success = send_verification_email(
        to_email=email,
        code=code_entry.code,
        purpose=purpose,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_from=smtp_from,
        smtp_use_tls=smtp_use_tls,
    )

    if not success:
        raise HTTPException(500, detail="Failed to send verification email.")

    return {"status": True, "message": "Verification code sent."}


@router.post("/verify/check-code")
async def check_verification_code(
    form_data: CheckCodeForm,
):
    valid = VerificationCodes.verify_code(
        form_data.email.lower(), form_data.code, form_data.purpose
    )
    if not valid:
        raise HTTPException(400, detail="Invalid or expired verification code.")
    return {"status": True, "message": "Verification code is valid."}


############################
# ChatNCHU: Forgot Password
############################


@router.post("/forgot-password")
async def forgot_password(
    form_data: ForgotPasswordForm,
):
    email = form_data.email.lower()

    # Verify the code
    valid = VerificationCodes.verify_code(email, form_data.code, "password_reset")
    if not valid:
        raise HTTPException(400, detail="Invalid or expired verification code.")

    # Find the user
    user = Users.get_user_by_email(email)
    if not user:
        raise HTTPException(400, detail="No account found with this email.")

    # Validate new password
    if len(form_data.new_password) < 8:
        raise HTTPException(400, detail="Password must be at least 8 characters.")

    # Update password
    hashed = get_password_hash(form_data.new_password)
    result = Auths.update_user_password_by_id(user.id, hashed)
    if not result:
        raise HTTPException(500, detail="Failed to update password.")

    # Mark code as used
    VerificationCodes.mark_code_used(email, form_data.code, "password_reset")

    return {"status": True, "message": "Password has been reset successfully."}


############################
# ChatNCHU: Demo Session
############################


def get_user_demo_limits(user_id: str, app_config) -> dict:
    """
    Get effective demo limits for a user.
    Group settings override global settings.
    If user is in multiple groups with demo_limits, use the most permissive values:
    - If any group disables the limit, it's disabled
    - Use the highest daily_limit across groups
    - Use the longest session_duration across groups
    Returns: { enabled, daily_limit, session_duration }
    """
    global_enabled = app_config.ENABLE_DEMO_TIME_LIMIT
    global_daily = app_config.DEMO_DAILY_LOGIN_LIMIT
    global_duration = app_config.DEMO_SESSION_DURATION

    user_groups = Groups.get_groups_by_member_id(user_id)
    if not user_groups:
        return {
            "enabled": global_enabled,
            "daily_limit": global_daily,
            "session_duration": global_duration,
        }

    # Check if any group has demo_limits configured
    groups_with_limits = []
    for group in user_groups:
        dl = (group.permissions or {}).get("demo_limits")
        if dl:
            groups_with_limits.append(dl)

    if not groups_with_limits:
        return {
            "enabled": global_enabled,
            "daily_limit": global_daily,
            "session_duration": global_duration,
        }

    # Merge: group > global, most permissive across groups
    enabled = True
    daily_limit = 0
    session_duration = 0

    for dl in groups_with_limits:
        e = dl.get("enable_demo_time_limit")
        if e is False:
            enabled = False
        d = dl.get("demo_daily_login_limit")
        if d is not None and d > daily_limit:
            daily_limit = d
        s = dl.get("demo_session_duration")
        if s is not None and s > session_duration:
            session_duration = s

    # If any group disables, disabled
    if not enabled:
        return {"enabled": False, "daily_limit": 0, "session_duration": 0}

    return {
        "enabled": True,
        "daily_limit": daily_limit if daily_limit > 0 else global_daily,
        "session_duration": session_duration if session_duration > 0 else global_duration,
    }


@router.get("/demo-session")
async def get_demo_session(
    request: Request,
    user=Depends(get_current_user),
):
    # Admin users are exempt from demo time limit
    if user.role in ("admin", "super_admin"):
        return {"enabled": False}

    limits = get_user_demo_limits(user.id, request.app.state.config)
    if not limits["enabled"]:
        return {"enabled": False}

    daily_limit = limits["daily_limit"]
    logins_today = DemoSessions.count_today_sessions(user.id)
    remaining_logins = max(0, daily_limit - logins_today)

    active = DemoSessions.get_active_session(user.id)

    if active is None:
        return {
            "enabled": True,
            "remaining": None,
            "has_session": False,
            "daily_limit": daily_limit,
            "logins_today": logins_today,
            "remaining_logins": remaining_logins,
        }

    remaining = DemoSessions.get_remaining_time(user.id)

    return {
        "enabled": True,
        "remaining": remaining,
        "has_session": True,
        "expires_at": active.expires_at,
        "logged_out": active.logged_out,
        "daily_limit": daily_limit,
        "logins_today": logins_today,
        "remaining_logins": remaining_logins,
    }


class ResetDemoSessionForm(BaseModel):
    user_id: str


@router.post("/admin/demo-session/reset")
async def reset_demo_session(
    request: Request,
    form_data: ResetDemoSessionForm,
    user=Depends(get_admin_user),
):
    success = DemoSessions.reset_today_session(form_data.user_id)
    if success:
        return {"success": True, "message": "Demo session reset successfully."}
    else:
        return {"success": True, "message": "No active session found for today."}


############################
# SignIn
############################


@router.post("/signin", response_model=SessionUserResponse)
async def signin(request: Request, response: Response, form_data: SigninForm):
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        if WEBUI_AUTH_TRUSTED_EMAIL_HEADER not in request.headers:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_TRUSTED_HEADER)

        trusted_email = request.headers[WEBUI_AUTH_TRUSTED_EMAIL_HEADER].lower()
        trusted_name = trusted_email
        if WEBUI_AUTH_TRUSTED_NAME_HEADER:
            trusted_name = request.headers.get(
                WEBUI_AUTH_TRUSTED_NAME_HEADER, trusted_email
            )
        if not Users.get_user_by_email(trusted_email.lower()):
            await signup(
                request,
                response,
                SignupForm(
                    email=trusted_email, password=str(uuid.uuid4()), name=trusted_name
                ),
            )
        user = Auths.authenticate_user_by_trusted_header(trusted_email)
    elif WEBUI_AUTH == False:
        admin_email = "admin@localhost"
        admin_password = "admin"

        if Users.get_user_by_email(admin_email.lower()):
            user = Auths.authenticate_user(admin_email.lower(), admin_password)
        else:
            if Users.get_num_users() != 0:
                raise HTTPException(400, detail=ERROR_MESSAGES.EXISTING_USERS)

            await signup(
                request,
                response,
                SignupForm(email=admin_email, password=admin_password, name="User"),
            )

            user = Auths.authenticate_user(admin_email.lower(), admin_password)
    else:
        # ChatNCHU: Allow login by employee_id (no @) or email (contains @)
        if "@" in form_data.email:
            user = Auths.authenticate_user(form_data.email.lower(), form_data.password)
        else:
            user = Auths.authenticate_user_by_employee_id(
                form_data.email, form_data.password
            )

    if user:
        # ChatNCHU: Demo session time limit check
        if user.role not in ("admin", "super_admin"):
            limits = get_user_demo_limits(user.id, request.app.state.config)
            if limits["enabled"]:
                daily_limit = limits["daily_limit"]
                duration = limits["session_duration"]

                # Check if there's an active (not expired, not logged out) session
                active_session = DemoSessions.get_active_session(user.id)
                if active_session:
                    # User has an active session, allow re-login
                    pass
                else:
                    # No active session — check if user has remaining logins
                    logins_today = DemoSessions.count_today_sessions(user.id)
                    if logins_today >= daily_limit:
                        raise HTTPException(
                            403,
                            detail="You have used all your login sessions for today. Please try again tomorrow.",
                        )
                    # Create new demo session
                    DemoSessions.create_session(user.id, duration=duration)

        expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
        expires_at = None
        if expires_delta:
            expires_at = int(time.time()) + int(expires_delta.total_seconds())

        token = create_token(
            data={"id": user.id},
            expires_delta=expires_delta,
        )

        datetime_expires_at = (
            datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
            if expires_at
            else None
        )

        # Set the cookie token
        response.set_cookie(
            key="token",
            value=token,
            expires=datetime_expires_at,
            httponly=True,  # Ensures the cookie is not accessible via JavaScript
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
        )

        user_permissions = get_permissions(
            user.id, request.app.state.config.USER_PERMISSIONS
        )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# Default User Role
############################


@router.get("/signup/user/role")
async def get_default_user_role(request: Request, user=Depends(get_admin_user)):
    return request.app.state.config.DEFAULT_USER_ROLE


############################
# SignUp
############################


@router.post("/signup", response_model=SessionUserResponse)
async def signup(request: Request, response: Response, form_data: SignupForm):

    # ChatNCHU: Always allow first user signup (admin creation)
    if Users.get_num_users() == 0:
        pass
    elif WEBUI_AUTH:
        if (
            not request.app.state.config.ENABLE_SIGNUP
            or not request.app.state.config.ENABLE_LOGIN_FORM
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )
    else:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
        )

    user_count = Users.get_num_users()
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    # ChatNCHU: Domain whitelist check (skip for first admin signup)
    if user_count > 0:
        domains = parse_allowed_domains(request.app.state.config.ALLOWED_EMAIL_DOMAINS)
        if domains:
            email_domain = form_data.email.lower().split("@")[-1]
            if email_domain not in domains:
                raise HTTPException(
                    400,
                    detail=f"Email domain @{email_domain} is not allowed. Allowed domains: {', '.join(domains)}",
                )

    # ChatNCHU: Email verification code check
    if request.app.state.config.ENABLE_EMAIL_VERIFICATION and user_count > 0:
        if not form_data.verification_code:
            raise HTTPException(400, detail="Verification code is required.")
        valid = VerificationCodes.verify_code(
            form_data.email.lower(), form_data.verification_code, "signup"
        )
        if not valid:
            raise HTTPException(400, detail="Invalid or expired verification code.")

    # ChatNCHU: Employee ID validation
    if user_count > 0 and not form_data.employee_id:
        raise HTTPException(400, detail="Employee ID / Student ID is required.")

    if form_data.employee_id:
        if not re.match(r'^[a-zA-Z0-9]+$', form_data.employee_id):
            raise HTTPException(400, detail="Employee ID / Student ID can only contain letters and numbers.")
        if Users.get_user_by_employee_id(form_data.employee_id):
            raise HTTPException(400, detail="This Employee ID / Student ID is already registered.")

    # ChatNCHU: Email local part validation (only alphanumeric)
    email_lower = form_data.email.lower()
    local_part = email_lower.split("@")[0]
    if not re.match(r'^[a-zA-Z0-9]+$', local_part):
        raise HTTPException(400, detail="Email username can only contain letters and numbers.")

    if Users.get_user_by_email(email_lower):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        role = (
            "super_admin" if user_count == 0 else request.app.state.config.DEFAULT_USER_ROLE
        )

        if user_count == 0:
            # After first admin, set signup based on env var (default: True)
            request.app.state.config.ENABLE_SIGNUP = os.environ.get("ENABLE_SIGNUP", "True").lower() == "true"

        # The password passed to bcrypt must be 72 bytes or fewer. If it is longer, it will be truncated before hashing.
        if len(form_data.password.encode("utf-8")) > 72:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.PASSWORD_TOO_LONG,
            )

        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url,
            role,
            employee_id=form_data.employee_id if form_data.employee_id else (form_data.name if user_count == 0 else None),
        )

        if user:
            # ChatNCHU: Mark verification code as used
            if request.app.state.config.ENABLE_EMAIL_VERIFICATION and form_data.verification_code:
                VerificationCodes.mark_code_used(
                    form_data.email.lower(), form_data.verification_code, "signup"
                )

            expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
            expires_at = None
            if expires_delta:
                expires_at = int(time.time()) + int(expires_delta.total_seconds())

            token = create_token(
                data={"id": user.id},
                expires_delta=expires_delta,
            )

            datetime_expires_at = (
                datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                if expires_at
                else None
            )

            # Set the cookie token
            response.set_cookie(
                key="token",
                value=token,
                expires=datetime_expires_at,
                httponly=True,  # Ensures the cookie is not accessible via JavaScript
                samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                secure=WEBUI_AUTH_COOKIE_SECURE,
            )

            if request.app.state.config.WEBHOOK_URL:
                post_webhook(
                    request.app.state.WEBUI_NAME,
                    request.app.state.config.WEBHOOK_URL,
                    WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                    {
                        "action": "signup",
                        "message": WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                        "user": user.model_dump_json(exclude_none=True),
                    },
                )

            user_permissions = get_permissions(
                user.id, request.app.state.config.USER_PERMISSIONS
            )

            return {
                "token": token,
                "token_type": "Bearer",
                "expires_at": expires_at,
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
                "permissions": user_permissions,
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except Exception as err:
        log.error(f"Signup error: {str(err)}")
        raise HTTPException(500, detail="An internal error occurred during signup.")


@router.get("/signout")
async def signout(request: Request, response: Response):
    # ChatNCHU: Mark demo session as logged out
    try:
        from open_webui.utils.auth import decode_token, get_http_authorization_cred
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header:
            auth_cred = get_http_authorization_cred(auth_header)
            token = auth_cred.credentials
        else:
            token = request.cookies.get("token")
        if token:
            data = decode_token(token)
            if data and "id" in data:
                user = Users.get_user_by_id(data["id"])
                if user and user.role not in ("admin", "super_admin"):
                    limits = get_user_demo_limits(user.id, request.app.state.config)
                    if limits["enabled"]:
                        DemoSessions.mark_logged_out(user.id)
    except Exception:
        pass

    response.delete_cookie("token")

    if ENABLE_OAUTH_SIGNUP.value:
        oauth_id_token = request.cookies.get("oauth_id_token")
        if oauth_id_token:
            try:
                async with ClientSession() as session:
                    async with session.get(OPENID_PROVIDER_URL.value) as resp:
                        if resp.status == 200:
                            openid_data = await resp.json()
                            logout_url = openid_data.get("end_session_endpoint")
                            if logout_url:
                                response.delete_cookie("oauth_id_token")
                                return RedirectResponse(
                                    headers=response.headers,
                                    url=f"{logout_url}?id_token_hint={oauth_id_token}",
                                )
                        else:
                            raise HTTPException(
                                status_code=resp.status,
                                detail="Failed to fetch OpenID configuration",
                            )
            except Exception as e:
                log.error(f"OpenID signout error: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to sign out from the OpenID provider.",
                )

    return {"status": True}


############################
# AddUser
############################


@router.post("/add", response_model=SigninResponse)
async def add_user(form_data: AddUserForm, user=Depends(get_admin_user)):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    if not form_data.employee_id:
        raise HTTPException(400, detail="Employee ID / Student ID is required.")

    if Users.get_user_by_employee_id(form_data.employee_id):
        raise HTTPException(400, detail="This Employee ID / Student ID is already registered.")

    # ChatNCHU: Only super_admin can create super_admin users
    if form_data.role == "super_admin" and user.role != "super_admin":
        raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

    try:
        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url,
            form_data.role,
            employee_id=form_data.employee_id,
        )

        if user:
            token = create_token(data={"id": user.id})
            return {
                "token": token,
                "token_type": "Bearer",
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except Exception as err:
        log.error(f"Add user error: {str(err)}")
        raise HTTPException(
            500, detail="An internal error occurred while adding the user."
        )


############################
# GetAdminDetails
############################


@router.get("/admin/details")
async def get_admin_details(request: Request, user=Depends(get_current_user)):
    if request.app.state.config.SHOW_ADMIN_DETAILS:
        admin_email = request.app.state.config.ADMIN_EMAIL
        admin_name = None

        log.info(f"Admin details - Email: {admin_email}, Name: {admin_name}")

        if admin_email:
            admin = Users.get_user_by_email(admin_email)
            if admin:
                admin_name = admin.name
        else:
            admin = Users.get_first_user()
            if admin:
                admin_email = admin.email
                admin_name = admin.name

        return {
            "name": admin_name or "",
            "email": admin_email,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)


############################
# ToggleSignUp
############################


@router.get("/admin/config")
async def get_admin_config(request: Request, user=Depends(get_admin_user)):
    # ChatNCHU: Limited admin only sees a subset of config
    config = {
        "SHOW_ADMIN_DETAILS": request.app.state.config.SHOW_ADMIN_DETAILS,
        "ENABLE_SIGNUP": request.app.state.config.ENABLE_SIGNUP,
        "DEFAULT_USER_ROLE": request.app.state.config.DEFAULT_USER_ROLE,
        # ChatNCHU
        "ALLOWED_EMAIL_DOMAINS": request.app.state.config.ALLOWED_EMAIL_DOMAINS,
        "ADMIN_EMAIL": request.app.state.config.ADMIN_EMAIL,
        "ENABLE_DEMO_TIME_LIMIT": request.app.state.config.ENABLE_DEMO_TIME_LIMIT,
        "DEMO_DAILY_LOGIN_LIMIT": request.app.state.config.DEMO_DAILY_LOGIN_LIMIT,
        "DEMO_SESSION_DURATION": request.app.state.config.DEMO_SESSION_DURATION,
    }

    if user.role == "super_admin":
        config.update({
            "WEBUI_URL": request.app.state.config.WEBUI_URL,
            "ENABLE_API_KEY": request.app.state.config.ENABLE_API_KEY,
            "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,
            "API_KEY_ALLOWED_ENDPOINTS": request.app.state.config.API_KEY_ALLOWED_ENDPOINTS,
            "JWT_EXPIRES_IN": request.app.state.config.JWT_EXPIRES_IN,
            "ENABLE_COMMUNITY_SHARING": request.app.state.config.ENABLE_COMMUNITY_SHARING,
            "ENABLE_MESSAGE_RATING": request.app.state.config.ENABLE_MESSAGE_RATING,
            "ENABLE_CHANNELS": request.app.state.config.ENABLE_CHANNELS,
            "ENABLE_USER_WEBHOOKS": request.app.state.config.ENABLE_USER_WEBHOOKS,
            "ENABLE_EMAIL_VERIFICATION": request.app.state.config.ENABLE_EMAIL_VERIFICATION,
            "SMTP_HOST": request.app.state.config.SMTP_HOST,
            "SMTP_PORT": request.app.state.config.SMTP_PORT,
            "SMTP_USER": request.app.state.config.SMTP_USER,
            "SMTP_PASSWORD": request.app.state.config.SMTP_PASSWORD,
            "SMTP_FROM": request.app.state.config.SMTP_FROM,
            "SMTP_USE_TLS": request.app.state.config.SMTP_USE_TLS,
        })

    return config


class AdminConfig(BaseModel):
    SHOW_ADMIN_DETAILS: bool
    ENABLE_SIGNUP: bool
    DEFAULT_USER_ROLE: str
    # Super admin only fields (Optional so limited admin can omit them)
    WEBUI_URL: Optional[str] = None
    ENABLE_API_KEY: Optional[bool] = None
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS: Optional[bool] = None
    API_KEY_ALLOWED_ENDPOINTS: Optional[str] = None
    JWT_EXPIRES_IN: Optional[str] = None
    ENABLE_COMMUNITY_SHARING: Optional[bool] = None
    ENABLE_MESSAGE_RATING: Optional[bool] = None
    ENABLE_CHANNELS: Optional[bool] = None
    ENABLE_USER_WEBHOOKS: Optional[bool] = None
    # ChatNCHU
    ALLOWED_EMAIL_DOMAINS: Optional[str] = None
    ENABLE_EMAIL_VERIFICATION: Optional[bool] = None
    ENABLE_DEMO_TIME_LIMIT: Optional[bool] = None
    DEMO_DAILY_LOGIN_LIMIT: Optional[int] = None
    DEMO_SESSION_DURATION: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_USE_TLS: Optional[bool] = None
    ADMIN_EMAIL: Optional[str] = None


@router.post("/admin/config")
async def update_admin_config(
    request: Request, form_data: AdminConfig, user=Depends(get_admin_user)
):
    # Fields both admin and super_admin can update
    request.app.state.config.SHOW_ADMIN_DETAILS = form_data.SHOW_ADMIN_DETAILS
    request.app.state.config.ENABLE_SIGNUP = form_data.ENABLE_SIGNUP

    if form_data.DEFAULT_USER_ROLE in ["pending", "user", "admin"]:
        request.app.state.config.DEFAULT_USER_ROLE = form_data.DEFAULT_USER_ROLE

    # ChatNCHU shared settings
    if form_data.ALLOWED_EMAIL_DOMAINS is not None:
        request.app.state.config.ALLOWED_EMAIL_DOMAINS = form_data.ALLOWED_EMAIL_DOMAINS
    if form_data.ADMIN_EMAIL is not None:
        request.app.state.config.ADMIN_EMAIL = form_data.ADMIN_EMAIL
    if form_data.ENABLE_DEMO_TIME_LIMIT is not None:
        request.app.state.config.ENABLE_DEMO_TIME_LIMIT = form_data.ENABLE_DEMO_TIME_LIMIT
    if form_data.DEMO_DAILY_LOGIN_LIMIT is not None:
        request.app.state.config.DEMO_DAILY_LOGIN_LIMIT = form_data.DEMO_DAILY_LOGIN_LIMIT
    if form_data.DEMO_SESSION_DURATION is not None:
        request.app.state.config.DEMO_SESSION_DURATION = form_data.DEMO_SESSION_DURATION

    # Super admin only fields
    if user.role == "super_admin":
        if form_data.WEBUI_URL is not None:
            request.app.state.config.WEBUI_URL = form_data.WEBUI_URL
        if form_data.ENABLE_API_KEY is not None:
            request.app.state.config.ENABLE_API_KEY = form_data.ENABLE_API_KEY
        if form_data.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS is not None:
            request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = (
                form_data.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS
            )
        if form_data.API_KEY_ALLOWED_ENDPOINTS is not None:
            request.app.state.config.API_KEY_ALLOWED_ENDPOINTS = (
                form_data.API_KEY_ALLOWED_ENDPOINTS
            )
        if form_data.ENABLE_CHANNELS is not None:
            request.app.state.config.ENABLE_CHANNELS = form_data.ENABLE_CHANNELS

        if form_data.JWT_EXPIRES_IN is not None:
            pattern = r"^(-1|0|(-?\d+(\.\d+)?)(ms|s|m|h|d|w))$"
            if re.match(pattern, form_data.JWT_EXPIRES_IN):
                request.app.state.config.JWT_EXPIRES_IN = form_data.JWT_EXPIRES_IN

        if form_data.ENABLE_COMMUNITY_SHARING is not None:
            request.app.state.config.ENABLE_COMMUNITY_SHARING = (
                form_data.ENABLE_COMMUNITY_SHARING
            )
        if form_data.ENABLE_MESSAGE_RATING is not None:
            request.app.state.config.ENABLE_MESSAGE_RATING = form_data.ENABLE_MESSAGE_RATING
        if form_data.ENABLE_USER_WEBHOOKS is not None:
            request.app.state.config.ENABLE_USER_WEBHOOKS = form_data.ENABLE_USER_WEBHOOKS

        if form_data.ENABLE_EMAIL_VERIFICATION is not None:
            request.app.state.config.ENABLE_EMAIL_VERIFICATION = form_data.ENABLE_EMAIL_VERIFICATION
        if form_data.SMTP_HOST is not None:
            request.app.state.config.SMTP_HOST = form_data.SMTP_HOST
        if form_data.SMTP_PORT is not None:
            request.app.state.config.SMTP_PORT = form_data.SMTP_PORT
        if form_data.SMTP_USER is not None:
            request.app.state.config.SMTP_USER = form_data.SMTP_USER
        if form_data.SMTP_PASSWORD is not None:
            request.app.state.config.SMTP_PASSWORD = form_data.SMTP_PASSWORD
        if form_data.SMTP_FROM is not None:
            request.app.state.config.SMTP_FROM = form_data.SMTP_FROM
        if form_data.SMTP_USE_TLS is not None:
            request.app.state.config.SMTP_USE_TLS = form_data.SMTP_USE_TLS

    return await get_admin_config(request=request, user=user)


class LdapServerConfig(BaseModel):
    label: str
    host: str
    port: Optional[int] = None
    attribute_for_mail: str = "mail"
    attribute_for_username: str = "uid"
    app_dn: str
    app_dn_password: str
    search_base: str
    search_filters: str = ""
    use_tls: bool = True
    certificate_path: Optional[str] = None
    ciphers: Optional[str] = "ALL"


@router.get("/admin/config/ldap/server", response_model=LdapServerConfig)
async def get_ldap_server(request: Request, user=Depends(get_admin_user)):
    return {
        "label": request.app.state.config.LDAP_SERVER_LABEL,
        "host": request.app.state.config.LDAP_SERVER_HOST,
        "port": request.app.state.config.LDAP_SERVER_PORT,
        "attribute_for_mail": request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL,
        "attribute_for_username": request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": request.app.state.config.LDAP_APP_DN,
        "app_dn_password": request.app.state.config.LDAP_APP_PASSWORD,
        "search_base": request.app.state.config.LDAP_SEARCH_BASE,
        "search_filters": request.app.state.config.LDAP_SEARCH_FILTERS,
        "use_tls": request.app.state.config.LDAP_USE_TLS,
        "certificate_path": request.app.state.config.LDAP_CA_CERT_FILE,
        "ciphers": request.app.state.config.LDAP_CIPHERS,
    }


@router.post("/admin/config/ldap/server")
async def update_ldap_server(
    request: Request, form_data: LdapServerConfig, user=Depends(get_admin_user)
):
    required_fields = [
        "label",
        "host",
        "attribute_for_mail",
        "attribute_for_username",
        "app_dn",
        "app_dn_password",
        "search_base",
    ]
    for key in required_fields:
        value = getattr(form_data, key)
        if not value:
            raise HTTPException(400, detail=f"Required field {key} is empty")

    request.app.state.config.LDAP_SERVER_LABEL = form_data.label
    request.app.state.config.LDAP_SERVER_HOST = form_data.host
    request.app.state.config.LDAP_SERVER_PORT = form_data.port
    request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL = form_data.attribute_for_mail
    request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME = (
        form_data.attribute_for_username
    )
    request.app.state.config.LDAP_APP_DN = form_data.app_dn
    request.app.state.config.LDAP_APP_PASSWORD = form_data.app_dn_password
    request.app.state.config.LDAP_SEARCH_BASE = form_data.search_base
    request.app.state.config.LDAP_SEARCH_FILTERS = form_data.search_filters
    request.app.state.config.LDAP_USE_TLS = form_data.use_tls
    request.app.state.config.LDAP_CA_CERT_FILE = form_data.certificate_path
    request.app.state.config.LDAP_CIPHERS = form_data.ciphers

    return {
        "label": request.app.state.config.LDAP_SERVER_LABEL,
        "host": request.app.state.config.LDAP_SERVER_HOST,
        "port": request.app.state.config.LDAP_SERVER_PORT,
        "attribute_for_mail": request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL,
        "attribute_for_username": request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": request.app.state.config.LDAP_APP_DN,
        "app_dn_password": request.app.state.config.LDAP_APP_PASSWORD,
        "search_base": request.app.state.config.LDAP_SEARCH_BASE,
        "search_filters": request.app.state.config.LDAP_SEARCH_FILTERS,
        "use_tls": request.app.state.config.LDAP_USE_TLS,
        "certificate_path": request.app.state.config.LDAP_CA_CERT_FILE,
        "ciphers": request.app.state.config.LDAP_CIPHERS,
    }


@router.get("/admin/config/ldap")
async def get_ldap_config(request: Request, user=Depends(get_admin_user)):
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


class LdapConfigForm(BaseModel):
    enable_ldap: Optional[bool] = None


@router.post("/admin/config/ldap")
async def update_ldap_config(
    request: Request, form_data: LdapConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.ENABLE_LDAP = form_data.enable_ldap
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


############################
# API Key
############################


# create api key
@router.post("/api_key", response_model=ApiKey)
async def generate_api_key(request: Request, user=Depends(get_current_user)):
    if not request.app.state.config.ENABLE_API_KEY and user.role != "super_admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.API_KEY_CREATION_NOT_ALLOWED,
        )

    api_key = create_api_key()
    success = Users.update_user_api_key_by_id(user.id, api_key)

    if success:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_API_KEY_ERROR)


# delete api key
@router.delete("/api_key", response_model=bool)
async def delete_api_key(request: Request, user=Depends(get_current_user)):
    if not request.app.state.config.ENABLE_API_KEY and user.role != "super_admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.API_KEY_CREATION_NOT_ALLOWED,
        )
    success = Users.update_user_api_key_by_id(user.id, None)
    return success


# get api key
@router.get("/api_key", response_model=ApiKey)
async def get_api_key(request: Request, user=Depends(get_current_user)):
    if not request.app.state.config.ENABLE_API_KEY and user.role != "super_admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.API_KEY_NOT_FOUND,
        )
    api_key = Users.get_user_api_key_by_id(user.id)
    if api_key:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(404, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)
