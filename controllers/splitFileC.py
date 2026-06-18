# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint
from flask import render_template
from flask import redirect
from flask import session
from flask import url_for

# Import the entities used to retrieve file details and create fragments.
from entities.File import File
from entities.Fragment import Fragment


# Create the blueprint containing the file-splitting route.
split_file_bp = Blueprint(
    "split_file_bp",
    __name__
)


# Split an encrypted file into the configured number of fragments.
@split_file_bp.route(
    "/upload/split/<int:file_id>",
    methods=["POST"]
)
def splitFile(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Retrieve the encrypted file path and its k-of-n configuration.
    encrypted_file_details = File.getEncryptedFileDetails(
        file_id,
        owner_id
    )

    # Stop processing if the encrypted file details cannot be found.
    if encrypted_file_details is None:
        processing_data = File.getProcessingSummary(
            file_id,
            owner_id
        )

        return render_template(
            "processing.html",
            processingData=processing_data,
            errorMessage="Encrypted file details could not be found."
        ), 400

    # Use zfec to split the encrypted file into the configured fragments.
    fragment_list = Fragment.splitIntoFragments(
        file_id=encrypted_file_details["file_id"],
        encrypted_temp_path=encrypted_file_details["encrypted_temp_path"],
        total_fragments=encrypted_file_details["total_fragments"],
        required_fragments=encrypted_file_details["required_fragments"]
    )

    # Treat the operation as failed if the expected fragments were not created.
    if len(fragment_list) != encrypted_file_details["total_fragments"]:

        # Record the failed processing status in the database.
        File.updateFileStatus(
            file_id,
            owner_id,
            "failed"
        )

        # Retrieve updated information for redisplaying the processing page.
        processing_data = File.getProcessingSummary(
            file_id,
            owner_id
        )

        return render_template(
            "processing.html",
            processingData=processing_data,
            errorMessage="File splitting failed."
        ), 400

    # Keep the file pending until its fragments are moved into storage nodes.
    File.updateFileStatus(
        file_id,
        owner_id,
        "pending_processing"
    )

    # Retrieve updated information for the processing page.
    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    # Redisplay the processing page and report successful splitting.
    return render_template(
        "processing.html",
        processingData=processing_data,
        successMessage="File split successfully."
    )