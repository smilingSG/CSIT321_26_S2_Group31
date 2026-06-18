# Import utilities for file handling and generating unique filenames.
import os
import uuid

# Import Flask components used for routing, templates, requests, JSON, and sessions.
from flask import Blueprint, render_template, request, jsonify, redirect, session, url_for

# Import Werkzeug's utility for sanitising uploaded filenames.
from werkzeug.utils import secure_filename

# Import the File entity used to create, retrieve, and delete file records.
from entities.File import File


# Create the blueprint containing the file-upload routes.
upload_bp = Blueprint("upload_bp", __name__)

# Define the directory used to store uploaded files temporarily.
TEMP_UPLOAD_FOLDER: str = "temp_uploads"

# Create the temporary upload directory if it does not already exist.
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)


# Display the file-upload page.
@upload_bp.route("/upload", methods=["GET"])
def uploadPage():

    # Redirect unauthenticated users to the login page.
    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    # Display the upload boundary without additional data.
    return render_template("upload.html")


# Receive and temporarily store an uploaded file.
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
        # Sanitise the original filename to prevent unsafe path characters.
        original_filename: str = secure_filename(uploaded_file.filename)

        # Preserve the original file extension.
        file_extension: str = os.path.splitext(original_filename)[1]

        # Generate a unique storage filename to prevent naming conflicts.
        stored_filename: str = str(uuid.uuid4()) + file_extension

        # Build the path where the temporary file will be stored.
        temp_file_path: str = os.path.join(
            TEMP_UPLOAD_FOLDER,
            stored_filename
        )

        # Save the uploaded file in the temporary upload directory.
        uploaded_file.save(temp_file_path)

        # Retrieve the size of the saved file in bytes.
        file_size: int = os.path.getsize(temp_file_path)

        # Retrieve the browser-provided MIME type.
        file_type: str = uploaded_file.content_type or "Unknown"

        # Validate the file type and create its temporary database record.
        file_id = File.createTempFileRecord(
            owner_id=owner_id,
            file_name=original_filename,
            stored_filename=stored_filename,
            file_size=file_size,
            file_type=file_type,
            temp_upload_path=temp_file_path
        )

        # Remove the physical file if validation rejects its file type.
        if file_id is None:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

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

    # Return an error if an unexpected upload operation fails.
    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Upload error: " + str(error)
        }), 500


# Cancel an upload and remove its temporary file and database record.
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

    # Retrieve the temporary record belonging to the logged-in user.
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

    # Delete the corresponding temporary database record.
    File.deleteTempFileRecord(
        file_id,
        owner_id
    )

    # Return a successful response to the upload boundary.
    return jsonify({
        "success": True,
        "message": "Temporary upload removed successfully."
    })