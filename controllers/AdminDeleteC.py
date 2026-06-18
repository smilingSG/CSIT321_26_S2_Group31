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
    def deleteUser(user_id: int) -> bool:

        if not UserAccount.checkUserExistsById(user_id):
            return False

        UserAccount.deleteAccount(user_id)

        return True


@admin_delete_bp.route("/user-management/delete/<int:user_id>", methods=["POST"])
def deleteUser(user_id: int):

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    user_deleted = AdminDeleteC.deleteUser(user_id)

    if not user_deleted:
        flash("User not found.", "error")
        return redirect(url_for("admin_search_bp.userManagement"))

    flash("User account deleted successfully.", "success")
    return redirect(url_for("admin_search_bp.userManagement"))
