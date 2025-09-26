import asyncio
from core.ai_converter import AIConverter
from core.tg_parser import TelegramParser
from core.visual_map import VisualMap
from loguru import logger

async def main():
    cleared_message = None
    async with TelegramParser('rinda_parser') as parser:
        cleared_message = await parser.parse_messages()
    
    print(cleared_message)

    
    ai = AIConverter()
    ai_result = ai.proccess_data(cleared_message, max_workers=2)
    
    logger.info(f"Processed {ai_result['total_cities']} cities")
    logger.info(f"Total number of weapons: {ai_result['total_weapons_count']}")
    
    visual_map = VisualMap(full_json_data=ai_result)
    visual_map.create_map()


if __name__ == "__main__":
    asyncio.run(main())