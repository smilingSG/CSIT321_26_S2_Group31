# Import Flask components used for routing, JSON responses, and sessions.
from flask import Blueprint, jsonify, session

# Import the File entity used to remove temporary files.
from entities.File import File


# Create the blueprint containing the file replacement route.
replace_bp = Blueprint("replace_bp", __name__)


# Remove the existing temporary file before the user uploads a replacement.
@replace_bp.route("/upload/replace/<int:file_id>", methods=["POST"])
def replaceTempFile(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before replacing a file."
        }), 401

    # Ask the entity to remove the temporary file if it still exists.
    file_deleted = File.deleteTempFileRecord(
        file_id,
        owner_id
    )

    if not file_deleted:
        return jsonify({
            "success": False,
            "message": "Temporary file could not be removed."
        }), 500

    return jsonify({
        "success": True,
        "message": "Temporary file removed. Please upload a replacement file."
    })
