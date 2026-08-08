# Import Flask components used for routing, templates, requests, JSON, and sessions.
from flask import Blueprint, render_template, request, jsonify, redirect, session, url_for

# Import the File entity used to store, retrieve, and delete uploaded files.
from entities.File import File

# Import the UploadSession entity used by resumable uploads.
from entities.UploadSession import UploadSession
from entities.Fragment import Fragment
from entities.StorageNodeOCI import StorageNode

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


# Start a resumable upload session before chunks are uploaded.
@upload_bp.route("/upload/start", methods=["POST"])
def startUploadSession():

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before uploading a file."
        }), 401

    # Retrieve basic file information from the boundary.
    file_name = request.form.get("file_name")
    total_size = request.form.get("total_size", type=int)

    if file_name is None or total_size is None:
        return jsonify({
            "success": False,
            "message": "Upload details are incomplete."
        }), 400

    # Validate the selected file type before creating an upload session.
    is_allowed_file_type = File.isAllowedFileType(
        file_name
    )

    if not is_allowed_file_type:
        return jsonify({
            "success": False,
            "message": "File type is not allowed."
        }), 400

    # Ask the entity to create the upload session and empty temporary file.
    upload_session = UploadSession.startUpload(
        owner_id,
        file_name,
        total_size
    )

    if upload_session is None:
        return jsonify({
            "success": False,
            "message": "Upload session could not be created."
        }), 400

    return jsonify({
        "success": True,
        "upload_id": upload_session["uploadID"],
        "bytes_uploaded": upload_session["bytesUploaded"],
        "total_size": upload_session["totalSize"]
    })


# Receive one file chunk and pass it to the UploadSession entity for storage.
@upload_bp.route("/upload/chunk", methods=["POST"])
def uploadChunk():

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before uploading a file."
        }), 401

    # Retrieve the upload session, chunk position, and chunk data from the boundary.
    upload_id = request.form.get("upload_id", type=int)
    chunk_start = request.form.get("chunk_start", type=int)
    chunk_file = request.files.get("chunk")

    if upload_id is None or chunk_start is None or chunk_file is None:
        return jsonify({
            "success": False,
            "message": "Upload chunk details are incomplete."
        }), 400

    # Ask the entity to save the chunk and update the saved progress.
    upload_progress = UploadSession.saveChunk(
        upload_id,
        owner_id,
        chunk_file,
        chunk_start
    )

    if upload_progress is None:
        return jsonify({
            "success": False,
            "message": "Upload chunk could not be saved."
        }), 400

    return jsonify({
        "success": True,
        "upload_id": upload_progress["uploadID"],
        "bytes_uploaded": upload_progress["bytesUploaded"],
        "total_size": upload_progress["totalSize"]
    })


# Complete a resumable upload and create the normal temporary file record.
@upload_bp.route("/upload/complete", methods=["POST"])
def completeUploadSession():

    owner_id = session.get("user_id")

    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before completing an upload."
        }), 401

    upload_id = request.form.get("upload_id", type=int)
    file_type = request.form.get("file_type") or "Unknown"

    if upload_id is None:
        return jsonify({
            "success": False,
            "message": "Upload session could not be found."
        }), 400

    # 1. Ask the entity to convert the completed session into a file record[cite: 6].
    file_id = UploadSession.completeUpload(
        upload_id,
        owner_id,
        file_type
    )

    if file_id is None:
        return jsonify({
            "success": False,
            "message": "Upload could not be completed."
        }), 400
   
    return jsonify({
        "success": True,
        "message": "Upload completed, fragmented, and distributed to OCI successfully.",
        "file_id": file_id
    })


# Cancel an incomplete upload session before a file record exists.
@upload_bp.route("/upload/cancel-session/<int:upload_id>", methods=["POST"])
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
