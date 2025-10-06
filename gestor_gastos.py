"""
Gestor de Gastos (GUI / Tkinter) - Responsivo + Filtro por Categoria (Fixos, Extras, Guardado)
- Tema rosa
- Competência por MÊS (mm/aaaa)
- Pagamento parcial (coluna "Restante")
- Categorias: fixo, extra, guardado
- Filtros por mês, status, categoria e busca
- Totais gerais e do mês filtrado
- Layout responsivo (grid + pesos, colunas auto-ajustáveis, scrollbars)
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

def dinheiro(valor) -> str:
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    q = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{q:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def parse_mm_aaaa(s: str) -> Optional[Tuple[int, int]]:
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
    s = (s or "").strip()
    if not s:
        return ""
    mmaaaa = parse_mm_aaaa(s)
    if mmaaaa:
        aa, mm = mmaaaa
        return f"{aa:04d}-{mm:02d}"
    try:
        datetime.strptime(s + "-01", "%Y-%m-%d")
        return s
    except Exception:
        return ""

def rotulo_competencia(iso_yyyy_mm: str) -> str:
    iso = (iso_yyyy_mm or "").strip()
    if not iso:
        return "-"
    try:
        aa, mm = iso.split("-")
        return f"{int(mm):02d}/{int(aa)}"
    except Exception:
        return "-"

@dataclass
class Despesa:
    id: str
    titulo: str
    valor: str
    competencia: str
    paga: bool
    paga_em: str
    tipo: str
    valor_pago: str

def carregar() -> List[Despesa]:
    if not os.path.exists(ARQUIVO):
        return []
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        out: List[Despesa] = []
        for d in bruto:
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

            if desp.tipo == "guardado":
                desp.paga = True
                if Decimal(desp.valor_pago) < Decimal(desp.valor):
                    desp.valor_pago = desp.valor
                if not desp.paga_em:
                    desp.paga_em = datetime.now().isoformat(timespec="seconds")

            if desp.tipo != "guardado":
                if Decimal(desp.valor_pago) >= Decimal(desp.valor):
                    desp.paga = True
                    if not desp.paga_em:
                        desp.paga_em = datetime.now().isoformat(timespec="seconds")

            out.append(desp)
        return out
    except Exception:
        try:
            os.replace(ARQUIVO, ARQUIVO + ".bak")
        except Exception:
            pass
        return []

def salvar(despesas: List[Despesa]):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump([asdict(d) for d in despesas], f, ensure_ascii=False, indent=2)

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

        for c in range(2):
            master.grid_columnconfigure(c, weight=1)
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

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Gastos - Rosa (Responsivo + Filtro por Categoria)")
        self.geometry("1150x720")
        self.minsize(880, 540)

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

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._monta_toolbar()
        self._monta_tabela()
        self._monta_totais()

        self.atualiza_lista()

        self.bind("<Delete>", lambda e: self.remover())
        self.bind("<Control-n>", lambda e: self.adicionar())
        self.bind("<Control-e>", lambda e: self.editar())
        self.bind("<Control-p>", lambda e: self.marcar_paga())

        self.tree.bind("<Configure>", lambda e: self._ajusta_colunas())

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

    def _monta_toolbar(self):
        bar = ttk.Frame(self, style="Soft.TFrame")
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        bar.grid_columnconfigure(0, weight=0)
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_columnconfigure(2, weight=0)
        bar.grid_columnconfigure(3, weight=0)
        bar.grid_columnconfigure(4, weight=1)  # campo Buscar cresce
        bar.grid_columnconfigure(5, weight=0)

        title = ttk.Label(bar, text="Gestor de Gastos (Mensal + Pagamento Parcial)", font=("Segoe UI", 16, "bold"), style="Pink.TLabel")
        title.grid(row=0, column=0, sticky="w", padx=(2, 16))

        ttk.Label(bar, text="Mês:", style="Pink.TLabel").grid(row=0, column=1, sticky="w")
        self.var_mes = tk.StringVar(value="Todos")
        self.cb_mes = ttk.Combobox(bar, textvariable=self.var_mes, width=12, state="readonly", style="Pink.TCombobox")
        self.cb_mes.grid(row=0, column=2, sticky="w", padx=6)
        self.cb_mes.bind("<<ComboboxSelected>>", lambda e: self.atualiza_lista())

        ttk.Label(bar, text="Status:", style="Pink.TLabel").grid(row=0, column=3, sticky="w", padx=(12, 0))
        self.var_filtro = tk.StringVar(value="todas")
        self.cb_filtro = ttk.Combobox(bar, textvariable=self.var_filtro, width=12, state="readonly", values=["todas", "pendentes", "pagas"], style="Pink.TCombobox")
        self.cb_filtro.grid(row=0, column=3, sticky="e", padx=(64, 6))
        self.cb_filtro.bind("<<ComboboxSelected>>", lambda e: self.atualiza_lista())

        ttk.Label(bar, text="Categoria:", style="Pink.TLabel").grid(row=0, column=4, sticky="w")
        self.var_categoria = tk.StringVar(value="todas")
        self.cb_categoria = ttk.Combobox(bar, textvariable=self.var_categoria, width=12, state="readonly", values=["todas", "fixo", "extra", "guardado"], style="Pink.TCombobox")
        self.cb_categoria.grid(row=0, column=5, sticky="w", padx=6)
        self.cb_categoria.bind("<<ComboboxSelected>>", lambda e: self.atualiza_lista())

        buscar_wrap = ttk.Frame(bar, style="Soft.TFrame")
        buscar_wrap.grid(row=0, column=6, sticky="ew", padx=(16, 4))
        buscar_wrap.grid_columnconfigure(1, weight=1)
        ttk.Label(buscar_wrap, text="Buscar:", style="Pink.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.var_busca = tk.StringVar()
        ent = ttk.Entry(buscar_wrap, textvariable=self.var_busca, width=28, style="Pink.TEntry")
        ent.grid(row=0, column=1, sticky="ew")
        ent.bind("<KeyRelease>", lambda e: self.atualiza_lista())

        btn_area = ttk.Frame(bar, style="Soft.TFrame")
        btn_area.grid(row=0, column=7, sticky="e")
        ttk.Button(btn_area, text="Adicionar", style="Pink.TButton", command=self.adicionar).pack(side="left", padx=3)
        ttk.Button(btn_area, text="Editar", style="Pink.TButton", command=self.editar).pack(side="left", padx=3)
        ttk.Button(btn_area, text="Marcar paga", style="Pink.TButton", command=self.marcar_paga).pack(side="left", padx=3)
        ttk.Button(btn_area, text="Remover", style="Pink.TButton", command=self.remover).pack(side="left", padx=3)
        ttk.Button(btn_area, text="Recarregar", style="Pink.TButton", command=self.recarregar).pack(side="left", padx=3)

    def _monta_tabela(self):
        table_wrap = ttk.Frame(self, style="Soft.TFrame")
        table_wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        cols = ("id", "titulo", "tipo", "valor", "restante", "mes", "status", "paga_em")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", style="Pink.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew")

        headings = {
            "id": "ID",
            "titulo": "Título",
            "tipo": "Tipo",
            "valor": "Valor",
            "restante": "Restante",
            "mes": "Mês",
            "status": "Status",
            "paga_em": "Pago em",
        }
        for c, txt in headings.items():
            self.tree.heading(c, text=txt, anchor="w" if c in ("id", "titulo") else "center")

        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.tag_configure("row_odd", background="#fff")
        self.tree.tag_configure("row_even", background="#fff8fb")

        self.tree.bind("<Double-1>", self._duplo_clique)

    def _monta_totais(self):
        totals = ttk.Frame(self, style="Soft.TFrame")
        totals.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))
        totals.grid_columnconfigure(0, weight=1)
        totals.grid_columnconfigure(1, weight=1)
        totals.grid_columnconfigure(2, weight=1)
        totals.grid_columnconfigure(3, weight=1)
        totals.grid_columnconfigure(4, weight=1)
        totals.grid_columnconfigure(5, weight=1)

        self.card_gastos_all = self._badge_card(totals, "Gastos (tudo)", "R$ 0,00")
        self.card_pendente_all = self._badge_card(totals, "Pendente (tudo)", "R$ 0,00")
        self.card_guardado_all = self._badge_card(totals, "Guardado (tudo)", "R$ 0,00")

        self.card_gastos_all.grid(row=0, column=0, sticky="ew", padx=6)
        self.card_pendente_all.grid(row=0, column=1, sticky="ew", padx=6)
        self.card_guardado_all.grid(row=0, column=2, sticky="ew", padx=6)

        self.card_gastos_mes = self._badge_card(totals, "Gastos (mês filtro)", "R$ 0,00")
        self.card_pendente_mes = self._badge_card(totals, "Pendente (mês filtro)", "R$ 0,00")
        self.card_guardado_mes = self._badge_card(totals, "Guardado (mês filtro)", "R$ 0,00")

        self.card_gastos_mes.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))
        self.card_pendente_mes.grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))
        self.card_guardado_mes.grid(row=1, column=2, sticky="ew", padx=6, pady=(8, 0))

        sizegrip = ttk.Sizegrip(self)
        sizegrip.grid(row=2, column=0, sticky="se", padx=4, pady=4)

    def _badge_card(self, parent, title, value):
        frame = ttk.Frame(parent, style="Card.TFrame")
        inner = ttk.Frame(frame, style="Card.TFrame")
        inner.pack(padx=10, pady=8, fill="x")
        ttk.Label(inner, text=title, font=("Segoe UI", 10, "bold"), style="BadgeTitle.TLabel").pack(anchor="w")
        v = ttk.Label(inner, text=value, font=("Segoe UI", 14, "bold"), style="BadgeValue.TLabel")
        v.pack(anchor="w", pady=(2, 0))
        frame._badge_value = v
        return frame

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
        f_categoria = self.var_categoria.get()
        if f_categoria != "todas":
            base = [d for d in base if d.tipo == f_categoria]

        f_status = self.var_filtro.get()
        if f_status == "pendentes":
            base = [d for d in base if d.tipo != "guardado" and (Decimal(d.valor) - Decimal(d.valor_pago)) > 0]
        elif f_status == "pagas":
            base = [d for d in base if d.tipo == "guardado" or (Decimal(d.valor) - Decimal(d.valor_pago)) <= 0]

        mes_sel = self.var_mes.get()
        if mes_sel and mes_sel != "Todos":
            alvo = parse_mm_aaaa(mes_sel)
            if alvo:
                aa, mm = alvo
                base = [d for d in base if d.competencia == f"{aa:04d}-{mm:02d}"]

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

    def _atualiza_totais(self):
        todas_despesas = list(self.despesas)
        
        gastos_total = self._sum_gastos_total(todas_despesas)
        pendente_total = self._sum_pendente(todas_despesas)
        guardado_total = self._sum_guardado(todas_despesas)
        
        self.card_gastos_all._badge_value.config(text=dinheiro(gastos_total))
        self.card_pendente_all._badge_value.config(text=dinheiro(pendente_total))
        self.card_guardado_all._badge_value.config(text=dinheiro(guardado_total))

    def _atualiza_totais_mes(self):
        despesas_filtradas = self._filtradas()
        
        gastos_mes = self._sum_gastos_total(despesas_filtradas)
        pendente_mes = self._sum_pendente(despesas_filtradas)
        guardado_mes = self._sum_guardado(despesas_filtradas)
        
        self.card_gastos_mes._badge_value.config(text=dinheiro(gastos_mes))
        self.card_pendente_mes._badge_value.config(text=dinheiro(pendente_mes))
        self.card_guardado_mes._badge_value.config(text=dinheiro(guardado_mes))

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

            tags = ["row_even" if idx % 2 == 0 else "row_odd"]

            self.tree.insert(
                "", "end", iid=d.id,
                values=(d.id, d.titulo, d.tipo.capitalize(), dinheiro(valor_dec), dinheiro(restante_dec), comp_label, status, pago_em),
                tags=tuple(tags)
            )

        self._ajusta_colunas()
        self._atualiza_totais()
        self._atualiza_totais_mes()

    def _ajusta_colunas(self):
        try:
            total = max(1, self.tree.winfo_width())
        except Exception:
            return

        w_id = 90
        w_tipo = 110
        w_val = 120
        w_rest = 120
        w_mes = 120
        w_status = 110
        w_pagoem_min = 160

        usados = w_id + w_tipo + w_val + w_rest + w_mes + w_status + w_pagoem_min
        w_titulo = max(200, total - usados - 8)

        self.tree.column("id", width=w_id, minwidth=70, anchor="w")
        self.tree.column("tipo", width=w_tipo, minwidth=90, anchor="center")
        self.tree.column("valor", width=w_val, minwidth=100, anchor="e")
        self.tree.column("restante", width=w_rest, minwidth=100, anchor="e")
        self.tree.column("mes", width=w_mes, minwidth=100, anchor="center")
        self.tree.column("status", width=w_status, minwidth=90, anchor="center")
        self.tree.column("paga_em", width=w_pagoem_min, minwidth=140, anchor="center")

        self.tree.column("titulo", width=w_titulo, minwidth=200, anchor="w")

    def adicionar(self):
        dlg = DespesaDialog(self, title="Nova entrada", styles=self.COLORS)
        if not getattr(dlg, "result", None):
            return
        r = dlg.result
        valor = Decimal(r["valor"])
        tipo = r["tipo"]
        if tipo == "guardado":
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
            d.valor_pago = str(novo_valor)
            d.paga = True
            if not d.paga_em:
                d.paga_em = datetime.now().isoformat(timespec="seconds")
        else:
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

        resp = simpledialog.askstring("Pagamento parcial", f"Valor a pagar agora (restante {dinheiro(restante)}):", parent=self)
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
        d = self._selecionada()
        if d and d.tipo != "guardado":
            self.marcar_paga()

if __name__ == "__main__":
    App().mainloop()

