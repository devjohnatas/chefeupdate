import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
import aiohttp
import asyncio
import time
import random

from src.utils.helpers import create_chapter_embed

class RemoveTagButton(ui.View):
    def __init__(self, cargo_id: int):
        super().__init__(timeout=None)
        self.add_item(ui.Button(
            label="Remover Tag",
            style=discord.ButtonStyle.danger,
            custom_id=f"remove_tag_{cargo_id}",
            emoji="🗑️"
        ))

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.config = bot.config
        self.db = bot.db

    async def check_command_channel(self, interaction: discord.Interaction) -> bool:
        """Verifica se o comando está sendo executado no canal correto"""
        channel_id = interaction.channel_id
        parent_id = getattr(interaction.channel, 'parent_id', None)
        
        cmd_channel = self.config.command_channel_id
        
        if cmd_channel and channel_id != cmd_channel and parent_id != cmd_channel:
            await interaction.response.send_message(
                f"❌ Este comando só pode ser usado no canal <#{cmd_channel}>",
                ephemeral=True
            )
            return False
        return True

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """Verifica se o usuário possui permissões de administrador"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return False
        return True

    async def log_command(self, interaction: discord.Interaction, command_name: str, details: str):
        log_channel_id = self.config.log_channel_id
        if not log_channel_id:
            return
            
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            user_info = f"Usuário: {interaction.user} | ID: {interaction.user.id}" if interaction else "Origem: Tarefa Automática"
            color = discord.Color.green() if self.config.api_type == 'yomu' else discord.Color.from_rgb(95, 12, 165)
            
            embed = discord.Embed(
                title=f"📢 Comando Executado: {command_name}",
                description=details,
                color=color
            )
            embed.set_footer(text=user_info)
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                print(f"Erro ao enviar log para o canal: {e}")

    @app_commands.command(name="registrar_obra", description="Registra uma nova obra no banco de dados.")
    async def registrar_obra(self, interaction: discord.Interaction, nome: str, sinopse: str = "", cargo_id: str = None, capa: str = "", parceiro_nome: str = None, parceiro_link: str = None):
        if interaction.guild.id != self.config.allowed_guild_id:
            await interaction.response.send_message("❌ Comando não disponível neste servidor.", ephemeral=True)
            return

        if not await self.is_admin(interaction):
            return

        if not await self.check_command_channel(interaction):
            return

        await interaction.response.defer()
        await self.log_command(interaction, "registrar_obra", f"Tentando registrar obra: {nome}")

        obra = self.db.get_project_data(nome)
        if obra:
            await interaction.followup.send("❌ Obra já está registrada no banco de dados!")
            await self.log_command(interaction, "registrar_obra", f"Erro: Obra {nome} já registrada.")
            return

        cargo_id_final = None
        if cargo_id:
            cargo_id_final = int(cargo_id)
        else:
            if self.config.cargo_base_id:
                try:
                    from discord import utils
                    guild = interaction.guild
                    base_role = guild.get_role(self.config.cargo_base_id)
                    
                    if not base_role:
                        await interaction.followup.send(f"❌ Cargo base não encontrado! Verifique o ID.")
                        return
                    
                    existing_role = utils.get(guild.roles, name=nome)
                    
                    if existing_role:
                        cargo_id_final = existing_role.id
                    else:
                        new_role = await guild.create_role(
                            name=nome,
                            mentionable=True,
                            reason=f"Cargo criado automaticamente para a obra: {nome}"
                        )
                        try:
                            await new_role.edit(position=base_role.position - 1)
                        except:
                            pass
                        cargo_id_final = new_role.id
                except Exception as e:
                    await interaction.followup.send(f"⚠️ Obra será registrada sem cargo. Erro ao criar cargo: {e}", ephemeral=True)
                    return

        obra_data = {
            "nome": nome,
            "sinopse": sinopse,
            "cargo_id": cargo_id_final,
            "imagem": capa
        }
        if parceiro_nome and parceiro_link:
            obra_data["parceiro"] = {"nome": parceiro_nome, "link": parceiro_link}

        try:
            success = self.db.insert_obra(obra_data)
            if success:
                await interaction.followup.send(f"✅ Obra **{nome}** registrada com sucesso!")
                await self.log_command(interaction, "registrar_obra", f"Obra {nome} registrada com sucesso. Cargo ID: {cargo_id_final}")
            else:
                await interaction.followup.send(f"⚠️ Obra **{nome}** já existe no banco de dados!")
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao registrar obra: {e}")

    @app_commands.command(name="alterarregistro", description="Altera as informações de uma obra já registrada.")
    async def alterarregistro(self, interaction: discord.Interaction, nome: str, novo_nome: str = None, sinopse: str = None, cargo_id: str = None, capa: str = None, parceiro_nome: str = None, parceiro_link: str = None):
        if interaction.guild.id != self.config.allowed_guild_id:
            await interaction.response.send_message("❌ Comando não disponível neste servidor.", ephemeral=True)
            return

        if not await self.is_admin(interaction):
            return

        if not await self.check_command_channel(interaction):
            return

        await self.log_command(interaction, "alterarregistro", f"Tentando alterar registro da obra: {nome}")

        obra = self.db.get_project_data(nome)
        if not obra:
            await interaction.response.send_message("❌ Obra não encontrada no banco de dados!")
            return

        update_data = {}
        if novo_nome:
            update_data["nome"] = novo_nome
        if sinopse:
            update_data["sinopse"] = sinopse
        if cargo_id:
            update_data["cargo_id"] = int(cargo_id)
        if capa:
            update_data["imagem"] = capa
        if parceiro_nome or parceiro_link:
            update_data["parceiro"] = {
                "nome": parceiro_nome or (obra.get("parceiro", {}).get("nome") if obra.get("parceiro") else ""),
                "link": parceiro_link or (obra.get("parceiro", {}).get("link") if obra.get("parceiro") else "")
            }

        if not update_data:
            await interaction.response.send_message("⚠ Nenhum dado novo foi fornecido para alteração.")
            return

        try:
            success = self.db.update_obra(obra["id"], update_data)
            if success:
                await interaction.response.send_message(f"✅ Obra **{nome}** atualizada com sucesso!")
                await self.log_command(interaction, "alterarregistro", f"Obra {nome} alterada com sucesso.")
            else:
                await interaction.response.send_message(f"❌ Erro ao atualizar obra")
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao atualizar obra: {e}")

    @app_commands.command(name="apagarregistro", description="Remove uma obra do banco de dados.")
    async def apagarregistro(self, interaction: discord.Interaction, nome: str):
        if interaction.guild.id != self.config.allowed_guild_id:
            await interaction.response.send_message("❌ Comando não disponível neste servidor.", ephemeral=True)
            return

        if not await self.is_admin(interaction):
            return

        if not await self.check_command_channel(interaction):
            return

        obra = self.db.get_project_data(nome)
        if not obra:
            await interaction.response.send_message("❌ Obra não encontrada no banco de dados!")
            return

        try:
            success = self.db.delete_obra(obra["id"])
            if success:
                await interaction.response.send_message(f"✅ A obra **{nome}** foi removida do banco de dados.")
                await self.log_command(interaction, "apagarregistro", f"Obra {nome} removida com sucesso.")
            else:
                await interaction.response.send_message(f"❌ Erro ao remover obra")
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao remover obra: {e}")

    @app_commands.command(name="zerar_capitulos", description="Zera os números dos capítulos de uma obra específica.")
    async def zerar_capitulos(self, interaction: discord.Interaction, nome: str):
        if interaction.guild.id != self.config.allowed_guild_id:
            await interaction.response.send_message("❌ Comando não disponível neste servidor.", ephemeral=True)
            return

        if not await self.is_admin(interaction):
            return

        if not await self.check_command_channel(interaction):
            return

        await interaction.response.defer()
        
        try:
            obra = self.db.get_project_data(nome)
            if not obra:
                await interaction.followup.send(f"❌ Obra **{nome}** não encontrada no banco de dados!")
                return

            success = self.db.reset_chapter_numbers(nome)
            if success:
                await interaction.followup.send(f"✅ Capítulos da obra **{nome}** foram zerados com sucesso!")
                await self.log_command(interaction, "zerar_capitulos", f"Capítulos de {nome} zerados.")
            else:
                await interaction.followup.send(f"⚠️ Nenhum capítulo encontrado para a obra **{nome}** ou erro ao zerar.")

        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao zerar capítulos: {e}")

    @app_commands.command(name="excluir_historico", description="Exclui o histórico de uma obra específica")
    async def excluir_historico(self, interaction: discord.Interaction, obra_id: str):
        if not await self.is_admin(interaction):
            return

        if not await self.check_command_channel(interaction):
            return

        try:
            obra = self.db.get_project_data(obra_id)
            if not obra:
                await interaction.response.send_message("❌ Obra não encontrada!", ephemeral=True)
                return

            self.db.delete_obra_history(obra_id)
            await interaction.response.send_message(f"✅ Histórico da obra '{obra['nome']}' excluído com sucesso!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao excluir histórico: {e}", ephemeral=True)

    @app_commands.command(name="listar_obras", description="Lista todas as obras cadastradas no banco de dados.")
    async def listar_obras(self, interaction: discord.Interaction):
        if interaction.guild.id != self.config.allowed_guild_id:
            await interaction.response.send_message("❌ Comando não disponível neste servidor.", ephemeral=True)
            return
        
        if not await self.check_command_channel(interaction):
            return

        await interaction.response.defer()

        try:
            obras = self.db.get_all_obras()
            if not obras:
                await interaction.followup.send("📚 Nenhuma obra cadastrada no banco de dados.")
                return

            embed = discord.Embed(
                title="📚 Obras Cadastradas",
                description=f"Total: {len(obras)} obras",
                color=discord.Color.from_rgb(95, 12, 165)
            )

            obras_por_pagina = 10
            total_paginas = (len(obras) + obras_por_pagina - 1) // obras_por_pagina

            for i in range(0, len(obras), obras_por_pagina):
                pagina_obras = obras[i:i + obras_por_pagina]
                pagina_num = (i // obras_por_pagina) + 1
                
                lista_obras = []
                for obra in pagina_obras:
                    status = "✅" if obra.get('cargo_id') else "⚠️"
                    parceiro = f" | 🤝 {obra.get('parceiro', {}).get('nome', '')}" if obra.get('parceiro') else ""
                    lista_obras.append(f"{status} **{obra['nome']}**{parceiro}")
                
                embed.add_field(
                    name=f"Página {pagina_num}/{total_paginas}",
                    value="\n".join(lista_obras),
                    inline=False
                )

            embed.set_footer(text="✅ = Configurada | ⚠️ = Precisa configuração")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao listar obras: {e}")

    @app_commands.command(name="set_embed_style", description="Define o estilo padrão para os embeds de publicação (default, image_like).")
    async def set_embed_style(self, interaction: discord.Interaction, style: str):
        if interaction.guild.id != self.config.allowed_guild_id:
            await interaction.response.send_message("❌ Comando não disponível neste servidor.", ephemeral=True)
            return
        
        if not await self.check_command_channel(interaction):
            return

        valid_styles = ["default", "image_like"]
        if style.lower() not in valid_styles:
            await interaction.response.send_message(f"❌ Estilo inválido. Estilos disponíveis: {', '.join(valid_styles)}")
            return

        guild_id = interaction.guild.id
        settings = {"embed_style": style.lower()}

        try:
            self.db.set_guild_settings(guild_id, settings)
            await interaction.response.send_message(f"✅ Estilo de embed padrão definido para `{style.lower()}`.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao salvar configurações: {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            
            # Pegar Tag
            if custom_id.startswith("get_tag_"):
                try:
                    cargo_id = int(custom_id.replace("get_tag_", ""))
                    cargo = interaction.guild.get_role(cargo_id)
                    
                    if not cargo:
                        await interaction.response.send_message("❌ Este cargo não existe mais no servidor.", ephemeral=True)
                        return
                    
                    if cargo in interaction.user.roles:
                        await interaction.response.send_message(
                            f"Você já possui a tag {cargo.mention}!", 
                            ephemeral=True, 
                            view=RemoveTagButton(cargo_id)
                        )
                    else:
                        await interaction.user.add_roles(cargo, reason="Usuário clicou no botão de Pegar Tag")
                        await interaction.response.send_message(
                            f"✅ Tag {cargo.mention} adicionada com sucesso!", 
                            ephemeral=True,
                            view=RemoveTagButton(cargo_id)
                        )
                except discord.errors.Forbidden:
                    await interaction.response.send_message("❌ O bot não tem permissão para te dar este cargo. Verifique se o cargo do bot está acima deste cargo.", ephemeral=True)
                except ValueError:
                    pass
                except Exception as e:
                    await interaction.response.send_message(f"❌ Erro ao adicionar tag: {e}", ephemeral=True)
            
            # Remover Tag
            elif custom_id.startswith("remove_tag_"):
                try:
                    cargo_id = int(custom_id.replace("remove_tag_", ""))
                    cargo = interaction.guild.get_role(cargo_id)
                    
                    if not cargo:
                        await interaction.response.send_message("❌ Este cargo não existe mais no servidor.", ephemeral=True)
                        return
                        
                    if cargo in interaction.user.roles:
                        await interaction.user.remove_roles(cargo, reason="Usuário clicou no botão de Remover Tag")
                        await interaction.response.send_message(f"✅ Tag {cargo.mention} removida com sucesso!", ephemeral=True)
                    else:
                        await interaction.response.send_message(f"Você não possui a tag {cargo.mention}.", ephemeral=True)
                except discord.errors.Forbidden:
                    await interaction.response.send_message("❌ O bot não tem permissão para remover este cargo.", ephemeral=True)
                except ValueError:
                    pass
                except Exception as e:
                    await interaction.response.send_message(f"❌ Erro ao remover tag: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Commands(bot)
    await bot.add_cog(cog)
    return cog
