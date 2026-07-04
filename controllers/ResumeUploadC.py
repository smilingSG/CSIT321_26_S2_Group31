# Import Flask components used for routing, JSON responses, requests, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import request
from flask import session

# Import the UploadSession entity used to retrieve and continue upload progress.
from entities.UploadSession import UploadSession


# Create the blueprint containing the resume-upload route.
resume_upload_bp = Blueprint(
    "resume_upload_bp",
    __name__
)


# Resume a paused upload session from its saved progress.
@resume_upload_bp.route(
    "/upload/resume",
    methods=["POST"]
)
def resumeUpload():

    # Retrieve the logged-in user's ID from the session.
    user_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if user_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before resuming an upload."
        }), 401

    # Retrieve the upload session selected by the boundary.
    upload_id = request.form.get("upload_id", type=int)

    if upload_id is None:
        return jsonify({
            "success": False,
            "message": "Upload session could not be found."
        }), 400

    # Ask the entity for the saved progress before continuing the upload.
    upload_progress = UploadSession.retrieveProgress(
        upload_id,
        user_id
    )

    if upload_progress is None:
        return jsonify({
            "success": False,
            "message": "Saved upload progress could not be found."
        }), 404

    # Ask the entity to mark the upload session as active again.
    upload_continued = UploadSession.continueUpload(
        upload_id,
        user_id
    )

    if not upload_continued:
        return jsonify({
            "success": False,
            "message": "Upload could not be resumed."
        }), 400

    return jsonify({
        "success": True,
        "message": "Upload resumed.",
        "upload_id": upload_progress["uploadID"],
        "bytes_uploaded": upload_progress["bytesUploaded"],
        "total_size": upload_progress["totalSize"]
    })
