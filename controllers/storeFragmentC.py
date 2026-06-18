# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

# Import entities used to manage files, fragments, and storage nodes.
from entities.File import File
from entities.Fragment import Fragment
from entities.StorageNode import StorageNode


# Create the blueprint containing the fragment-storage route.
store_fragment_bp = Blueprint(
    "store_fragment_bp",
    __name__
)


# Store each generated fragment in a separate active storage node.
@store_fragment_bp.route(
    "/upload/store-fragments/<int:file_id>",
    methods=["POST"]
)
def storeFragments(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Retrieve the processing record belonging to the logged-in user.
    file_record = File.getProcessingFileDetails(
        file_id,
        owner_id
    )

    # Return an error if the file does not exist or belongs to another user.
    if file_record is None:
        return "Processing file record not found.", 404

    # Only allow storage after encryption and fragmentation are complete.
    if file_record["file_status"] != "pending_processing":
        return renderStorageFailure(
            file_id,
            owner_id,
            "File is not ready for fragment storage."
        )

    # Retrieve the generated fragment records for the selected file.
    fragment_list = Fragment.getFragmentList(file_id)

    # Retrieve the expected fragment count and other processing information.
    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    # Ensure that every expected fragment record exists before storage begins.
    if (
        processing_data is None
        or len(fragment_list) != processing_data["totalFragments"]
    ):
        return renderStorageFailure(
            file_id,
            owner_id,
            "The complete fragment list could not be found."
        )

    # Retrieve active storage nodes, ordered using the entity's selection rule.
    active_node_list = StorageNode.getActiveStorageNodes()

    # Ensure that one active node is available for every fragment.
    if len(active_node_list) < len(fragment_list):
        return renderStorageFailure(
            file_id,
            owner_id,
            "There are not enough active storage nodes."
        )

    # Select one different active storage node for each fragment.
    selected_nodes = active_node_list[:len(fragment_list)]

    # Track stored files so they can be removed if part of the operation fails.
    stored_fragment_paths = []

    try:
        # Pair every fragment with one selected storage node.
        for fragment_data, storage_node in zip(
            fragment_list,
            selected_nodes
        ):
            # Copy the temporary fragment into the selected node folder.
            stored_fragment_path = StorageNode.storeFragment(
                fragment_data,
                storage_node["node_path"]
            )

            # Stop processing if the physical fragment could not be stored.
            if stored_fragment_path is None:
                raise OSError("Fragment could not be stored.")

            # Remember the stored path for possible failure cleanup.
            stored_fragment_paths.append(stored_fragment_path)

            # Update the fragment record with its node and permanent path.
            fragment_updated = Fragment.updateFragmentStorage(
                fragment_data["fragment_id"],
                storage_node["node_id"],
                stored_fragment_path
            )

            # Stop processing if the fragment metadata update fails.
            if not fragment_updated:
                raise RuntimeError(
                    "Fragment metadata could not be updated."
                )

    # Roll back stored files and metadata if any storage step fails.
    except (OSError, RuntimeError):

        # Remove fragments already copied into storage nodes.
        for stored_fragment_path in stored_fragment_paths:
            StorageNode.deleteStoredFragment(
                stored_fragment_path
            )

        # Restore the fragment records to their temporary storage state.
        Fragment.restorePendingFragmentStorage(
            fragment_list
        )

        # Mark the file as failed and redisplay the processing page.
        return renderStorageFailure(
            file_id,
            owner_id,
            "Fragment storage failed."
        )

    # Delete temporary fragment files after permanent storage succeeds.
    Fragment.deleteTemporaryFragmentFiles(file_id)

    # Delete the temporary encrypted file because it is no longer needed.
    File.deleteEncryptedTemporaryFile(
        file_id,
        owner_id
    )

    # Mark the complete file-processing workflow as successful.
    File.updateFileStatus(
        file_id,
        owner_id,
        "processed"
    )

    # Retrieve the updated processing information.
    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    # Redisplay the processing page with a success message.
    return render_template(
        "processing.html",
        processingData=processing_data,
        successMessage="Fragments stored separately."
    )


# Mark fragment storage as failed and display the processing error.
def renderStorageFailure(file_id: int,
                         owner_id: int,
                         error_message: str):

    # Update the file record to indicate processing failure.
    File.updateFileStatus(
        file_id,
        owner_id,
        "failed"
    )

    # Retrieve the latest processing information for the page.
    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    # Return a direct error if the processing information is unavailable.
    if processing_data is None:
        return error_message, 404

    # Redisplay the processing page with the storage error.
    return render_template(
        "processing.html",
        processingData=processing_data,
        errorMessage=error_message
    ), 400