from flask import Blueprint, render_template
from .auth import login_required

bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("home.html")