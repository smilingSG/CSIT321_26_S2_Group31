from flask import Blueprint
from flask import flash
from flask import redirect
from flask import session
from flask import url_for

from entities.File import File
from entities.Fragment import Fragment
from entities.ShareLink import ShareLink
from entities.StorageNodeOCI import StorageNode
from entities.SystemSetting import SystemSetting
from entities.UploadSession import UploadSession
from entities.UserAccount import UserAccount

admin_delete_bp = Blueprint("admin_delete_bp", __name__)


def getPostLoginRedirect(role: str) -> str:

    if role == "user_admin":
        return url_for("user_management_bp.userAdminDashboard")

    return url_for("dashboard_bp.dashboard")


class AdminDeleteC:

    @staticmethod
    def deleteUser(user_id: int,
                   administrator_id: int) -> bool:

        if not UserAccount.checkUserExistsById(user_id):
            return False

        try:
            file_ids = File.getFileIdsByOwner(user_id)
            fragment_paths = Fragment.getStoredFragmentPathsByFileIds(file_ids)
            node_ids = list({
                fragment_path["node_id"]
                for fragment_path in fragment_paths
                if fragment_path.get("node_id") is not None
            })
            node_paths = StorageNode.getStorageNodePaths(node_ids)

            for fragment_path in fragment_paths:
                fragment_path["node_path"] = node_paths.get(
                    fragment_path.get("node_id")
                )

            if not ShareLink.deleteShareLinksForUser(user_id, file_ids):
                return False
            if not UploadSession.deleteUploadSessionsForUser(user_id, file_ids):
                return False
            if not StorageNode.deleteStoredFragments(fragment_paths):
                return False
            if not Fragment.deleteFragmentsByFileIds(file_ids):
                return False
            if not File.deleteFilesByOwner(user_id):
                return False
            if not UserAccount.deletePasswordResetTokens(user_id):
                return False
            if not SystemSetting.reassignUpdatedBy(user_id, administrator_id):
                return False

            return UserAccount.deleteAccount(
                user_id=user_id,
                replacement_user_id=administrator_id
            )
        except Exception:
            return False


@admin_delete_bp.route("/user-management/delete/<int:user_id>", methods=["POST"])
def deleteUser(user_id: int):

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    administrator_id = session.get("user_id")

    if user_id == administrator_id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin_search_bp.userManagement"))

    user_deleted = AdminDeleteC.deleteUser(
        user_id=user_id,
        administrator_id=administrator_id
    )

    if not user_deleted:
        flash("User could not be deleted.", "error")
        return redirect(url_for("admin_search_bp.userManagement"))

    flash("User account deleted successfully.", "success")
    return redirect(url_for("admin_search_bp.userManagement"))
