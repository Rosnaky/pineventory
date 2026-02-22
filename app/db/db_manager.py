
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db = None

    async def connect(self):
        self.db = await 
