# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint
from flask import render_template
from flask import redirect
from flask import session
from flask import url_for

# Import the File entity used for encryption and file information.
from entities.File import File


# Create the blueprint containing the file encryption route.
encrypt_file_bp = Blueprint(
    "encrypt_file_bp",
    __name__
)


# Automatically encrypt the selected file and display the processing page.
@encrypt_file_bp.route(
    "/upload/process/<int:file_id>",
    methods=["GET"]
)
def encryptFile(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Encrypt the temporary file belonging to the logged-in user.
    encryption_success = File.encryptFile(
        file_id,
        owner_id
    )

    # Stop processing if the file could not be encrypted.
    if encryption_success is False:
        return "File encryption failed.", 400

    # Retrieve the information required by the processing page.
    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    # Return an error if the processing information cannot be retrieved.
    if processing_data is None:
        return "Processing summary could not be found.", 404

    # Display the processing page with the encrypted file information.
    return render_template(
        "processing.html",
        processingData=processing_data
    )