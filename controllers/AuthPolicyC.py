from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.SystemSetting import SystemSetting

auth_policy_bp = Blueprint(
    "auth_policy_bp",
    __name__
)


def requireSystemAdmin():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "system_admin":
        return redirect(url_for("dashboard_bp.dashboard"))

    return None


@auth_policy_bp.route(
    "/system-admin/settings/auth-policy",
    methods=["POST"]
)
def setAuthPolicy():

    auth_redirect = requireSystemAdmin()

    if auth_redirect is not None:
        return auth_redirect

    policy_config = {
        "max_login_attempts": request.form.get("max_login_attempts")
    }

    update_success = SystemSetting.updateAuthPolicy(
        policy_config,
        session.get("user_id")
    )

    settings = SystemSetting.getSecuritySettings()

    if not update_success:
        return render_template(
            "AdminConfigPage.html",
            settings=settings,
            errorMessage="Unable to update authentication policy. Check the policy value."
        ), 400

    return render_template(
        "AdminConfigPage.html",
        settings=settings,
        successMessage="Authentication policy updated."
    )
