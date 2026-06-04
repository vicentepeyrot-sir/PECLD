# -*- coding: utf-8 -*-
"""
escolher_datas.py — Vicente_WFM
================================
Pergunta o período desejado e executa o processo completo:
  1. Login no GPM
  2. Download das notas executadas
  3. Descompactação
  4. Filtro pelo período informado
  5. Salvamento do Excel na pasta do Drive

Execute com:
    python escolher_datas.py
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import executar_downloads


# ── Paleta ─────────────────────────────────────────────────────────────────────
COR_FUNDO    = "#1e1e2e"
COR_DESTAQUE = "#7c3aed"
COR_BOTAO    = "#6d28d9"
COR_HOVER    = "#5b21b6"
COR_TEXTO    = "#f1f5f9"
COR_SUBTEXTO = "#94a3b8"
COR_ENTRADA  = "#334155"
COR_BORDA    = "#475569"
COR_VERDE    = "#4ade80"
COR_VERMELHO = "#f87171"


def _campo_data(pai, rotulo, valor_inicial):
    """Bloco label + entry; devolve (StringVar, Entry)."""
    bloco = tk.Frame(pai, bg=COR_FUNDO)
    bloco.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=6)

    tk.Label(
        bloco, text=rotulo,
        bg=COR_FUNDO, fg=COR_SUBTEXTO,
        font=("Segoe UI", 8, "bold")
    ).pack(anchor="w", pady=(0, 4))

    var = tk.StringVar(value=valor_inicial)
    frame_borda = tk.Frame(bloco, bg=COR_BORDA, bd=1)
    frame_borda.pack(fill=tk.X, ipady=1)

    entry = tk.Entry(
        frame_borda,
        textvariable=var,
        bg=COR_ENTRADA, fg=COR_TEXTO,
        insertbackground=COR_TEXTO,
        relief=tk.FLAT,
        font=("Segoe UI", 14, "bold"),
        justify="center",
        bd=6, width=12,
    )
    entry.pack(fill=tk.X)
    return var, entry


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Escolher Período — PECLD")
        self.resizable(False, False)
        self.configure(bg=COR_FUNDO)

        largura, altura = 480, 360
        x = (self.winfo_screenwidth()  - largura) // 2
        y = (self.winfo_screenheight() - altura)  // 2
        self.geometry(f"{largura}x{altura}+{x}+{y}")

        self._build_ui()

    # ── Interface ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        hoje  = datetime.now().date()
        ontem = hoje - timedelta(days=1)

        tk.Frame(self, bg=COR_DESTAQUE, height=6).pack(fill=tk.X)

        corpo = tk.Frame(self, bg=COR_FUNDO, padx=28, pady=20)
        corpo.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            corpo, text="Relatório de Notas Executadas",
            bg=COR_FUNDO, fg=COR_TEXTO,
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")
        tk.Label(
            corpo, text="Selecione o período e clique em Iniciar",
            bg=COR_FUNDO, fg=COR_SUBTEXTO,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(2, 16))

        # ── Atalhos de período ─────────────────────────────────────────────────
        linha_atalhos = tk.Frame(corpo, bg=COR_FUNDO)
        linha_atalhos.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            linha_atalhos, text="Atalhos:",
            bg=COR_FUNDO, fg=COR_SUBTEXTO,
            font=("Segoe UI", 8)
        ).pack(side=tk.LEFT, padx=(0, 6))

        for label, ini, fim in [
            ("Hoje",           hoje,                     hoje),
            ("Ontem",          ontem,                    ontem),
            ("Últimos 7 dias", hoje - timedelta(days=6), hoje),
            ("Mês atual",      hoje.replace(day=1),      hoje),
        ]:
            btn = tk.Button(
                linha_atalhos, text=label,
                bg=COR_ENTRADA, fg=COR_TEXTO,
                relief=tk.FLAT, cursor="hand2",
                font=("Segoe UI", 8), padx=8, pady=3,
                command=lambda i=ini, f=fim: self._set_periodo(i, f)
            )
            btn.pack(side=tk.LEFT, padx=2)

        # ── Campos de data ─────────────────────────────────────────────────────
        linha_campos = tk.Frame(corpo, bg=COR_FUNDO)
        linha_campos.pack(fill=tk.X, pady=(0, 4))

        self.var_inicio, _ = _campo_data(
            linha_campos, "DATA INICIAL", ontem.strftime("%d/%m/%Y")
        )
        tk.Label(
            linha_campos, text="→",
            bg=COR_FUNDO, fg=COR_SUBTEXTO,
            font=("Segoe UI", 18)
        ).pack(side=tk.LEFT, padx=4, pady=(18, 0))

        self.var_fim, entry_fim = _campo_data(
            linha_campos, "DATA FINAL", hoje.strftime("%d/%m/%Y")
        )
        entry_fim.bind("<Return>", lambda e: self._executar())

        tk.Label(
            corpo, text="Formato: DD/MM/AAAA",
            bg=COR_FUNDO, fg=COR_SUBTEXTO,
            font=("Segoe UI", 8)
        ).pack(pady=(4, 0))

        # ── Botão principal ────────────────────────────────────────────────────
        self.btn = tk.Button(
            corpo,
            text="▶  Iniciar Processo",
            bg=COR_BOTAO, fg=COR_TEXTO,
            activebackground=COR_HOVER, activeforeground=COR_TEXTO,
            relief=tk.FLAT, cursor="hand2",
            font=("Segoe UI", 11, "bold"),
            pady=10,
            command=self._executar
        )
        self.btn.pack(fill=tk.X, pady=(18, 0))
        self.btn.bind("<Enter>", lambda e: self.btn.config(bg=COR_HOVER))
        self.btn.bind("<Leave>", lambda e: self.btn.config(bg=COR_BOTAO))

        # ── Status ─────────────────────────────────────────────────────────────
        self.var_status = tk.StringVar(value="")
        self.lbl_status = tk.Label(
            corpo, textvariable=self.var_status,
            bg=COR_FUNDO, fg=COR_SUBTEXTO,
            font=("Segoe UI", 8), wraplength=420
        )
        self.lbl_status.pack(pady=(10, 0))

    # ── Ações ──────────────────────────────────────────────────────────────────
    def _set_periodo(self, inicio, fim):
        self.var_inicio.set(inicio.strftime("%d/%m/%Y"))
        self.var_fim.set(fim.strftime("%d/%m/%Y"))

    def _parse(self, var, nome):
        try:
            return datetime.strptime(var.get().strip(), "%d/%m/%Y").date()
        except ValueError:
            messagebox.showerror(
                "Data inválida",
                f"'{var.get().strip()}' não é válido para '{nome}'.\nUse DD/MM/AAAA."
            )
            return None

    def _executar(self):
        inicio = self._parse(self.var_inicio, "Data Inicial")
        if not inicio:
            return
        fim = self._parse(self.var_fim, "Data Final")
        if not fim:
            return
        if inicio > fim:
            messagebox.showerror("Período inválido",
                                 "A data inicial não pode ser maior que a data final.")
            return

        self.btn.config(state=tk.DISABLED, text="⏳  Processando...")
        self.var_status.set(
            f"Executando processo completo: {inicio.strftime('%d/%m/%Y')} → {fim.strftime('%d/%m/%Y')}..."
        )
        self.lbl_status.config(fg=COR_SUBTEXTO)
        self.update()

        try:
            executar_downloads(data_inicio=inicio, data_fim=fim)

            self.var_status.set(
                f"✔  Concluído! Período: {inicio.strftime('%d/%m/%Y')} → {fim.strftime('%d/%m/%Y')}"
            )
            self.lbl_status.config(fg=COR_VERDE)
            messagebox.showinfo(
                "Concluído",
                f"Processo finalizado com sucesso!\n\n"
                f"Período: {inicio.strftime('%d/%m/%Y')} até {fim.strftime('%d/%m/%Y')}\n"
                f"Arquivo salvo na pasta do Drive."
            )
        except Exception as exc:
            self.var_status.set(f"✘  Erro: {exc}")
            self.lbl_status.config(fg=COR_VERMELHO)
            messagebox.showerror("Erro", f"Ocorreu um erro durante o processo:\n\n{exc}")
        finally:
            self.btn.config(state=tk.NORMAL, text="▶  Iniciar Processo")


if __name__ == "__main__":
    app = App()
    app.mainloop()
