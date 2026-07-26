# Import Flask components used for routing, forms, sessions, redirects, and templates.
from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from flask import url_for

# Import entities used to retrieve file details and storage node information.
from entities.File import File

# local
# from entities.StorageNodeLocal import StorageNode

# OCI
from entities.StorageNodeOCI import StorageNode


# Create the blueprint containing the fragment configuration routes.
configure_fragments_bp = Blueprint(
    "configure_fragments_bp",
    __name__
)


# Display the fragment configuration page for the selected file.
@configure_fragments_bp.route(
    "/upload/fragments/<int:file_id>",
    methods=["GET"]
)
def fragmentConfigurationPage(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Retrieve the file information needed by the configuration page.
    preview_data = File.getFilePreviewDetails(
        file_id,
        owner_id
    )

    if preview_data is None:
        return "File record could not be found.", 404

    active_node_count = StorageNode.getActiveStorageNodeCount()

    # Display the fragment configuration page with the file information.
    return render_template(
        "fragmentConfiguration.html",
        previewData=preview_data,
        activeNodeCount=active_node_count
    )


# Pass the submitted k-of-n configuration to the File entity.
@configure_fragments_bp.route(
    "/upload/fragments/<int:file_id>",
    methods=["POST"]
)
def configureFragments(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Retrieve the submitted n and k values from the boundary.
    total_fragments = request.form.get(
        "total_fragments"
    )

    required_fragments = request.form.get(
        "required_fragments"
    )

    # Retrieve the active-node count required by the entity's validation.
    active_node_count = StorageNode.getActiveStorageNodeCount()

    # Ask the File entity to validate and save the configuration.
    validation_error = File.updateFragmentConfiguration(
        file_id,
        owner_id,
        total_fragments,
        required_fragments,
        active_node_count
    )

    if validation_error is not None:
        preview_data = File.getFilePreviewDetails(
            file_id,
            owner_id
        )

        return render_template(
            "fragmentConfiguration.html",
            previewData=preview_data,
            activeNodeCount=active_node_count,
            errorMessage=validation_error
        )

    # Continue to the automatic file-encryption stage.
    return redirect(
        url_for(
            "encrypt_file_bp.encryptFile",
            file_id=file_id
        )
    )
