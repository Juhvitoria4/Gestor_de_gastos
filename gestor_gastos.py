#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gestor de Gastos (GUI / Tkinter)
- Tema rosa
- Competência por MÊS (mm/aaaa) no lugar de data de vencimento
- Pagamento parcial: valor restante permanece pendente
- Categorias: fixo, extra, guardado
- Filtros por mês, status e busca
- Totais gerais e do mês filtrado
- Persistência em despesas.json (compatível com versões anteriores)
"""

import json
import os
import uuid
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Tuple, List

ARQUIVO = "despesas.json"
TIPOS = ["fixo", "extra", "guardado"]

# ====================== UTIL ======================

def dinheiro(valor) -> str:
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    q = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{q:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def parse_mm_aaaa(s: str) -> Optional[Tuple[int, int]]:
    """Recebe 'mm/aaaa' e devolve (ano, mes)."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        mm, aa = s.split("/")
        return int(aa), int(mm)
    except Exception:
        return None

def rotulo_mm_aaaa(ano: int, mes: int) -> str:
    return f"{mes:02d}/{ano:d}"

def normaliza_competencia(s: str) -> str:
    """
    Aceita:
      - 'mm/aaaa' -> 'aaaa-mm'
      - 'aaaa-mm' -> 'aaaa-mm'
      - ''        -> ''
    """
    s = (s or "").strip()
    if not s:
        return ""
    # mm/aaaa
    mmaaaa = parse_mm_aaaa(s)
    if mmaaaa:
        aa, mm = mmaaaa
        return f"{aa:04d}-{mm:02d}"
    # já 'aaaa-mm'?
    try:
        datetime.strptime(s + "-01", "%Y-%m-%d")
        return s
    except Exception:
        return ""

def rotulo_competencia(iso_yyyy_mm: str) -> str:
    """Converte 'aaaa-mm' -> 'mm/aaaa' (para exibir)."""
    iso = (iso_yyyy_mm or "").strip()
    if not iso:
        return "-"
    try:
        aa, mm = iso.split("-")
        return f"{int(mm):02d}/{int(aa)}"
    except Exception:
        return "-"

# ====================== MODELO ======================

@dataclass
class Despesa:
    id: str
    titulo: str
    valor: str          # Decimal em string
    competencia: str    # 'aaaa-mm' ou ''
    paga: bool
    paga_em: str        # ISO timestamp ou ''
    tipo: str           # fixo | extra | guardado
    valor_pago: str     # Decimal em string (acumula pagamentos parciais)

def carregar() -> List[Despesa]:
    if not os.path.exists(ARQUIVO):
        return []
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        out: List[Despesa] = []
        for d in bruto:
            # Back-compat: migrar 'vencimento' (data) para 'competencia' (aaaa-mm)
            comp = d.get("competencia", "")
            if not comp:
                venc = d.get("vencimento", "")
                if venc:
                    try:
                        dt = datetime.strptime(venc, "%Y-%m-%d").date()
                        comp = f"{dt.year:04d}-{dt.month:02d}"
                    except Exception:
                        comp = ""
            comp = normaliza_competencia(comp)

            tipo = (d.get("tipo") or "extra").lower()
            if tipo not in TIPOS:
                tipo = "extra"

            valor = str(d.get("valor", "0"))
            valor_pago = str(d.get("valor_pago", "0"))

            paga = bool(d.get("paga", False))
            paga_em = d.get("paga_em", "")

            desp = Despesa(
                id=d.get("id", str(uuid.uuid4())[:8]),
                titulo=d.get("titulo", "Sem título"),
                valor=valor,
                competencia=comp,
                paga=paga,
                paga_em=paga_em,
                tipo=tipo,
                valor_pago=valor_pago
            )

            # Regra para 'guardado': considerar pago integral
            if desp.tipo == "guardado":
                desp.paga = True
                if Decimal(desp.valor_pago) < Decimal(desp.valor):
                    desp.valor_pago = desp.valor
                if not desp.paga_em:
                    desp.paga_em = datetime.now().isoformat(timespec="seconds")

            # Se não guardado e valor_pago >= valor -> pago
            if desp.tipo != "guardado":
                if Decimal(desp.valor_pago) >= Decimal(desp.valor):
                    desp.paga = True
                    if not desp.paga_em:
                        desp.paga_em = datetime.now().isoformat(timespec="seconds")

            out.append(desp)
        return out
    except Exception:
        # backup se corrompido
        try:
            os.replace(ARQUIVO, ARQUIVO + ".bak")
        except Exception:
            pass
        return []

def salvar(despesas: List[Despesa]):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump([asdict(d) for d in despesas], f, ensure_ascii=False, indent=2)

# ====================== DIÁLOGO ======================

class DespesaDialog(simpledialog.Dialog):
    def __init__(self, master, title="Nova entrada", despesa: Despesa | None = None, styles=None):
        self._despesa = despesa
        self._styles = styles or {}
        super().__init__(master, title=title)

    def body(self, master):
        try:
            master.configure(bg=self._styles.get("bg_soft"))
        except Exception:
            pass

        ttk.Label(master, text="Título:", style="Pink.TLabel").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.titulo = ttk.Entry(master, width=44, style="Pink.TEntry")
        self.titulo.grid(row=0, column=1, padx=6, pady=6)

        ttk.Label(master, text="Valor (ex: 199,90):", style="Pink.TLabel").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.valor = ttk.Entry(master, width=20, style="Pink.TEntry")
        self.valor.grid(row=1, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(master, text="Mês (mm/aaaa):", style="Pink.TLabel").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.comp = ttk.Entry(master, width=20, style="Pink.TEntry")
        self.comp.grid(row=2, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(master, text="Tipo:", style="Pink.TLabel").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        self.tipo = ttk.Combobox(master, values=TIPOS, state="readonly", width=18, style="Pink.TCombobox")
        self.tipo.grid(row=3, column=1, padx=6, pady=6, sticky="w")

        if self._despesa:
            self.titulo.insert(0, self._despesa.titulo)
            try:
                dec = Decimal(self._despesa.valor).quantize(Decimal("0.01"))
                self.valor.insert(0, str(dec).replace(".", ","))
            except Exception:
                self.valor.insert(0, self._despesa.valor)
            self.comp.insert(0, rotulo_competencia(self._despesa.competencia))
            self.tipo.set(self._despesa.tipo)
        else:
            hoje = date.today()
            self.comp.insert(0, rotulo_mm_aaaa(hoje.year, hoje.month))
            self.tipo.set("extra")

        return self.titulo

    def validate(self):
        titulo = self.titulo.get().strip() or "Sem título"
        s_valor = self.valor.get().strip().replace("R$", "").replace(" ", "")
        s_valor = s_valor.replace(".", "").replace(",", ".")
        try:
            valor = Decimal(s_valor)
        except (InvalidOperation, ValueError):
            messagebox.showerror("Erro", "Valor inválido. Use algo como 1234,56.")
            return False

        comp_ui = self.comp.get().strip()
        comp_iso = normaliza_competencia(comp_ui)
        if not comp_iso:
            messagebox.showerror("Erro", "Mês inválido. Use mm/aaaa (ex.: 10/2025).")
            return False

        tipo = (self.tipo.get() or "extra").lower()
        if tipo not in TIPOS:
            messagebox.showerror("Erro", "Selecione um tipo válido (fixo, extra ou guardado).")
            return False

        self.result = {
            "titulo": titulo,
            "valor": str(valor),
            "competencia": comp_iso,
            "tipo": tipo,
        }
        return True

# ====================== APP (TK) ======================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Gastos - Rosa (Mensal + Parcial)")
        self.geometry("1150x720")
        self.resizable(True, True)

        self.COLORS = {
            "primary": "#E91E63",
            "primary_mid": "#F06292",
            "primary_soft": "#F8BBD0",
            "bg_soft": "#FDEEF4",
            "bg_card": "#FCE4EC",
            "text": "#4A4A4A",
            "white": "#FFFFFF",
            "line": "#F5C6D6",
        }
        self.configure(bg=self.COLORS["bg_soft"])

        self.style = ttk.Style(self)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
        self._configura_estilos()

        self.despesas: List[Despesa] = carregar()

        wrapper = tk.Frame(self, bg=self.COLORS["bg_soft"])
        wrapper.pack(fill="both", expand=True)

        self._monta_toolbar(wrapper)
        self._monta_tabela(wrapper)
        self._monta_totais(wrapper)

        self.atualiza_lista()

        self.bind("<Delete>", lambda e: self.remover())
        self.bind("<Control-n>", lambda e: self.adicionar())
        self.bind("<Control-e>", lambda e: self.editar())
        self.bind("<Control-p>", lambda e: self.marcar_paga())

    # ---------- ESTILOS ----------

    def _configura_estilos(self):
        c = self.COLORS
        self.style.configure("Pink.TButton", background=c["primary"], foreground=c["white"], borderwidth=0, padding=(12, 8))
        self.style.map("Pink.TButton", background=[("active", c["primary_mid"])])
        self.style.configure("Pink.TLabel", background=c["bg_soft"], foreground=c["text"])
        self.style.configure("Pink.TEntry", fieldbackground=c["white"], foreground=c["text"])
        self.style.configure("Pink.TCombobox", fieldbackground=c["white"], foreground=c["text"])
        self.style.map("Pink.TCombobox", fieldbackground=[("readonly", c["white"])])
        self.style.configure("Pink.Treeview", background=c["white"], fieldbackground=c["white"], foreground=c["text"], rowheight=26, bordercolor=c["line"], borderwidth=1)
        self.style.configure("Pink.Treeview.Heading", background=c["primary"], foreground=c["white"], relief="flat", padding=(8, 6))
        self.style.map("Pink.Treeview.Heading", background=[("active", c["primary_mid"])])
        self.style.configure("Card.TFrame", background=c["bg_card"], relief="flat")
        self.style.configure("Soft.TFrame", background=c["bg_soft"])
        self.style.configure("BadgeTitle.TLabel", background=c["bg_card"], foreground=c["text"])
        self.style.configure("BadgeValue.TLabel", background=c["bg_card"], foreground=c["primary"])

    # ---------- UI ----------

    def _monta_toolbar(self, parent):
        bar = ttk.Frame(parent, style="Soft.TFrame")
        bar.pack(fill="x", padx=12, pady=(12, 6))

        title = ttk.Label(bar, text="Gestor de Gastos", font=("Segoe UI", 18, "bold"), style="Pink.TLabel")
        title.pack(side="left", padx=(2, 16))

        ttk.Label(bar, text="Mês:", style="Pink.TLabel").pack(side="left")
        self.var_mes = tk.StringVar(value="Todos")
        self.cb_mes = ttk.Combobox(bar, textvariable=self.var_mes, width=12, state="readonly", style="Pink.TCombobox")
        self.cb_mes.pack(side="left", padx=6)
        self.cb_mes.bind("<<ComboboxSelected>>", lambda e: self.atualiza_lista())

        ttk.Label(bar, text="Status:", style="Pink.TLabel").pack(side="left", padx=(12, 0))
        self.var_filtro = tk.StringVar(value="todas")
        self.cb_filtro = ttk.Combobox(bar, textvariable=self.var_filtro, width=12, state="readonly", values=["todas", "pendentes", "pagas"], style="Pink.TCombobox")
        self.cb_filtro.pack(side="left", padx=6)
        self.cb_filtro.bind("<<ComboboxSelected>>", lambda e: self.atualiza_lista())

        ttk.Label(bar, text="Buscar:", style="Pink.TLabel").pack(side="left", padx=(16, 4))
        self.var_busca = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.var_busca, width=28, style="Pink.TEntry")
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: self.atualiza_lista())

        btn_area = ttk.Frame(bar, style="Soft.TFrame")
        btn_area.pack(side="right")
        ttk.Button(btn_area, text="Adicionar", style="Pink.TButton", command=self.adicionar).pack(side="left", padx=4)
        ttk.Button(btn_area, text="Editar", style="Pink.TButton", command=self.editar).pack(side="left", padx=4)
        ttk.Button(btn_area, text="Marcar paga", style="Pink.TButton", command=self.marcar_paga).pack(side="left", padx=4)
        ttk.Button(btn_area, text="Remover", style="Pink.TButton", command=self.remover).pack(side="left", padx=4)
        ttk.Button(btn_area, text="Recarregar", style="Pink.TButton", command=self.recarregar).pack(side="left", padx=4)

    def _monta_tabela(self, parent):
        table_wrap = ttk.Frame(parent, style="Soft.TFrame")
        table_wrap.pack(fill="both", expand=True, padx=12, pady=6)

        cols = ("id", "titulo", "tipo", "valor", "restante", "mes", "status", "paga_em")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=18, style="Pink.Treeview")
        self.tree.pack(fill="both", expand=True, side="left")

        self.tree.heading("id", text="ID", anchor="w")
        self.tree.heading("titulo", text="Título", anchor="w")
        self.tree.heading("tipo", text="Tipo", anchor="center")
        self.tree.heading("valor", text="Valor", anchor="center")
        self.tree.heading("restante", text="Restante", anchor="center")
        self.tree.heading("mes", text="Mês", anchor="center")
        self.tree.heading("status", text="Status", anchor="center")
        self.tree.heading("paga_em", text="Pago em", anchor="center")

        self.tree.column("id", width=90, anchor="w")
        self.tree.column("titulo", width=400, anchor="w")
        self.tree.column("tipo", width=110, anchor="center")
        self.tree.column("valor", width=120, anchor="e")
        self.tree.column("restante", width=120, anchor="e")
        self.tree.column("mes", width=120, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("paga_em", width=160, anchor="center")

        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("row_odd", background="#fff")
        self.tree.tag_configure("row_even", background="#fff8fb")

        self.tree.bind("<Double-1>", self._duplo_clique)

    def _monta_totais(self, parent):
        row1 = ttk.Frame(parent, style="Soft.TFrame")
        row1.pack(fill="x", padx=12, pady=(6, 3))
        self.card_gastos_all = self._badge_card(row1, "Gastos (tudo)", "R$ 0,00")
        self.card_pendente_all = self._badge_card(row1, "Pendente (tudo)", "R$ 0,00")
        self.card_guardado_all = self._badge_card(row1, "Guardado (tudo)", "R$ 0,00")
        for w in (self.card_gastos_all, self.card_pendente_all, self.card_guardado_all):
            w.pack(side="left", padx=6)

        row2 = ttk.Frame(parent, style="Soft.TFrame")
        row2.pack(fill="x", padx=12, pady=(3, 12))
        self.card_gastos_mes = self._badge_card(row2, "Gastos (mês filtro)", "R$ 0,00")
        self.card_pendente_mes = self._badge_card(row2, "Pendente (mês filtro)", "R$ 0,00")
        self.card_guardado_mes = self._badge_card(row2, "Guardado (mês filtro)", "R$ 0,00")
        for w in (self.card_gastos_mes, self.card_pendente_mes, self.card_guardado_mes):
            w.pack(side="left", padx=6)

        hint = ttk.Label(parent, text="Dicas: Duplo clique abre pagamento parcial • Ctrl+N (Adicionar) • Ctrl+E (Editar) • Ctrl+P (Pagar) • Del (Remover)", style="Pink.TLabel")
        hint.pack(anchor="e", padx=12, pady=(0, 8))

    def _badge_card(self, parent, title, value):
        frame = ttk.Frame(parent, style="Card.TFrame")
        inner = ttk.Frame(frame, style="Card.TFrame")
        inner.pack(padx=10, pady=8)
        ttk.Label(inner, text=title, font=("Segoe UI", 10, "bold"), style="BadgeTitle.TLabel").pack(anchor="w")
        v = ttk.Label(inner, text=value, font=("Segoe UI", 14, "bold"), style="BadgeValue.TLabel")
        v.pack(anchor="w", pady=(2, 0))
        frame._badge_value = v
        return frame

    # ---------- LÓGICA ----------

    def _meses_disponiveis(self):
        chaves = set()
        for d in self.despesas:
            if d.competencia:
                aa, mm = d.competencia.split("-")
                chaves.add((int(aa), int(mm)))
        ordenado = sorted(list(chaves), key=lambda x: (x[0], x[1]), reverse=True)
        return [rotulo_mm_aaaa(aa, mm) for aa, mm in ordenado]

    def _atualiza_combo_mes(self):
        meses = self._meses_disponiveis()
        valores = ["Todos"] + meses
        atual = self.var_mes.get()
        self.cb_mes["values"] = valores
        if atual not in valores:
            self.var_mes.set("Todos")

    def _aplica_filtros_base(self, base: List[Despesa]) -> List[Despesa]:
        # status
        f = self.var_filtro.get()
        if f == "pendentes":
            base = [d for d in base if d.tipo != "guardado" and (Decimal(d.valor) - Decimal(d.valor_pago)) > 0]
        elif f == "pagas":
            base = [d for d in base if d.tipo == "guardado" or (Decimal(d.valor) - Decimal(d.valor_pago)) <= 0]

        # mês
        mes_sel = self.var_mes.get()
        if mes_sel and mes_sel != "Todos":
            alvo = parse_mm_aaaa(mes_sel)
            if alvo:
                aa, mm = alvo
                base = [d for d in base if d.competencia == f"{aa:04d}-{mm:02d}"]

        # busca
        q = (self.var_busca.get() or "").strip().lower()
        if q:
            base = [d for d in base if q in d.titulo.lower()]
        return base

    def _filtradas(self) -> List[Despesa]:
        return self._aplica_filtros_base(list(self.despesas))

    def _sum_guardado(self, linhas: List[Despesa]) -> Decimal:
        return sum((Decimal(d.valor) for d in linhas if d.tipo == "guardado"), Decimal("0"))

    def _sum_gastos_total(self, linhas: List[Despesa]) -> Decimal:
        return sum((Decimal(d.valor) for d in linhas if d.tipo in ("fixo", "extra")), Decimal("0"))

    def _sum_pendente(self, linhas: List[Despesa]) -> Decimal:
        return sum(((Decimal(d.valor) - Decimal(d.valor_pago)) for d in linhas if d.tipo in ("fixo", "extra")), Decimal("0"))

    def atualiza_lista(self):
        self._atualiza_combo_mes()

        for i in self.tree.get_children():
            self.tree.delete(i)

        linhas = self._filtradas()
        for idx, d in enumerate(linhas):
            valor_dec = Decimal(d.valor)
            pago_dec = Decimal(d.valor_pago)
            restante_dec = max(Decimal("0"), valor_dec - pago_dec)

            status = "PAGA" if (d.tipo == "guardado" or restante_dec <= 0) else "PENDENTE"
            comp_label = rotulo_competencia(d.competencia)
            pago_em = d.paga_em.replace("T", " ") if d.paga_em else "-"

            tags = []
            tags.append("row_even" if idx % 2 == 0 else "row_odd")

            self.tree.insert(
                "", "end", iid=d.id,
                values=(d.id, d.titulo, d.tipo.capitalize(), dinheiro(valor_dec), dinheiro(restante_dec), comp_label, status, pago_em),
                tags=tuple(tags)
            )

        self._atualiza_totais()
        self._atualiza_totais_mes()

    def _atualiza_totais(self):
        linhas = list(self.despesas)
        gastos_all = self._sum_gastos_total(linhas)
        pendente_all = self._sum_pendente(linhas)
        guardado_all = self._sum_guardado(linhas)

        self.card_gastos_all._badge_value.config(text=dinheiro(gastos_all))
        self.card_pendente_all._badge_value.config(text=dinheiro(pendente_all))
        self.card_guardado_all._badge_value.config(text=dinheiro(guardado_all))

    def _atualiza_totais_mes(self):
        linhas = self._filtradas()
        gastos_mes = self._sum_gastos_total(linhas)
        pendente_mes = self._sum_pendente(linhas)
        guardado_mes = self._sum_guardado(linhas)

        self.card_gastos_mes._badge_value.config(text=dinheiro(gastos_mes))
        self.card_pendente_mes._badge_value.config(text=dinheiro(pendente_mes))
        self.card_guardado_mes._badge_value.config(text=dinheiro(guardado_mes))

    # ---------- AÇÕES ----------

    def adicionar(self):
        dlg = DespesaDialog(self, title="Nova entrada", styles=self.COLORS)
        if not getattr(dlg, "result", None):
            return
        r = dlg.result
        valor = Decimal(r["valor"])
        tipo = r["tipo"]
        if tipo == "guardado":
            # Guardado entra como pago integral (não é pendência)
            valor_pago = valor
            paga = True
            paga_em = datetime.now().isoformat(timespec="seconds")
        else:
            valor_pago = Decimal("0")
            paga = False
            paga_em = ""

        nova = Despesa(
            id=str(uuid.uuid4())[:8],
            titulo=r["titulo"],
            valor=str(valor),
            competencia=r["competencia"],
            paga=paga,
            paga_em=paga_em,
            tipo=tipo,
            valor_pago=str(valor_pago),
        )
        self.despesas.append(nova)
        salvar(self.despesas)
        self.atualiza_lista()

    def _selecionada(self) -> Optional[Despesa]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Atenção", "Selecione um item na tabela.")
            return None
        _id = sel[0]
        for d in self.despesas:
            if d.id == _id:
                return d
        return None

    def editar(self):
        d = self._selecionada()
        if not d:
            return
        dlg = DespesaDialog(self, title=f"Editar: {d.titulo}", despesa=d, styles=self.COLORS)
        if not getattr(dlg, "result", None):
            return
        r = dlg.result
        novo_valor = Decimal(r["valor"])
        antigo_pago = Decimal(d.valor_pago)

        d.titulo = r["titulo"]
        d.valor = str(novo_valor)
        d.competencia = r["competencia"]
        d.tipo = r["tipo"]

        if d.tipo == "guardado":
            d.valor_pago = str(novo_valor)  # pago integral
            d.paga = True
            if not d.paga_em:
                d.paga_em = datetime.now().isoformat(timespec="seconds")
        else:
            # Se reduzir valor abaixo do já pago, trunca
            if antigo_pago > novo_valor:
                d.valor_pago = str(novo_valor)
            d.paga = Decimal(d.valor_pago) >= novo_valor
            if d.paga and not d.paga_em:
                d.paga_em = datetime.now().isoformat(timespec="seconds")
            if not d.paga:
                d.paga_em = ""

        salvar(self.despesas)
        self.atualiza_lista()

    def marcar_paga(self):
        d = self._selecionada()
        if not d:
            return
        if d.tipo == "guardado":
            messagebox.showinfo("Info", "Itens do tipo 'guardado' não têm pendência.")
            return

        valor_total = Decimal(d.valor)
        pago_atual = Decimal(d.valor_pago)
        restante = max(Decimal("0"), valor_total - pago_atual)
        if restante <= 0:
            messagebox.showinfo("Info", "Essa despesa já está totalmente paga.")
            return

        # pergunta quanto pagar agora (padrão = restante)
        resp = simpledialog.askstring(
            "Pagamento parcial",
            f"Valor a pagar agora (restante {dinheiro(restante)}):",
            parent=self
        )
        if resp is None:
            return
        s = resp.strip().replace("R$", "").replace(" ", "")
        s = s.replace(".", "").replace(",", ".")
        try:
            pagar_agora = Decimal(s)
        except (InvalidOperation, ValueError):
            messagebox.showerror("Erro", "Valor inválido.")
            return
        if pagar_agora <= 0:
            messagebox.showerror("Erro", "Informe um valor maior que zero.")
            return

        novo_pago = pago_atual + pagar_agora
        if novo_pago > valor_total:
            if not messagebox.askyesno("Confirmar", "Valor informado é maior que o restante. Deseja quitar a despesa mesmo assim?"):
                return
            novo_pago = valor_total

        d.valor_pago = str(novo_pago)
        if novo_pago >= valor_total:
            d.paga = True
            d.paga_em = datetime.now().isoformat(timespec="seconds")
        else:
            d.paga = False
            d.paga_em = ""

        salvar(self.despesas)
        self.atualiza_lista()

    def remover(self):
        d = self._selecionada()
        if not d:
            return
        if not messagebox.askyesno("Confirmar", f"Remover '{d.titulo}'?"):
            return
        self.despesas = [x for x in self.despesas if x.id != d.id]
        salvar(self.despesas)
        self.atualiza_lista()

    def recarregar(self):
        self.despesas = carregar()
        self.atualiza_lista()

    def _duplo_clique(self, _event):
        # atalho: duplo clique para abrir pagamento parcial
        d = self._selecionada()
        if d and d.tipo != "guardado":
            self.marcar_paga()

# ====================== MAIN ======================

if __name__ == "__main__":
    App().mainloop()
