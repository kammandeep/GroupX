from flask import Flask, render_template, Blueprint

bp = Blueprint('watchlist', __name__)

def watchlist():
    
    return render_template(
            'watchlist.html',  
        )