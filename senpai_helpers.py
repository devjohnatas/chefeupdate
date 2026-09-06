import discord
from discord import ButtonStyle, ui
import re # Importar o módulo re para usar regex
import time
import random

def format_chapter_number(chapter_str):
    """
    Formata e normaliza o número do capítulo.
    Lida com casos como:
    - "1 ao 5" -> "1 ao 5"
    - "5 ao 1" -> "1 ao 5"
    - "1" -> "1"
    - "1, 2, 3" -> "1, 2, 3"
    """
    if not chapter_str:
        return "N/A"
    
    # Se não contém "ao", retorna o valor original
    if "ao" not in chapter_str:
        return chapter_str
    
    try:
        # Divide a string em números
        parts = chapter_str.split("ao")
        num1 = int(parts[0].strip())
        num2 = int(parts[1].strip())
        
        # Ordena os números
        start = min(num1, num2)
        end = max(num1, num2)
        
        # Se os números são iguais, retorna apenas um
        if start == end:
            return str(start)
        
        # Retorna no formato normalizado
        return f"{start} ao {end}"
    except (ValueError, IndexError):
        # Se houver qualquer erro na conversão, retorna o valor original
        return chapter_str

def extract_last_chapter_number(chapter_str):
    """
    Extrai o último número de uma string de capítulo, lidando com intervalos e números únicos.
    Exemplos:
    - "1 ao 5" -> 5
    - "5 ao 1" -> 5
    - "83" -> 83
    - "1, 2, 3" -> 3
    - "Capítulo 10" -> 10
    - "Extra 5.5" -> 5 (ou 5.5 se necessário, por enquanto int)
    - "abc" -> 0 (ou outro valor padrão/erro)
    """
    if not chapter_str:
        return 0 # Retorna 0 ou -1 se a string for vazia ou None

    # Tenta encontrar todos os números na string
    numbers = re.findall(r'\d+', chapter_str)

    if not numbers:
        return 0 # Nenhum número encontrado

    try:
        # Converte os números encontrados para inteiros e pega o máximo
        # Isso lida com "1 ao 5", "5 ao 1", "1, 2, 3", "Capítulo 10", etc.
        last_number = max(int(n) for n in numbers)
        return last_number
    except ValueError:
        return 0 # Erro na conversão para int, retorna 0
    except Exception as e:
        print(f"Erro ao extrair número do capítulo '{chapter_str}': {e}")
        return 0 # Lida com outros possíveis erros

class PartnerButton(ui.View):
    def __init__(self, partner_link):
        super().__init__(timeout=None)
        self.add_item(ui.Button(
            label="Entrar no Discord do Parceiro",
            style=ButtonStyle.link,
            url=partner_link
        ))

def create_chapter_embed(obra, capitulo, imagem, mensagem=None, mention_everyone=False, mention_leitores=False, style="default", api_description=None, vip_info=None):
    from src.config.config import CARGO_FIXO_ID, LEITORES_ROLE_ID, CARGO_BASE_ID
    
    print(f"[DEBUG - create_chapter_embed] Recebido capitulo: '{capitulo}', Style: {style}")

    # Processar informações de VIP e liberação
    if vip_info is None:
        vip_info = {'vip_only': False, 'release_at': None, 'release_in_minutes': None}
    
    vip_only = vip_info.get('vip_only', False)
    release_at = vip_info.get('release_at')
    release_in_minutes = vip_info.get('release_in_minutes')
    
    # Determinar se o capítulo está liberado
    is_released = release_at is None or release_in_minutes is None or release_in_minutes <= 0

    # SEMPRE mencionar PRIMEIRO: cargo de todas as obras (1425928323351183381)
    # SEGUNDO: cargo específico da obra (se existir e for diferente)
    mentions = [f"<@&{CARGO_BASE_ID}>"]  # Primeiro: SEMPRE o cargo de todas as obras
    
    # Se a obra tiver um cargo específico E for diferente do cargo base, adicionar como segundo
    cargo_obra = obra.get("cargo_id")
    if cargo_obra and cargo_obra != CARGO_BASE_ID:
        mentions.append(f"<@&{cargo_obra}>")  # Segundo: cargo específico da obra
    
    if mention_everyone:
        mentions.append("@everyone")
    if mention_leitores:
        mentions.append(f"<@&{LEITORES_ROLE_ID}>")
    mention_str = " ".join(mentions)

    # Formata o número do capítulo
    formatted_chapter = format_chapter_number(capitulo)

    embed = None # Inicializa embed como None
    content = mention_str # A mensagem de texto vai para content (que é o mention_str)
    view = None # Inicializa view como None
    
    # Construir conteúdo baseado no estilo
    if style == "image_like":
        # Construir a mensagem de texto normal com melhor formatação
        message_text = f"{mention_str}\n\n"
        
        # Título e Capítulo em negrito
        message_text += f"**{obra['nome']} - Capítulo(s) {formatted_chapter}**\n"
        
        # Adicionar informações de VIP e liberação
        if vip_only:
            message_text += f"👑 **CAPÍTULO VIP**\n"
        
        if not is_released and release_in_minutes and release_in_minutes > 0:
            hours = release_in_minutes // 60
            minutes = release_in_minutes % 60
            if hours > 0:
                message_text += f"⏰ **Liberação em {hours}h {minutes}min**\n"
            else:
                message_text += f"⏰ **Liberação em {minutes}min**\n"
        elif is_released:
            message_text += f"✨ Um novo capítulo foi lançado!\n"
        else:
            message_text += f"✨ Um novo capítulo foi lançado!\n"

        # Link para o site com emoji
        message_text += f"\n🔗 Leia agora no SenPai: <https://senpaiscan.com>\n"
        # Adiciona a tag do projeto com emoji (agora incluída sempre neste estilo, conforme exemplo 2)
        message_text += f"📌 Pegue a tag do projeto: <id:customize>\n"

        # Mensagem da Staff (se houver), formatada como bloco de citação Discord
        if mensagem: 
            message_text += f"\n💬 Mensagem da Staff:\n>>> {mensagem}\n"

        # Adicionar informações do parceiro, se existirem, com emojis
        if obra.get('parceiro') and obra['parceiro'].get('nome') and obra['parceiro'].get('link'):
            message_text += f"\n🤝 Obra em parceria com {obra['parceiro']['nome']}.\n"
            # Envolve o link do Discord em < > para evitar preview
            message_text += f"🔗 Link do Discord deles: <{obra['parceiro']['link']}>\n"
            # A view (botão) será adicionada abaixo se houver parceiro
             
        content = message_text.strip() # Atribui a mensagem de texto a content
        embed = None # Garante que o embed é None para este estilo
        # view é definido abaixo

    else: # Estilo "default" (mantém o embed)
        # Construir descrição simplificada
        description = f"📚 **Capítulo:** `{formatted_chapter}`\n"
        
        # Adicionar link
        description += "🔗 [**Leia agora no SenPai!**](https://senpaiscan.com)\n\n"
        
        # Adicionar tag do projeto
        description += f"📌 **Pegue a tag do projeto:** <id:customize>"
        
        # Adicionar mensagem da staff se houver
        if mensagem:
            # Limpar a mensagem de caracteres problemáticos e usar formatação segura
            mensagem_limpa = mensagem.replace(">>>", "").replace("```", "").strip()
            description += f"\n\n💬 **Mensagem da Staff:**\n{mensagem_limpa}"
        
        # Converter cor hexadecimal para int
        embed_color = int("5F0CA5", 16)
        
        # Criar timestamp único para evitar agrupamento de mensagens
        timestamp_unique = int(time.time() * 1000) + random.randint(0, 999)
        
        embed = discord.Embed(
            title=f"🔥 Novo Capítulo de {obra['nome']}!",
            description=description,
            color=embed_color,
            timestamp=discord.utils.utcnow()  # Timestamp único para cada embed
        )
        
        # Adicionar footer com ID único para forçar separação (removido para não interferir no header do bot)
        # embed.set_footer(text=f"ID: {timestamp_unique % 10000}", icon_url=None)
    
        # Adicionar informações do parceiro APENAS para o estilo default (no embed description)
        if obra.get('parceiro') and obra['parceiro'].get('nome') and obra['parceiro'].get('link'):
             embed.description += (
                 f"\n\n🤝 **Obra em parceria com {obra['parceiro']['nome']}.**\n"
                 f"🔗 **Link do Discord deles:** {obra['parceiro']['link']}\n"
             )

        # Usar thumbnail em vez de imagem grande
        if imagem:
            embed.set_thumbnail(url=imagem)
        
        content = mention_str # Para o estilo default, o content é apenas as menções
        # A view (botão) será adicionada abaixo se houver parceiro para o estilo default

    # Cria a view e adiciona os botões
    view = ui.View(timeout=None)
    
    # Botão Pegar Tag (só adiciona se tiver um cargo_id específico)
    if cargo_obra and cargo_obra != CARGO_BASE_ID:
        view.add_item(ui.Button(
            label="Pegar Tag",
            style=discord.ButtonStyle.primary,
            custom_id=f"get_tag_{cargo_obra}"
        ))
        
    # Botão Reportar Capítulo (Link para o canal)
    # URL = https://discord.com/channels/GUILD_ID/CHANNEL_ID
    view.add_item(ui.Button(
        label="Reportar Capítulo",
        style=discord.ButtonStyle.link,
        url="https://discord.com/channels/1450494368384286772/1450494370448019622"
    ))

    # Botão de parceiro independentemente do estilo, se houver link
    if obra.get('parceiro') and obra['parceiro'].get('link'):
        view.add_item(ui.Button(
            label="Discord do Parceiro",
            style=discord.ButtonStyle.link,
            url=obra['parceiro']['link']
        ))
        
    # Retorna o conteúdo da mensagem, o embed (que pode ser None) e a view (que pode ser None)
    return content, embed, view 