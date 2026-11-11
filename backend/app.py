from pathlib import Path

from flask import Flask, abort
from sqlalchemy import func, select

from . import auth, db, pages, routes
from .config import Config
from .models import Company, Prediction, Stock, StockData
from .security import csrf_token

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_ROOT / "templates"),
        static_folder=str(FRONTEND_ROOT / "static"),
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(routes.auth_bp)
    app.register_blueprint(pages.bp)
    app.context_processor(lambda: {"csrf_token": csrf_token})

    @app.get("/api/stocks")
    def get_stocks():
        session = db.get_db()
        stocks = session.execute(
            select(Stock, Company.name)
            .join(Company, Company.id == Stock.company_id)
            .order_by(Stock.ticker)
        ).all()
        return [
            {
                "id": stock.id,
                "ticker": stock.ticker,
                "company_name": company_name,
                "exchange_code": stock.exchange_code,
                "current_price": session.scalar(
                    select(StockData.close)
                    .where(StockData.ticker == stock.ticker)
                    .order_by(StockData.date.desc())
                    .limit(1)
                ),
            }
            for stock, company_name in stocks
        ]

    @app.get("/api/stocks/<int:stock_id>")
    def get_stock(stock_id):
        session = db.get_db()
        stock = session.get(Stock, stock_id)
        if stock is None:
            abort(404)
        company = session.get(Company, stock.company_id)
        return {
            "id": stock.id,
            "ticker": stock.ticker,
            "company_name": company.name if company else None,
        }

    @app.get("/api/stocks/<int:stock_id>/close")
    def get_stock_close(stock_id):
        session = db.get_db()
        stock = session.get(Stock, stock_id)
        if stock is None:
            abort(404)
        price = session.scalar(
            select(StockData.close)
            .where(StockData.ticker == stock.ticker)
            .order_by(StockData.date.desc())
            .limit(1)
        )
        return {"price": price}

    @app.get("/api/stock-data")
    def get_stock_data():
        session = db.get_db()
        stocks = session.scalars(select(Stock).order_by(Stock.ticker)).all()
        result = []
        for stock in stocks:
            prices = session.scalars(
                select(StockData)
                .where(StockData.ticker == stock.ticker)
                .order_by(StockData.date.desc())
                .limit(7)
            ).all()
            if prices:
                result.append(
                    {
                        "ticker": stock.ticker,
                        "data": [
                            {
                                "date": price.date,
                                "open": round(price.open, 2),
                                "high": round(price.high, 2),
                                "low": round(price.low, 2),
                                "close": round(price.close, 2),
                                "volume": price.volume,
                            }
                            for price in prices
                        ],
                    }
                )
        return result

    @app.get("/api/predictions")
    def get_predictions():
        session = db.get_db()
        predictions = session.execute(
            select(Prediction, Company.name)
            .join(Stock, Stock.ticker == Prediction.ticker)
            .join(Company, Company.id == Stock.company_id)
            .order_by(Prediction.prediction_date.desc())
        ).all()
        return [
            {
                "ticker": prediction.ticker,
                "prediction_date": prediction.prediction_date,
                "predicted_close": prediction.predicted_close,
                "actual_close": prediction.actual_close,
                "confidence_score": prediction.confidence_score,
                "direction": prediction.direction,
                "company_name": company_name,
            }
            for prediction, company_name in predictions
        ]

    @app.get("/api/companies")
    def get_companies():
        companies = db.get_db().scalars(
            select(Company).order_by(Company.name)
        ).all()
        return [
            {
                "id": company.id,
                "name": company.name,
                "sector": company.sector,
                "industry": company.industry,
                "website": company.website,
            }
            for company in companies
        ]

    @app.get("/health")
    def health():
        company_count = db.get_db().scalar(select(func.count()).select_from(Company))
        return {"status": "healthy", "companies_count": company_count}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
