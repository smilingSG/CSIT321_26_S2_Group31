# Import Flask components used for routing, JSON responses, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import session

# Import entities used by the processed file deletion flow.
from entities.File import File
from entities.Fragment import Fragment
from entities.ShareLink import ShareLink
from entities.StorageNodeOCI import StorageNode
from entities.UploadSession import UploadSession


# Create the blueprint containing the file-management deletion route.
delete_from_file_mgmt_bp = Blueprint(
    "delete_from_file_mgmt_bp",
    __name__
)


# Process a request to delete a processed file from the file-management page.
@delete_from_file_mgmt_bp.route(
    "/files/delete/<int:file_id>",
    methods=["POST"]
)
def deleteFromFileMgmt(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before deleting a file."
        }), 401

    # Confirm that the processed file belongs to the logged-in user.
    file_delete_details = File.getFileDeleteDetails(
        file_id,
        owner_id
    )

    if file_delete_details is None:
        return jsonify({
            "success": False,
            "message": "Unable to delete file."
        }), 404

    # Retrieve stored fragment paths before database records are removed.
    fragment_paths = Fragment.getStoredFragmentPaths(file_id)

    # Delete related records and stored objects before deleting the main file record.
    share_links_deleted = ShareLink.deleteShareLinks(file_id)
    upload_sessions_deleted = UploadSession.deleteUploadSessions(file_id)
    stored_fragments_deleted = StorageNode.deleteStoredFragments(fragment_paths)
    fragments_deleted = False
    file_record_deleted = False

    if (
        share_links_deleted
        and upload_sessions_deleted
        and stored_fragments_deleted
    ):
        fragments_deleted = Fragment.deleteFragments(file_id)

    if fragments_deleted:
        file_record_deleted = File.deleteFileRecord(
            file_id,
            owner_id
        )

    if not file_record_deleted:
        return jsonify({
            "success": False,
            "message": "Unable to delete file."
        }), 400

    return jsonify({
        "success": True,
        "message": "File deleted successfully."
    })
