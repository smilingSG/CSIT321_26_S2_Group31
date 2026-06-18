# Import operating system utilities for checking and deleting temporary files.
import os

# Import Flask components used for routing, JSON responses, and sessions.
from flask import Blueprint, jsonify, session

# Import the File entity used to retrieve and delete temporary file records.
from entities.File import File


# Create the blueprint containing the file replacement route.
replace_bp = Blueprint("replace_bp", __name__)

# Define the folder used for temporary uploaded files.
TEMP_UPLOAD_FOLDER: str = "temp_uploads"


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

    # Retrieve the temporary file record belonging to the logged-in user.
    file_record = File.getTempFileById(
        file_id,
        owner_id
    )

    # Return an error if the temporary file record cannot be found.
    if file_record is None:
        return jsonify({
            "success": False,
            "message": "Temporary file record not found."
        }), 404

    # Retrieve the temporary file's local storage path.
    temp_file_path: str = file_record["temp_upload_path"]

    # Delete the physical temporary file if it still exists.
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    # Delete the corresponding temporary file record from the database.
    File.deleteTempFileRecord(
        file_id,
        owner_id
    )

    # Tell the boundary that the user can now upload a replacement.
    return jsonify({
        "success": True,
        "message": "Temporary file removed. Please upload a replacement file."
    })