from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.UserAccount import UserAccount


profile_bp = Blueprint("profile_bp", __name__)


class ProfileC:

    @staticmethod
    def getProfile(user_id: int):

        return UserAccount.getUserDetails(user_id)

    @staticmethod
    def updateProfile(user_id: int,
                      display_name: str,
                      new_password: str,
                      confirm_password: str):

        return UserAccount.updateProfile(
            user_id=user_id,
            display_name=display_name,
            new_password=new_password,
            confirm_password=confirm_password
        )

@profile_bp.route("/profile", methods=["GET", "POST"])
def profilePage():

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    success_message = None
    error_message = None

    if request.method == "POST":
        profile_updated, profile_message = ProfileC.updateProfile(
            user_id=user_id,
            display_name=request.form.get("display_name", ""),
            new_password=request.form.get("new_password", ""),
            confirm_password=request.form.get("confirm_password", "")
        )

        if profile_updated:
            session["username"] = request.form.get("display_name", "").strip()
            success_message = profile_message
        else:
            error_message = profile_message

    user_profile = ProfileC.getProfile(user_id)

    if user_profile is None:
        session.clear()
        return redirect(url_for("login_bp.login"))

    return render_template(
        "profile.html",
        userProfile=user_profile,
        successMessage=success_message,
        errorMessage=error_message
    )
