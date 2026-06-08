import os
import uuid

from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import mysql.connector

app = Flask(__name__)
app.secret_key = "temporary_secret_key"

TEMP_UPLOAD_FOLDER = "temp_uploads"
app.config["TEMP_UPLOAD_FOLDER"] = TEMP_UPLOAD_FOLDER

TEMP_USER_ID = 1

os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)


def get_db_connection():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="Root",
        database="lazarus_db"
    )


@app.route("/")
def home():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    dashboard_data = {
        "total_files": 0,
        "shared_files": 0,
        "active_links": 0,
        "recovered_files": 0
    }

    return render_template("dashboard.html", data=dashboard_data)


@app.route("/upload", methods=["GET"])
def upload_page():
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    uploaded_file = request.files.get("file")
    total_fragments = request.form.get("total_fragments")
    required_fragments = request.form.get("required_fragments")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({
            "success": False,
            "message": "Please select a file."
        }), 400

    if total_fragments is None or required_fragments is None:
        return jsonify({
            "success": False,
            "message": "Please enter fragment settings."
        }), 400

    try:
        total_fragments = int(total_fragments)
        required_fragments = int(required_fragments)
    except ValueError:
        return jsonify({
            "success": False,
            "message": "Fragment values must be valid numbers."
        }), 400

    if total_fragments < 2:
        return jsonify({
            "success": False,
            "message": "Total fragments must be at least 2."
        }), 400

    if required_fragments < 1:
        return jsonify({
            "success": False,
            "message": "Required fragments must be at least 1."
        }), 400

    if required_fragments > total_fragments:
        return jsonify({
            "success": False,
            "message": "Required fragments cannot be greater than total fragments."
        }), 400

    try:
        original_filename = secure_filename(uploaded_file.filename)
        file_extension = os.path.splitext(original_filename)[1]
        stored_filename = str(uuid.uuid4()) + file_extension
        file_path = os.path.join(app.config["TEMP_UPLOAD_FOLDER"], stored_filename)

        uploaded_file.save(file_path)

        file_size = os.path.getsize(file_path)
        file_type = uploaded_file.content_type

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO files
            (owner_id, original_filename, stored_filename, file_size, file_type,
             total_fragments, required_fragments, file_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            TEMP_USER_ID,
            original_filename,
            stored_filename,
            file_size,
            file_type,
            total_fragments,
            required_fragments,
            "pending_processing"
        ))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            "success": True,
            "message": "File uploaded successfully. File is ready for confirmation."
        })

    except mysql.connector.Error as error:
        return jsonify({
            "success": False,
            "message": "Database error: " + str(error)
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Upload error: " + str(error)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)