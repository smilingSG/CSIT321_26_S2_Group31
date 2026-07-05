from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.SystemSetting import SystemSetting

max_expiry_settings_bp = Blueprint(
    "max_expiry_settings_bp",
    __name__
)


def requireSystemAdmin():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "system_admin":
        return redirect(url_for("dashboard_bp.dashboard"))

    return None


@max_expiry_settings_bp.route(
    "/system-admin/settings",
    methods=["GET"]
)
def adminConfigPage():

    auth_redirect = requireSystemAdmin()

    if auth_redirect is not None:
        return auth_redirect

    settings = SystemSetting.getSecuritySettings()

    return render_template(
        "AdminConfigPage.html",
        settings=settings
    )


@max_expiry_settings_bp.route(
    "/system-admin/settings/max-expiry",
    methods=["POST"]
)
def configureMaxExpiry():

    auth_redirect = requireSystemAdmin()

    if auth_redirect is not None:
        return auth_redirect

    max_duration = request.form.get("max_duration")

    update_success = SystemSetting.updateMaxExpiryDuration(
        max_duration,
        session.get("user_id")
    )

    settings = SystemSetting.getSecuritySettings()

    if not update_success:
        return render_template(
            "AdminConfigPage.html",
            settings=settings,
            errorMessage="Invalid max expiry duration. Enter 1 to 168 hours."
        ), 400

    return render_template(
        "AdminConfigPage.html",
        settings=settings,
        successMessage="Max expiry duration set."
    )
