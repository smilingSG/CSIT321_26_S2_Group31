# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint, render_template, redirect, session, url_for, send_file

# Import the File entity used to retrieve file preview information.
from entities.File import File


# Create the blueprint containing the file preview route.
preview_bp = Blueprint("preview_bp", __name__)


# Display the preview page for the selected temporary uploaded file.
@preview_bp.route("/upload/preview/<int:file_id>", methods=["GET"])
def generatePreview(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Retrieve preview information for a file belonging to the logged-in user.
    preview_data = File.getFilePreviewDetails(
        file_id,
        owner_id
    )

    # Return an error if the file does not exist or belongs to another user.
    if preview_data is None:
        return "Preview data could not be found.", 404

    # Display the preview page with the retrieved file information.
    return render_template(
        "preview.html",
        previewData=preview_data
    )


# Serve the temporary uploaded file so the preview boundary can display it.
@preview_bp.route("/upload/preview-file/<int:file_id>", methods=["GET"])
def previewUploadedFile(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Confirm that the temporary file belongs to the logged-in user.
    file_record = File.getTempFileById(
        file_id,
        owner_id
    )

    # Return an error if the file does not exist or belongs to another user.
    if file_record is None:
        return "Preview file could not be found.", 404

    # Return the temporary upload as an inline browser preview where supported.
    return send_file(
        file_record["temp_upload_path"],
        as_attachment=False,
        download_name=file_record["stored_filename"]
    )
