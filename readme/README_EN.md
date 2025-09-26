# 🗺️ FREE MONITOR - English Documentation

## 📋 Project Description

**FREE MONITOR** - automated aerial threats visualization system for Ukraine map. Based on data from Telegram monitoring channels, it automatically:

🔹 **Parses data** from Telegram channels about weapon attacks and flight directions  
🔹 **Processes information** using AI (Google Gemini) to obtain coordinates  
🔹 **Stores data** in SQLite database for fast access  
🔹 **Generates maps** with trajectories and threat types visualization  
🔹 **Creates infographics** with current information  

## ⚠️ IMPORTANT
- **At the current development stage, only [Rinda Monitoring](https://t.me/kudy_letyt) channel is supported**, the process for using other channels is described below!

## 🎯 Core Functionality

### 📡 Telegram Parser (`core/tg_parser.py`)
- Connection to Telegram API via Pyrogram
- Parsing messages from channels
- Time filtering (only current data - last 20 minutes)
- Automatic removal of duplicate routes

### 🤖 AI Converter (`core/ai_converter.py`)
- Using Google Gemini API for text data processing
- Recognition of weapon types: UAVs, Cruise missiles (X101), Ballistics
- Determining coordinates of cities and regions of Ukraine
- Coordinate validation (checking belonging to Ukraine territory)
- Multi-threaded processing for increased speed

### 🗃️ SQLite Database (`core/ai_converter.py: SQLiteFlow`)
- Storage of city and region coordinates
- Region name normalization
- Connection pool for performance optimization
- Automatic duplicate removal
- Database usage statistics

### 🗺️ Visualization (`core/visual_map.py`)
- Map generation in 1920x1080 pixels resolution
- Using Natural Earth vector data
- Display of cities, regions and Ukraine borders
- Visualization of weapon trajectories with different icons
- Information panels with current data

## 📁 Project Structure

```
free_monitor/
├── core/                   # Core system modules
│   ├── ai_converter.py     # AI processing and database
│   ├── config.py           # Colors and constants configuration
│   ├── tg_parser.py        # Telegram parser
│   ├── utils.py            # Helper functions
│   └── visual_map.py       # Map generation
│
├── data/                   # Data and instructions
│   └── model_instructions.md # AI model instructions
│
├── db/                     # Database
│   └── cities_coordinates.db # SQLite coordinates database
│
├── gened_maps/             # Generated maps
│   └── map_*.png           # Maps with timestamps
│
├── logs/                   # Logs
│   └── *.log               # Telegram parser logs
│
├── shapes/                              # Geographic data
│   ├── ne_10m_admin_0_countries/        # Country borders
│   ├── ne_10m_admin_1_states_provinces/ # Regions/states
│   ├── ne_10m_populated_places/         # Populated places
│   └── ne_10m_rivers_lake_centerlines/  # Rivers and lakes
│
├── telegram_sessions/     # Telegram sessions
│   └── *.session          # Session files
│
├── weapons/              # Weapon icons
│   ├── balistic.svg      # Ballistic missiles
│   ├── uav.svg           # UAVs
│   └── x101.svg          # Cruise missiles
│
├── main.py               # Entry point
└── pyproject.toml        # Project configuration
```

## 🚀 Installation and Setup

### Prerequisites
- Python 3.10+
- **One of package managers** (choose one):
  - [UV package manager](https://docs.astral.sh/uv/#highlights) (recommended)
  - [Poetry](https://python-poetry.org/docs/#installation)
  - pip
- [Telegram API keys](https://my.telegram.org/apps)
- [Google Gemini API key](https://aistudio.google.com/app/api-keys)

### 1. Clone Repos
```bash
git clone <repository-url>
cd free_monitor
```

### 2. Install Dependencies

Choose one of the dependency installation options:

#### Option 1: UV (recommended)
```bash
uv sync
```

#### Option 2: Poetry
```bash
# First copy Poetry configuration
cp pyproject_poetry.toml pyproject.toml

# Install dependencies
poetry install
```

#### Option 3: pip + requirements.txt
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables Setup
Create `.env` file based on `.env.example` or the fragment below:
```env
# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number

# Google Gemini API
GOOGLE_API_KEY=your_google_api_key
```

### 4. Run

Depending on chosen installation method:

#### UV:
```bash
uv run main.py
```

#### Poetry:
```bash
poetry run python main.py
```

#### pip + venv:
```bash
# Make sure virtual environment is activated
python main.py
```

## ⚙️ Configuration

### Color Scheme (`core/config.py`)
```python
COLORS = {
    'background': '#0f1115',     # [HEX] Map background
    'ukraine_fill': '#1f2a37',   # [HEX] Ukraine fill
    'border_line': '#9aa5b1',    # [HEX] Border lines
    'target': '#ff4444',         # [HEX] Targets
    'arrow': '#ffff44',          # [HEX] Arrows
    # ... other colors
}
```

### Weapon Types and Colors
```python
WEAPON_COLORS = {
    'БпЛА': '#CE983C',           # [HEX] Orange
    'х101': '#4488ff',           # [HEX] Blue
    'Балістика': '#ff4444',      # [HEX] Red
}
```

### AI Model Used for Processing
```python
AI_MODEL = 'gemini-2.0-flash-lite' # Cheapest model
```

## 🔄 Workflow Algorithm

1. **Data Collection**: Telegram parser gets last 7 messages from monitoring channels
2. **Filtering**: Removes outdated messages (older than 20 minutes) and duplicate directions (*information about weapon count per direction is dynamic*)
3. **AI Processing**: Google Gemini analyzes text and determines:
   - Attack regions
   - Weapon types
   - Target cities
   - Precise coordinates (*Region and direction*)
4. **Storage**: Data is stored in SQLite database for future use
   - If a settlement already exists in the database, it will be used directly without additional AI calls
5. **Visualization**: Map is generated with:
   - Ukraine and regions contours
   - City markers (*Settlement name*)
   - Weapon trajectories with corresponding icons
   - Information panels (*Date, type and weapon count*)

## 🛠️ Technologies and Dependencies

See full dependencies list in `pyproject.toml`, `requirements.txt` or `pyproject_poetry.toml` files.

## 📈 Statistics and Monitoring

The system maintains detailed statistics:
- Number of processed regions
- Total target count
- Used weapon types
- Request processing time
- Database statistics

## 🔧 Functionality Extension

### Adding Other Telegram Channels
1. Create / modify parser in `core/` folder
2. Implement data collection interface
3. Modify AI prompt `data/model_instruction.md` for your needs
4. Add processing in `main.py`

### Adding New Weapon Types
1. Add SVG icon to `weapons/` folder
2. Update configuration in `core/config.py`
3. Add AI processing (topology, conversion to required format)

## 🐛 Debugging

### Logs
All logs are stored in `logs/` folder:
- `*.logs`

### Common Issues
1. **Telegram API errors**: Check API keys correctness
2. **Google Gemini errors**: Check quotas and API key
3. **Missing coordinates**: Check database state \ AI

## 🤝 Contributing

The project is fully open source for non-commercial use. Improvement suggestions are welcome:

1. Create repository fork
2. **Mandatory** rewrite telegram parser for your channel in `core/tg_parser.py`
3. Make changes to AI instructions in `core/ai_converter.py` `data/model_instructions.md`
4. Adapt other code parts for your needs
5. Create Pull Request with changes description

## ⚠️ Disclaimer

The project is created for visualization and monitoring information based on data from open sources (*telegram channels*). Authors are not responsible for real-time data accuracy, errors are possible. Always use official sources for threat information.

---
🇺🇦 **Glory to Ukraine!**
