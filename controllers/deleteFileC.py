# Import Flask components used for routing, JSON responses, requests, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import request
from flask import session

# Import entities used by the delete flow.
from entities.File import File
from entities.Fragment import Fragment
from entities.ShareLink import ShareLink
from entities.UploadSession import UploadSession


# Create the blueprint containing the file deletion route.
delete_bp = Blueprint(
    "delete_bp",
    __name__
)


# Process a request to delete either a temporary upload or a processed file.
@delete_bp.route(
    "/upload/delete/<int:file_id>",
    methods=["POST"]
)
@delete_bp.route(
    "/files/delete/<int:file_id>",
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

    if request.path.startswith("/files/delete/"):
        file_exists = File.verifyFileOwner(
            file_id,
            owner_id
        )

        if not file_exists:
            return jsonify({
                "success": False,
                "message": "Unable to delete file."
            }), 404

        share_links_deleted = ShareLink.deleteShareLinks(file_id)
        upload_sessions_deleted = UploadSession.deleteUploadSessions(file_id)
        fragments_deleted = Fragment.deleteFragments(file_id)
        file_record_deleted = False

        if (
            share_links_deleted
            and upload_sessions_deleted
            and fragments_deleted
        ):
            file_record_deleted = File.deleteFileRecord(
                file_id,
                owner_id
            )

        if not file_record_deleted:
            return jsonify({
                "success": False,
                "message": "Unable to delete file."
            }), 400

        return jsonify({
            "success": True,
            "message": "File deleted successfully."
        })

    # Confirm that the temporary file belongs to the logged-in user.
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
