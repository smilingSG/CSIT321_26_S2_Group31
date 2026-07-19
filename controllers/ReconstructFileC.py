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

# local
# from entities.StorageNodeLocal import StorageNode

# OCI
from entities.StorageNodeOCI import StorageNode



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
def reconstructFile(file_id: int):

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

    # Ask the File entity for the reconstruction requirements.
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

    # Ask the Fragment entity for available stored fragment paths.
    available_fragment_paths = Fragment.getAvailableFragments(file_id)

    # Ask the StorageNode entity to retrieve readable fragment bytes from the paths.
    available_fragments = StorageNode.retrieveFragments(
        available_fragment_paths
    )

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
