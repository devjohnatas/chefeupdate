import discord
from discord import ButtonStyle, ui
import re
from src.config.config import BotConfig

def format_chapter_number(chapter_str):
    if not chapter_str:
        return "N/A"
    
    if "ao" not in chapter_str:
        return chapter_str
    
    try:
        parts = chapter_str.split("ao")
        num1 = int(parts[0].strip())
        num2 = int(parts[1].strip())
        
        start = min(num1, num2)
        end = max(num1, num2)
        
        if start == end:
            return str(start)
        
        return f"{start} ao {end}"
    except (ValueError, IndexError):
        return chapter_str

def extract_last_chapter_number(chapter_str):
    if not chapter_str:
        return 0

    numbers = re.findall(r'\d+', chapter_str)

    if not numbers:
        return 0

    try:
        last_number = max(int(n) for n in numbers)
        return last_number
    except ValueError:
        return 0
    except Exception as e:
        print(f"Erro ao extrair número do capítulo '{chapter_str}': {e}")
        return 0

class PartnerButton(ui.View):
    def __init__(self, partner_link):
        super().__init__(timeout=None)
        self.add_item(ui.Button(
            label="Entrar no Discord do Parceiro",
            style=ButtonStyle.link,
            url=partner_link
        ))

def create_chapter_embed(obra, capitulo, imagem, config: BotConfig, mensagem=None, mention_everyone=False, mention_leitores=False, style="default", api_description=None, vip_info=None, channel_id=None):
    
    if vip_info is None:
        vip_info = {'vip_only': False, 'release_at': None, 'release_in_minutes': None}
    
    vip_only = vip_info.get('vip_only', False)
    release_at = vip_info.get('release_at')
    release_in_minutes = vip_info.get('release_in_minutes')
    
    is_released = release_at is None or release_in_minutes is None or release_in_minutes <= 0

    cargo_fixo_to_use = config.cargo_fixo_id
    if config.api_type == 'yomu' and channel_id and str(channel_id) == str(config.yomu_translation_channel_id):
        cargo_fixo_to_use = config.cargo_translation_id

    mentions = [f"<@&{cargo_fixo_to_use}>"] if cargo_fixo_to_use else []
    
    if obra.get("cargo_id"):
        mentions.append(f"<@&{obra['cargo_id']}>")
    if mention_everyone:
        mentions.append("@everyone")
    if mention_leitores and config.leitores_role_id:
        mentions.append(f"<@&{config.leitores_role_id}>")
    if obra.get('parceiro') and obra['parceiro'].get('nome') and config.cargo_fixo_id:
        mentions.append(f"<@&{config.cargo_fixo_id}>")
        
    mention_str = " ".join(mentions)

    formatted_chapter = format_chapter_number(capitulo)

    embed = None
    content = mention_str
    view = None
    
    site_url = "https://yomu.com.br" if config.api_type == 'yomu' else ("https://senpaiscan.com" if config.api_type == 'senpai' else "https://corujatoon.com")
    site_name = "Yomu" if config.api_type == 'yomu' else ("SenPai" if config.api_type == 'senpai' else "Coruja")
    
    # Custom color per bot
    color = discord.Color.orange() if config.api_type == 'yomu' else (discord.Color.from_rgb(95, 12, 165) if config.api_type == 'senpai' else discord.Color.blue())
    
    if style == "image_like":
        message_text = f"{mention_str}\n\n"
        message_text += f"**{obra['nome']} - Capítulo(s) {formatted_chapter}**\n"
        
        if vip_only:
            message_text += f"👑 **CAPÍTULO VIP**\n"
        
        if not is_released and release_in_minutes and release_in_minutes > 0:
            hours = release_in_minutes // 60
            minutes = release_in_minutes % 60
            if hours > 0:
                message_text += f"⏰ **Liberação em {hours}h {minutes}min**\n"
            else:
                message_text += f"⏰ **Liberação em {minutes}min**\n"
        else:
            message_text += f"✨ Um novo capítulo foi lançado!\n"

        message_text += f"\n🔗 Leia agora no {site_name}: <{site_url}>\n"
        message_text += f"\n*Para receber notificações desta obra na sua DM, acesse o site, vá em configurações e depois adicione-a no menu de notificações.*\n"

        if mensagem: 
            message_text += f"\n💬 Mensagem da Staff:\n>>> {mensagem}\n"

        if obra.get('parceiro') and obra['parceiro'].get('nome'):
            if config.api_type == 'yomu' and channel_id and str(channel_id) == str(config.scan_channel_id):
                message_text += f"\n🤝 Está obra está sendo traduzida pela scan {obra['parceiro']['nome']}.\n"
            else:
                message_text += f"\n🤝 Obra em parceria com {obra['parceiro']['nome']}.\n"
            if obra['parceiro'].get('link'):
                message_text += f"🔗 Link do Discord deles: <{obra['parceiro']['link']}>\n"
             
        content = message_text.strip()
        embed = None

    else: 
        description = f"📚 **Capítulo:** `{formatted_chapter}`\n\n"
        
        if vip_only:
            description += "👑 **CAPÍTULO VIP**\n\n"
        
        if not is_released and release_in_minutes and release_in_minutes > 0:
            hours = release_in_minutes // 60
            minutes = release_in_minutes % 60
            if hours > 0:
                description += f"⏰ **Liberação em {hours}h {minutes}min**\n\n"
            else:
                description += f"⏰ **Liberação em {minutes}min**\n\n"
        
        if mensagem:
            description += f"💬 **Staff:**\n>>> {mensagem}\n\n"
        
        description += f"🔗 [**Leia agora no {site_name}!**]({site_url})"
        
        embed = discord.Embed(
            title=f"🔥 Novo Capítulo de {obra['nome']}!",
            description=description,
            color=color
        )
        embed.set_footer(text="Para receber notificações desta obra na sua DM, acesse o site, vá em configurações e depois adicione-a no menu de notificações.")
    
        if obra.get('parceiro') and obra['parceiro'].get('nome'):
             if config.api_type == 'yomu' and channel_id and str(channel_id) == str(config.scan_channel_id):
                 embed.description += f"\n\n🤝 **Está obra está sendo traduzida pela scan {obra['parceiro']['nome']}.**\n"
             else:
                 embed.description += f"\n\n🤝 **Obra em parceria com {obra['parceiro']['nome']}.**\n"
             if obra['parceiro'].get('link'):
                 embed.description += f"🔗 **Link do Discord deles:** {obra['parceiro']['link']}\n"

        if imagem:
            if config.api_type == 'yomu' and channel_id and str(channel_id) == str(config.scan_channel_id):
                embed.set_thumbnail(url=imagem)
            else:
                embed.set_image(url=imagem)
        
        content = mention_str

    view = ui.View(timeout=None)
    
    if config.api_type == 'yomu' and channel_id and str(channel_id) == str(config.yomu_translation_channel_id):
        cargo_obra = obra.get("cargo_id")
        if cargo_obra:
            view.add_item(ui.Button(
                label="Pegar Tag",
                style=discord.ButtonStyle.primary,
                custom_id=f"get_tag_{cargo_obra}"
            ))
            
        view.add_item(ui.Button(
            label="Reportar Capítulo",
            style=discord.ButtonStyle.link,
            url="https://discord.com/channels/1270029470438260797/1271111578476871841"
        ))
        
    if obra.get('parceiro') and obra['parceiro'].get('link'):
        view.add_item(ui.Button(
            label="Discord do Parceiro",
            style=discord.ButtonStyle.link,
            url=obra['parceiro']['link']
        ))
        
    if len(view.children) == 0:
        view = None
        
    return content, embed, view
