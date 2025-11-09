from app.db import MongoDB
from app.core.config import DataBaseSettings
from app.utils.get_logger import logger

############################### Get DB ##########################

db_client: MongoDB|None=None
#storedb_client: StoreManagerDB|None=None

def get_db():
    ''' Method to configure database '''
    global db_client
    if db_client:
        return db_client
    try:
        logger.warning(f"db_client not found. Initializing it again...")
        db_client = MongoDB(DataBaseSettings())
        return db_client
    except Exception as e:
        raise Exception(f"Unable to Connect to Database: {e}")