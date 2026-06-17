from flask import Blueprint
from flask import flash
from flask import redirect
from flask import session
from flask import url_for

from controllers.LoginC import getPostLoginRedirect
from entities.UserAccount import UserAccount

admin_suspend_bp = Blueprint("admin_suspend_bp", __name__)


class AdminSuspendC:

    @staticmethod
    def suspendUser(user_id: int) -> bool:

        if not UserAccount.checkUserExistsById(user_id):
            return False

        account_status = UserAccount.getStatus(user_id)

        if account_status == "suspended":
            return False

        UserAccount.setStatus(
            user_id=user_id,
            account_status="suspended"
        )

        return True

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


@admin_suspend_bp.route("/user-management/suspend/<int:user_id>", methods=["POST"])
def suspendUser(user_id: int):

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    user_suspended = AdminSuspendC.suspendUser(user_id)

    if not user_suspended:
        flash("User not found or already suspended.", "error")
        return redirect(url_for("user_management_bp.userManagement"))

    flash("User account suspended successfully.", "success")
    return redirect(url_for("user_management_bp.userManagement"))


@admin_suspend_bp.route("/user-management/unsuspend/<int:user_id>", methods=["POST"])
def unsuspendUser(user_id: int):

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    user_unsuspended = AdminSuspendC.unsuspendUser(user_id)

    if not user_unsuspended:
        flash("User not found or already active.", "error")
        return redirect(url_for("user_management_bp.userManagement"))

    flash("User account unsuspended successfully.", "success")
    return redirect(url_for("user_management_bp.userManagement"))
