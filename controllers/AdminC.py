from typing import Optional

from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.UserAccount import UserAccount
from entities.SystemSetting import SystemSetting

admin_bp = Blueprint("admin_bp", __name__)


def getPostLoginRedirect(role: str) -> str:

    if role == "user_admin":
        return url_for("user_management_bp.userAdminDashboard")

    return url_for("dashboard_bp.dashboard")


class AdminC:

    @staticmethod
    def createUser(username: str,
                   email: str,
                   password: str,
                   role: str) -> Optional[str]:

        if UserAccount.checkUserExists(
            username=username,
            email=email
        ):
            return "Account exists."

        if (not SystemSetting.validateUsernameAgainstPolicy(username)
                or not SystemSetting.validatePasswordAgainstPolicy(password)):
            return "Username or password does not meet the current account policy."

        user_id = UserAccount.createAccount(
            username=username,
            email=email,
            password=password,
            role=role
        )

        if user_id is None:
            return "Username or password does not meet the current account policy."

        return None


@admin_bp.route("/user-management/create", methods=["GET", "POST"])
def createUser():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    if request.method == "GET":
        return render_template(
            "AdminPg.html",
            username=session.get("username")
        )

    username: str = request.form.get("username", "").strip()
    email: str = request.form.get("email", "").strip()
    password: str = request.form.get("password", "")
    role: str = request.form.get("role", "user")

    valid_roles = {
        "user",
        "user_admin",
        "system_admin"
    }

    if username == "" or email == "" or password == "" or role not in valid_roles:
        flash("Please enter valid account details.", "error")
        return redirect(url_for("admin_bp.createUser"))

    creation_error = AdminC.createUser(
        username=username,
        email=email,
        password=password,
        role=role
    )

    if creation_error is not None:
        flash(creation_error, "error")
        return redirect(url_for("admin_bp.createUser"))

    flash("User account created successfully.", "success")
    return redirect(url_for("admin_search_bp.userManagement"))
