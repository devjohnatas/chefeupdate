import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import traceback
import io
import os
from urllib.parse import urlsplit, urlunsplit, quote, unquote
from src.utils.helpers import create_chapter_embed

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot, commands_cog):
        self.bot = bot
        self.config = bot.config
        self.db = bot.db
        self.commands_cog = commands_cog

    @tasks.loop(minutes=20)
    async def check_new_chapters(self):
        try:
            print(f"[{self.config.name}] 🔍 Verificando novos lançamentos...")
            
            if self.config.api_type == 'yomu':
                url = f"{self.config.api_base_url}/recent-updates"
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                }
                params = {}
            else:
                url = f"{self.config.api_base_url}/updates"
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                }
                params = {"api": self.config.api_key, "page": 1, "limit": 50}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        print(f"[{self.config.name}] ❌ Erro na API: {response.status}")
                        return
                    data = await response.json()
            
            if not data.get('success'):
                print(f"[{self.config.name}] ❌ Erro na resposta: {data.get('error')}")
                return
            
            updates = data.get('updates', [])
            print(f"[{self.config.name}] ✅ Encontradas {len(updates)} obras com novos lançamentos")
            
            for update in updates:
                await self.process_release(update)
                
        except Exception as e:
            print(f"[{self.config.name}] ❌ Erro na verificação: {e}")
            traceback.print_exc()

    async def fetch_image_file(self, image_url: str) -> discord.File | None:
        if not image_url or not isinstance(image_url, str):
            return None
        try:
            image_url = image_url.strip()
            parts = list(urlsplit(image_url))
            parts[2] = quote(unquote(parts[2]), safe='/:@!$&\'()*+,=')
            parts[3] = quote(unquote(parts[3]), safe='=&?/:@!$&\'()*+,=')
            clean_url = urlunsplit(parts)
            
            path = parts[2]
            raw_filename = os.path.basename(unquote(path))
            if not raw_filename or '.' not in raw_filename:
                filename = 'cover.png'
            else:
                filename = "".join(c if c.isalnum() or c in '._-' else '_' for c in raw_filename)
                while '__' in filename:
                    filename = filename.replace('__', '_')
                if not filename.strip('_.') or '.' not in filename:
                    filename = 'cover.png'
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
            }
            
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(clean_url, headers=headers) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        if image_bytes:
                            buffer = io.BytesIO(image_bytes)
                            buffer.seek(0)
                            return discord.File(fp=buffer, filename=filename)
        except Exception as e:
            pass
        return None

    async def process_release(self, update):
        serie = update
        
        if self.config.api_type == 'yomu':
            chapters = update.get('latestChapters', [])
        else:
            chapters = update.get('chapters', [])
            
        if not serie or not chapters:
            return
        
        nome = serie.get('title', '').lower()
        if not nome:
            nome = serie.get('slug', '').replace('-', ' ').lower()
            
        obra = self.db.get_project_data(nome)
        if not obra:
            nome_obra = serie.get('title', nome)
            cargo_criado_id = None
            
            if self.config.api_type == 'yomu' and serie.get('isYomuTranslation', False):
                cargo_criado_id = await self.create_yomu_role(nome_obra)
            elif self.config.api_type != 'yomu' and self.config.cargo_base_id:
                cargo_criado_id = await self.create_base_role(nome_obra)
            
            cover_url = serie.get('cover') or serie.get('coverImage', 'https://yomu.com.br/default_cover.jpg')
            
            obra_data = {
                "nome": nome,
                "sinopse": "",
                "cargo_id": cargo_criado_id,
                "imagem": cover_url
            }
            
            success = self.db.insert_obra(obra_data)
            if success:
                obra = self.db.get_project_data(nome)
                if not obra:
                    obra = self.db.get_project_data(serie.get('title', ''))
                    if not obra:
                        return
            else:
                return
        
        if serie.get('scan') and not serie.get('isYomuTranslation'):
            scan_link = serie['scan'].get('discord') or serie['scan'].get('url') or serie['scan'].get('website') or serie['scan'].get('link') or ''
            obra['parceiro'] = {
                'nome': serie['scan'].get('name', ''),
                'link': scan_link
            }
        
        await self.process_chapters_interval(obra, chapters, serie)

    async def process_chapters_interval(self, obra, chapters, serie):
        nome = obra['nome']
        last_published = self.db.get_last_published_chapter_number(nome)
        
        new_chapters = []
        for chapter in chapters:
            chapter_number = chapter.get('number', 0)
            if chapter_number > last_published:
                new_chapters.append(chapter_number)
        
        if not new_chapters:
            return
        
        new_chapters.sort()
        intervals = self.detect_chapter_intervals(new_chapters)
        
        for interval in intervals:
            await self.process_chapter_interval(obra, interval, serie, chapters)

    def detect_chapter_intervals(self, chapter_numbers):
        if not chapter_numbers:
            return []
        intervals = []
        start = chapter_numbers[0]
        end = chapter_numbers[0]
        for i in range(1, len(chapter_numbers)):
            if chapter_numbers[i] == end + 1:
                end = chapter_numbers[i]
            else:
                intervals.append((start, end))
                start = chapter_numbers[i]
                end = chapter_numbers[i]
        intervals.append((start, end))
        return intervals

    def extract_vip_info_from_chapters(self, chapters_data, start, end):
        if not chapters_data:
            return {'vip_only': False, 'release_at': None, 'release_in_minutes': None}
        
        vip_only = False
        release_at = None
        release_in_minutes = None
        
        for chapter in chapters_data:
            chapter_number = chapter.get('number', 0)
            if start <= chapter_number <= end:
                if chapter.get('isVip', False):
                    vip_only = True
                
                chapter_release_at = chapter.get('releaseAt')
                if chapter_release_at and chapter_release_at is not True:
                    try:
                        from datetime import datetime, timezone
                        release_dt = datetime.fromisoformat(chapter_release_at.replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        diff_minutes = int((release_dt - now).total_seconds() / 60)
                        if diff_minutes > 0:
                            if release_in_minutes is None or diff_minutes > release_in_minutes:
                                release_at = chapter_release_at
                                release_in_minutes = diff_minutes
                    except Exception as e:
                        pass
        return {'vip_only': vip_only, 'release_at': release_at, 'release_in_minutes': release_in_minutes}

    async def process_chapter_interval(self, obra, interval, serie, chapters_data=None):
        start, end = interval
        nome = obra['nome']
        
        if start == end:
            chapter_str = str(start)
        else:
            chapter_str = f"{start} ao {end}"
        
        if self.db.is_chapter_published(nome, chapter_str):
            return
        
        tipo = (serie.get('type') or '').lower()
        is_adult = tipo in ['yaoi', 'yuri', 'hentai', 'pornhwa'] or serie.get('isAdult', False)
        is_yomu_translation = serie.get('isYomuTranslation', False)
        is_scan = bool(serie.get('scan'))
        
        channel_id = None
        
        if self.config.api_type == 'yomu':
            if is_adult:
                return
            if is_yomu_translation:
                channel_id = self.config.yomu_translation_channel_id
            elif is_scan:
                channel_id = self.config.scan_channel_id
            else:
                vip_info = self.extract_vip_info_from_chapters(chapters_data, start, end)
                self.db.mark_chapter_as_published(
                    nome, chapter_str, vip_only=vip_info.get('vip_only', False),
                    release_at=vip_info.get('release_at'), release_in_minutes=vip_info.get('release_in_minutes')
                )
                return
        else:
            channel_id = self.config.adult_channel_id if is_adult else self.config.announcement_channel_id

        if not channel_id:
            return

        destino = self.bot.get_channel(channel_id)
        if destino:
            is_in_discord = await self.check_if_published_in_discord(destino, nome, chapter_str)
            if is_in_discord:
                print(f"[{self.config.name}] ⏭️ Intervalo {chapter_str} de {nome} já está no Discord. Marcando no BD e pulando.")
                vip_info = self.extract_vip_info_from_chapters(chapters_data, start, end)
                self.db.mark_chapter_as_published(
                    nome, chapter_str, vip_only=vip_info.get('vip_only', False),
                    release_at=vip_info.get('release_at'), release_in_minutes=vip_info.get('release_in_minutes')
                )
                return

        imagem = serie.get('cover') or serie.get('coverImage') or obra.get('imagem', 'https://yomu.com.br/default_cover.jpg')
        
        vip_info = self.extract_vip_info_from_chapters(chapters_data, start, end)
        
        guild_settings = self.db.get_guild_settings(self.config.allowed_guild_id)
        embed_style = guild_settings.get("embed_style", "default") if guild_settings else "default"
        
        mention_str, embed, view = create_chapter_embed(
            obra, chapter_str, imagem, config=self.config, style=embed_style, vip_info=vip_info, channel_id=channel_id
        )

        file_attachment = None
        if imagem:
            file_attachment = await self.fetch_image_file(imagem)
            if file_attachment and embed is not None:
                attachment_url = f"attachment://{file_attachment.filename}"
                if self.config.api_type == 'yomu' and channel_id == self.config.scan_channel_id:
                    embed.set_thumbnail(url=attachment_url)
                else:
                    embed.set_image(url=attachment_url)
            
        destino = self.bot.get_channel(channel_id)
        if destino:
            try:
                await self._send_webhook(destino, mention_str, embed, view, file_attachment)
                
                self.db.mark_chapter_as_published(
                    nome, chapter_str, vip_only=vip_info.get('vip_only', False),
                    release_at=vip_info.get('release_at'), release_in_minutes=vip_info.get('release_in_minutes')
                )
                print(f"[{self.config.name}] ✅ Intervalo {chapter_str} de {nome} anunciado e marcado como publicado!")
            except Exception as e:
                print(f"[{self.config.name}] ❌ Erro inesperado: {e}")

    async def check_if_published_in_discord(self, canal: discord.TextChannel, nome: str, chapter_str: str) -> bool:
        """Verifica nos últimos 50 envios do canal se a obra e o capítulo já foram postados."""
        try:
            nome_lower = nome.lower()
            async for msg in canal.history(limit=50):
                content = msg.content.lower()
                if msg.embeds:
                    for embed in msg.embeds:
                        if embed.title:
                            content += " " + embed.title.lower()
                        if embed.description:
                            content += " " + embed.description.lower()
                
                # Se o nome da série está na mensagem E o número do capítulo também está
                if nome_lower in content and (str(chapter_str) in content):
                    # Confirmação adicional para não pegar números aleatórios no meio de outras palavras
                    import re
                    # Procura por limites de palavras para o capítulo (evita achar "12" em "120")
                    if re.search(r'\b' + re.escape(str(chapter_str)) + r'\b', content):
                        return True
        except Exception as e:
            print(f"[{self.config.name}] Erro ao verificar histórico do canal {canal.name}: {e}")
        return False

    async def _send_webhook(self, canal, content, embed, view, file):
        import time, random
        unique_id = int(time.time() * 1000) + random.randint(0, 99999)
        wh_name = f"{self.config.name}-{unique_id}"
        
        try:
            wh = await canal.create_webhook(name=wh_name)
            await asyncio.sleep(2)
            try:
                kwargs = {
                    "content": content,
                    "embed": embed,
                    "username": f"Lançamentos {self.config.name}",
                    "avatar_url": self.bot.user.display_avatar.url if self.bot.user.display_avatar else None,
                    "wait": True
                }
                if view: kwargs["view"] = view
                if file is not None: kwargs["file"] = file
                    
                msg = await wh.send(**kwargs)
            finally:
                await wh.delete(reason="Mensagem de lançamento enviada")
            return msg
        except Exception:
            fallback_kwargs = {"content": content, "embed": embed, "view": view}
            if file:
                if hasattr(file.fp, "seek"): file.fp.seek(0)
                fallback_kwargs["file"] = file
            return await canal.send(**fallback_kwargs)

    async def create_yomu_role(self, nome_obra: str) -> int | None:
        try:
            guild = self.bot.get_guild(self.config.allowed_guild_id)
            if not guild: return None
            novo_cargo = await guild.create_role(name=nome_obra, mentionable=True)
            cargo_ref = guild.get_role(self.config.cargo_translation_id)
            if cargo_ref:
                try:
                    await novo_cargo.edit(position=max(cargo_ref.position - 1, 1))
                except: pass
            return novo_cargo.id
        except:
            return None

    async def create_base_role(self, nome_obra: str) -> int | None:
        try:
            guild = self.bot.get_guild(self.config.allowed_guild_id)
            if not guild: return None
            novo_cargo = await guild.create_role(name=nome_obra, mentionable=True)
            cargo_ref = guild.get_role(self.config.cargo_base_id)
            if cargo_ref:
                try:
                    await novo_cargo.edit(position=max(cargo_ref.position - 1, 1))
                except: pass
            return novo_cargo.id
        except:
            return None

async def setup(bot, commands_cog):
    cog = Tasks(bot, commands_cog)
    await bot.add_cog(cog)
    cog.check_new_chapters.start()
    return cog
