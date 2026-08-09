from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

from entities.ShareLink import ShareLink
from entities.File import File


view_shared_users_bp = Blueprint("view_shared_users_bp", __name__)


class ViewSharedUsersC:

    @staticmethod
    def viewSharedUsers(file_id: int,
                        user_id: int):

        if not File.verifyFileOwnership(file_id=file_id, owner_id=user_id):
            return None, "Unable to view shared users for this file."
        return ShareLink.getSharedUsers(file_id), None


@view_shared_users_bp.route("/shared/users/<int:file_id>", methods=["GET"])
def viewSharedUsers(file_id: int):

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    shared_user_list, error_message = ViewSharedUsersC.viewSharedUsers(
        file_id=file_id,
        user_id=user_id
    )

    return render_template(
        "sharedUsers.html",
        fileID=file_id,
        sharedUsers=shared_user_list or [],
        errorMessage=error_message
    )
