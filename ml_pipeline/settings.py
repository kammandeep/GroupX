from pathlib import Path
from sqlalchemy import create_engine

db_path = Path(__file__).parent.parent / "instance" / "groupx.sqlite3"
print("GroupX/instance ", db_path, db_path.exists())
assert db_path.exists(), f"Database not found at {db_path}"

engine = create_engine(f"sqlite:///{db_path.as_posix()}")    

artifacts_path = Path(__file__).parent / "artifacts"


symbol_map = {'AAPL' : 0, 'AMZN' : 1, 'GOOGL' : 2, 'MSFT' : 3,'NVDA' : 4}
symbol_map_reverse = {0 : 'AAPL', 1 : 'AMZN', 2 : 'GOOGL', 3 : 'MSFT', 4 : 'NVDA'}
