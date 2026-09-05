import sqlite3
import os
from datetime import datetime
from src.utils.helpers import extract_last_chapter_number

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """Cria e retorna uma conexão com o banco SQLite"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permite acesso por nome das colunas
        return conn

    def init_database(self):
        """Inicializa o banco de dados criando as tabelas necessárias"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Tabela de obras
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS obras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT UNIQUE NOT NULL,
                    sinopse TEXT,
                    cargo_id INTEGER,
                    imagem TEXT,
                    parceiro_nome TEXT,
                    parceiro_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabela de capítulos publicados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS capitulos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    capitulo_str TEXT NOT NULL,
                    last_number INTEGER NOT NULL,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    vip_only BOOLEAN DEFAULT FALSE,
                    release_at TIMESTAMP NULL,
                    release_in_minutes INTEGER NULL,
                    UNIQUE(nome, capitulo_str)
                )
            ''')
            
            # Tabela de configurações do servidor
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    embed_style TEXT DEFAULT 'default',
                    announcement_channel_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices para melhor performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_obras_nome ON obras(nome)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_capitulos_nome ON capitulos(nome)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_capitulos_last_number ON capitulos(last_number)')
            
            # Migração: adicionar novos campos se não existirem
            try:
                cursor.execute('ALTER TABLE capitulos ADD COLUMN vip_only BOOLEAN DEFAULT FALSE')
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute('ALTER TABLE capitulos ADD COLUMN release_at TIMESTAMP NULL')
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute('ALTER TABLE capitulos ADD COLUMN release_in_minutes INTEGER NULL')
            except sqlite3.OperationalError:
                pass
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"ERRO - Erro ao inicializar banco de dados {self.db_path}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ============================================================================
    # FUNÇÕES DE OBRAS
    # ============================================================================

    def get_project_data(self, nome):
        """Busca dados de uma obra pelo nome"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'SELECT * FROM obras WHERE LOWER(nome) LIKE LOWER(?)', 
                (f'%{nome}%',)
            )
            row = cursor.fetchone()
            
            if row:
                # Converter para dicionário compatível com o código existente
                obra = {
                    'id': row['id'],
                    'nome': row['nome'],
                    'sinopse': row['sinopse'],
                    'cargo_id': row['cargo_id'],
                    'imagem': row['imagem']
                }
                
                # Adicionar dados do parceiro se existirem
                if row['parceiro_nome'] and row['parceiro_link']:
                    obra['parceiro'] = {
                        'nome': row['parceiro_nome'],
                        'link': row['parceiro_link']
                    }
                
                return obra
            return None
            
        except Exception as e:
            print(f"ERRO - Erro ao buscar obra {nome}: {e}")
            return None
        finally:
            conn.close()

    def insert_obra(self, obra_data):
        """Insere uma nova obra no banco"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO obras (nome, sinopse, cargo_id, imagem, parceiro_nome, parceiro_link)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                obra_data['nome'],
                obra_data.get('sinopse', ''),
                obra_data.get('cargo_id'),
                obra_data.get('imagem', ''),
                obra_data.get('parceiro', {}).get('nome') if obra_data.get('parceiro') else None,
                obra_data.get('parceiro', {}).get('link') if obra_data.get('parceiro') else None
            ))
            
            conn.commit()
            return True
            
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_all_obras(self):
        """Retorna todas as obras cadastradas"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM obras ORDER BY nome')
            rows = cursor.fetchall()
            
            obras = []
            for row in rows:
                obra = {
                    'id': row['id'],
                    'nome': row['nome'],
                    'sinopse': row['sinopse'],
                    'cargo_id': row['cargo_id'],
                    'imagem': row['imagem']
                }
                
                if row['parceiro_nome'] and row['parceiro_link']:
                    obra['parceiro'] = {
                        'nome': row['parceiro_nome'],
                        'link': row['parceiro_link']
                    }
                
                obras.append(obra)
            
            return obras
            
        except Exception as e:
            print(f"ERRO - Erro ao buscar obras: {e}")
            return []
        finally:
            conn.close()

    def update_obra(self, obra_id, update_data):
        """Atualiza uma obra existente"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            set_clauses = []
            values = []
            
            for key, value in update_data.items():
                if key == 'parceiro':
                    if isinstance(value, dict):
                        set_clauses.append('parceiro_nome = ?')
                        set_clauses.append('parceiro_link = ?')
                        values.extend([value.get('nome'), value.get('link')])
                else:
                    set_clauses.append(f'{key} = ?')
                    values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(obra_id)
            
            query = f"UPDATE obras SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            
            if cursor.rowcount > 0:
                return True
            else:
                return False
            
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_obra(self, obra_id):
        """Remove uma obra do banco"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM obras WHERE id = ?', (obra_id,))
            conn.commit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def reset_chapter_numbers(self, nome):
        """Zera os números dos capítulos de uma obra específica"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM capitulos WHERE LOWER(nome) LIKE LOWER(?)', (f'%{nome}%',))
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def reset_all_chapter_numbers(self):
        """Zera todos os números de capítulos de todas as obras"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM capitulos')
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    # ============================================================================
    # FUNÇÕES DE CAPÍTULOS
    # ============================================================================

    def get_last_published_chapter_number(self, nome):
        """Retorna o último número de capítulo publicado para uma obra"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT last_number FROM capitulos 
                WHERE LOWER(nome) LIKE LOWER(?) 
                ORDER BY last_number DESC 
                LIMIT 1
            ''', (f'%{nome}%',))
            
            row = cursor.fetchone()
            return row['last_number'] if row else 0
            
        except Exception as e:
            return 0
        finally:
            conn.close()

    def mark_chapter_as_published(self, nome, capitulo_str, vip_only=False, release_at=None, release_in_minutes=None):
        """Marca um capítulo como publicado"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            last_number = extract_last_chapter_number(capitulo_str)
            
            cursor.execute('''
                INSERT OR REPLACE INTO capitulos (nome, capitulo_str, last_number, vip_only, release_at, release_in_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome, capitulo_str, last_number, vip_only, release_at, release_in_minutes))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def is_chapter_published(self, nome, capitulo_str):
        """Verifica se um capítulo já foi publicado"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 1 FROM capitulos 
                WHERE LOWER(nome) = LOWER(?) AND capitulo_str = ?
            ''', (nome, capitulo_str))
            
            return cursor.fetchone() is not None
            
        except Exception as e:
            return False
        finally:
            conn.close()

    def get_chapter_history(self, nome, limit=10):
        """Retorna o histórico de capítulos de uma obra"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT capitulo_str, last_number, published_at, vip_only, release_at, release_in_minutes
                FROM capitulos 
                WHERE LOWER(nome) LIKE LOWER(?) 
                ORDER BY published_at DESC 
                LIMIT ?
            ''', (f'%{nome}%', limit))
            
            return cursor.fetchall()
            
        except Exception as e:
            return []
        finally:
            conn.close()

    def get_chapter_details(self, nome, capitulo_str):
        """Retorna detalhes completos de um capítulo específico"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT capitulo_str, last_number, published_at, vip_only, release_at, release_in_minutes
                FROM capitulos 
                WHERE LOWER(nome) = LOWER(?) AND capitulo_str = ?
            ''', (nome, capitulo_str))
            
            row = cursor.fetchone()
            if row:
                return {
                    'capitulo_str': row['capitulo_str'],
                    'last_number': row['last_number'],
                    'published_at': row['published_at'],
                    'vip_only': bool(row['vip_only']),
                    'release_at': row['release_at'],
                    'release_in_minutes': row['release_in_minutes']
                }
            return None
            
        except Exception as e:
            return None
        finally:
            conn.close()

    # ============================================================================
    # FUNÇÕES DE CONFIGURAÇÕES DO SERVIDOR
    # ============================================================================

    def get_guild_settings(self, guild_id):
        """Retorna as configurações de um servidor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM guild_settings WHERE guild_id = ?', (guild_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'guild_id': row['guild_id'],
                    'embed_style': row['embed_style'],
                    'announcement_channel_id': row['announcement_channel_id']
                }
            return None
            
        except Exception as e:
            return None
        finally:
            conn.close()

    def set_guild_settings(self, guild_id, settings):
        """Salva as configurações de um servidor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO guild_settings 
                (guild_id, embed_style, announcement_channel_id, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                guild_id,
                settings.get('embed_style', 'default'),
                settings.get('announcement_channel_id')
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_obra_history(self, obra_id: str) -> bool:
        """Exclui o histórico de uma obra específica (compatibilidade)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM capitulos WHERE nome = ?', (obra_id,))
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

# Para fins de migração, os arquivos de tasks e commands do bot vão importar `Database`
