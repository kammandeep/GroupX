from flask import Flask, render_template, Blueprint

bp = Blueprint('watchlist', __name__)

def watchlist():
    db = get_db() #replace with actual database get function
    
    watchlist = db.execute(
            "SELECT COUNT(*) FROM symbol WHERE status = 'active'"
        ).fetchall()
    
    return render_template(
            'watchlist.html',
            watchlist=watchlist
        )