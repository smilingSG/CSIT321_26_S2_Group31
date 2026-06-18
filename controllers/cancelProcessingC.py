# Import Flask components used for routing, JSON responses, and sessions.
from flask import Blueprint
from flask import jsonify
from flask import session

# Import entities used to remove incomplete processing data.
from entities.File import File
from entities.Fragment import Fragment


# Create the blueprint containing the processing-cancellation route.
cancel_processing_bp = Blueprint(
    "cancel_processing_bp",
    __name__
)


# Cancel processing and remove its temporary files and metadata.
@cancel_processing_bp.route(
    "/upload/process/cancel/<int:file_id>",
    methods=["POST"]
)
def cancelProcessing(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Reject the request if the user is not logged in.
    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before cancelling processing."
        }), 401

    # Confirm that the processing record belongs to the logged-in user.
    file_record = File.getProcessingFileDetails(
        file_id,
        owner_id
    )

    if file_record is None:
        return jsonify({
            "success": False,
            "message": "Processing file record not found."
        }), 404

    # Ask the entities to remove pending fragments and encrypted file data.
    Fragment.deletePendingFragments(file_id)

    file_deleted = File.deleteProcessingFileRecord(
        file_id,
        owner_id
    )

    if not file_deleted:
        return jsonify({
            "success": False,
            "message": "Processing file could not be removed."
        }), 500

    return jsonify({
        "success": True,
        "message": "Processing file removed successfully."
    })
