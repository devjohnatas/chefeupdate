import asyncio
import os
import sys

# Ensure src is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config.config import YOMU_CONFIG, SENPAI_CONFIG, CORUJA_CONFIG
from src.bot import ConfigBot

async def start_bot(config):
    if not config.token:
        print(f"⚠️ Aviso: Token para {config.name} não encontrado. O bot não será iniciado.")
        return
        
    bot = ConfigBot(config)
    try:
        await bot.start(config.token)
    except Exception as e:
        print(f"❌ Erro fatal no bot {config.name}: {e}")

async def main():
    print("Iniciando Sistema Multi-Bots (Chefe-update)...")
    
    # Criar diretório de databases se não existir
    if not os.path.exists("databases"):
        os.makedirs("databases")
        
    bots = [
        start_bot(YOMU_CONFIG),
        start_bot(SENPAI_CONFIG),
        start_bot(CORUJA_CONFIG)
    ]
    
    await asyncio.gather(*bots)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDesligando os bots...")
