from entities.UserAccount import UserAccount


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
