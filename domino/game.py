"""
domino/game.py — Jugador y Partida (lógica pura del juego)
==============================================================
"""

import random
from dataclasses import dataclass, field
from typing import Optional

from .modos import MODOS
from .tiles import EMOJI_NUM, emoji_ficha


@dataclass
class Jugador:
    user_id: int
    nombre: str
    username: Optional[str] = None
    mano: list = field(default_factory=list)
    dm_message_id: Optional[int] = None
    voto_cancelar: bool = False
    voto_iniciar: bool = False
    equipo: Optional[str] = None

    @property
    def tag(self) -> str:
        """Llama al usuario por su @username si existe; si no, por su enlace Markdown."""
        if self.username:
            return f"@{self.username}"
        return f"[{self.nombre}](tg://user?id={self.user_id})"


@dataclass
class Partida:
    chat_id: int
    modo: str
    jugadores: list = field(default_factory=list)
    tablero: list = field(default_factory=list)
    turno_idx: int = 0
    pases_seguidos: int = 0
    estado: str = "lobby"
    group_message_id: Optional[int] = None
    historial: list = field(default_factory=list)
    turno_ping_message_id: Optional[int] = None
    texto_apertura: str = ""
    # Telegram devuelve un file_id cuando se sube la foto del tablero al
    # grupo. Guardándolo acá, los DMs de los jugadores reusan esa misma
    # foto en vez de subirla otra vez: 1 subida por jugada en vez de 5.
    # Se pone en None cada vez que cambia el tablero (ver _confirmar_jugada).
    tablero_file_id: Optional[str] = None

    def extremo_izq(self) -> Optional[int]:
        return self.tablero[0][0] if self.tablero else None

    def extremo_der(self) -> Optional[int]:
        return self.tablero[-1][1] if self.tablero else None

    def jugador_actual(self) -> Jugador:
        return self.jugadores[self.turno_idx]

    def siguiente_turno(self) -> None:
        self.turno_idx = (self.turno_idx + 1) % len(self.jugadores)

    def tiene_jugada(self, jugador: Jugador) -> bool:
        if not self.tablero:
            return True
        izq, der = self.extremo_izq(), self.extremo_der()
        return any(izq in ficha or der in ficha for ficha in jugador.mano)

    def puntos_mano(self, jugador: Jugador) -> int:
        return sum(a + b for a, b in jugador.mano)

    def jugadores_equipo(self, letra: str) -> list:
        return [j for j in self.jugadores if j.equipo == letra]

    @property
    def es_equipos(self) -> bool:
        return MODOS[self.modo]["equipos"]

    def equipo_lleno(self, letra: str) -> bool:
        cupo = MODOS[self.modo]["max_jugadores"] // 2
        return len(self.jugadores_equipo(letra)) >= cupo

    def cupo_completo(self) -> bool:
        return len(self.jugadores) >= MODOS[self.modo]["max_jugadores"]

    def cumple_minimo(self) -> bool:
        return len(self.jugadores) >= MODOS[self.modo]["min_jugadores"]

    def todos_votaron_iniciar(self) -> bool:
        return all(j.voto_iniciar for j in self.jugadores)

    def iniciar(self, fichas: list) -> None:
        if self.estado != "lobby":
            raise ValueError(f"la partida ya no está en lobby (estado actual: {self.estado!r})")

        hand_size = MODOS[self.modo]["hand_size"]
        baraja = list(fichas)
        random.shuffle(baraja)
        for jugador in self.jugadores:
            jugador.mano = baraja[:hand_size]
            baraja = baraja[hand_size:]

        abridor, ficha_apertura = encontrar_apertura(self)

        idx_abridor = self.jugadores.index(abridor)
        self.jugadores = self.jugadores[idx_abridor:] + self.jugadores[:idx_abridor]

        self.colocar_ficha(ficha_apertura)
        abridor.mano.remove(ficha_apertura)
        self.texto_apertura = f"▶️ {abridor.nombre} salió con {emoji_ficha(*ficha_apertura)}"

        self.turno_idx = 0
        self.siguiente_turno()

        intentos = 0
        while intentos < len(self.jugadores) and not self.tiene_jugada(self.jugador_actual()):
            jugador = self.jugador_actual()
            izq, der = self.extremo_izq(), self.extremo_der()
            self.historial = [f"⏭️ {jugador.nombre} no lleva {EMOJI_NUM[izq]} {EMOJI_NUM[der]}"]
            self.pases_seguidos += 1
            self.siguiente_turno()
            intentos += 1

        self.estado = "jugando"

    def colocar_ficha(self, ficha, lado: Optional[str] = None) -> None:
        a, b = ficha

        if not self.tablero:
            self.tablero.append((a, b))
            return

        der = self.extremo_der()
        izq = self.extremo_izq()
        puede_der = a == der or b == der
        puede_izq = a == izq or b == izq

        if lado == "izq" and puede_izq:
            orientada = (a, b) if b == izq else (b, a)
            self.tablero.insert(0, orientada)
        elif lado == "der" and puede_der:
            orientada = (a, b) if a == der else (b, a)
            self.tablero.append(orientada)
        elif lado is None and puede_der:
            orientada = (a, b) if a == der else (b, a)
            self.tablero.append(orientada)
        elif lado is None and puede_izq:
            orientada = (a, b) if b == izq else (b, a)
            self.tablero.insert(0, orientada)
        else:
            raise ValueError(
                "La ficha no combina con ningún extremo del tablero (o el lado pedido no es válido)"
            )

    def es_jugada_ambigua(self, ficha) -> bool:
        izq, der = self.extremo_izq(), self.extremo_der()
        if izq is None or der is None or izq == der:
            return False
        return {ficha[0], ficha[1]} == {izq, der}

    def lista_jugadores_numerada(self) -> str:
        lineas = []
        for i, jugador in enumerate(self.jugadores):
            marca = " 👈 (turno)" if i == self.turno_idx else ""
            lineas.append(f"{i + 1}. {jugador.nombre}{marca}")
        return "\n".join(lineas)


def encontrar_apertura(partida: Partida):
    doble_max = MODOS[partida.modo]["doble_max"]

    for valor in range(doble_max, -1, -1):
        doble = (valor, valor)
        for jugador in partida.jugadores:
            if doble in jugador.mano:
                return jugador, doble

    candidatos = [
        (jugador, ficha)
        for jugador in partida.jugadores
        for ficha in jugador.mano
    ]
    mejor_valor = max(a + b for _, (a, b) in candidatos)
    empatados = [c for c in candidatos if sum(c[1]) == mejor_valor]
    return random.choice(empatados)