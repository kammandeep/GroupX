from flask import render_template, Blueprint, g
from . import db, queries
from .auth import login_required

bp = Blueprint('watchlist', __name__)

@bp.route('/watchlist')
@login_required
def watchlist():  
    rows = queries.watchlist_overview(db.get_db(), g.user.id)
    
    return render_template(
            'watchlist.html',
            watchlist=rows
        )