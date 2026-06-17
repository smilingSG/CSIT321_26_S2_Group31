from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from controllers.LoginC import getPostLoginRedirect
from entities.UserAccount import UserAccount

admin_search_bp = Blueprint("admin_search_bp", __name__)


class AdminSearchC:

    @staticmethod
    def searchUser(query: str):

        if query == "":
            user_accounts = UserAccount.getAllUserAccounts()
        else:
            user_accounts = UserAccount.findUser(query)

        return {
            "query": query,
            "hasSearch": query != "",
            "hasResults": len(user_accounts) > 0,
            "users": [
                {
                    "userID": user_account["user_id"],
                    "username": user_account["username"],
                    "email": user_account["email"],
                    "role": AdminSearchC.formatRole(user_account["role"]),
                    "accountStatus": AdminSearchC.formatStatus(
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


@admin_search_bp.route("/user-management")
def searchUser():

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