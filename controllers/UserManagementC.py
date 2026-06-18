from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for

from entities.UserAccount import UserAccount

user_management_bp = Blueprint("user_management_bp", __name__)


def getPostLoginRedirect(role: str) -> str:

    if role == "user_admin":
        return url_for("user_management_bp.userAdminDashboard")

    return url_for("dashboard_bp.dashboard")


class UserManagementC:

    @staticmethod
    def getUserManagementData():

        user_accounts = UserAccount.getAllUserAccounts()

        return {
            "users": [
                {
                    "userID": user_account["user_id"],
                    "username": user_account["username"],
                    "email": user_account["email"],
                    "role": UserManagementC.formatRole(user_account["role"]),
                    "accountStatus": UserManagementC.formatStatus(
                        user_account["account_status"]
                    ),
                    "isSuspended": user_account["account_status"] == "suspended"
                }
                for user_account in user_accounts
            ]
        }

    @staticmethod
    def formatRole(role: str) -> str:

        role_labels = {
            "user": "User",
            "user_admin": "User Admin",
            "system_admin": "System Admin"
        }

        return role_labels.get(role, role)

    @staticmethod
    def formatStatus(account_status: str) -> str:

        status_labels = {
            "active": "Active",
            "suspended": "Suspended"
        }

        return status_labels.get(account_status, account_status)


@user_management_bp.route("/user-admin-dashboard")
def userAdminDashboard():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    return render_template(
        "AdminDashboard.html",
        username=session.get("username")
    )
