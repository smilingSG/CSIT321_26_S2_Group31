# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

# Import the File entity used for file listing.
from entities.File import File


# Create the blueprint containing the file-management page route.
file_management_bp = Blueprint(
    "file_management_bp",
    __name__
)


# Display the file-management boundary.
@file_management_bp.route("/files", methods=["GET"])
def fileManagementPage():

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Ask the entity for the user's processed files.
    managed_files = File.getManagedFilesByOwner(owner_id)

    # Display the file-management boundary with real file records.
    return render_template(
        "fileManagement.html",
        managedFiles=managed_files,
        searchQuery=""
    )
