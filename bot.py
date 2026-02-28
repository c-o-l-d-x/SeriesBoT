import logging
import asyncio
from pyrogram import Client
from pyrogram.enums import ParseMode
from aiohttp import web
from web_server import web_server
from info import API_ID, API_HASH, BOT_TOKEN, MAIN_DB_CHANNEL, ADMINS, PORT
from pyrogram import utils as pyroutils
from auth_manager import auth_manager  # Import auth manager

pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="SeriesBot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="plugins")
        )
        self.main_db_channel = None
    
    async def start(self):
        await super().start()
        me = await self.get_me()
        
        logging.info(f"Bot started as @{me.username}")
        
        # Initialize auth manager to load auth users from database
        try:
            await auth_manager.initialize()
            logging.info("✅ Auth Manager loaded successfully")
        except Exception as e:
            logging.error(f"❌ Failed to initialize Auth Manager: {e}")
        
        # Initialize and resolve Main DB channel
        try:
            if MAIN_DB_CHANNEL:
                if isinstance(MAIN_DB_CHANNEL, int):
                    logging.info(f"Main DB Channel ID: {MAIN_DB_CHANNEL}")
                    
                    # Use resolve_peer to force Pyrogram to cache it properly
                    try:
                        peer = await self.resolve_peer(MAIN_DB_CHANNEL)
                        logging.info(f"✅ Main DB channel peer resolved: {peer}")
                        
                        # Store the channel info
                        class ChannelInfo:
                            def __init__(self, channel_id):
                                self.id = channel_id
                        
                        self.main_db_channel = ChannelInfo(MAIN_DB_CHANNEL)
                        
                    except Exception as resolve_error:
                        logging.error(f"❌ Cannot resolve Main DB channel: {resolve_error}")
                        logging.error("⚠️ CRITICAL: Bot cannot find the Main DB channel!")
                        logging.error("This usually means:")
                        logging.error("  1. Bot was NEVER added to the channel")
                        logging.error("  2. Bot was removed from the channel")
                        logging.error("  3. Session file is corrupted")
                        logging.error(f"  4. Add bot here: https://t.me/c/{abs(MAIN_DB_CHANNEL) - 1000000000000}/1")
                        
                        # Try one more time with a delay
                        await asyncio.sleep(2)
                        try:
                            peer = await self.resolve_peer(MAIN_DB_CHANNEL)
                            logging.info(f"✅ Main DB channel resolved on retry: {peer}")
                            self.main_db_channel = ChannelInfo(MAIN_DB_CHANNEL)
                        except:
                            logging.error("❌ Still cannot resolve. Bot will continue but batch features won't work.")
                            self.main_db_channel = ChannelInfo(MAIN_DB_CHANNEL)  # Store anyway
                            
                else:
                    # Username provided
                    self.main_db_channel = await self.get_chat(MAIN_DB_CHANNEL)
                    logging.info(f"Main DB channel: {self.main_db_channel.title} ({self.main_db_channel.id})")
            else:
                logging.warning("⚠️ MAIN_DB_CHANNEL not configured in info.py!")
                logging.warning("Batch features will not work without Main DB Channel.")
                    
        except Exception as e:
            logging.error(f"Error initializing Main DB channel: {e}")
        
        # Send restart notification to Main DB channel
        if self.main_db_channel:
            try:
                test = await self.send_message(
                    chat_id=self.main_db_channel.id,
                    text="✅ <b>Bot Restarted!</b>"
                )
                logging.info("✅ Restart notification sent to Main DB channel")
                await test.delete()
            except Exception as e:
                logging.error(f"❌ Cannot send to Main DB channel: {e}")
                logging.error("Bot will work but you need to fix Main DB channel access!")
        
        # Send to admins
        for admin in ADMINS:
            try:
                await self.send_message(admin, text="✅ <b>Bot Restarted!</b>", parse_mode=ParseMode.HTML)
                logging.info(f"✅ Sent to admin {admin}")
            except Exception as e:
                logging.warning(f"Cannot reach admin {admin}: {e}")
    
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()
    logging.info(f"✅ Web server started on {bind_address}:{PORT}")
    
    async def stop(self, *args):
        await super().stop()
        logging.info("Bot stopped")

if __name__ == "__main__":
    Bot().run()
