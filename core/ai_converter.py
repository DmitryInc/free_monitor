import json
import re
import os
import sqlite3
from typing import Dict, List, Any, Optional
from core.config import AI_MODEL
from loguru import logger
from dotenv import load_dotenv
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
import time
import random

load_dotenv()

class SQLiteFlow:
    """
    Class for working with SQLite database of cities coordinates

    Args:
        db_path: str - path to the database
        pool_size: int - size of the connection pool
    """
    def __init__(self, db_path: str = "db/cities_coordinates.db", pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._connection_pool = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        
        self._init_database()
        self._init_connection_pool()
        self.clean_region_duplicates()
        
        self.region_corrections = {
            "хмельничена": "хмельниччина",
            "хмельниченна": "хмельниччина"
        }
    
    def _init_database(self):
        """
        Initialize database

        Args:
            None
            
        Returns:
            None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city_name TEXT NOT NULL,
                    region_name TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    source TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(city_name, region_name)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS regions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region_name TEXT NOT NULL UNIQUE,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    source TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logger.success(f"Database initialized: {self.db_path}")
    
    def _init_connection_pool(self):
        """Initialize connection pool for SQLite
        
        Args:
            None
            
        Returns:
            None
        """
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._connection_pool.put(conn)
    
    def _get_connection(self):
        """Get connection from pool
        
        Args:
            None
            
        Returns:
            Connection - connection to the database
        """
        return self._connection_pool.get()
    
    def _return_connection(self, conn):
        """Return connection to pool
        
        Args:
            conn: Connection - connection to the database
            
        Returns:
            None
        """
        self._connection_pool.put(conn)
    
    def normalize_region_name(self, region_name: str) -> str:
        """
        Normalize region name - fix typos and apply title case
        
        Args:
            region_name: str - original region name
            
        Returns:
            str - normalized region name with title case
        """
        cleaned = region_name.strip().lower()
        
        if cleaned in self.region_corrections:
            corrected = self.region_corrections[cleaned]
            return corrected.title()
        
        return region_name.strip().title()
    
    def get_city_coordinates(self, city_name: str, region_name: str) -> Optional[Dict[str, Any]]:
        """
        Get city coordinates from database
        
        Args:
            city_name: str - city name
            region_name: str - region name
            
        Returns:
            Optional[Dict[str, Any]] - dictionary with city coordinates
        """
        try:
            normalized_region = self.normalize_region_name(region_name)
            
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT latitude, longitude, confidence, source 
                    FROM cities 
                    WHERE city_name = ? AND region_name = ?
                ''', (city_name, normalized_region))
                
                result = cursor.fetchone()
                if result:
                    latitude, longitude, confidence, source = result
                    logger.info(f"Found in DB: {city_name}, {region_name}")
                    return {
                        "coordinates": {
                            "latitude": latitude,
                            "longitude": longitude
                        },
                        "confidence": confidence,
                        "source": f"database_{source}"
                    }
                return None
            finally:
                self._return_connection(conn)
        except Exception as e:
            logger.error(f"Error reading from DB: {e}")
            return None
    
    def save_city_coordinates(
        self, city_name: str, region_name: str, latitude: float, 
        longitude: float, confidence: float = 0.8, source: str = "AI"
    ) -> bool:
        """
        Save city coordinates to database
        
        Args:
            city_name: str - city name
            region_name: str - region name
            latitude: float - latitude
            longitude: float - longitude
            confidence: float - confidence
            source: str - source

        Returns:
            bool - True if coordinates were saved, False otherwise
        """
        try:
            if not self._validate_ukraine_coordinates(latitude, longitude):
                return False
            
            normalized_region = self.normalize_region_name(region_name)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO cities 
                    (city_name, region_name, latitude, longitude, confidence, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (city_name, normalized_region, latitude, longitude, confidence, source))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving to DB: {e}")
            return False
    
    def _validate_ukraine_coordinates(self, latitude: float, longitude: float) -> bool:
        """
        Check if coordinates are within Ukraine
        
        Args:
            latitude: float - latitude
            longitude: float - longitude
            
        Returns:
            bool - True if coordinates are within Ukraine, False otherwise
        """
        return (44.0 <= latitude <= 52.5) and (22.0 <= longitude <= 40.5)
    
    # def city_exists_with_different_coordinates(self, city_name: str, region_name: str, 
    #     latitude: float, 
    #     longitude: float, 
    #     tolerance: float = 0.01
    # ) -> bool:
    #     """
    #     Check if city exists with different coordinates
        
    #     Args:
    #         city_name: str - city name
    #         region_name: str - region name
    #         latitude: float - latitude
    #         longitude: float - longitude
    #         tolerance: float - tolerance
            
    #     Returns:
    #         bool - True if city exists with different coordinates, False otherwise
    #     """
    #     try:
    #         with sqlite3.connect(self.db_path) as conn:
    #             cursor = conn.cursor()
    #             cursor.execute('''
    #                 SELECT latitude, longitude, region_name 
    #                 FROM cities 
    #                 WHERE city_name = ?
    #             ''', (city_name,))
                
    #             results = cursor.fetchall()
    #             for db_lat, db_lon, db_region in results:
    #                 lat_diff = abs(db_lat - latitude)
    #                 lon_diff = abs(db_lon - longitude)
                    
    #                 if lat_diff < tolerance and lon_diff < tolerance and db_region != region_name:
    #                     logger.warning(f"Duplicate found: {city_name} in {db_region} with coordinates {db_lat}, {db_lon}")
    #                     return True
                        
    #             return False
    #     except Exception as e:
    #         logger.error(f"Error checking duplicates: {e}")
    #         return False
    
    def get_region_coordinates(self, region_name: str) -> Optional[Dict[str, Any]]:
        """
        Get region coordinates from database (case-insensitive search)
        
        Args:
            region_name: str - region name
            
        Returns:
            Optional[Dict[str, Any]] - dictionary with region coordinates
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT latitude, longitude, confidence, source 
                    FROM regions 
                    WHERE LOWER(region_name) = LOWER(?)
                ''', (region_name.strip(),))
                
                result = cursor.fetchone()
                if result:
                    latitude, longitude, confidence, source = result
                    logger.info(f"Found region in DB: {region_name}")
                    return {
                        "coordinates": {
                            "latitude": latitude,
                            "longitude": longitude
                        },
                        "confidence": confidence,
                        "source": f"database_{source}"
                    }
                return None
        except Exception as e:
            logger.error(f"Error reading region from DB: {e}")
            return None
    
    def save_region_coordinates(
        self, region_name: str, latitude: float, 
        longitude: float, confidence: float = 0.8, source: str = "AI"
    ) -> bool:
        """
        Save region coordinates to database
        
        Args:
            region_name: str - region name
            latitude: float - latitude
            longitude: float - longitude
            confidence: float - confidence
            source: str - source

        Returns:
            bool - True if coordinates were saved, False otherwise
        """
        try:
            if not self._validate_ukraine_coordinates(latitude, longitude):
                logger.warning(f"Region coordinates {region_name} out of Ukraine: {latitude}, {longitude}")
                return False
            
            normalized_region = self.normalize_region_name(region_name)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id FROM regions 
                    WHERE LOWER(region_name) = LOWER(?)
                ''', (normalized_region,))
                
                if cursor.fetchone():
                    logger.info(f"Region {region_name} already exists in DB, skipping save")
                    return True
                
                cursor.execute('''
                    INSERT INTO regions 
                    (region_name, latitude, longitude, confidence, source)
                    VALUES (?, ?, ?, ?, ?)
                ''', (normalized_region, latitude, longitude, confidence, source))
                
                conn.commit()
                logger.info(f"Saved region to DB: {normalized_region} -> {latitude}, {longitude}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving region to DB: {e}")
            return False

    def clean_region_duplicates(self) -> int:
        """
        Clean duplicate regions from database (case-insensitive)
        
        Returns:
            int - number of duplicates removed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find case-insensitive duplicates
                cursor.execute('''
                    SELECT LOWER(region_name) as lower_name, 
                           COUNT(*) as count,
                           GROUP_CONCAT(id) as ids,
                           GROUP_CONCAT(region_name) as names
                    FROM regions 
                    GROUP BY LOWER(region_name) 
                    HAVING COUNT(*) > 1
                ''')
                
                duplicates = cursor.fetchall()
                total_removed = 0
                
                for lower_name, count, ids_str, names_str in duplicates:
                    ids = [int(x) for x in ids_str.split(',')]
                    names = names_str.split(',')
                    
                    logger.info(f"Found {count} case variations for region: {lower_name}")
                    logger.info(f"Variations: {names}")
                    
                    # Keep the latest entry (highest id) and normalize its name
                    latest_id = max(ids)
                    latest_index = ids.index(latest_id)
                    latest_name = names[latest_index]
                    
                    # Normalize and update the latest entry
                    normalized_name = self.normalize_region_name(latest_name)
                    cursor.execute('''
                        UPDATE regions 
                        SET region_name = ? 
                        WHERE id = ?
                    ''', (normalized_name, latest_id))
                    
                    # Remove all other entries
                    for region_id in ids:
                        if region_id != latest_id:
                            cursor.execute('DELETE FROM regions WHERE id = ?', (region_id,))
                            total_removed += 1
                    
                    logger.info(f"Kept {normalized_name} (id: {latest_id}), removed {count-1} duplicates")
                
                conn.commit()
                logger.info(f"Total region duplicates removed: {total_removed}")
                return total_removed
                
        except Exception as e:
            logger.error(f"Error cleaning duplicates: {e}")
            return 0

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dict[str, Any] - dictionary with database statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total number of cities
                cursor.execute('SELECT COUNT(*) FROM cities')
                total_cities = cursor.fetchone()[0]
                
                # Total number of regions from cities table
                cursor.execute('SELECT COUNT(DISTINCT region_name) FROM cities')
                total_regions_cities = cursor.fetchone()[0]
                
                # Total number of regions from regions table
                cursor.execute('SELECT COUNT(*) FROM regions')
                total_regions_coords = cursor.fetchone()[0]
                
                # Data sources
                cursor.execute('SELECT source, COUNT(*) FROM cities GROUP BY source')
                sources = dict(cursor.fetchall())
                
                return {
                    "total_cities": total_cities,
                    "total_regions": total_regions_cities,
                    "total_regions_with_coords": total_regions_coords,
                    "sources": sources,
                    "database_path": self.db_path
                }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

class AIConverter:
    """
    Class for converting input data to JSON dictionary

    Args:
        api_delay: float - delay between API calls
        max_retries: int - maximum number of retries
    """
    def __init__(self, api_delay: float = 2.0, max_retries: int = 3):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.error("GOOGLE_API_KEY not found")
            raise ValueError("GOOGLE_API_KEY not found")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(AI_MODEL)
        
        self.db = SQLiteFlow()
        self.api_delay = api_delay
        self.max_retries = max_retries 
        self._last_api_call = 0
        self._api_lock = threading.Lock()
        self.instructions = self._load_model_instructions()
        
    def _load_model_instructions(self) -> str:
        """
        Load model instructions from file
        
        Returns:
            str - model instructions
        """
        with open("data/model_instructions.md", "r", encoding="utf-8") as f:
            return f.read()
        
    def extract_weapon_info(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract weapon information, grouping by regions
        
        Args:
            text: str - input text
            
        Returns:
            Dict[str, List[Dict[str, Any]]] - dictionary with regions and weapons
        """
        regions = {}
        
        lines = text.strip().split('\n')
        current_region = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.endswith(':'):
                current_region = line.replace(':', '')
                if current_region not in regions:
                    regions[current_region] = []
                continue
            
            if current_region:
                # Special processing for "Group/Groups KR"
                group_kr_match = re.search(r'(?:(\d+)х?\s+)?(?:ГРУПИ?|Групи?)\s+КР\s+курсом\s+на\s+(.+)', line, re.IGNORECASE)
                if group_kr_match:
                    count_str, target_city = group_kr_match.groups()
                    groups_count = int(count_str) if count_str else 1
                    total_count = groups_count * 2  # Each group = 2 units
                    
                    
                    regions[current_region].append({
                        'weapon_type': "Х101",
                        'count': total_count,
                        'target_city': target_city.strip()
                    })
                    continue
                
                # Regular pattern for other weapon types
                standard_match = re.search(r'(?:(\d+)х?\s+)?(\S+)\s+курсом\s+на\s+(.+)', line)
                if standard_match:
                    count_str, weapon_type, target_city = standard_match.groups()
                    count = int(count_str) if count_str else 1
                    
                    # Mapping for regular KR (without "group" word)
                    if weapon_type.upper() == "КР":
                        weapon_type = "Х101"
                                        
                    regions[current_region].append({
                        'weapon_type': weapon_type,
                        'count': count,
                        'target_city': target_city.strip()
                    })
        
        logger.info(f"Found regions: {list(regions.keys())}")
        # for region, weapons in regions.items():
        #     logger.info(f"{region}: {len(weapons)} directions")
        
        return regions

    def _rate_limited_api_call(self, prompt: str) -> Optional[str]:
        """
        Make API call with rate limiting and retry logic
        
        Args:
            prompt: str - prompt for AI
            
        Returns:
            Optional[str] - response from AI or None
        """
        with self._api_lock:
            current_time = time.time()
            time_since_last_call = current_time - self._last_api_call
            
            if time_since_last_call < self.api_delay:
                sleep_time = self.api_delay - time_since_last_call
                logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Making API call (attempt {attempt + 1}/{self.max_retries})")
                    response = self.model.generate_content(prompt)
                    self._last_api_call = time.time()
                    
                    if response and response.text:
                        return response.text.strip()
                    else:
                        logger.warning("Empty response from Gemini API")
                        
                except Exception as e:
                    error_message = str(e)
                    logger.error(f"Gemini API error (attempt {attempt + 1}): {error_message}")
                    
                    if "quota" in error_message.lower() or "429" in error_message:
                        if attempt < self.max_retries - 1:
                            backoff_time = (2 ** attempt) * 10 + random.uniform(1, 5)
                            logger.info(f"Quota exceeded, waiting {backoff_time:.2f} seconds before retry")
                            time.sleep(backoff_time)
                        else:
                            logger.error("Max retries exceeded for quota error")
                            return None
                    elif "rate limit" in error_message.lower():
                        if attempt < self.max_retries - 1:
                            backoff_time = self.api_delay * (2 ** attempt) + random.uniform(1, 3)
                            logger.info(f"Rate limit hit, waiting {backoff_time:.2f} seconds before retry")
                            time.sleep(backoff_time)
                        else:
                            logger.error("Max retries exceeded for rate limit error")
                            return None
                    else:
                        if attempt < self.max_retries - 1:
                            time.sleep(1 + random.uniform(0.5, 1.5))
                
                self._last_api_call = time.time()
            
            logger.error(f"All {self.max_retries} attempts failed")
            return None

    def get_region_coordinates_from_ai(self, region_name: str, weapons_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get region coordinates from prompt to AI
        
        Args:
            region_name: str - region name
            weapons_list: List[Dict[str, Any]] - list of weapons
            
        Returns:
            Dict[str, Any] - dictionary with region coordinates
        """
        targets = []
        weapons_for_ai = []
        
        region_coords = self.db.get_region_coordinates(region_name)
        
        for weapon in weapons_list:
            city_name = weapon['target_city']
            db_coords = self.db.get_city_coordinates(city_name, region_name)
            
            if db_coords:
                targets.append({
                    "city": city_name,
                    "weapon_type": weapon['weapon_type'],
                    "count": weapon['count'],
                    "coordinates": db_coords['coordinates'],
                    "confidence": db_coords['confidence'],
                    "source": db_coords['source']
                })
            else:
                weapons_for_ai.append(weapon)
        
        if weapons_for_ai or not region_coords:
            logger.info(f"Request to AI for {len(weapons_for_ai)} cities from {region_name}")
            
            input_data = {
                "region": region_name,
                "weapons": weapons_for_ai
            }
            
            prompt = f"""
                {self.instructions}

                INPUT:
                {json.dumps(input_data, ensure_ascii=False)}

                RETURN ONLY JSON:""".strip()

            try:
                response_text = self._rate_limited_api_call(prompt)
                
                if response_text is None:
                    logger.error("Failed to get response from API after all retries")
                    return {"error": "api_error"}
                
                cleaned_response = self.clean_json_response(response_text)
                ai_result = json.loads(cleaned_response)
                
                if 'region_coordinates' in ai_result and not region_coords:
                    reg_coords = ai_result['region_coordinates']
                    self.db.save_region_coordinates(
                        region_name=region_name,
                        latitude=reg_coords['latitude'],
                        longitude=reg_coords['longitude'],
                        confidence=ai_result.get('region_confidence', 0.8),
                        source='Gemini'
                    )
                    region_coords = {
                        "coordinates": reg_coords,
                        "confidence": ai_result.get('region_confidence', 0.8),
                        "source": "database_Gemini"
                    }
                
                if 'targets' in ai_result:
                    for target in ai_result['targets']:
                        targets.append(target)
                        
                        coords = target['coordinates']
                        self.db.save_city_coordinates(
                            city_name=target['city'],
                            region_name=region_name,
                            latitude=coords['latitude'],
                            longitude=coords['longitude'],
                            confidence=target.get('confidence', 0.8),
                            source='Gemini'
                        )
                        
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {e}")
                logger.error(f"Raw response: {response_text}")
                return {"error": "json_parse_error"}
            except Exception as e:
                logger.error(f"General processing error: {e}")
                return {"error": "processing_error"}
        
        result = {
            "region": region_name,
            "targets": targets
        }
        
        if region_coords:
            result["coordinates_rn"] = region_coords['coordinates']
            
        return result

    def clean_json_response(self, response: str) -> str:
        """
        Clean JSON response from prompt to AI
        
        Args:
            response: str - response from AI
            
        Returns:
            str - cleaned response
        """
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'\s*```', '', response)
        
        start_idx = response.find('{')
        if start_idx == -1:
            return response
        
        end_idx = response.rfind('}') + 1
        if end_idx <= start_idx:
            return response
        
        return response[start_idx:end_idx].strip()

    def _process_single_region(self, region_name: str, weapons_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Process single region with weapons list
        
        Args:
            region_name: str - region name
            weapons_list: List[Dict[str, Any]] - list of weapons
            
        Returns:
            Optional[Dict[str, Any]] - dictionary with region data or None
        """
        try:
            coords_data = self.get_region_coordinates_from_ai(region_name, weapons_list)
            
            if 'error' not in coords_data and 'targets' in coords_data:
                region_targets = []
                region_weapons_count = 0
                
                for target in coords_data['targets']:
                    region_targets.append({
                        "city": target["city"],
                        "weapon_type": target["weapon_type"],
                        "count": target["count"],
                        "latitude": target["coordinates"]["latitude"],
                        "longitude": target["coordinates"]["longitude"],
                        "confidence": target.get("confidence", 0.8),
                        "source": target.get("source", "AI_generated")
                    })
                    
                    region_weapons_count += target["count"]
                
                region_data = {
                    "region": region_name,
                    "targets": region_targets,
                    "total_processed": len(region_targets),
                    "tokens_used": 100,
                    "weapons_count": region_weapons_count
                }
                
                if 'coordinates_rn' in coords_data:
                    region_data["coordinates_rn"] = coords_data['coordinates_rn']
                
                return region_data
            else:
                logger.error(f"Error processing region {region_name}: {coords_data}")
                return None
        except Exception as e:
            logger.error(f"Exception processing region {region_name}: {e}")
            return None

    def proccess_data(self, data: str, max_workers: int = 2) -> Dict[str, Any]:
        """
        Process data and return dictionary with regions and weapons (parallel version)
        
        Args:
            data: str - input data
            max_workers: int - maximum number of parallel workers
            
        Returns:
            Dict[str, Any] - dictionary with regions and weapons
        """
        regions_weapons = self.extract_weapon_info(data)
        
        regions_data = []
        total_weapons_count = 0
        all_weapon_types = set()
        total_cities = 0
        
        logger.info(f"Processing {len(regions_weapons)} regions with max_workers={max_workers}")
        
        if max_workers == 1:
            for region_name, weapons_list in regions_weapons.items():
                try:
                    region_data = self._process_single_region(region_name, weapons_list)
                    if region_data:
                        regions_data.append(region_data)
                        
                        total_weapons_count += region_data.get("weapons_count", 0)
                        total_cities += len(region_data["targets"])
                        
                        for target in region_data["targets"]:
                            all_weapon_types.add(target["weapon_type"])
                        
                        logger.info(f"Successfully processed region: {region_name}")
                    else:
                        logger.error(f"Failed to process region: {region_name}")
                except Exception as e:
                    logger.error(f"Exception for region {region_name}: {e}")
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_region = {
                    executor.submit(self._process_single_region, region_name, weapons_list): region_name
                    for region_name, weapons_list in regions_weapons.items()
                }
                
                for future in as_completed(future_to_region):
                    region_name = future_to_region[future]
                    try:
                        region_data = future.result()
                        if region_data:
                            regions_data.append(region_data)
                            
                            total_weapons_count += region_data.get("weapons_count", 0)
                            total_cities += len(region_data["targets"])
                            
                            for target in region_data["targets"]:
                                all_weapon_types.add(target["weapon_type"])
                            
                            logger.info(f"Successfully processed region: {region_name}")
                        else:
                            logger.error(f"Failed to process region: {region_name}")
                    except Exception as e:
                        logger.error(f"Exception for region {region_name}: {e}")
        
        result = {
            "regions": regions_data,
            "total_regions": len(regions_data),
            "total_cities": total_cities,
            "total_weapons_used": list(all_weapon_types),
            "total_weapons_count": total_weapons_count,
            "total_tokens_used": sum(r.get("tokens_used", 0) for r in regions_data),
            "processing_mode": "sequential" if max_workers == 1 else "parallel", 
            "status": "success",
            "database_stats": self.db.get_database_stats()
        }
        
        return result
