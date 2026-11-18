from flask import Blueprint, render_template
from .auth import login_required
from .onboarding import onboarding_required


bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
@onboarding_required
def home():
    return render_template("home.html")