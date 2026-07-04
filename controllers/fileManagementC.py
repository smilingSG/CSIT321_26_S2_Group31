# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint
from flask import render_template
from flask import redirect
from flask import session
from flask import url_for


# Create the blueprint containing the file-management page route.
file_management_bp = Blueprint(
    "file_management_bp",
    __name__
)


# Display the file-management boundary.
@file_management_bp.route("/files", methods=["GET"])
def fileManagementPage():

    # Redirect unauthenticated users to the login page.
    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    # Display static UI first. Real file records will be connected later.
    return render_template("fileManagement.html")
