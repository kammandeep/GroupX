from flask import Blueprint, jsonify, request

from . import db, queries
from .auth import login_required

bp = Blueprint("stock_search", __name__)

MAX_QUERY_LENGTH = 40
MAX_RESULTS = 50


@bp.get("/api/stock-search")
@login_required
def stock_search():
    """Stocks in the database whose ticker or company name contains `q`.

    An empty `q` lists every available stock; an empty result means "not available".
    """
    q = request.args.get("q", "").strip().lower()[:MAX_QUERY_LENGTH]
    matches = [
        {"ticker": row["ticker"], "name": row["company_name"],
         "price": row["close"], "change_pct": row["change_pct"]}
        for row in queries.latest_prices(db.get_db())
        if q in row["ticker"].lower() or q in row["company_name"].lower()
    ]
    return jsonify(stocks=matches[:MAX_RESULTS])
