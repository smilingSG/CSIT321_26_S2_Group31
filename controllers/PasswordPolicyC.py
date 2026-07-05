from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.SystemSetting import SystemSetting

password_policy_bp = Blueprint(
    "password_policy_bp",
    __name__
)


def requireSystemAdmin():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "system_admin":
        return redirect(url_for("dashboard_bp.dashboard"))

    return None


@password_policy_bp.route(
    "/system-admin/settings/password-policy",
    methods=["POST"]
)
def setPasswordPolicy():

    auth_redirect = requireSystemAdmin()

    if auth_redirect is not None:
        return auth_redirect

    policy_rules = {
        "min_length": request.form.get("min_length"),
        "max_length": request.form.get("max_length"),
        "require_number": request.form.get("require_number"),
        "require_special": request.form.get("require_special")
    }

    update_success = SystemSetting.updatePasswordPolicy(
        policy_rules,
        session.get("user_id")
    )

    settings = SystemSetting.getSecuritySettings()

    if not update_success:
        return render_template(
            "AdminConfigPage.html",
            settings=settings,
            errorMessage="Unable to update password policy. Check the policy values."
        ), 400

    return render_template(
        "AdminConfigPage.html",
        settings=settings,
        successMessage="Password policy updated."
    )
