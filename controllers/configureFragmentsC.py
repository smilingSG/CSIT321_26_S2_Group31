# Import Flask components used for routing, forms, sessions, redirects, and templates.
from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from flask import url_for

# Import entities used to retrieve file details and storage node information.
from entities.File import File
from entities.StorageNode import StorageNode


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

    # Return an error if the file does not exist or does not belong to the user.
    if preview_data is None:
        return "File record could not be found.", 404

    # Display the fragment configuration page with the file information.
    return render_template(
        "fragmentConfiguration.html",
        previewData=preview_data
    )


# Process the fragment configuration submitted by the user.
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

    # Retrieve the total number of fragments, n, from the submitted form.
    total_fragments = request.form.get(
        "total_fragments"
    )

    # Retrieve the required reconstruction threshold, k, from the form.
    required_fragments = request.form.get(
        "required_fragments"
    )

    # Count the storage nodes currently marked as active.
    active_node_count = StorageNode.getActiveStorageNodeCount()

    # Validate the submitted k-of-n configuration.
    validation_error = validateFragmentConfig(
        total_fragments,
        required_fragments,
        active_node_count
    )

    # Redisplay the page with an error if the configuration is invalid.
    if validation_error is not None:

        preview_data = File.getFilePreviewDetails(
            file_id,
            owner_id
        )

        return render_template(
            "fragmentConfiguration.html",
            previewData=preview_data,
            errorMessage=validation_error
        )

    # Save the validated k-of-n configuration in the file record.
    File.updateFragmentConfiguration(
        file_id,
        owner_id,
        int(total_fragments),
        int(required_fragments)
    )

    # Continue to the automatic file encryption stage.
    return redirect(
        url_for(
            "encrypt_file_bp.encryptFile",
            file_id=file_id
        )
    )


# Validate the submitted k-of-n values against the available storage nodes.
def validateFragmentConfig(
    total_fragments,
    required_fragments,
    active_node_count
):

    # Ensure that a total fragment value was submitted.
    if total_fragments is None:
        return "Please enter total fragments."

    # Ensure that a required fragment value was submitted.
    if required_fragments is None:
        return "Please enter required fragments."

    # Convert the submitted form values from strings into integers.
    try:

        total_fragments = int(
            total_fragments
        )

        required_fragments = int(
            required_fragments
        )

    # Reject values that cannot be converted into integers.
    except ValueError:

        return "Fragment values must be numbers."

    # At least two fragments must be generated.
    if total_fragments < 2:
        return (
            "Total fragments must be at least 2."
        )

    # At least one fragment must be required for reconstruction.
    if required_fragments < 1:
        return (
            "Required fragments must be at least 1."
        )

    # The reconstruction threshold cannot exceed the total fragment count.
    if required_fragments > total_fragments:
        return (
            "Required fragments cannot be greater "
            "than total fragments."
        )

    # One active storage node must be available for every generated fragment.
    if total_fragments > active_node_count:
        return (
            "Total fragments cannot be greater "
            "than the number of active storage nodes."
        )

    # Return no error when every validation check passes.
    return None