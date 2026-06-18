# Import operating system utilities for checking and deleting temporary files.
import os

# Import Flask components used for routing, JSON responses, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import session

# Import the File entity used to retrieve and delete file records.
from entities.File import File


# Create the blueprint containing the file deletion route.
delete_bp = Blueprint(
    "delete_bp",
    __name__
)

# Define the folder used for temporary file uploads. NOT CURRENTLY IN USE MAY REMOVE LATER
TEMP_UPLOAD_FOLDER = "temp_uploads"


# Process a request to delete a temporary uploaded file.
@delete_bp.route(
    "/upload/delete/<int:file_id>",
    methods=["POST"]
)
def deleteFile(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before deleting a file."
        }), 401

    # Retrieve the temporary file record belonging to the logged-in user.
    file_record = File.getTempFileById(
        file_id,
        owner_id
    )

    # Return an error if the file does not exist or belongs to another user.
    if file_record is None:
        return jsonify({
            "success": False,
            "message": "File not found."
        }), 404

    # Retrieve the temporary file's local storage path.
    temp_file_path = file_record["temp_upload_path"]

    # Delete the physical temporary file if it still exists.
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    # Delete the corresponding file record from the database.
    File.removeFile(
        file_id,
        owner_id
    )

    # Return a successful JSON response to the boundary.
    return jsonify({
        "success": True,
        "message": "File deleted."
    })