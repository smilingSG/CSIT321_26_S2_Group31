# Import Flask components used for routing, JSON responses, requests, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import request
from flask import session

# Import the UploadSession entity used to save upload progress.
from entities.UploadSession import UploadSession


# Create the blueprint containing the pause-upload route.
pause_upload_bp = Blueprint(
    "pause_upload_bp",
    __name__
)


# Pause the current upload session and save its latest progress.
@pause_upload_bp.route(
    "/upload/pause",
    methods=["POST"]
)
def pauseUpload():

    # Retrieve the logged-in user's ID from the session.
    user_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if user_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before pausing an upload."
        }), 401

    # Retrieve the upload session selected by the boundary.
    upload_id = request.form.get("upload_id", type=int)

    if upload_id is None:
        return jsonify({
            "success": False,
            "message": "Upload session could not be found."
        }), 400

    # Ask the entity to save the latest progress and mark the upload as paused.
    progress_saved = UploadSession.saveProgress(
        upload_id,
        user_id
    )

    if not progress_saved:
        return jsonify({
            "success": False,
            "message": "Upload progress could not be paused."
        }), 400

    return jsonify({
        "success": True,
        "message": "Upload paused."
    })
