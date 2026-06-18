from typing import Optional
from typing import Dict
from typing import Any

from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.UserAccount import UserAccount

admin_update_bp = Blueprint("admin_update_bp", __name__)


def getPostLoginRedirect(role: str) -> str:

    if role == "user_admin":
        return url_for("user_management_bp.userAdminDashboard")

    return url_for("dashboard_bp.dashboard")


class AdminUpdateC:

    @staticmethod
    def getUpdateUserData(user_id: int) -> Optional[Dict[str, Any]]:

        user_account = UserAccount.getUserDetails(user_id)

        if user_account is None:
            return None

        return {
            "userID": user_account["user_id"],
            "username": user_account["username"],
            "email": user_account["email"],
            "role": user_account["role"],
            "roleLabel": AdminUpdateC.formatRole(user_account["role"])
        }

    @staticmethod
    def formatRole(role: str) -> str:

        role_labels = {
            "user": "User",
            "user_admin": "User Admin",
            "system_admin": "System Admin"
        }

        return role_labels.get(role, role)

    @staticmethod
    def updateUser(user_id: int,
                   username: str,
                   email: str,
                   role: str) -> bool:

        if not UserAccount.checkUserExistsById(user_id):
            return False

        UserAccount.updateAccount(
            user_id=user_id,
            username=username,
            email=email,
            role=role
        )

        return True


@admin_update_bp.route("/user-management/update/<int:user_id>", methods=["GET", "POST"])
def updateUser(user_id: int):

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    if request.method == "GET":
        user_account = AdminUpdateC.getUpdateUserData(user_id)

        if user_account is None:
            flash("User not found.", "error")
            return redirect(url_for("admin_search_bp.userManagement"))

        return render_template(
            "AdminUpdatePg.html",
            user=user_account,
            username=session.get("username")
        )

    username: str = request.form.get("username", "").strip()
    email: str = request.form.get("email", "").strip()
    role: str = request.form.get("role", "user")

    valid_roles = {
        "user",
        "user_admin",
        "system_admin"
    }

    if username == "" or email == "" or role not in valid_roles:
        flash("Please enter valid user details.", "error")
        return redirect(url_for("admin_update_bp.updateUser", user_id=user_id))

    user_updated = AdminUpdateC.updateUser(
        user_id=user_id,
        username=username,
        email=email,
        role=role
    )

    if not user_updated:
        flash("User not found.", "error")
        return redirect(url_for("admin_search_bp.userManagement"))

    flash("User account updated successfully.", "success")
    return redirect(url_for("admin_search_bp.userManagement"))
