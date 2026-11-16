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
    "sections": (
        (
            "A simple way to think about it",
            "A backtest is a practice run for a trading idea. Instead of waiting "
            "for the market to move, we apply the rules to old price data and "
            "see what would have happened."
        ),
        (
            "What it can teach you",
            "A backtest can show how often a strategy was right, how much it "
            "gained or lost, and how large its worst drop was. It helps you ask "
            "better questions before trusting a strategy."
        ),
        (
            "Important limitation",
            "Past results are not a promise about the future. Market conditions "
            "change, and a backtest may not include fees, slippage or unexpected "
            "events."
        ),
    ),
    "category": "basics",
    "read_time": 4,
}

LESSONS = (
    {
        "slug": "reading-a-signal",
        "title": "Reading a signal",
        "summary": "What BUY, HOLD and SELL mean",
        "sections": (
            (
                "BUY",
                "The model sees conditions that match its rules for a possible "
                "upward move. It is not an instruction or a guarantee."
            ),
            (
                "HOLD",
                "The model does not see a strong enough reason to change its "
                "current view. The stock can still rise or fall."
            ),
            (
                "SELL",
                "The model sees conditions that match its rules for a possible "
                "downward move. Always consider your own risk first."
            ),
            (
                "Read the context",
                "Check the strategy, date, confidence and backtest results "
                "alongside a signal. One signal is only one piece of information."
            ),
        ),
        "category": "basics",
        "read_time": 3,
    },
    {
        "slug": "accuracy-explained",
        "title": "Accuracy explained",
        "summary": "What 72% really tells you",
        "sections": (
            (
                "The basic calculation",
                "If a strategy made 100 test predictions and 72 were correct, "
                "its accuracy for that test was 72%."
            ),
            (
                "What it does not mean",
                "A 72% accuracy score does not mean the next prediction has a "
                "72% chance of being correct. It describes a past test, not a "
                "guaranteed future result."
            ),
            (
                "Look beyond one number",
                "Check how many predictions were tested, which dates were used, "
                "and how large the wins and losses were. A high accuracy score "
                "can still hide a large loss."
            ),
        ),
        "category": "basics",
        "read_time": 4,
    },
    {
        "slug": "max-drop",
        "title": "Max drop",
        "summary": "The worst fall a strategy had",
        "sections": (
            (
                "How it works",
                "Maximum drawdown measures the largest fall from a previous high "
                "to a later low during a period. It is usually shown as a "
                "percentage."
            ),
            (
                "A simple example",
                "If an account grows from $1,000 to $1,200 and later falls to "
                "$900 before recovering, the drawdown from that $1,200 peak is "
                "25%."
            ),
            (
                "Why it matters",
                "Two strategies can earn similar returns but have very different "
                "drawdowns. Understanding the worst drop helps you decide what "
                "level of risk you can realistically handle."
            ),
        ),
        "category": "risk",
        "read_time": 3,
    },
    {
        "slug": "moving-averages",
        "title": "Moving averages",
        "summary": "The line behind many strategies",
        "sections": (
            (
                "What it is",
                "A moving average adds recent closing prices and divides by the "
                "number of days. A 5-day moving average, for example, uses the "
                "last five closing prices."
            ),
            (
                "Reading the line",
                "A rising average can show that recent prices have generally been "
                "moving higher. A falling average can show the opposite. The "
                "average follows price; it does not predict it perfectly."
            ),
            (
                "Short versus long",
                "Short averages react quickly but can be noisy. Long averages "
                "move more slowly and can make a broad trend easier to see."
            ),
        ),
        "category": "strategies",
        "read_time": 5,
    },
    {
        "slug": "rsi-in-2-minutes",
        "title": "RSI in 2 minutes",
        "summary": "Spot oversold stocks",
        "sections": (
            (
                "What RSI measures",
                "The Relative Strength Index, or RSI, compares recent upward and "
                "downward price movements on a scale from 0 to 100."
            ),
            (
                "Common guideposts",
                "Readings above 70 are often described as overbought and readings "
                "below 30 as oversold. These are clues about momentum, not "
                "automatic buy or sell instructions."
            ),
            (
                "Use it with context",
                "A stock can stay overbought during a strong uptrend or oversold "
                "during a strong downtrend. Look at the trend and other evidence "
                "before drawing a conclusion."
            ),
        ),
        "category": "charts",
        "read_time": 2,
    },
    {
        "slug": "risk-and-position-size",
        "title": "Risk and position size",
        "summary": "Never bet more than you can lose",
        "sections": (
            (
                "What position size means",
                "Position size is the amount of money invested in one stock or "
                "trade. It is different from whether the idea itself is good."
            ),
            (
                "Why smaller can be safer",
                "If one stock falls, a smaller position limits how much it can "
                "hurt your overall account. Diversification can also reduce the "
                "impact of one unexpected move."
            ),
            (
                "Start with a loss you can handle",
                "Before entering a trade, decide how much money you are prepared "
                "to lose. Never use money needed for essential expenses, and "
                "remember that every investment can lose value."
            ),
        ),
        "category": "risk",
        "read_time": 5,
    },
)


def get_lesson(slug):
    if slug == FEATURED_LESSON["slug"]:
        return FEATURED_LESSON
    return next((lesson for lesson in LESSONS if lesson["slug"] == slug), None)
