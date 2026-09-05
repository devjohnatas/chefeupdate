import os
from dotenv import load_dotenv

load_dotenv()

class BotConfig:
    def __init__(
        self,
        name: str,
        token: str,
        db_path: str,
        api_base_url: str,
        api_key: str,
        api_type: str,
        command_prefix: str = "/",
        allowed_guild_id: int = 0,
        command_channel_id: int = 0,
        announcement_channel_id: int = 0,
        adult_channel_id: int = 0,
        publication_channel_id: int = 0,
        cargo_fixo_id: int = 0,
        leitores_role_id: int = 0,
        log_channel_id: int = 0,
        cargo_base_id: int = 0,
        # Yomu specific
        yomu_translation_channel_id: int = 0,
        scan_channel_id: int = 0,
        cargo_limite_inferior_id: int = 0,
        cargo_translation_id: int = 0,
    ):
        self.name = name
        self.token = token
        self.db_path = db_path
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.api_type = api_type # 'yomu', 'senpai', 'coruja'
        self.command_prefix = command_prefix
        
        self.allowed_guild_id = allowed_guild_id
        self.command_channel_id = command_channel_id
        self.announcement_channel_id = announcement_channel_id
        self.adult_channel_id = adult_channel_id
        self.publication_channel_id = publication_channel_id
        
        self.cargo_fixo_id = cargo_fixo_id
        self.leitores_role_id = leitores_role_id
        self.log_channel_id = log_channel_id
        self.cargo_base_id = cargo_base_id
        
        # Yomu specific
        self.yomu_translation_channel_id = yomu_translation_channel_id
        self.scan_channel_id = scan_channel_id
        self.cargo_limite_inferior_id = cargo_limite_inferior_id
        self.cargo_translation_id = cargo_translation_id

# -----------------
# YOMU CONFIG
# -----------------
YOMU_CONFIG = BotConfig(
    name="Yomu",
    token=os.getenv('YOMU_DISCORD_TOKEN', ''),
    db_path="databases/yomu_bot.db",
    api_base_url="https://yomu.com.br/api/v1",
    api_key=os.getenv('YOMU_API_TOKEN', 'yomucomics_3f7a9c2d1b8e4f5a9d6c7b1e0f2a8c9d'),
    api_type="yomu",
    allowed_guild_id=1270029470438260797,
    command_channel_id=1374077861547348059,
    adult_channel_id=1449470347555508430,
    cargo_fixo_id=1332877347979792506,
    leitores_role_id=1332861606081728573,
    log_channel_id=1335305435665924106,
    
    yomu_translation_channel_id=1462819658372485315,
    scan_channel_id=1499875308688637962,
    cargo_limite_inferior_id=1335301257929166900,
    cargo_translation_id=1463186265502384221
)

# -----------------
# SENPAI CONFIG
# -----------------
SENPAI_CONFIG = BotConfig(
    name="SenPai",
    token=os.getenv('SENPAI_DISCORD_TOKEN', ''),
    db_path="databases/lancamento_senpai.db",
    api_base_url="https://senpaiscan.com/api/bot",
    api_key=os.getenv('SENPAI_API_KEY', ''),
    api_type="senpai",
    allowed_guild_id=1450494368384286772,
    announcement_channel_id=1450507000952918217,
    adult_channel_id=1450507000952918217,
    command_channel_id=1450910762049601537,
    publication_channel_id=1450507000952918217,
    cargo_fixo_id=1332877347979792506,
    leitores_role_id=1332861606081728573,
    log_channel_id=1450910762049601537,
    cargo_base_id=1452026938674643096
)

# -----------------
# CORUJA CONFIG
# -----------------
CORUJA_CONFIG = BotConfig(
    name="Coruja",
    token=os.getenv('CORUJA_DISCORD_TOKEN', ''),
    db_path="databases/coruja_lancamentos.db",
    api_base_url=os.getenv('CORUJA_API_BASE_URL', "http://localhost:3000/api/bot"),
    api_key=os.getenv('CORUJA_API_KEY', 'corujatoon1254546'),
    api_type="coruja",
    allowed_guild_id=1439799955475791968,
    announcement_channel_id=1440153252875210812,
    adult_channel_id=1449480019624853655,
    command_channel_id=1490444231461044264,
    publication_channel_id=1440153252875210812,
    cargo_fixo_id=1332877347979792506,
    leitores_role_id=1332861606081728573,
    log_channel_id=1335305435665924106,
    cargo_base_id=1440807311848374282
)
