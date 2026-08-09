# Import Flask components used for routing, JSON responses, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import session

# Import entities used to cancel upload sessions and temporary uploaded files.
from entities.File import File
from entities.UploadSession import UploadSession


# Create the blueprint containing upload-cancellation routes.
cancel_upload_bp = Blueprint(
    "cancel_upload_bp",
    __name__
)


# Cancel an incomplete upload session before a file record exists.
@cancel_upload_bp.route("/upload/cancel-session/<int:upload_id>", methods=["POST"])
def cancelUploadSession(upload_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before cancelling an upload."
        }), 401

    # Ask the entity to cancel the upload session and remove the temporary file.
    upload_cancelled = UploadSession.cancelUpload(
        upload_id,
        owner_id
    )

    if not upload_cancelled:
        return jsonify({
            "success": False,
            "message": "Upload session could not be cancelled."
        }), 400

    return jsonify({
        "success": True,
        "message": "Upload session cancelled."
    })


# Cancel a completed temporary upload before encryption.
@cancel_upload_bp.route("/upload/cancel/<int:file_id>", methods=["POST"])
def cancelUpload(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before cancelling an upload."
        }), 401

    # Confirm that the temporary record belongs to the logged-in user.
    file_record = File.getTempFileById(
        file_id,
        owner_id
    )

    if file_record is None:
        return jsonify({
            "success": False,
            "message": "Temporary file record not found."
        }), 404

    # Ask the entity to remove both the physical file and its metadata.
    file_deleted = File.deleteTempFileRecord(
        file_id,
        owner_id
    )

    if not file_deleted:
        return jsonify({
            "success": False,
            "message": "Temporary upload could not be removed."
        }), 500

    return jsonify({
        "success": True,
        "message": "Temporary upload removed successfully."
    })
