from flask import Blueprint
from flask import render_template
from flask import redirect
from flask import session
from flask import url_for

from entities.File import File
from entities.Fragment import Fragment


split_file_bp = Blueprint(
    "split_file_bp",
    __name__
)


@split_file_bp.route(
    "/upload/split/<int:file_id>",
    methods=["POST"]
)
def splitFile(file_id: int):

    owner_id = session.get("user_id")

    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    encrypted_file_details = File.getEncryptedFileDetails(
        file_id,
        owner_id
    )

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

    fragment_list = Fragment.splitIntoFragments(
        file_id=encrypted_file_details["file_id"],
        encrypted_temp_path=encrypted_file_details["encrypted_temp_path"],
        total_fragments=encrypted_file_details["total_fragments"],
        required_fragments=encrypted_file_details["required_fragments"]
    )

    if len(fragment_list) != encrypted_file_details["total_fragments"]:
        File.updateFileStatus(
            file_id,
            owner_id,
            "failed"
        )

        processing_data = File.getProcessingSummary(
            file_id,
            owner_id
        )

        return render_template(
            "processing.html",
            processingData=processing_data,
            errorMessage="File splitting failed."
        ), 400

    File.updateFileStatus(
        file_id,
        owner_id,
        "pending_processing"
    )

    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    return render_template(
        "processing.html",
        processingData=processing_data,
        successMessage="File split successfully."
    )
