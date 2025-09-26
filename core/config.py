# Ukraine cities names map deserealization
UA_NAME_MAP = {
    'Kyiv': 'Київ', 'Kharkiv': 'Харків', 'Odesa': 'Одеса', 'Odessa': 'Одеса',
    'Dnipro': 'Дніпро', 'Dnipropetrovs’k': 'Дніпро', 'Lviv': 'Львів',
    'Zaporizhzhya': 'Запоріжжя', 'Zaporizhya': 'Запоріжжя',
    'Kryvyi Rih': 'Кривий Ріг', 'Mykolayiv': 'Миколаїв', 'Nikolaev': 'Миколаїв',
    'Vinnytsia': 'Вінниця', 'Kherson': 'Херсон', 'Poltava': 'Полтава',
    'Chernihiv': 'Чернігів', 'Cherkasy': 'Черкаси', 'Zhytomyr': 'Житомир',
    'Sumy': 'Суми', 'Khmelnytskyy': 'Хмельницький', 'Khmelnytskyi': 'Хмельницький',
    'Chernivtsi': 'Чернівці', 'Ternopil': 'Тернопіль', 'Ivano-Frankivsk': 'Івано-Франківськ',
    'Rivne': 'Рівне', 'Lutsk': 'Луцьк', 'Kramatorsk': 'Краматорськ',
    'Mariupol': 'Маріуполь', 'Melitopol': 'Мелітополь', 'Berdyans’k': 'Бердянськ', 'Berdyansky': 'Бердянськ', 'Berdyansk': 'Бердянськ',
    'Nikopol': 'Нікополь', 'Kropyvnytskyi': 'Кропивницький', 'Kirovohrad': 'Кіровоград',
    'Kovel': 'Ковель', 'Drohobych': 'Дрогобич', 'Uzhgorod': 'Ужгород',
    'Vinnytsya': 'Вінниця', 'Bila Tserkva': 'Біла Церква', 'Brovary': 'Бровари',
    'Chernobyl': 'Чорнобиль', 'Nizhyn': 'Ніжин', 'Fastiv': 'Фастів', 'Konotop': 'Конотоп',
    'Shostka': 'Шостка', 'Kupyansk': 'Купянськ', 'Kryvyy Rih': 'Кривий Ріг',
    'Kremenchuk': 'Кременчук', 'Voznesensk': 'Вознесенськ', 'Uman': 'Умань', 'Kamyanets-Podilskyy': "Кам'янець-Подільський",
    'Luhanks': 'Луганськ', 'Izmayil': 'Ізмаїл', 'Makiyivka': 'Макіївка',
     'Korosten': 'Коростень', 'Luhansk': 'Луганськ', 'Donetsk': 'Донецьк', 'Horlivka': 'Горлівка', 'Illichivsk': 'Іллічівськ',
     'Lysychansk': 'Лисичанськ',
}

# Excluded cities in map
EXCLUDED_CITIES = (
    'лисичанськ', 'макіївка', 
    'ізмаїл', 'іллічівськ', 'горлівка'
)

COLORS = {
    'background': '#0f1115', 
    'ukraine_fill': '#1f2a37',
    'border_line': '#9aa5b1',
    'region_line': '#4b5563',
    'city_point': '#3d4f67',  
    'city_point_edge': '#A6CBFF',
    'city_label': '#7597c3',
    'target': '#ff4444',
    'region_point': '#44ff44',
    'arrow': '#ffff44',
    'info_text_color': '#A5CBFF',
}

# Weapon colors in HEX
WEAPON_COLORS = {
    'БпЛА': '#CE983C',
    'Крилата ракета': '#4488ff',
    'х101': '#4488ff',
    'Балістика': '#ff4444',
    'Кинжал': '#ff8844',
}

# Weapon icons paths
WEAPON_ICONS = {
    'БпЛА': 'weapons/uav.svg',
    'Крилата ракета': 'weapons/x101.svg',
    'х101': 'weapons/x101.svg',
    'x101': 'weapons/x101.svg',
    'Балістика': 'weapons/balistic.svg',
    'balistic': 'weapons/balistic.svg',
    'Кинжал': 'weapons/balistic.svg',
}

# Icon rotation offset degrees
WEAPON_ICON_ROTATION_OFFSET_DEG = {
    'БпЛА': 90.0,
    'Крилата ракета': 90.0,
    'х101': 90.0,
    'Балістика': 90.0,
    'Кинжал': 90.0,
}

# No targets message
NO_TARGETS_MESSAGE = (
    "Повітряний простір чистий,",
    "або цілі не фіксуються!"
)

# Main label in left corner
LABEL = 'FREE MONITOR'

# AI model for converting data
AI_MODEL = 'gemini-2.0-flash-lite'