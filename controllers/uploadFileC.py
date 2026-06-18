# Import Flask components used for routing, templates, requests, JSON, and sessions.
from flask import Blueprint, render_template, request, jsonify, redirect, session, url_for

# Import the File entity used to store, retrieve, and delete uploaded files.
from entities.File import File


# Create the blueprint containing the file-upload routes.
upload_bp = Blueprint("upload_bp", __name__)


# Display the file-upload page.
@upload_bp.route("/upload", methods=["GET"])
def uploadPage():

    # Redirect unauthenticated users to the login page.
    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    # Display the upload boundary without additional data.
    return render_template("upload.html")


# Receive an uploaded file and pass it to the File entity for storage.
@upload_bp.route("/upload/temp", methods=["POST"])
def uploadTempFile():

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before uploading a file."
        }), 401

    # Retrieve the uploaded file from the submitted multipart form.
    uploaded_file = request.files.get("file")

    # Reject the request if no file was selected.
    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({
            "success": False,
            "message": "Please select a file."
        }), 400

    try:
        # Ask the File entity to validate, save, and record the upload.
        file_id = File.createTempFileRecord(
            owner_id,
            uploaded_file
        )

        if file_id is None:
            return jsonify({
                "success": False,
                "message": "File type is not allowed."
            }), 400

        # Return the file ID needed by the subsequent upload workflow.
        return jsonify({
            "success": True,
            "message": "Upload completed successfully.",
            "file_id": file_id
        })

    # Convert unexpected entity failures into an HTTP error response.
    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Upload error: " + str(error)
        }), 500


# Cancel an upload through the File entity.
@upload_bp.route("/upload/cancel/<int:file_id>", methods=["POST"])
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
