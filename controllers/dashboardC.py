from flask import Blueprint, render_template, redirect, session, url_for

from entities.File import File

dashboard_bp = Blueprint("dashboard_bp", __name__)


@dashboard_bp.route("/")
def home():
    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    return redirect(url_for("dashboard_bp.dashboard"))


@dashboard_bp.route("/dashboard")
def dashboard():
    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    dashboard_data = {
        "total_files": File.countProcessedFilesByOwner(user_id),
        "shared_files": 0,
        "active_links": 0,
        "recovered_files": 0
    }

    return render_template(
        "dashboard.html",
        data=dashboard_data,
        username=session.get("username")
    )
