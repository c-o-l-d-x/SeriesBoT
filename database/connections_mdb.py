import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

myclient = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)
mydb = myclient[DATABASE_NAME]


async def add_connection(user_id, group_id):
    """Add connection between user and group"""
    mycol = mydb['CONNECTION']
    
    query = {'_id': str(user_id)}
    data = {
        '_id': str(user_id),
        'group_id': str(group_id)
    }
    
    try:
        await mycol.update_one(query, {"$set": data}, upsert=True)
        return True
    except Exception as e:
        logger.exception('Error in add_connection', exc_info=True)
        return False


async def active_connection(user_id):
    """Get active connection for user"""
    mycol = mydb['CONNECTION']
    
    query = {'_id': str(user_id)}
    try:
        result = await mycol.find_one(query)
        if result:
            return result.get('group_id')
        return None
    except:
        return None


async def delete_connection(user_id):
    """Delete connection for user"""
    mycol = mydb['CONNECTION']
    
    query = {'_id': str(user_id)}
    try:
        await mycol.delete_one(query)
        return True
    except:
        return False


async def all_connections(user_id):
    """Get all connections for user (currently only stores one)"""
    mycol = mydb['CONNECTION']
    
    query = {'_id': str(user_id)}
    try:
        result = await mycol.find_one(query)
        if result:
            return [result.get('group_id')]
        return []
    except:
        return []
