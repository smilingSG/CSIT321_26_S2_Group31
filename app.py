from flask import Flask

from controllers.dashboardC import dashboard_bp
from controllers.uploadFileC import upload_bp

app = Flask(__name__)
app.secret_key = "temporary_secret_key"

app.register_blueprint(dashboard_bp)
app.register_blueprint(upload_bp)

if __name__ == "__main__":
    app.run(debug=True)