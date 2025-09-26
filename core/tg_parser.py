import asyncio
import os
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, asdict
from loguru import logger
from pyrogram import Client
from pyrogram.errors import (
    FloodWait, AuthKeyUnregistered, UserDeactivated,
)
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from core.utils import delete_simillar_routes

load_dotenv()

@dataclass
class TelegramMessage:
    """Simple structure for storing Telegram message data"""
    message_id: int
    text: str
    date: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['date'] = self.date.isoformat()
        return data

class TelegramParser:
    def __init__(self, 
            session_name: str = "telegram_parser",
        ):
        """
        Parser initialization
        
        Args:
            api_id: Application ID from my.telegram.org
            api_hash: Application hash from my.telegram.org  
            session_name: Session file name
            phone_number: Phone number for authorization
        """
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.phone_number = os.getenv("TELEGRAM_PHONE")
        self.channel_name = os.getenv("TELEGRAM_CHANNEL")
        self.session_name = session_name

        session_dir = "telegram_sessions"
        os.makedirs(session_dir, exist_ok=True)
        
        session_path = os.path.join(session_dir, session_name)
        
        self.client = Client(
            name=session_path,
            # name=session_name,
            api_id=self.api_id,
            api_hash=self.api_hash,
            phone_number=self.phone_number
        )
        
        logger.add(
            f"logs/{self.session_name}.log",
            rotation="1 day",
            retention="7 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )
        
        self.stats = {
            'total_messages': 0,
            'total_channels': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self) -> bool:
        try:
            logger.info("Connecting to Telegram API...")
            await self.client.start()            
            me = await self.client.get_me()
            logger.info(f"Successfully connected as: {me.first_name} (@{me.username})")
            
            return True
            
        except (AuthKeyUnregistered, UserDeactivated) as e:
            logger.error(f"Authorization error: {e}")
            return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    async def disconnect(self):
        """Disconnecting from Telegram API"""
        try:
            await self.client.stop()
            logger.success("Disconnect from Telegram API completed")
        except Exception as e:
            logger.error(f"Err with disconnect: {e}")

    async def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """
        Getting channel information
        
        Returns:
            Dict with channel information or None if channel not found
        """
        try:
            if self.channel_name.startswith('@'):
                self.channel_name = self.channel_name[1:]
                
            chat = await self.client.get_chat(self.channel_name)
            
            return {
                'id': chat.id,
                'title': chat.title,
                'username': chat.username,
                'type': str(chat.type),
                'members_count': getattr(chat, 'members_count', None),
                'description': getattr(chat, 'description', None)
            }
            
        except Exception as e:
                logger.error(f"Error getting channel info {self.channel_name}: {e}")
                return None

    async def parse_channel_messages(
        self, 
        limit: int = 100,
    ) -> AsyncGenerator[TelegramMessage, None]:
        """
        Channel messages parsing
        
        Args:
            limit: Maximum number of messages
            offset_date: Date from which to start parsing
            search_query: Search query for message filtering
            
        Yields:
            TelegramMessage: Message object
        """
        try:
            if self.channel_name.startswith('@'):
                self.channel_name = self.channel_name[1:]
            
            channel_info = await self.get_channel_info()
            if not channel_info:
                return
            
            message_count = 0
            
            now = datetime.now(ZoneInfo('Europe/Kyiv'))
            
            async for message in self.client.get_chat_history(
                chat_id=self.channel_name,
                limit=limit
            ):
                try:
                    await asyncio.sleep(0.1)
  
                    msg_date = message.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=ZoneInfo('Europe/Kyiv'))
                    
                    message_age = now - msg_date
                    age_seconds = message_age.total_seconds()

                    texts = ('Ситуація станом на 00:00', 'Зафіксовано пуски ударних', 'Пуски КАБ')

                    if age_seconds > 20 * 60 or any(text in message.text for text in texts):
                        continue
                
                    
                    telegram_message = TelegramMessage(
                        message_id=message.id,
                        text=message.text or "",
                        date=message.date
                    )
                    
                    message_count += 1
                    self.stats['total_messages'] += 1
                    
                    yield telegram_message
                    
                    if message_count % 50 == 0:
                        logger.info(f"Processed {message_count} messages from channel {self.channel_name}")
                        
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    continue
                except Exception as e:
                    self.stats['errors'] += 1
                    continue
                        
        except Exception as e:
            logger.error(f"Error parsing channel {self.channel_name}: {e}")
            self.stats['errors'] += 1
            
    async def parse_messages(self):        
        self.stats['start_time'] = datetime.now()
        self.stats['total_channels'] = 1
        
        all_messages = []
        
        logger.info(f"Starting channel parsing {self.channel_name}")
        
        async for message in self.parse_channel_messages(
            limit=7
        ):
            all_messages.append(message)        
        self.stats['end_time'] = datetime.now()

        logger.info(f"Total received {len(all_messages)} messages")
        cleared = delete_simillar_routes(all_messages)
        return cleared
