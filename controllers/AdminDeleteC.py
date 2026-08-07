from flask import Blueprint
from flask import flash
from flask import redirect
from flask import session
from flask import url_for

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

        return UserAccount.deleteAccount(
            user_id=user_id,
            replacement_user_id=administrator_id
        )


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
