import discord
from discord.ext import commands, tasks
from discord import utils
import requests
import traceback
import asyncio
import time
import random
from src.config.config import ANNOUNCEMENT_CHANNEL_ID, ADULT_CHANNEL_ID, UPDATES_URL, API_PARAMS, API_HEADERS, ALLOWED_GUILD_ID
from src.utils.helpers import create_chapter_embed, extract_last_chapter_number
from src.database.database import get_project_data, mark_chapter_as_published, is_chapter_published, get_guild_settings, get_last_published_chapter_number, insert_obra, update_obra
from .commands import Commands # Importa Commands para tipagem e acesso

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot, commands_cog: Commands):
        self.bot = bot
        # Usa a instância de Commands passada durante o setup
        self.commands_cog = commands_cog

    # Tarefa automática para verificar novos capítulos usando a API Monster Updates
    @tasks.loop(minutes=5)
    async def check_new_chapters(self):
        try:
            print("🔍 Verificando novos lançamentos...")
            
            # Fazer requisição para a API Monster Updates
            # Usar apenas query parameter (recomendado pela documentação)
            params = {**API_PARAMS, 'page': 1, 'limit': 30}
            
            # Construir URL completa para debug
            from urllib.parse import urlencode
            full_url = f"{UPDATES_URL}?{urlencode(params)}"
            print(f"🔗 URL da requisição: {full_url}")
            print(f"🔑 Chave API usada: {API_PARAMS.get('api', 'NÃO CONFIGURADA')}")
            
            # Tentar primeiro apenas com query parameter (sem headers)
            # Se falhar, podemos tentar com header depois
            try:
                response = requests.get(
                    UPDATES_URL, 
                    params=params,
                    timeout=30  # Timeout de 30 segundos
                )
            except requests.exceptions.Timeout:
                print("❌ Erro: Timeout na requisição para a API (30s)")
                return
            except requests.exceptions.RequestException as req_error:
                print(f"❌ Erro na requisição: {req_error}")
                return
            
            if response.status_code != 200:
                print(f"❌ Erro na API: {response.status_code}")
                if response.status_code == 401:
                    print("❌ Erro de autenticação. Verifique a chave da API.")
                # Log do conteúdo da resposta para debug
                print(f"📄 Conteúdo da resposta (primeiros 500 chars): {response.text[:500]}")
                return
            
            # Verificar se a resposta tem conteúdo antes de tentar fazer parse do JSON
            if not response.text or not response.text.strip():
                print(f"❌ Erro: Resposta vazia da API (status {response.status_code})")
                print(f"📄 Headers da resposta: {dict(response.headers)}")
                return
            
            # Verificar Content-Type - se não for JSON, parar imediatamente
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/json' not in content_type:
                print(f"❌ Erro: API retornou HTML em vez de JSON!")
                print(f"📄 Content-Type recebido: {content_type}")
                print(f"📄 URL chamada: {full_url}")
                print(f"📄 Status code: {response.status_code}")
                print(f"📄 Conteúdo da resposta (primeiros 500 chars): {response.text[:500]}")
                print(f"💡 Possíveis causas:")
                print(f"   - URL da API incorreta ou endpoint não existe")
                print(f"   - Autenticação falhou e redirecionou para página HTML")
                print(f"   - Servidor retornando página de erro em HTML")
                return
            
            # Tentar fazer parse do JSON com tratamento de erro
            try:
                data = response.json()
            except ValueError as json_error:
                print(f"❌ Erro ao fazer parse do JSON: {json_error}")
                print(f"📄 URL chamada: {full_url}")
                print(f"📄 Conteúdo da resposta (primeiros 500 chars): {response.text[:500]}")
                print(f"📄 Status code: {response.status_code}")
                print(f"📄 Headers: {dict(response.headers)}")
                return
            
            if not data.get('success'):
                print(f"❌ Erro na resposta: {data.get('error')}")
                return
            
            updates = data.get('obras', [])
            print(f"✅ Encontradas {len(updates)} obras com atualizações")
            
            # Processar cada atualização com delay maior para garantir que todas mostrem o header do bot
            for update in updates:
                await self.process_update(update)
                # Delay entre cada obra para evitar rate limit
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ Erro na verificação: {e}")
            traceback.print_exc()


    async def process_update(self, update):
        """Processa uma atualização específica da API"""
        title = update.get('titulo', '').strip()
        slug = update.get('slug', '')
        cover_image = update.get('capa')
        chapters = update.get('capitulos', [])
        
        if not title or not chapters:
            return
        
        print(f"📚 Processando: {title} - {len(chapters)} capítulos")
        
        # Verificar se a obra está registrada no bot (busca exata pelo título original)
        obra = get_project_data(title)
        
        if not obra:
            print(f"⚠️ Obra '{title}' não registrada no bot - criando automaticamente...")
            
            # Criar obra no banco com o título original (sem criar cargo automaticamente)
            obra_data = {
                "nome": title,
                "sinopse": "",
                "cargo_id": None,
                "imagem": cover_image or ''
            }
            
            success = insert_obra(obra_data)
            if success:
                print(f"✅ Obra '{title}' criada no banco (sem cargo atrelado)!")
                obra = get_project_data(title)
                if not obra:
                    print(f"❌ Erro crítico: Obra '{title}' inserida mas não encontrada")
                    return
            else:
                print(f"❌ Erro ao inserir obra '{title}' no banco")
                return
        
        # Verificar se a obra foi encontrada/criada com sucesso
        if not obra:
            print(f"❌ Erro: Não foi possível obter dados da obra {title}")
            return
            
        # Salva o link da capa e só altera quando o link que vier for diferente
        if cover_image and cover_image != obra.get('imagem'):
            print(f"🔄 Atualizando capa de '{title}' para a nova URL da API...")
            success_update = update_obra(obra['id'], {"imagem": cover_image})
            if success_update:
                obra['imagem'] = cover_image # Atualizar o objeto local para usar na publicação atual
        
        # Processar capítulos em intervalos
        await self.process_chapters_interval(obra, chapters, update)

    async def process_chapters_interval(self, obra, chapters, update):
        """Processa capítulos em intervalos (ex: 18 ao 35)"""
        nome = obra['nome']
        last_published = get_last_published_chapter_number(nome)
        
        # Filtrar apenas capítulos novos
        new_chapters = []
        for chapter in chapters:
            chapter_number = float(chapter.get('numero', 0))
            if chapter_number > last_published:
                new_chapters.append(chapter_number)
                print(f"✅ Capítulo {chapter_number} detectado")
        
        if not new_chapters:
            print(f"⏭️ Nenhum capítulo novo para {nome}")
            return
        
        # Ordenar capítulos
        new_chapters.sort()
        
        # Detectar intervalos
        intervals = self.detect_chapter_intervals(new_chapters)
        
        for interval in intervals:
            await self.process_chapter_interval(obra, interval, update, chapters)
            # Pequeno delay entre intervalos para evitar rate limit
            await asyncio.sleep(1)

    def format_chapter_number(self, number):
        """Formata número de capítulo removendo .0 se for inteiro"""
        if isinstance(number, float) and number.is_integer():
            return str(int(number))
        return str(number)
    
    def detect_chapter_intervals(self, chapter_numbers):
        """Detecta intervalos de capítulos (ex: [18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35] -> [(18,35)])"""
        if not chapter_numbers:
            return []
        
        intervals = []
        start = chapter_numbers[0]
        end = chapter_numbers[0]
        
        for i in range(1, len(chapter_numbers)):
            # Verificar se é consecutivo (diferença de exatamente 1.0)
            # Capítulos decimais (ex: 215.5) não são consecutivos
            if chapter_numbers[i] == end + 1.0:
                # Capítulo consecutivo, estender intervalo
                end = chapter_numbers[i]
            else:
                # Gap encontrado, finalizar intervalo atual
                intervals.append((start, end))
                start = chapter_numbers[i]
                end = chapter_numbers[i]
        
        # Adicionar último intervalo
        intervals.append((start, end))
        
        return intervals

    def extract_vip_info_from_chapters(self, chapters_data, start, end):
        """Extrai informações de VIP e liberação dos capítulos no intervalo"""
        if not chapters_data:
            return {'vip_only': False, 'release_at': None, 'release_in_minutes': None}
        
        # A API Monster Updates não retorna informações de VIP ou liberação agendada
        # Retornar valores padrão
        return {
            'vip_only': False,
            'release_at': None,
            'release_in_minutes': None
        }

    async def process_chapter_interval(self, obra, interval, update, chapters_data=None):
        """Processa um intervalo de capítulos"""
        start, end = interval
        nome = obra['nome']
        
        # Criar string do intervalo com formatação adequada
        if start == end:
            chapter_str = self.format_chapter_number(start)
        else:
            chapter_str = f"{self.format_chapter_number(start)} ao {self.format_chapter_number(end)}"
        
        print(f"🆕 Novo intervalo detectado: {chapter_str}")
        
        # Verificar se já foi publicado
        if is_chapter_published(nome, chapter_str):
            print(f"⏭️ Intervalo {chapter_str} já foi publicado")
            return
        
        # Preparar dados para o embed
        imagem = update.get('capa') or obra.get('imagem') or 'https://monstercomics.com.br/default_cover.jpg'
        api_description = None  # A API não retorna descrição
        
        # Extrair informações de VIP e liberação dos capítulos
        vip_info = self.extract_vip_info_from_chapters(chapters_data, start, end)
        
        # Carrega as configurações do servidor para obter o estilo padrão
        guild_settings = get_guild_settings(ALLOWED_GUILD_ID)
        embed_style = guild_settings.get("embed_style", "default") if guild_settings else "default"
        
        # Criar embed e enviar notificação
        mention_str, embed, view = create_chapter_embed(
            obra, 
            chapter_str, 
            imagem, 
            api_description=api_description, 
            style=embed_style,
            vip_info=vip_info
        )
        
        # Verificar se a obra é adulta e escolher o canal apropriado
        is_adult = False
        for genero in update.get('generos', []):
            if genero.get('nome', '').lower() in ['adulto', '+18', '18+', 'smut', 'maduro']:
                is_adult = True
                break
        channel_id = ADULT_CHANNEL_ID if is_adult else ANNOUNCEMENT_CHANNEL_ID
        channel_type = "adulto" if is_adult else "normal"
        
        print(f"📢 Enviando para canal {channel_type} (ID: {channel_id})")
        
        destino = self.bot.get_channel(channel_id)
        if destino:
            try:
                # TÉCNICA (igual ao yomu-staff): Zero-width spaces no username do webhook
                # O Discord considera usernames diferentes e não agrupa os blocos de mensagens
                zwsp = "\u200b" * (hash(nome + chapter_str) % 5)  # 0 a 4 zero-width spaces únicos por obra/cap
                wh_username = f"Coruja Lançamentos{zwsp}"
                
                # Criar webhook no canal
                webhook = await destino.create_webhook(name="CorujaLancamentos")
                
                try:
                    # Preparar parâmetros para o webhook (não passar view se for None)
                    webhook_params = {
                        "content": mention_str,
                        "embed": embed,
                        "username": wh_username,
                        "avatar_url": self.bot.user.display_avatar.url,
                        "wait": True  # Aguardar resposta para obter o objeto message
                    }
                    # Só adicionar view se não for None
                    if view is not None:
                        webhook_params["view"] = view
                    
                    # Enviar mensagem através do webhook com nome e avatar do bot
                    message = await webhook.send(**webhook_params)
                    
                    # Adicionar reações automáticas
                    reactions = ['🇴', '🇧', '🇬', '<:Coruja:1483273297876619284>']
                    for reaction in reactions:
                        try:
                            await message.add_reaction(reaction)
                        except Exception as e:
                            print(f"❌ Erro ao adicionar reação {reaction}: {e}")
                    
                    # Marcar como publicado com informações de VIP e liberação
                    mark_chapter_as_published(
                        nome, 
                        chapter_str, 
                        vip_only=vip_info.get('vip_only', False),
                        release_at=vip_info.get('release_at'),
                        release_in_minutes=vip_info.get('release_in_minutes')
                    )
                    print(f"✅ Intervalo {chapter_str} de {nome} anunciado e marcado como publicado! (ID: {message.id})")
                finally:
                    # Sempre deletar o webhook após usar
                    try:
                        await webhook.delete()
                    except Exception as e:
                        print(f"⚠️  Erro ao deletar webhook: {e}")
                
                # Delay entre mensagens
                await asyncio.sleep(0.5)
            except discord.errors.Forbidden as e:
                print(f"❌ Erro de permissão ao enviar mensagem no canal: {e}")
            except Exception as e:
                print(f"❌ Erro inesperado: {e}")
        else:
            print(f"❌ Canal ({channel_type}, ID: {channel_id}) não encontrado.")

    async def process_chapter(self, obra, chapter, update):
        """Processa um capítulo específico"""
        chapter_number = float(chapter.get('numero', 0))
        chapter_str = self.format_chapter_number(chapter_number)
        chapter_title = chapter.get('titulo', f"Capítulo {chapter_str}")
        nome = obra['nome']  # SQLite usa 'nome', não 'name'
        
        # Verificar se já foi publicado
        if is_chapter_published(nome, chapter_str):
            print(f"⏭️ Capítulo {chapter_str} já foi publicado")
            return
        
        # Verificar se é um novo capítulo
        last_published = get_last_published_chapter_number(nome)
        if chapter_number <= last_published:
            print(f"⏭️ Capítulo {chapter_str} não é novo (último: {last_published})")
            return
        
        print(f"🆕 Novo capítulo detectado: {chapter_str}")
        
        # Preparar dados para o embed
        imagem = update.get('capa') or obra.get('imagem') or 'https://monstercomics.com.br/default_cover.jpg'
        api_description = None  # A API não retorna descrição
        
        # Extrair informações de VIP e liberação do capítulo
        vip_info = {
            'vip_only': False,  # A API não retorna essa informação
            'release_at': None,
            'release_in_minutes': None
        }
        
        # Carrega as configurações do servidor para obter o estilo padrão
        guild_settings = get_guild_settings(ALLOWED_GUILD_ID)
        embed_style = guild_settings.get("embed_style", "default") if guild_settings else "default"
        
        # Criar embed e enviar notificação
        mention_str, embed, view = create_chapter_embed(
            obra, 
            chapter_str, 
            imagem, 
            api_description=api_description, 
            style=embed_style,
            vip_info=vip_info
        )
        
        # Verificar se a obra é adulta e escolher o canal apropriado
        is_adult = False
        for genero in update.get('generos', []):
            if genero.get('nome', '').lower() in ['adulto', '+18', '18+', 'smut', 'maduro']:
                is_adult = True
                break
        channel_id = ADULT_CHANNEL_ID if is_adult else ANNOUNCEMENT_CHANNEL_ID
        channel_type = "adulto" if is_adult else "normal"
        
        print(f"📢 Enviando para canal {channel_type} (ID: {channel_id})")
        
        destino = self.bot.get_channel(channel_id)
        if destino:
            try:
                # TÉCNICA (igual ao yomu-staff): Zero-width spaces no username do webhook
                zwsp = "\u200b" * (hash(nome + chapter_str) % 5)
                wh_username = f"Coruja Lançamentos{zwsp}"
                
                # Criar webhook no canal
                webhook = await destino.create_webhook(name="CorujaLancamentos")
                
                try:
                    # Preparar parâmetros para o webhook (não passar view se for None)
                    webhook_params = {
                        "content": mention_str,
                        "embed": embed,
                        "username": wh_username,
                        "avatar_url": self.bot.user.display_avatar.url,
                        "wait": True  # Aguardar resposta para obter o objeto message
                    }
                    # Só adicionar view se não for None
                    if view is not None:
                        webhook_params["view"] = view
                    
                    # Enviar mensagem através do webhook com nome e avatar do bot
                    message = await webhook.send(**webhook_params)
                    
                    # Adicionar reações automáticas
                    reactions = ['🇴', '🇧', '🇬', '<:Coruja:1483273297876619284>']
                    for reaction in reactions:
                        try:
                            await message.add_reaction(reaction)
                        except Exception as e:
                            print(f"❌ Erro ao adicionar reação {reaction}: {e}")
                    
                    # Marcar como publicado com informações de VIP e liberação
                    mark_chapter_as_published(
                        nome, 
                        chapter_str, 
                        vip_only=vip_info.get('vip_only', False),
                        release_at=vip_info.get('release_at'),
                        release_in_minutes=vip_info.get('release_in_minutes')
                    )
                    print(f"✅ Capítulo {chapter_str} de {nome} anunciado e marcado como publicado! (ID: {message.id})")
                finally:
                    # Sempre deletar o webhook após usar
                    try:
                        await webhook.delete()
                    except Exception as e:
                        print(f"⚠️  Erro ao deletar webhook: {e}")
                
                # Delay entre mensagens
                await asyncio.sleep(2)
            except discord.errors.Forbidden as e:
                print(f"❌ Erro de permissão ao enviar mensagem no canal: {e}")
            except Exception as e:
                print(f"❌ Erro inesperado: {e}")
        else:
            print(f"❌ Canal ({channel_type}, ID: {channel_id}) não encontrado.")

async def setup(bot, commands_cog: Commands):
    cog = Tasks(bot, commands_cog)
    await bot.add_cog(cog)
    print("Tasks cog carregado. A tarefa de verificação de capítulos deve iniciar em breve.")
    # O loop da tarefa check_new_chapters (@tasks.loop) deve iniciar automaticamente.
    # Não precisamos chamar .start() aqui se a tarefa estiver decorada corretamente.
    return cog # Return the cog instance 