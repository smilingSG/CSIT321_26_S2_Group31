# Import Flask components used for routing, JSON responses, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import session

# Import the File entity used to retrieve and delete files.
from entities.File import File


# Create the blueprint containing the file deletion route.
delete_bp = Blueprint(
    "delete_bp",
    __name__
)


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

    # Confirm that the file belongs to the logged-in user.
    file_record = File.getTempFileById(
        file_id,
        owner_id
    )

    if file_record is None:
        return jsonify({
            "success": False,
            "message": "File not found."
        }), 404

    # Ask the entity to remove both the physical file and its metadata.
    file_deleted = File.removeFile(
        file_id,
        owner_id
    )

    if not file_deleted:
        return jsonify({
            "success": False,
            "message": "File could not be deleted."
        }), 500

    return jsonify({
        "success": True,
        "message": "File deleted."
    })
