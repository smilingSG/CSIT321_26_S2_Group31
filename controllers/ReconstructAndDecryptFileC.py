from io import BytesIO

from flask import Blueprint
from flask import jsonify
from flask import redirect
from flask import send_file
from flask import session
from flask import url_for

from entities.File import File
from entities.Fragment import Fragment
from entities.StorageNodeOCI import StorageNode


reconstruct_and_decrypt_file_bp = Blueprint(
    "reconstruct_and_decrypt_file_bp",
    __name__
)


class ReconstructAndDecryptFileC:

    @staticmethod
    def recoverFile(file_id: int, owner_id: int):

        file_record = File.getOwnerDownloadDetails(file_id, owner_id)

        if file_record is None:
            return None

        fragment_paths = Fragment.getAvailableFragments(file_id)
        available_fragments = StorageNode.retrieveFragments(fragment_paths)

        return Fragment.reconstructAndProcessFragments(
            available_fragments,
            file_record["required_fragments"],
            file_record["total_fragments"],
            file_record["encrypted_size"],
            processor=lambda encrypted_data: File.decryptReconstructedData(
                file_record,
                encrypted_data
            )
        )


@reconstruct_and_decrypt_file_bp.route(
    "/files/download/<int:file_id>",
    methods=["GET"]
)
def reconstructAndDecryptFile(file_id: int):

    owner_id = session.get("user_id")

    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    original_file = ReconstructAndDecryptFileC.recoverFile(
        file_id,
        owner_id
    )

    if original_file is None:
        return jsonify({
            "success": False,
            "message": (
                "Unable to recover file. All available fragment "
                "combinations failed."
            )
        }), 400

    return send_file(
        BytesIO(original_file["fileBytes"]),
        as_attachment=True,
        download_name=original_file["fileName"],
        mimetype=original_file["fileType"]
    )
