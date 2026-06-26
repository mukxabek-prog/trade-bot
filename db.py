"""
Steal a Brainrot o'yinidagi rarity tizimiga asoslangan (Common -> OG) virtual
brainrot katalogi. Narxlar VIRTUAL COIN da, real Robux/pul bilan hech qanday
bog'liqligi yo'q — bu shunchaki bot ichidagi o'yin iqtisodiyoti.

Diqqat: asl o'yin har hafta yangi brainrotlar bilan to'ldiriladi va narxlar
o'zgaradi, shu sababli bu yerdagi ro'yxat "ilhomlangan" ro'yxat, 100% rasmiy
nusxa emas. Xohlagan vaqtda shu fayldagi ro'yxatni o'zgartirib, o'zingiz
yangi item, rarity yoki narx qo'shishingiz mumkin.
"""

RARITY_ORDER = [
    "Common",
    "Rare",
    "Epic",
    "Legendary",
    "Mythic",
    "Brainrot God",
    "Secret",
    "OG",
]

RARITY_EMOJI = {
    "Common": "⚪️",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟠",
    "Mythic": "🔴",
    "Brainrot God": "🟡",
    "Secret": "⚫️",
    "OG": "✨",
}

# /shop "konveyer"ida shu rarity'dan item chiqish ehtimoli (foizlarda, jami 100)
RARITY_SPAWN_WEIGHT = {
    "Common": 40,
    "Rare": 25,
    "Epic": 15,
    "Legendary": 10,
    "Mythic": 5,
    "Brainrot God": 3,
    "Secret": 1.5,
    "OG": 0.5,
}

# id, nom, rarity, narx (coin)
BRAINROTS = [
    # ---- Common ----
    {"id": 1, "name": "Noobini Pizzanini", "rarity": "Common", "price": 50},
    {"id": 2, "name": "Pipi Corni", "rarity": "Common", "price": 70},
    {"id": 3, "name": "Capuccino Assassino", "rarity": "Common", "price": 90},
    {"id": 4, "name": "Lirili Larila", "rarity": "Common", "price": 110},
    {"id": 5, "name": "Boneca Ambalabu", "rarity": "Common", "price": 130},

    # ---- Rare ----
    {"id": 6, "name": "Trippi Troppi", "rarity": "Rare", "price": 180},
    {"id": 7, "name": "Pinealotto Fruttarino", "rarity": "Rare", "price": 220},
    {"id": 8, "name": "Brr Brr Patapim", "rarity": "Rare", "price": 260},
    {"id": 9, "name": "Tralalero Tralala", "rarity": "Rare", "price": 320},
    {"id": 10, "name": "Chimpanzini Bananini", "rarity": "Rare", "price": 380},

    # ---- Epic ----
    {"id": 11, "name": "Bombardiro Crocodillo", "rarity": "Epic", "price": 450},
    {"id": 12, "name": "Tung Tung Tung Sahur", "rarity": "Epic", "price": 550},
    {"id": 13, "name": "Ballerina Cappuccina", "rarity": "Epic", "price": 650},
    {"id": 14, "name": "Trulimero Trulicina", "rarity": "Epic", "price": 800},
    {"id": 15, "name": "Espresso Signora", "rarity": "Epic", "price": 950},

    # ---- Legendary ----
    {"id": 16, "name": "Burbaloni Loliloli", "rarity": "Legendary", "price": 1100},
    {"id": 17, "name": "Seraphino Gruyero", "rarity": "Legendary", "price": 1500},
    {"id": 18, "name": "Garamaraman Dengoroman", "rarity": "Legendary", "price": 1900},
    {"id": 19, "name": "Crocodildo Penguino", "rarity": "Legendary", "price": 2400},
    {"id": 20, "name": "Torrtuginni Dragonfruitini", "rarity": "Legendary", "price": 2900},

    # ---- Mythic ----
    {"id": 21, "name": "Frigo Camelo", "rarity": "Mythic", "price": 3300},
    {"id": 22, "name": "Berenjello Angello", "rarity": "Mythic", "price": 4200},
    {"id": 23, "name": "Bobritto Bandito Supremo", "rarity": "Mythic", "price": 5100},
    {"id": 24, "name": "Tigrullini Watermelondrini", "rarity": "Mythic", "price": 6300},
    {"id": 25, "name": "Orangutini Ananassini", "rarity": "Mythic", "price": 7500},

    # ---- Brainrot God ----
    {"id": 26, "name": "Cocofanto Elefanto", "rarity": "Brainrot God", "price": 9000},
    {"id": 27, "name": "Dumborino Miracello", "rarity": "Brainrot God", "price": 12000},
    {"id": 28, "name": "Girafaiana Coffeena", "rarity": "Brainrot God", "price": 15500},
    {"id": 29, "name": "Rhinotonkoo Lavandelu", "rarity": "Brainrot God", "price": 19000},

    # ---- Secret ----
    {"id": 30, "name": "La Vacca Saturno Saturnita", "rarity": "Secret", "price": 24000},
    {"id": 31, "name": "Jackorilla", "rarity": "Secret", "price": 32000},
    {"id": 32, "name": "Coffin Tung Tung Tung Sahur", "rarity": "Secret", "price": 41000},
    {"id": 33, "name": "Griffin", "rarity": "Secret", "price": 58000},

    # ---- OG ----
    {"id": 34, "name": "Headless Horseman", "rarity": "OG", "price": 70000},
    {"id": 35, "name": "John Pork", "rarity": "OG", "price": 85000},
    {"id": 36, "name": "Skibidi Toilet", "rarity": "OG", "price": 100000},
    {"id": 37, "name": "Meowl", "rarity": "OG", "price": 125000},
    {"id": 38, "name": "Strawberry Elephant", "rarity": "OG", "price": 145000},
]

BRAINROTS_BY_ID = {item["id"]: item for item in BRAINROTS}


def get_item(item_id: int):
    return BRAINROTS_BY_ID.get(item_id)


def items_by_rarity(rarity: str):
    return [i for i in BRAINROTS if i["rarity"] == rarity]
