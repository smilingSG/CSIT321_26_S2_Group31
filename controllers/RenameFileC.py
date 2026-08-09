# Import Flask components used for routing, JSON responses, requests, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import request
from flask import session

# Import the File entity used for renaming processed files.
from entities.File import File


# Create the blueprint containing the file-rename route.
rename_file_bp = Blueprint(
    "rename_file_bp",
    __name__
)


# Rename a processed file belonging to the logged-in user.
@rename_file_bp.route("/files/rename/<int:file_id>", methods=["POST"])
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
