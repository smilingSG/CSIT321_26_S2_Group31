from typing import Optional

import os
import secrets
import smtplib
from datetime import datetime
from datetime import timedelta
from email.message import EmailMessage

from flask import Blueprint
from flask import current_app
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from entities.UserAccount import UserAccount

register_bp = Blueprint("register_bp", __name__)


class RegisterC:

    @staticmethod
    def register(username: str,
                 email: str,
                 password: str) -> tuple[bool, Optional[str]]:

        if UserAccount.checkUserExists(
            username=username,
            email=email
        ):
            return False, "Account already exists."

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=30)

        verification_created = UserAccount.createRegistrationVerification(
            username=username,
            email=email,
            password=password,
            role="user",
            token=token,
            expires_at=expires_at
        )

        if not verification_created:
            return False, "Username or password does not meet the current policy."

        verification_url = url_for(
            "register_bp.verifyAccount",
            username=username,
            token=token,
            _external=True
        )

        return RegisterC.sendRegistrationEmail(
            email=email,
            username=username,
            token=token,
            verification_url=verification_url
        )

    @staticmethod
    def sendRegistrationEmail(email: str,
                              username: str,
                              token: str,
                              verification_url: str) -> tuple[bool, Optional[str]]:

        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_username = os.environ.get("SMTP_USERNAME")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        smtp_sender = os.environ.get("SMTP_FROM", smtp_username)
        smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

        if not smtp_host or not smtp_sender:
            current_app.logger.warning(
                "Registration email is not configured. Verification token for %s: %s",
                email,
                token
            )
            return False, "Email service is not configured. Verification token was written to the server log for local testing."

        message = EmailMessage()
        message["Subject"] = "Lazarus account verification"
        message["From"] = smtp_sender
        message["To"] = email
        message.set_content(f"""
Hi {username},

Use this verification code to finish creating your Lazarus account.

Verification code:
{token}

Verification link:
{verification_url}

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
            current_app.logger.warning("Registration email failed: %s", exc)
            return False, "We could not send the verification email. Please try again later."

        return True, None

    @staticmethod
    def verifyRegistration(username: str,
                           token: str) -> bool:

        return UserAccount.verifyRegistration(
            username=username,
            token=token
        )


@register_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")

    username: str = request.form.get("username", "").strip()
    email: str = request.form.get("email", "").strip()
    password: str = request.form.get("password", "")
    confirm_password: str = request.form.get("confirm_password", "")

    if username == "" or email == "" or password == "" or confirm_password == "":
        return render_template(
            "register.html",
            error="Please fill in all fields.",
            username=username,
            email=email
        ), 400

    if password != confirm_password:
        return render_template(
            "register.html",
            error="Passwords do not match.",
            username=username,
            email=email
        ), 400

    email_sent, email_error = RegisterC.register(
        username=username,
        email=email,
        password=password
    )

    if not email_sent:
        return render_template(
            "register.html",
            error=email_error,
            username=username,
            email=email
        ), 400

    return redirect(
        url_for(
            "register_bp.verifyAccount",
            username=username,
            sent="1"
        )
    )


@register_bp.route("/register/verify", methods=["GET", "POST"])
def verifyAccount():

    username: str = request.values.get("username", "").strip()
    token: str = request.values.get("token", "").strip()

    if request.method == "GET":
        return render_template(
            "verify_registration.html",
            username=username,
            token=token,
            success=(
                "A verification code has been sent to your email."
                if request.args.get("sent") == "1"
                else None
            )
        )

    if username == "" or token == "":
        return render_template(
            "verify_registration.html",
            error="Please enter your username and verification code.",
            username=username,
            token=token
        ), 400

    account_verified = RegisterC.verifyRegistration(
        username=username,
        token=token
    )

    if not account_verified:
        return render_template(
            "verify_registration.html",
            error="The username or verification code is invalid or expired.",
            username=username,
            token=token
        ), 400

    return render_template(
        "verify_registration.html",
        success="Account verified and created successfully. You can now log in.",
        verified=True
    )
