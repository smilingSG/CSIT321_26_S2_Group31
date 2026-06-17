from flask import Flask, redirect, session, url_for

from controllers.AdminC import admin_bp
from controllers.AdminUpdateC import admin_update_bp
from controllers.AdminViewC import admin_view_bp
from controllers.LoginC import login_bp
from controllers.UserManagementC import user_management_bp
from controllers.dashboardC import dashboard_bp
from controllers.uploadFileC import upload_bp
from controllers.previewUploadedFileC import preview_bp
from controllers.replaceUploadedFileC import replace_bp
from controllers.configureFragmentsC import configure_fragments_bp
from controllers.deleteFileC import delete_bp
from controllers.encryptFileC import encrypt_file_bp

app = Flask(__name__)
app.secret_key = "temporary_secret_key"


@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("login_bp.login"))


app.register_blueprint(login_bp)
app.register_blueprint(user_management_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(preview_bp)
app.register_blueprint(replace_bp)
app.register_blueprint(configure_fragments_bp)
app.register_blueprint(delete_bp)
app.register_blueprint(encrypt_file_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(admin_update_bp)
app.register_blueprint(admin_view_bp)

if __name__ == "__main__":
    app.run(debug=True)
