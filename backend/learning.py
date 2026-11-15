LEARN_CATEGORIES = (
    ("all", "All"),
    ("basics", "Basics"),
    ("strategies", "Strategies"),
    ("charts", "Reading charts"),
    ("risk", "Risk"),
)

FEATURED_LESSON = {
    "slug": "what-is-a-backtest",
    "title": "Start here: What is a backtest?",
    "summary": "See how a strategy would have done on past data, and why that is useful.",
    "body": (
        "A backtest applies a set of trading rules to historical market data. "
        "It can help you understand how a strategy behaved before you consider "
        "using it with current data."
    ),
    "category": "basics",
    "read_time": 4,
}

LESSONS = (
    {
        "slug": "reading-a-signal",
        "title": "Reading a signal",
        "summary": "What BUY, HOLD and SELL mean",
        "body": (
            "A signal is a model's summary of the information it has reviewed. "
            "BUY, HOLD and SELL describe the model's view, not a guarantee of what "
            "the stock will do next."
        ),
        "category": "basics",
        "read_time": 3,
    },
    {
        "slug": "accuracy-explained",
        "title": "Accuracy explained",
        "summary": "What 72% really tells you",
        "body": (
            "Accuracy is the share of past predictions that were correct under a "
            "specific test. It does not predict the next trade, and it should be "
            "read alongside the time period, sample size and strategy risk."
        ),
        "category": "basics",
        "read_time": 4,
    },
    {
        "slug": "max-drop",
        "title": "Max drop",
        "summary": "The worst fall a strategy had",
        "body": (
            "Maximum drawdown measures the largest peak-to-trough fall in a "
            "strategy's value during a period. A smaller drawdown can make a "
            "strategy easier to stick with when markets are difficult."
        ),
        "category": "risk",
        "read_time": 3,
    },
    {
        "slug": "moving-averages",
        "title": "Moving averages",
        "summary": "The line behind many strategies",
        "body": (
            "A moving average smooths recent prices into a line that makes trends "
            "easier to see. Different time windows react at different speeds, so "
            "a moving average is context rather than a prediction by itself."
        ),
        "category": "strategies",
        "read_time": 5,
    },
    {
        "slug": "rsi-in-2-minutes",
        "title": "RSI in 2 minutes",
        "summary": "Spot oversold stocks",
        "body": (
            "The Relative Strength Index compares recent upward and downward "
            "price movements on a bounded scale. High or low readings can signal "
            "strong momentum, but they do not prove that a reversal will happen."
        ),
        "category": "charts",
        "read_time": 2,
    },
    {
        "slug": "risk-and-position-size",
        "title": "Risk and position size",
        "summary": "Never bet more than you can lose",
        "body": (
            "Position size is how much of your money is placed in one investment. "
            "Keeping positions small enough to handle a loss is one way to limit "
            "the damage of an unexpected move."
        ),
        "category": "risk",
        "read_time": 5,
    },
)


def get_lesson(slug):
    if slug == FEATURED_LESSON["slug"]:
        return FEATURED_LESSON
    return next((lesson for lesson in LESSONS if lesson["slug"] == slug), None)
