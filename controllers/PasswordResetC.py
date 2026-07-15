import os
import secrets
import smtplib
from datetime import datetime
from datetime import timedelta
from email.message import EmailMessage
from typing import Optional

from flask import Blueprint
from flask import current_app
from flask import render_template
from flask import request
from flask import url_for

from entities.UserAccount import UserAccount

password_reset_bp = Blueprint("password_reset_bp", __name__)


class PasswordResetC:

    @staticmethod
    def requestReset(email: str) -> tuple[bool, Optional[str]]:

        user_account = UserAccount.getByEmail(email)

        if user_account is None or user_account["account_status"] != "active":
            return True, None

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=30)

        UserAccount.createPasswordResetToken(
            user_id=user_account["user_id"],
            token=token,
            expires_at=expires_at
        )

        reset_url = url_for(
            "password_reset_bp.resetPassword",
            email=email,
            token=token,
            _external=True
        )

        return PasswordResetC.sendResetEmail(
            to_email=email,
            username=user_account["username"],
            token=token,
            reset_url=reset_url
        )

    @staticmethod
    def sendResetEmail(to_email: str,
                       username: str,
                       token: str,
                       reset_url: str) -> tuple[bool, Optional[str]]:

        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_username = os.environ.get("SMTP_USERNAME")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        smtp_sender = os.environ.get("SMTP_FROM", smtp_username)
        smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

        if not smtp_host or not smtp_sender:
            current_app.logger.warning(
                "Password reset email is not configured. Reset token for %s: %s",
                to_email,
                token
            )
            return False, "Email service is not configured. Reset token was written to the server log for local testing."

        message = EmailMessage()
        message["Subject"] = "Lazarus password reset"
        message["From"] = smtp_sender
        message["To"] = to_email
        message.set_content(f"""
Hi {username},

We received a request to reset your Lazarus password.

Verification code:
{token}

Reset link:
{reset_url}

This code expires in 30 minutes. If you did not request this, you can ignore this email.
""".strip())

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_use_tls:
                    server.starttls()
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            current_app.logger.warning("Password reset email failed: %s", exc)
            return False, "We could not send the verification email. Please try again later."

        return True, None

    @staticmethod
    def updatePassword(email: str,
                       token: str,
                       new_password: str) -> bool:

        return UserAccount.resetPassword(
            email=email,
            token=token,
            new_password=new_password
        )


@password_reset_bp.route("/reset-password", methods=["GET", "POST"])
def resetPassword():

    if request.method == "GET":
        return render_template(
            "reset_password.html",
            email=request.args.get("email", ""),
            token=request.args.get("token", "")
        )

    action = request.form.get("action", "")
    email = request.form.get("email", "").strip()
    token = request.form.get("token", "").strip()
    new_password = request.form.get("new_password", "")

    if action == "send_code":
        if email == "":
            return render_template(
                "reset_password.html",
                error="Please enter your registered email address.",
                email=email,
                token=token
            ), 400

        email_sent, email_error = PasswordResetC.requestReset(email)

        if not email_sent:
            return render_template(
                "reset_password.html",
                error=email_error,
                email=email,
                token=token
            ), 503

        return render_template(
            "reset_password.html",
            success="If that email belongs to an active account, a verification code has been sent.",
            email=email
        )

    if email == "" or token == "" or new_password == "":
        return render_template(
            "reset_password.html",
            error="Please enter your email, verification code, and new password.",
            email=email,
            token=token
        ), 400

    if len(new_password) < 8:
        return render_template(
            "reset_password.html",
            error="Password must be at least 8 characters long.",
            email=email,
            token=token
        ), 400

    password_updated = PasswordResetC.updatePassword(
        email=email,
        token=token,
        new_password=new_password
    )

    if not password_updated:
        return render_template(
            "reset_password.html",
            error="The verification code is invalid or expired.",
            email=email,
            token=token
        ), 400

    return render_template(
        "reset_password.html",
        success="Password updated successfully. You can now log in with your new password.",
        email=email
    )
