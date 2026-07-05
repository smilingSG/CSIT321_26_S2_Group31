from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.SystemSetting import SystemSetting

username_policy_bp = Blueprint(
    "username_policy_bp",
    __name__
)


def requireSystemAdmin():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "system_admin":
        return redirect(url_for("dashboard_bp.dashboard"))

    return None


@username_policy_bp.route(
    "/system-admin/settings/username-policy",
    methods=["POST"]
)
def setUsernamePolicy():

    auth_redirect = requireSystemAdmin()

    if auth_redirect is not None:
        return auth_redirect

    policy_rules = {
        "min_length": request.form.get("min_length"),
        "max_length": request.form.get("max_length")
    }

    update_success = SystemSetting.updateUsernamePolicy(
        policy_rules,
        session.get("user_id")
    )

    settings = SystemSetting.getSecuritySettings()

    if not update_success:
        return render_template(
            "AdminConfigPage.html",
            settings=settings,
            errorMessage="Unable to update username policy. Check the policy values."
        ), 400

    return render_template(
        "AdminConfigPage.html",
        settings=settings,
        successMessage="Username policy updated."
    )
