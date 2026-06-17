from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

from controllers.LoginC import getPostLoginRedirect

user_management_bp = Blueprint("user_management_bp", __name__)


@user_management_bp.route("/user-admin-dashboard")
def userAdminDashboard():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    return render_template(
        "AdminSearchPg.html",
        username=session.get("username")
    )