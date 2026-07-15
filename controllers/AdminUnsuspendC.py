from flask import Blueprint
from flask import flash
from flask import redirect
from flask import session
from flask import url_for

from entities.UserAccount import UserAccount

admin_unsuspend_bp = Blueprint("admin_unsuspend_bp", __name__)


def getPostLoginRedirect(role: str) -> str:

    if role == "user_admin":
        return url_for("user_management_bp.userAdminDashboard")

    return url_for("dashboard_bp.dashboard")


class AdminUnsuspendC:

    @staticmethod
    def unsuspendUser(user_id: int) -> bool:

        if not UserAccount.checkUserExistsById(user_id):
            return False

        account_status = UserAccount.getStatus(user_id)

        if account_status == "active":
            return False

        UserAccount.setStatus(
            user_id=user_id,
            account_status="active"
        )

        return True


@admin_unsuspend_bp.route("/user-management/unsuspend/<int:user_id>", methods=["POST"])
def unsuspendUser(user_id: int):

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    user_unsuspended = AdminUnsuspendC.unsuspendUser(user_id)

    if not user_unsuspended:
        flash("User not found or already active.", "error")
        return redirect(url_for("admin_search_bp.userManagement"))

    flash("User account unsuspended successfully.", "success")
    return redirect(url_for("admin_search_bp.userManagement"))
