from datetime import datetime, timezone
from app.utils.get_logger import logger
from pymongo import AsyncMongoClient
from app.core.config import DataBaseSettings
from typing import List, Dict, Any

class MongoDB:
    def __init__(self, cfg: DataBaseSettings) -> None:
        self.cfg = cfg
        self._client = AsyncMongoClient(cfg.MONGODB_CONNECTION_URL)
        self.db = self._client.get_database(cfg.MONGODB_DATABASE)
        logger.info(f'Connected to `{cfg.MONGODB_DATABASE}` successfully!')

    async def initialize(self):
        await self.db.get_collection(self.cfg.SUMMARY_COLLECTION).create_index("book_title", unique=True)

    async def update_book_chapters(self, book_title: str, chapters_data: List[Dict[str, Any]]):
        """
        Updates a book document with the latest list of chapters and their summaries.
        If the book doesn't exist, it creates a new document.
        """
        if not book_title or not chapters_data:
            logger.warning("Book title or chapters data is empty. Skipping DB update.")
            return

        collection = self.db.get_collection(self.cfg.SUMMARY_COLLECTION)
        try:
            result = await collection.update_one(
                {"book_title": book_title},
                {"$set": {
                    "chapters": chapters_data,
                    "last_updated": datetime.now(timezone.utc)
                }},
                upsert=True
            )
            if result.upserted_id:
                logger.info(f"Created new book document for '{book_title}' with {len(chapters_data)} chapter(s).")
            elif result.modified_count > 0:
                logger.info(f"Updated chapters for book '{book_title}'. Now has {len(chapters_data)} chapter(s).")
            else:
                logger.info(f"No changes made to chapters for book '{book_title}'.")
            return result
        except Exception as e:
            logger.error(f"Failed to update book chapters for '{book_title}' in MongoDB: {e}")
            raise

if __name__ == "__main__":
    import asyncio
    async def main():
        db = MongoDB(DataBaseSettings())