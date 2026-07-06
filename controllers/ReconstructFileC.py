# Import filesystem utilities used to clean up reconstructed temporary files.
import os
# Import BytesIO so decrypted data can be downloaded without another temp file.
from io import BytesIO

# Import Flask components used for routing, sessions, redirects, and file download.
from flask import Blueprint
from flask import after_this_request
from flask import redirect
from flask import send_file
from flask import session
from flask import url_for

# Import entities used in the reconstruction and decryption workflow.
from entities.File import File
from entities.Fragment import Fragment
from entities.StorageNode import StorageNode


# Create the blueprint containing the reconstruction route.
reconstruct_file_bp = Blueprint(
    "reconstruct_file_bp",
    __name__
)


# Delete a reconstructed temporary file if it still exists.
def cleanupReconstructedTempFile(reconstructed_path: str) -> None:

    if reconstructed_path is None:
        return

    if os.path.exists(reconstructed_path):
        try:
            os.remove(reconstructed_path)
        except OSError:
            pass


# Reconstruct and decrypt the file only when enough valid fragments are available.
@reconstruct_file_bp.route(
    "/files/reconstruct/<int:file_id>",
    methods=["GET"]
)
@reconstruct_file_bp.route(
    "/files/download/<int:file_id>",
    methods=["GET"]
)
def reconstructionPage(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Ask the File entity for the required and total fragment counts.
    reconstruction_data = File.getReconstructionRequirement(
        file_id,
        owner_id
    )

    if reconstruction_data is None:
        return "Reconstruction file record could not be found.", 404

    required_fragments = reconstruction_data["requiredFragments"]
    total_fragments = reconstruction_data["totalFragments"]
    encrypted_size = reconstruction_data["encryptedSize"]

    # Ask the Fragment entity for fragment metadata on active storage nodes.
    fragment_records = Fragment.getAvailableFragmentRecords(file_id)

    if len(fragment_records) < required_fragments:
        return (
            "Insufficient fragments. Required: "
            + str(required_fragments)
            + ", available: "
            + str(len(fragment_records))
            + "."
        ), 400

    available_fragments = []

    # Retrieve each selected fragment's physical bytes from its storage node path.
    for fragment_record in fragment_records:
        fragment_bytes = StorageNode.retrieveFragment(
            fragment_record["fragment_path"]
        )

        if fragment_bytes is None:
            continue

        available_fragments.append({
            "fragment_id": fragment_record["fragment_id"],
            "file_id": fragment_record["file_id"],
            "fragment_number": fragment_record["fragment_number"],
            "fragment_path": fragment_record["fragment_path"],
            "node_id": fragment_record["node_id"],
            "share_number": fragment_record["fragment_number"] - 1,
            "fragment_bytes": fragment_bytes
        })

        if len(available_fragments) == required_fragments:
            break

    if len(available_fragments) < required_fragments:
        return (
            "Insufficient readable fragments. Required: "
            + str(required_fragments)
            + ", readable: "
            + str(len(available_fragments))
            + "."
        ), 400

    # Ask the Fragment entity to reconstruct the encrypted file using zfec.
    reconstructed_path = Fragment.reconstructFragments(
        file_id,
        available_fragments,
        required_fragments,
        total_fragments,
        encrypted_size
    )

    if reconstructed_path is None:
        return "File reconstruction failed.", 400

    # Delete the reconstructed temporary file after Flask finishes the response.
    @after_this_request
    def removeReconstructedTempFile(response):
        cleanupReconstructedTempFile(reconstructed_path)
        return response

    try:
        # Ask the File entity to decrypt the reconstructed encrypted file.
        decrypted_file_data = File.decryptReconstructedFile(
            file_id,
            owner_id,
            reconstructed_path
        )

        if decrypted_file_data is None:
            cleanupReconstructedTempFile(reconstructed_path)
            return (
                "File decryption failed. The file may be corrupted or tampered with."
            ), 400

        # Send only the original decrypted file to the browser.
        return send_file(
            BytesIO(decrypted_file_data),
            as_attachment=True,
            download_name=reconstruction_data["fileName"],
            mimetype="application/octet-stream"
        )

    except Exception:
        cleanupReconstructedTempFile(reconstructed_path)
        raise
