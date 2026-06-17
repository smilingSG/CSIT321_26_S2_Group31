from typing import Optional
from typing import Dict
from typing import Any

from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

from controllers.LoginC import getPostLoginRedirect
from entities.UserAccount import UserAccount

admin_view_bp = Blueprint("admin_view_bp", __name__)


class AdminViewC:

    @staticmethod
    def viewUser(user_id: int) -> Optional[Dict[str, Any]]:

        user_account = UserAccount.getUserDetails(user_id)

        if user_account is None:
            return None

        return {
            "userID": user_account["user_id"],
            "username": user_account["username"],
            "email": user_account["email"],
            "role": AdminViewC.formatRole(user_account["role"]),
            "accountStatus": AdminViewC.formatStatus(
                user_account["account_status"]
            ),
            "createdAt": str(user_account["created_at"]),
            "updatedAt": str(user_account["updated_at"])
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
    def formatStatus(account_status: str) -> str:

        status_labels = {
            "active": "Active",
            "suspended": "Suspended"
        }

        return status_labels.get(account_status, account_status)


@admin_view_bp.route("/user-management/view/<int:user_id>")
def viewUser(user_id: int):

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    user_account = AdminViewC.viewUser(user_id)

    if user_account is None:
        flash("User not found.", "error")
        return redirect(url_for("admin_search_bp.searchUser"))

    return render_template(
        "AdminViewPg.html",
        user=user_account,
        username=session.get("username")
    )