from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for

from entities.File import File

configure_fragments_bp = Blueprint(
    "configure_fragments_bp",
    __name__
)


@configure_fragments_bp.route(
    "/upload/fragments/<int:file_id>",
    methods=["GET"]
)
def fragmentConfigurationPage(file_id: int):

    preview_data = File.getFilePreviewDetails(file_id)

    if preview_data is None:
        return "File record could not be found.", 404

    return render_template(
        "fragmentConfiguration.html",
        previewData=preview_data
    )


@configure_fragments_bp.route(
    "/upload/fragments/<int:file_id>",
    methods=["POST"]
)
def configureFragments(file_id: int):

    total_fragments = request.form.get(
        "total_fragments"
    )

    required_fragments = request.form.get(
        "required_fragments"
    )

    validation_error = validateFragmentConfig(
        total_fragments,
        required_fragments
    )

    if validation_error is not None:

        preview_data = File.getFilePreviewDetails(
            file_id
        )

        return render_template(
            "fragmentConfiguration.html",
            previewData=preview_data,
            errorMessage=validation_error
        )

    File.updateFragmentConfiguration(
        file_id,
        int(total_fragments),
        int(required_fragments)
    )

    return "Fragment configuration saved. Next page not implemented yet."


def validateFragmentConfig(
    total_fragments,
    required_fragments
):

    if total_fragments is None:
        return "Please enter total fragments."

    if required_fragments is None:
        return "Please enter required fragments."

    try:

        total_fragments = int(
            total_fragments
        )

        required_fragments = int(
            required_fragments
        )

    except ValueError:

        return "Fragment values must be numbers."

    if total_fragments < 2:
        return (
            "Total fragments must be at least 2."
        )

    if required_fragments < 1:
        return (
            "Required fragments must be at least 1."
        )

    if required_fragments > total_fragments:
        return (
            "Required fragments cannot be greater "
            "than total fragments."
        )

    return None