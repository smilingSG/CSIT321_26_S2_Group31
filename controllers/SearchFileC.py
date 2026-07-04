# Import Flask components used for routing, templates, sessions, and redirects.
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

# Import the File entity used to search the user's managed files.
from entities.File import File


# Create the blueprint containing the file search route.
search_file_bp = Blueprint(
    "search_file_bp",
    __name__
)


# Search processed files belonging to the logged-in user by file name.
@search_file_bp.route("/files/search", methods=["GET"])
def searchFile():

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    # Retrieve the search keyword submitted by the boundary.
    search_query = request.args.get("query", "")

    # Ask the File entity to query MySQL for matching processed files.
    managed_files = File.searchManagedFilesByName(
        owner_id,
        search_query
    )

    # Redisplay the file-management boundary with the searched file list.
    return render_template(
        "fileManagement.html",
        managedFiles=managed_files,
        searchQuery=search_query
    )
