# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint, render_template, redirect, session, url_for

# Import the File entity used to retrieve file information.
from entities.File import File
from entities.ShareLink import ShareLink


# Create the blueprint containing the dashboard routes.
dashboard_bp = Blueprint("dashboard_bp", __name__)


# Handle requests to the system's root URL.
@dashboard_bp.route("/")
def home():

    # Redirect unauthenticated users to the login page.
    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    # Redirect authenticated users to the dashboard page.
    return redirect(url_for("dashboard_bp.dashboard"))


# Display the dashboard for the authenticated user.
@dashboard_bp.route("/dashboard")
def dashboard():

    # Retrieve the logged-in user's ID from the session.
    user_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if user_id is None:
        return redirect(url_for("login_bp.login"))

    # Retrieve and prepare the user's dashboard statistics.
    dashboard_data = {
        "total_files": File.countProcessedFilesByOwner(user_id),
        "shared_files": ShareLink.countActiveLinksByOwner(user_id),
        "active_links": ShareLink.countActiveLinksByOwner(user_id)
    }

    # Display the dashboard with its statistics and logged-in username.
    return render_template(
        "dashboard.html",
        data=dashboard_data,
        username=session.get("username")
    )
