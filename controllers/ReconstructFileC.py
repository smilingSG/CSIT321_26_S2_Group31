# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

# Import entities used in the reconstruction workflow.
from entities.File import File
from entities.Fragment import Fragment


# Create the blueprint containing the reconstruction routes.
reconstruct_file_bp = Blueprint(
    "reconstruct_file_bp",
    __name__
)


# Display the reconstruction page for a processed file.
@reconstruct_file_bp.route(
    "/files/reconstruct/<int:file_id>",
    methods=["GET"]
)
def reconstructionPage(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Ask the File entity for the file's k-of-n reconstruction requirement.
    reconstruction_data = File.getReconstructionRequirement(
        file_id,
        owner_id
    )

    if reconstruction_data is None:
        return "Reconstruction file record could not be found.", 404

    return render_template(
        "reconstruction.html",
        reconstructionData=reconstruction_data
    )


# Reconstruct the encrypted file only when enough valid fragments are available.
@reconstruct_file_bp.route(
    "/files/reconstruct/<int:file_id>",
    methods=["POST"]
)
def reconstructFile(file_id: int):

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

    # Ask the Fragment entity for readable fragments on active storage nodes.
    available_fragments = Fragment.getAvailableFragments(file_id)

    if len(available_fragments) < required_fragments:
        return render_template(
            "reconstruction.html",
            reconstructionData=reconstruction_data,
            errorMessage="Insufficient fragments. Required: "
                         + str(required_fragments)
                         + ", available: "
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
        return render_template(
            "reconstruction.html",
            reconstructionData=reconstruction_data,
            errorMessage="File reconstruction failed."
        ), 400

    return render_template(
        "reconstruction.html",
        reconstructionData=reconstruction_data,
        successMessage="Encrypted file reconstructed successfully.",
        reconstructedPath=reconstructed_path
    )
