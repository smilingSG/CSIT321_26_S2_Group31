from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

from entities.File import File
from entities.Fragment import Fragment
from entities.StorageNode import StorageNode


store_fragment_bp = Blueprint(
    "store_fragment_bp",
    __name__
)


@store_fragment_bp.route(
    "/upload/store-fragments/<int:file_id>",
    methods=["POST"]
)
def storeFragments(file_id: int):

    owner_id = session.get("user_id")

    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    file_record = File.getProcessingFileDetails(
        file_id,
        owner_id
    )

    if (
        file_record is None
        or file_record["file_status"] != "pending_processing"
    ):
        return renderStorageFailure(
            file_id,
            owner_id,
            "File is not ready for fragment storage."
        )

    fragment_list = Fragment.getFragmentList(file_id)

    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    if (
        processing_data is None
        or len(fragment_list) != processing_data["totalFragments"]
    ):
        return renderStorageFailure(
            file_id,
            owner_id,
            "The complete fragment list could not be found."
        )

    active_node_list = StorageNode.getActiveStorageNodes()

    if len(active_node_list) < len(fragment_list):
        return renderStorageFailure(
            file_id,
            owner_id,
            "There are not enough active storage nodes."
        )

    selected_nodes = active_node_list[:len(fragment_list)]
    stored_fragment_paths = []

    try:
        for fragment_data, storage_node in zip(
            fragment_list,
            selected_nodes
        ):
            stored_fragment_path = StorageNode.storeFragment(
                fragment_data,
                storage_node["node_path"]
            )

            if stored_fragment_path is None:
                raise OSError("Fragment could not be stored.")

            stored_fragment_paths.append(stored_fragment_path)

            fragment_updated = Fragment.updateFragmentStorage(
                fragment_data["fragment_id"],
                storage_node["node_id"],
                stored_fragment_path
            )

            if not fragment_updated:
                raise RuntimeError(
                    "Fragment metadata could not be updated."
                )

    except (OSError, RuntimeError):
        for stored_fragment_path in stored_fragment_paths:
            StorageNode.deleteStoredFragment(
                stored_fragment_path
            )

        Fragment.restorePendingFragmentStorage(
            fragment_list
        )

        return renderStorageFailure(
            file_id,
            owner_id,
            "Fragment storage failed."
        )

    Fragment.deleteTemporaryFragmentFiles(file_id)

    File.deleteEncryptedTemporaryFile(
        file_id,
        owner_id
    )

    File.updateFileStatus(
        file_id,
        owner_id,
        "processed"
    )

    processing_data = File.getProcessingSummary(
        file_id,
        owner_id
    )

    return render_template(
        "processing.html",
        processingData=processing_data,
        successMessage="Fragments stored separately."
    )


def renderStorageFailure(file_id: int,
                         owner_id: int,
                         error_message: str):

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
        errorMessage=error_message
    ), 400
