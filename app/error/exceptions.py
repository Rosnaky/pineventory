
class DatabaseNotInitializedError(Exception):
    def __init__(self, message="Database connection pool is not initialized"):
        self.message = message
        super().__init__(self.message)
