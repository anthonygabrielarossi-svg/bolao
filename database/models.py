"""Estruturas de dados do bolao.

As classes deste modulo representam os registros principais do dominio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from utils.team_assets import get_team_logo_url


@dataclass(slots=True)
class Usuario:
    id: Optional[int]
    nome: str
    senha: str
    pontuacao_total: int = 0
    is_admin: bool = False
    aprovado: bool = True
    recuperacao_senha_solicitada: bool = False
    troca_senha_liberada: bool = False


@dataclass(slots=True)
class Jogo:
    id: Optional[int]
    time_a: str
    time_b: str
    placar_a: Optional[int] = None
    placar_b: Optional[int] = None
    finalizado: bool = False
    fase: str = "Fase de Grupos"
    grupo: Optional[str] = None
    data_jogo: Optional[str] = None
    status: str = "agendado"
    proximo_jogo_id: Optional[int] = None
    api_id: Optional[int] = None
    round_number: Optional[int] = None
    is_placeholder_bracket: bool = False
    time_casa: Optional[str] = None
    time_fora: Optional[str] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    home_team_logo_url: Optional[str] = None
    away_team_logo_url: Optional[str] = None
    match_number: Optional[int] = None
    gols_casa: Optional[int] = None
    gols_fora: Optional[int] = None
    estadio: Optional[str] = None
    competicao: str = "Copa do Mundo"

    def __post_init__(self) -> None:
        # Mantem os nomes antigos e novos sincronizados para compatibilidade.
        if not self.time_casa:
            self.time_casa = self.time_a
        if not self.time_fora:
            self.time_fora = self.time_b
        if self.gols_casa is None:
            self.gols_casa = self.placar_a
        if self.gols_fora is None:
            self.gols_fora = self.placar_b
        if not self.home_team_logo_url and self.home_team_id is not None:
            self.home_team_logo_url = get_team_logo_url(self.home_team_id)
        if not self.away_team_logo_url and self.away_team_id is not None:
            self.away_team_logo_url = get_team_logo_url(self.away_team_id)
        if not self.time_a and self.time_casa:
            self.time_a = self.time_casa
        if not self.time_b and self.time_fora:
            self.time_b = self.time_fora
        if self.placar_a is None:
            self.placar_a = self.gols_casa
        if self.placar_b is None:
            self.placar_b = self.gols_fora
        if not self.competicao:
            self.competicao = "Copa do Mundo"


@dataclass(slots=True)
class PalpitePartida:
    id: Optional[int]
    user_id: int
    match_id: int
    palpite_a: int
    palpite_b: int


@dataclass(slots=True)
class PalpiteEspecial:
    id: Optional[int]
    user_id: int
    campeao: str = ""
    vice: str = ""
    artilheiro: str = ""
    melhor_jogador: str = ""
    primeiro_grupo_a: str = ""
    segundo_grupo_a: str = ""
    classificados_grupos: str = ""


@dataclass(slots=True)
class ClassificacaoGrupo:
    id: Optional[int]
    grupo: str
    time_nome: str
    posicao: int = 0
    pontos: int = 0
    jogos: int = 0
    vitorias: int = 0
    empates: int = 0
    derrotas: int = 0
    gols_pro: int = 0
    gols_contra: int = 0
    saldo_gols: int = 0


@dataclass(slots=True)
class ResultadoOficial:
    id: int = 1
    campeao: str = ""
    vice: str = ""
    artilheiro: str = ""
    melhor_jogador: str = ""
    primeiro_grupo_a: str = ""
    segundo_grupo_a: str = ""


@dataclass(slots=True)
class PontuacaoUsuario:
    user_id: int
    nome: str
    pontos_partidas: int
    pontos_especiais: int
    pontuacao_total: int
    placares_exatos: int = 0
    resultados_certos: int = 0
    especiais_acertos: int = 0
