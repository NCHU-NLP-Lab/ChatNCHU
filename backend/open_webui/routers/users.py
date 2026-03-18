import logging
from typing import Optional

from open_webui.models.auths import Auths
from open_webui.models.groups import Groups
from open_webui.models.chats import Chats
from open_webui.models.users import (
    UserModel,
    UserRoleUpdateForm,
    Users,
    UserSettings,
    UserUpdateForm,
)


from open_webui.socket.main import get_active_status_by_user_id
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from open_webui.utils.auth import get_admin_user, get_super_admin_user, get_password_hash, get_verified_user
from open_webui.utils.access_control import get_permissions


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

############################
# GetUsers
############################


@router.get("/", response_model=list[UserModel])
async def get_users(
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    user=Depends(get_admin_user),
):
    return Users.get_users(skip, limit)


############################
# User Groups
############################


@router.get("/groups")
async def get_user_groups(user=Depends(get_verified_user)):
    return Groups.get_groups_by_member_id(user.id)


############################
# User Permissions
############################


@router.get("/permissions")
async def get_user_permissisions(request: Request, user=Depends(get_verified_user)):
    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    return user_permissions


############################
# User Default Permissions
############################
class WorkspacePermissions(BaseModel):
    models: bool = False
    knowledge: bool = False
    prompts: bool = False
    tools: bool = False


class SharingPermissions(BaseModel):
    public_models: bool = True
    public_knowledge: bool = True
    public_prompts: bool = True
    public_tools: bool = True


class ChatPermissions(BaseModel):
    controls: bool = True
    file_upload: bool = True
    delete: bool = True
    edit: bool = True
    stt: bool = True
    tts: bool = True
    call: bool = True
    multiple_models: bool = True
    temporary: bool = True
    temporary_enforced: bool = False


class FeaturesPermissions(BaseModel):
    direct_tool_servers: bool = False
    web_search: bool = True
    image_generation: bool = True
    code_interpreter: bool = True


class UserPermissions(BaseModel):
    workspace: WorkspacePermissions
    sharing: SharingPermissions
    chat: ChatPermissions
    features: FeaturesPermissions


@router.get("/default/permissions", response_model=UserPermissions)
async def get_default_user_permissions(request: Request, user=Depends(get_super_admin_user)):
    return {
        "workspace": WorkspacePermissions(
            **request.app.state.config.USER_PERMISSIONS.get("workspace", {})
        ),
        "sharing": SharingPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("sharing", {})
        ),
        "chat": ChatPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("chat", {})
        ),
        "features": FeaturesPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("features", {})
        ),
    }


@router.post("/default/permissions")
async def update_default_user_permissions(
    request: Request, form_data: UserPermissions, user=Depends(get_super_admin_user)
):
    request.app.state.config.USER_PERMISSIONS = form_data.model_dump()
    return request.app.state.config.USER_PERMISSIONS


############################
# UpdateUserRole
############################


@router.post("/update/role", response_model=Optional[UserModel])
async def update_user_role(form_data: UserRoleUpdateForm, user=Depends(get_admin_user)):
    # ChatNCHU: Role hierarchy guards
    # Cannot change own role
    if user.id == form_data.id:
        raise HTTPException(403, detail=ERROR_MESSAGES.ACTION_PROHIBITED)

    # Cannot change first user's role
    first_user = Users.get_first_user()
    if form_data.id == first_user.id:
        raise HTTPException(403, detail=ERROR_MESSAGES.ACTION_PROHIBITED)

    target_user = Users.get_user_by_id(form_data.id)
    if not target_user:
        raise HTTPException(404, detail=ERROR_MESSAGES.USER_NOT_FOUND)

    # Limited admin cannot assign super_admin role
    if user.role == "admin" and form_data.role == "super_admin":
        raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

    # Limited admin cannot modify super_admin users
    if user.role == "admin" and target_user.role == "super_admin":
        raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

    # Only first user can modify other super_admins
    if target_user.role == "super_admin" and user.id != first_user.id:
        raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

    return Users.update_user_role_by_id(form_data.id, form_data.role)


############################
# GetUserSettingsBySessionUser
############################


@router.get("/user/settings", response_model=Optional[UserSettings])
async def get_user_settings_by_session_user(user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserSettingsBySessionUser
############################


@router.post("/user/settings/update", response_model=UserSettings)
async def update_user_settings_by_session_user(
    form_data: UserSettings, user=Depends(get_verified_user)
):
    user = Users.update_user_settings_by_id(user.id, form_data.model_dump())
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserInfoBySessionUser
############################


@router.get("/user/info", response_model=Optional[dict])
async def get_user_info_by_session_user(user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.info
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserInfoBySessionUser
############################


@router.post("/user/info/update", response_model=Optional[dict])
async def update_user_info_by_session_user(
    form_data: dict, user=Depends(get_verified_user)
):
    user = Users.get_user_by_id(user.id)
    if user:
        if user.info is None:
            user.info = {}

        user = Users.update_user_by_id(user.id, {"info": {**user.info, **form_data}})
        if user:
            return user.info
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserById
############################


class UserResponse(BaseModel):
    name: str
    profile_image_url: str
    active: Optional[bool] = None


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, user=Depends(get_verified_user)):
    # Check if user_id is a shared chat
    # If it is, get the user_id from the chat
    if user_id.startswith("shared-"):
        chat_id = user_id.replace("shared-", "")
        chat = Chats.get_chat_by_id(chat_id)
        if chat:
            user_id = chat.user_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )

    user = Users.get_user_by_id(user_id)

    if user:
        return UserResponse(
            **{
                "name": user.name,
                "profile_image_url": user.profile_image_url,
                "active": get_active_status_by_user_id(user_id),
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserById
############################


@router.post("/{user_id}/update", response_model=Optional[UserModel])
async def update_user_by_id(
    user_id: str,
    form_data: UserUpdateForm,
    session_user=Depends(get_admin_user),
):
    user = Users.get_user_by_id(user_id)

    if user:
        # ChatNCHU: Role hierarchy guards for update
        first_user = Users.get_first_user()

        # Cannot edit first user (except by themselves — but role change still blocked)
        if user_id == first_user.id and session_user.id != first_user.id:
            raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

        # Limited admin cannot edit super_admin users
        if session_user.role == "admin" and user.role == "super_admin":
            raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

        # Only first user can edit other super_admins
        if user.role == "super_admin" and session_user.id != first_user.id:
            raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

        if form_data.email.lower() != user.email:
            email_user = Users.get_user_by_email(form_data.email.lower())
            if email_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.EMAIL_TAKEN,
                )

        if not form_data.employee_id or not form_data.employee_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee ID / Student ID is required.",
            )

        if form_data.password:
            hashed = get_password_hash(form_data.password)
            log.debug(f"hashed: {hashed}")
            Auths.update_user_password_by_id(user_id, hashed)

        if form_data.role:
            valid_roles = ["pending", "user", "admin", "super_admin", "suspended"] if session_user.role == "super_admin" else ["pending", "user", "admin", "suspended"]
            if form_data.role in valid_roles:
                if user_id != session_user.id and user_id != first_user.id:
                    Users.update_user_role_by_id(user_id, form_data.role)

        Auths.update_email_by_id(user_id, form_data.email.lower())
        update_data = {
            "name": form_data.name,
            "email": form_data.email.lower(),
            "profile_image_url": form_data.profile_image_url,
        }
        if form_data.employee_id is not None:
            new_eid = form_data.employee_id.strip() if form_data.employee_id else None
            if new_eid and new_eid != user.employee_id:
                existing = Users.get_user_by_employee_id(new_eid)
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This Employee ID / Student ID is already registered.",
                    )
            update_data["employee_id"] = new_eid
        updated_user = Users.update_user_by_id(user_id, update_data)

        if updated_user:
            return updated_user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.USER_NOT_FOUND,
    )


############################
# DeleteUserById
############################


@router.delete("/{user_id}", response_model=bool)
async def delete_user_by_id(user_id: str, user=Depends(get_admin_user)):
    if user.id == user_id:
        raise HTTPException(403, detail=ERROR_MESSAGES.ACTION_PROHIBITED)

    target_user = Users.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(404, detail=ERROR_MESSAGES.USER_NOT_FOUND)

    # ChatNCHU: Role hierarchy guards for delete
    first_user = Users.get_first_user()

    # Cannot delete first user
    if user_id == first_user.id:
        raise HTTPException(403, detail=ERROR_MESSAGES.ACTION_PROHIBITED)

    # Limited admin cannot delete super_admin users
    if user.role == "admin" and target_user.role == "super_admin":
        raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

    # Only first user can delete other super_admins
    if target_user.role == "super_admin" and user.id != first_user.id:
        raise HTTPException(403, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

    result = Auths.delete_auth_by_id(user_id)
    if result:
        return True

    raise HTTPException(500, detail=ERROR_MESSAGES.DELETE_USER_ERROR)
