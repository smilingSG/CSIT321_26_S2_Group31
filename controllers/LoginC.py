from typing import Optional
from typing import Dict
from typing import Any

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.UserAccount import UserAccount

login_bp = Blueprint("login_bp", __name__)


def getPostLoginRedirect(role: str) -> str:

    if role == "user_admin":
        return url_for("user_management_bp.userAdminDashboard")

    if role == "system_admin":
        return url_for("max_expiry_settings_bp.adminConfigPage")

    return url_for("dashboard_bp.dashboard")


class LoginC:

    @staticmethod
    def login(login_credential: str,
              password: str,
              selected_role: str) -> Optional[Dict[str, Any]]:

        user_account = UserAccount.authenticate(
            login_credential=login_credential,
            password=password
        )

        if user_account is None:
            return None

        if user_account["authResult"] != "success":
            return user_account

        if user_account["role"] != selected_role:
            return None

        return user_account


@login_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        if session.get("user_id") is not None:
            return redirect(
                getPostLoginRedirect(session.get("role"))
            )

        return render_template(
            "login.html",
            selected_role="user"
        )

    login_credential: str = request.form.get("login_credential", "").strip()
    password: str = request.form.get("password", "")
    selected_role: str = request.form.get("selected_role", "user")

    valid_roles = {
        "user",
        "user_admin",
        "system_admin"
    }

    if selected_role not in valid_roles:
        selected_role = "user"

    if login_credential == "" or password == "":
        return render_template(
            "login.html",
            error="Invalid input format.",
            login_credential=login_credential,
            selected_role=selected_role
        ), 400

    user_account = LoginC.login(
        login_credential=login_credential,
        password=password,
        selected_role=selected_role
    )

    if user_account is None:
        return render_template(
            "login.html",
            error="Invalid login credentials. Too many failed attempts will result in account suspension.",
            login_credential=login_credential,
            selected_role=selected_role
        ), 401

    if user_account.get("authResult") == "invalid":
        attempts_remaining = user_account.get("attemptsRemaining")

        return render_template(
            "login.html",
            error="Invalid login credentials. " + str(attempts_remaining) + " login attempts remaining before account suspension.",
            login_credential=login_credential,
            selected_role=selected_role
        ), 401

    if user_account.get("authResult") == "locked":
        return render_template(
            "login.html",
            error="Too many failed login attempts. This account has been suspended. Please contact a user administrator.",
            login_credential=login_credential,
            selected_role=selected_role
        ), 403

    if user_account.get("authResult") == "suspended":
        return render_template(
            "login.html",
            error="This account is suspended. Please contact a user administrator.",
            login_credential=login_credential,
            selected_role=selected_role
        ), 403

    session.clear()
    session["user_id"] = user_account["userID"]
    session["username"] = user_account["username"]
    session["role"] = user_account["role"]

    return redirect(getPostLoginRedirect(user_account["role"]))
