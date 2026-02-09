from flask import Blueprint, render_template

bp = Blueprint("institutions", __name__, url_prefix="/institutions")


@bp.route("/")
def institutions_index():
    return render_template("institutions.html")
