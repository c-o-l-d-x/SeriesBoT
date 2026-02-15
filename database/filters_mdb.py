import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
from pyrogram import enums
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

myclient = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)
mydb = myclient[DATABASE_NAME]


# ========== FILTER FUNCTIONS ==========

async def add_filter(grp_id, text, reply_text, btn, file, alert):
    """Add or update a filter"""
    mycol = mydb[str(grp_id)]
    
    data = {
        'text': str(text),
        'reply': str(reply_text),
        'btn': str(btn),
        'file': str(file),
        'alert': str(alert)
    }
    
    try:
        await mycol.update_one({'text': str(text)}, {"$set": data}, upsert=True)
    except Exception as e:
        logger.exception('Error adding filter', exc_info=True)


async def find_filter(group_id, name):
    """Find a specific filter by name"""
    mycol = mydb[str(group_id)]
    
    query = {'text': name}
    try:
        result = await mycol.find_one(query)
        if result:
            reply_text = result.get('reply')
            btn = result.get('btn')
            fileid = result.get('file')
            alert = result.get('alert')
            return reply_text, btn, alert, fileid
        return None, None, None, None
    except:
        return None, None, None, None


async def get_filters(group_id):
    """Get all filter names for a group"""
    mycol = mydb[str(group_id)]
    
    texts = []
    try:
        async for file in mycol.find():
            text = file.get('text')
            if text:
                texts.append(text)
    except:
        pass
    return texts


async def delete_filter(message, text, group_id):
    """Delete a specific filter"""
    mycol = mydb[str(group_id)]
    
    myquery = {'text': text}
    try:
        count = await mycol.count_documents(myquery)
        if count == 1:
            await mycol.delete_one(myquery)
            await message.reply_text(
                f"'<code>{text}</code>' deleted. I'll not respond to that filter anymore.",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await message.reply_text("Couldn't find that filter!", quote=True)
    except Exception as e:
        logger.error(f"Error deleting filter: {e}")
        await message.reply_text("Error deleting filter!", quote=True)


async def del_all(message, group_id, title):
    """Delete all filters for a group"""
    collections = await mydb.list_collection_names()
    
    if str(group_id) not in collections:
        await message.edit_text(f"Nothing to remove in {title}!")
        return
    
    mycol = mydb[str(group_id)]
    try:
        await mycol.drop()
        await message.edit_text(f"All filters from {title} have been removed")
    except Exception as e:
        logger.error(f"Error deleting all filters: {e}")
        await message.edit_text("Couldn't remove all filters from group!")


async def count_filters(group_id):
    """Count total filters for a group"""
    mycol = mydb[str(group_id)]
    
    try:
        count = await mycol.count_documents({})
        return False if count == 0 else count
    except:
        return False


async def filter_stats():
    """Get total filter statistics across all groups"""
    collections = await mydb.list_collection_names()
    
    # Remove non-filter collections
    exclude = ['CONNECTION', 'users', 'groups', 'gfilters', 'CHAT_SETTINGS', 'FORCE_SUB']
    for col in exclude:
        if col in collections:
            collections.remove(col)
    
    totalcount = 0
    for collection in collections:
        mycol = mydb[collection]
        count = await mycol.count_documents({})
        totalcount += count
    
    totalcollections = len(collections)
    
    return totalcollections, totalcount


# ========== GFILTER FUNCTIONS ==========

async def add_gfilter(gfilters, text, reply_text, btn, file, alert):
    """Add or update a global filter"""
    mycol = mydb[str(gfilters)]
    
    data = {
        'text': str(text),
        'reply': str(reply_text),
        'btn': str(btn),
        'file': str(file),
        'alert': str(alert)
    }
    
    try:
        await mycol.update_one({'text': str(text)}, {"$set": data}, upsert=True)
    except Exception as e:
        logger.exception('Error adding gfilter', exc_info=True)


async def find_gfilter(gfilters, name):
    """Find a specific global filter by name"""
    mycol = mydb[str(gfilters)]
    
    query = {'text': name}
    try:
        result = await mycol.find_one(query)
        if result:
            reply_text = result.get('reply')
            btn = result.get('btn')
            fileid = result.get('file')
            alert = result.get('alert')
            return reply_text, btn, alert, fileid
        return None, None, None, None
    except:
        return None, None, None, None


async def get_gfilters(gfilters):
    """Get all global filter names"""
    mycol = mydb[str(gfilters)]
    
    texts = []
    try:
        async for file in mycol.find():
            text = file.get('text')
            if text:
                texts.append(text)
    except:
        pass
    return texts


async def delete_gfilter(message, text, gfilters):
    """Delete a specific global filter"""
    mycol = mydb[str(gfilters)]
    
    myquery = {'text': text}
    try:
        count = await mycol.count_documents(myquery)
        if count == 1:
            await mycol.delete_one(myquery)
            await message.reply_text(
                f"'<code>{text}</code>' deleted. I'll not respond to that gfilter anymore.",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await message.reply_text("Couldn't find that gfilter!", quote=True)
    except Exception as e:
        logger.error(f"Error deleting gfilter: {e}")
        await message.reply_text("Error deleting gfilter!", quote=True)


async def del_allg(message, gfilters):
    """Delete all global filters"""
    collections = await mydb.list_collection_names()
    
    if str(gfilters) not in collections:
        await message.edit_text("Nothing to remove!")
        return
    
    mycol = mydb[str(gfilters)]
    try:
        await mycol.drop()
        await message.edit_text("All gfilters have been removed!")
    except Exception as e:
        logger.error(f"Error deleting all gfilters: {e}")
        await message.edit_text("Couldn't remove all gfilters!")


async def count_gfilters(gfilters):
    """Count total global filters"""
    mycol = mydb[str(gfilters)]
    
    try:
        count = await mycol.count_documents({})
        return False if count == 0 else count
    except:
        return False


async def gfilter_stats():
    """Get global filter statistics"""
    collections = await mydb.list_collection_names()
    
    # Only count gfilters collection
    if 'gfilters' not in collections:
        return 0, 0
    
    mycol = mydb['gfilters']
    count = await mycol.count_documents({})
    
    return 1, count
