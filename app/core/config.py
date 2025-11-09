from pydantic_settings import BaseSettings
from datetime import timezone
import os 
from dotenv import load_dotenv
load_dotenv(override=True)



class SupabaseSettings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str

    class config:
        env_file = '.env'
        extra = "ignore"

class DataBaseSettings(BaseSettings):
    # DB settings
    MONGODB_DATABASE:str|None = None
    MONGODB_ROOT_USERNAME: str|None = None
    MONGODB_ROOT_PASSWORD: str|None = None
    MONGODB_CONNECTION_URL:str
    # summary collection
    SUMMARY_COLLECTION: str = "book_summary"

class BookGenerationSettings(BaseSettings):
    GOOGLE_API_KEY: str