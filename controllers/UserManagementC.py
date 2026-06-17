from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from controllers.AdminSearchC import AdminSearchC
from controllers.LoginC import getPostLoginRedirect
from entities.UserAccount import UserAccount

user_management_bp = Blueprint("user_management_bp", __name__)


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
        "AdminSearchPg.html",
        username=session.get("username")
    )


@user_management_bp.route("/user-management")
def userManagement():

    if session.get("user_id") is None:
        return redirect(url_for("login_bp.login"))

    if session.get("role") != "user_admin":
        return redirect(getPostLoginRedirect(session.get("role")))

    search_query: str = request.args.get("query", "").strip()

    user_management_data = AdminSearchC.searchUser(search_query)

    return render_template(
        "UserManagementPg.html",
        data=user_management_data,
        username=session.get("username")
    )
