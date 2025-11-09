from functools import lru_cache
from app.services.supabase import AsyncClient, acreate_client
from app.core.config import SupabaseSettings

supa_settings = SupabaseSettings()
_client = None


async def get_supabase_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = await acreate_client(supa_settings.SUPABASE_URL,
                                       supa_settings.SUPABASE_SECRET_KEY)
    return _client 