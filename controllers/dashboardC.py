from flask import Blueprint, render_template, redirect, url_for

from entities.File import File

dashboard_bp = Blueprint("dashboard_bp", __name__)


@dashboard_bp.route("/")
def home():
    return redirect(url_for("dashboard_bp.dashboard"))


@dashboard_bp.route("/dashboard")
def dashboard():
    temp_user_id: int = 1

    dashboard_data = {
        "total_files": File.countProcessedFilesByOwner(temp_user_id),
        "shared_files": 0,
        "active_links": 0,
        "recovered_files": 0
    }

    return render_template("dashboard.html", data=dashboard_data)