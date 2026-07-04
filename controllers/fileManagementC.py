# Import Flask components used for routing, templates, sessions, redirects, and JSON.
from flask import Blueprint
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

# Import the File entity used for file listing and renaming.
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
        managedFiles=managed_files
    )


# Rename a processed file belonging to the logged-in user.
@file_management_bp.route("/files/rename/<int:file_id>", methods=["POST"])
def renameFile(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject unauthenticated rename requests.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before renaming a file."
        }), 401

    # Retrieve the new name entered at the boundary.
    new_name = request.form.get("new_name")

    if new_name is None:
        return jsonify({
            "success": False,
            "message": "Please enter a file name."
        }), 400

    # Ask the entity to check duplicate names and update the file name.
    rename_error = File.updateName(
        owner_id,
        file_id,
        new_name
    )

    if rename_error is not None:
        return jsonify({
            "success": False,
            "message": rename_error
        }), 400

    return jsonify({
        "success": True,
        "message": "File renamed successfully."
    })
