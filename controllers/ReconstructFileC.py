# Import filesystem utilities used to clean up reconstructed temporary files.
import os

# Import Flask components used for routing, sessions, redirects, and JSON responses.
from flask import Blueprint
from flask import jsonify
from flask import redirect
from flask import session
from flask import url_for

# Import entities used in the encrypted file reconstruction workflow.
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


# Reconstruct the encrypted file only when enough valid fragments are available.
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

    # Remove any previous reconstructed temporary file from the same session.
    previous_reconstructed_path = session.get("reconstructed_temp_path")
    cleanupReconstructedTempFile(previous_reconstructed_path)
    session.pop("reconstructed_temp_path", None)
    session.pop("reconstructed_file_id", None)

    # Ask the File entity for the required and total fragment counts.
    reconstruction_data = File.getReconstructionRequirement(
        file_id,
        owner_id
    )

    if reconstruction_data is None:
        return jsonify({
            "success": False,
            "message": "Unable to reconstruct file. File record could not be found."
        }), 404

    required_fragments = reconstruction_data["requiredFragments"]
    total_fragments = reconstruction_data["totalFragments"]
    encrypted_size = reconstruction_data["encryptedSize"]

    # Ask the Fragment entity for stored fragment paths and metadata.
    fragment_records = Fragment.getAvailableFragmentRecords(file_id)

    available_fragments = []

    # Try to retrieve each fragment's physical bytes from its storage node path.
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

    # Ask the Fragment entity to reconstruct the encrypted file using zfec.
    reconstructed_path = Fragment.reconstructFragments(
        file_id,
        available_fragments,
        required_fragments,
        total_fragments,
        encrypted_size
    )

    if reconstructed_path is None:
        return jsonify({
            "success": False,
            "message": "Unable to reconstruct file. Not enough fragments are currently available."
        }), 400

    # Keep the reconstructed encrypted file path for the next processing step.
    session["reconstructed_temp_path"] = reconstructed_path
    session["reconstructed_file_id"] = file_id

    return jsonify({
        "success": True,
        "message": "Encrypted file reconstructed successfully. Preparing file for decryption."
    })


# Remove the reconstructed encrypted file if the user leaves before decryption.
@reconstruct_file_bp.route(
    "/files/reconstruct/cleanup",
    methods=["POST"]
)
def cleanupReconstruction():

    reconstructed_path = session.get("reconstructed_temp_path")

    cleanupReconstructedTempFile(reconstructed_path)

    session.pop("reconstructed_temp_path", None)
    session.pop("reconstructed_file_id", None)

    return "", 204
