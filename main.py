# -*- coding: utf-8 -*-
"""
Дневник расходов — Android-приложение на Kivy.
Сборка: buildozer android debug (см. buildozer.spec и .github/workflows/build.yml)
"""
import json
import os
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import get_color_from_hex

# ---- палитра: тёплый стиль ----
C_BG = get_color_from_hex("#FAF6F0")
C_CARD = get_color_from_hex("#FFFFFF")
C_ACCENT = get_color_from_hex("#E9734F")   # расход
C_GREEN = get_color_from_hex("#5FA46B")    # доход
C_TEXT = get_color_from_hex("#3D3229")
C_MUTED = get_color_from_hex("#8A7A6B")
C_CHIKA = get_color_from_hex("#F3E9DE")    # неактивная категория
C_CHSEL = get_color_from_hex("#E9734F")    # выбранная категория

CATS_EXPENSE = ["Еда", "Транспорт", "Дом", "Здоровье", "Связь", "Одежда", "Развлечения", "Прочее"]
CATS_INCOME = ["Зарплата", "Подработка", "Подарок", "Прочее"]


def rub(x):
    return f"{x:,.2f}".replace(",", " ") + " руб."


class Card(BoxLayout):
    """Белая карточка со скруглёнными углами."""
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*C_CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size


def make_label(text, size=dp(16), color=C_TEXT, bold=False, halign="left", **kw):
    lbl = Label(text=text, font_size=size, color=color,
                halign=halign, valign="middle", markup=True, **kw)
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    return lbl


def make_btn(text, cb, bg=C_ACCENT, height=dp(52), size_hint=(1, None), color=(1, 1, 1, 1)):
    b = Button(text=text, background_normal="", background_color=bg,
               font_size=dp(18), color=color, size_hint=size_hint, height=height)
    b.bind(on_release=lambda inst: cb())
    return b


def spacer(h=dp(10)):
    return BoxLayout(size_hint=(1, None), height=h)


def scroll_column():
    grid = GridLayout(cols=1, spacing=dp(10), padding=[dp(14), dp(8)],
                      size_hint=(1, None))
    grid.bind(minimum_height=grid.setter("height"))
    sv = ScrollView()
    sv.add_widget(grid)
    return sv, grid


class DiaryApp(App):
    title = "Дневник расходов"

    # ---------- данные ----------
    def load(self):
        try:
            with open(self.data_file(), "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        self.records = d.get("records", [])
        self.goals = d.get("goals", {})

    def save(self):
        path = self.data_file()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"records": self.records, "goals": self.goals},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def data_file(self):
        return os.path.join(self.user_data_dir, "diary.json")

    def totals(self, records):
        inc = sum(r["amount"] for r in records if r["kind"] == "income")
        exp = sum(r["amount"] for r in records if r["kind"] == "expense")
        return inc, exp

    def period_records(self, days):
        if days is None:
            return self.records
        now = datetime.now()
        out = []
        for r in self.records:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            if (now - d).days < days:
                out.append(r)
        return out

    # ---------- сборка интерфейса ----------
    def build(self):
        Window.clearcolor = C_BG
        Window.softinput_mode = "below_target"
        self.load()
        self.pending_kind = "expense"
        self.sel_cat = CATS_EXPENSE[-1]

        sm = ScreenManager()
        self.home = self.make_home("home")
        self.add_scr = self.make_add("add")
        self.rep_scr = self.make_report("report")
        self.goals_scr = self.make_goals("goals")
        for s in (self.home, self.add_scr, self.rep_scr, self.goals_scr):
            sm.add_widget(s)
        self.sm = sm
        return sm

    def go(self, name):
        self.root.current = name

    # ---------- ГЛАВНЫЙ ЭКРАН ----------
    def make_home(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        root.add_widget(make_label("[b]Дневник расходов[/b]", dp(24)))

        card = Card(orientation="vertical", padding=dp(14), spacing=dp(4),
                    size_hint=(1, None), height=dp(118))
        self.lbl_balance = make_label("", dp(26), C_TEXT)
        self.lbl_today = make_label("", dp(15), C_MUTED)
        card.add_widget(self.lbl_balance)
        card.add_widget(self.lbl_today)
        root.add_widget(card)

        row = BoxLayout(size_hint=(1, None), height=dp(56), spacing=dp(10))
        row.add_widget(make_btn("+ Расход", lambda: self.open_add("expense"), C_ACCENT))
        row.add_widget(make_btn("+ Доход", lambda: self.open_add("income"), C_GREEN))
        root.add_widget(row)

        row2 = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(10))
        row2.add_widget(make_btn("Отчёты", lambda: self.go("report"),
                                 get_color_from_hex("#7B6A5A")))
        row2.add_widget(make_btn("Цели", lambda: self.go("goals"),
                                 get_color_from_hex("#7B6A5A")))
        root.add_widget(row2)

        root.add_widget(make_label("Последние записи", dp(16), C_MUTED))
        self.home_scroll, self.home_grid = scroll_column()
        root.add_widget(self.home_scroll)

        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.refresh_home())
        return scr

    def refresh_home(self):
        inc, exp = self.totals(self.records)
        self.lbl_balance.text = f"[b]Баланс: {rub(inc - exp)}[/b]"
        today = datetime.now().strftime("%Y-%m-%d")
        t_exp = sum(r["amount"] for r in self.records
                    if r["kind"] == "expense" and r["date"] == today)
        self.lbl_today.text = f"Расходов сегодня: {rub(t_exp)}   Всего записей: {len(self.records)}"

        self.home_grid.clear_widgets()
        if not self.records:
            self.home_grid.add_widget(make_label("Записей пока нет.\nНажмите «+ Расход».",
                                                 dp(16), C_MUTED))
            return
        for r in reversed(self.records[-12:]):
            sign = "−" if r["kind"] == "expense" else "+"
            col = C_ACCENT if r["kind"] == "expense" else C_GREEN
            cmt = f' · {r["comment"]}' if r.get("comment") else ""
            card = Card(orientation="vertical", padding=dp(10), spacing=dp(2),
                        size_hint=(1, None), height=dp(64))
            card.add_widget(make_label(f'{sign}{rub(r["amount"])}  {r["category"]}',
                                       dp(17), col))
            card.add_widget(make_label(f'{r["date"]} {r.get("time","")}{cmt}',
                                       dp(13), C_MUTED))
            self.home_grid.add_widget(card)

    # ---------- ЭКРАН ДОБАВЛЕНИЯ ----------
    def open_add(self, kind):
        self.pending_kind = kind
        self.rebuild_cats()
        self.add_title.text = ("Новый расход" if kind == "expense" else "Новый доход")
        self.amount_input.text = ""
        self.comment_input.text = ""
        self.add_msg.text = ""
        self.root.current = "add"

    def make_add(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        top = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(8))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                C_CHIKA, dp(48), size_hint=(None, 1), color=C_TEXT))
        self.add_title = make_label("[b]Новый расход[/b]", dp(22))
        top.add_widget(self.add_title)
        root.add_widget(top)

        self.amount_input = TextInput(font_size=dp(26), multiline=False,
                                      input_filter="float", size_hint=(1, None),
                                      height=dp(60), hint_text="Сумма")
        root.add_widget(self.amount_input)

        root.add_widget(make_label("Категория", dp(15), C_MUTED))
        self.cats_grid = GridLayout(cols=4, spacing=dp(8), size_hint=(1, None))
        self.cats_grid.bind(minimum_height=self.cats_grid.setter("height"))
        root.add_widget(self.cats_grid)

        self.comment_input = TextInput(font_size=dp(17), multiline=False,
                                       size_hint=(1, None), height=dp(48),
                                       hint_text="Комментарий (можно пусто)")
        root.add_widget(self.comment_input)

        root.add_widget(make_btn("Сохранить", self.save_record))
        self.add_msg = make_label("", dp(15), C_ACCENT)
        root.add_widget(self.add_msg)

        scr.add_widget(root)
        return scr

    def rebuild_cats(self):
        cats = CATS_EXPENSE if self.pending_kind == "expense" else CATS_INCOME
        if self.sel_cat not in cats:
            self.sel_cat = cats[-1]
        self.cats_grid.clear_widgets()
        for c in cats:
            b = Button(text=c, font_size=dp(15),
                       background_normal="",
                       background_color=C_CHSEL if c == self.sel_cat else C_CHIKA,
                       color=(1, 1, 1, 1) if c == self.sel_cat else C_TEXT,
                       size_hint=(1, None), height=dp(44))
            b.bind(on_release=lambda inst, cat=c: self.pick_cat(cat))
            self.cats_grid.add_widget(b)

    def pick_cat(self, cat):
        self.sel_cat = cat
        self.rebuild_cats()

    def save_record(self):
        raw = self.amount_input.text.strip().replace(",", ".").replace(" ", "")
        try:
            amount = round(float(raw), 2)
        except ValueError:
            self.add_msg.text = "Введите сумму числом."
            return
        if amount <= 0:
            self.add_msg.text = "Сумма должна быть больше нуля."
            return
        self.records.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "kind": self.pending_kind,
            "amount": amount,
            "category": self.sel_cat,
            "comment": self.comment_input.text.strip(),
        })
        self.save()
        self.refresh_home()
        self.root.current = "home"

    # ---------- ОТЧЁТЫ ----------
    def make_report(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        top = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(8))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                C_CHIKA, dp(48), size_hint=(None, 1), color=C_TEXT))
        top.add_widget(make_label("[b]Отчёты[/b]", dp(22)))
        root.add_widget(top)

        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(6))
        for t, d in [("Сегодня", 1), ("Неделя", 7), ("Месяц", 31), ("Всё", None)]:
            row.add_widget(make_btn(t, lambda dd=d: self.show_report(dd),
                                    C_CHIKA, dp(44), color=C_TEXT))
        root.add_widget(row)

        self.report_lbl = make_label("", dp(16))
        root.add_widget(self.report_lbl)
        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.show_report(7))
        return scr

    def show_report(self, days):
        recs = self.period_records(days)
        title = {1: "Сегодня", 7: "За неделю", 31: "За месяц", None: "За всё время"}[days]
        if not recs:
            self.report_lbl.text = f"[b]{title}[/b]\nЗаписей нет."
            return
        inc, exp = self.totals(recs)
        lines = [f"[b]{title}[/b]",
                 f"Доходы: {rub(inc)}",
                 f"Расходы: {rub(exp)}",
                 f"Остаток: {rub(inc - exp)}", ""]
        by_cat = {}
        for r in recs:
            if r["kind"] == "expense":
                by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]
        if by_cat:
            mx = max(by_cat.values())
            for cat, s in sorted(by_cat.items(), key=lambda x: -x[1]):
                bar = "#" * max(1, int(s / mx * 14))
                lines.append(f"{cat}: {rub(s)} {bar}")
        self.report_lbl.text = "\n".join(lines)

    # ---------- ЦЕЛИ ----------
    def make_goals(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        top = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(8))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                C_CHIKA, dp(48), size_hint=(None, 1), color=C_TEXT))
        top.add_widget(make_label("[b]Цели[/b]", dp(22)))
        root.add_widget(top)

        self.goals_scroll, self.goals_grid = scroll_column()
        root.add_widget(self.goals_scroll)

        bottom = Card(orientation="vertical", padding=dp(10), spacing=dp(8),
                      size_hint=(1, None), height=dp(150))
        bottom.add_widget(make_label("Новая цель", dp(15), C_MUTED))
        self.goal_name = TextInput(font_size=dp(17), multiline=False,
                                   size_hint=(1, None), height=dp(44),
                                   hint_text="Название (например, Отпуск)")
        self.goal_target = TextInput(font_size=dp(17), multiline=False,
                                     input_filter="float", size_hint=(1, None),
                                     height=dp(44), hint_text="Нужная сумма")
        bottom.add_widget(self.goal_name)
        bottom.add_widget(self.goal_target)
        bottom.add_widget(make_btn("Создать цель", self.create_goal, C_GREEN, dp(44)))
        root.add_widget(bottom)

        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.refresh_goals())
        return scr

    def refresh_goals(self):
        self.goals_grid.clear_widgets()
        if not self.goals:
            self.goals_grid.add_widget(make_label("Целей пока нет.\nСоздайте первую внизу.",
                                                  dp(16), C_MUTED))
            return
        for gname, g in self.goals.items():
            saved = sum(r["amount"] for r in self.records
                        if r["kind"] == "income" and r.get("comment") == f"цель:{gname}")
            pct = min(100, saved / g["target"] * 100) if g["target"] else 0
            row = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(6))
            row.add_widget(make_label(f"{gname}: {pct:.0f}%", dp(16),
                                      size_hint=(0.55, 1)))
            row.add_widget(make_label(rub(saved), dp(14), C_MUTED, size_hint=(0.25, 1)))
            row.add_widget(make_btn("×", lambda gn=gname: self.del_goal(gn),
                                    C_CHIKA, dp(44), size_hint=(0.1, 1), color=C_ACCENT))
            self.goals_grid.add_widget(row)
            fund_row = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(6))
            ti = TextInput(font_size=dp(16), multiline=False, input_filter="float",
                           size_hint=(0.6, None), height=dp(48), hint_text="Сумма")
            fund_row.add_widget(ti)
            fund_row.add_widget(make_btn("Отложить", lambda gn=gname, t=ti: self.fund_goal(gn, t),
                                         C_GREEN, dp(44), size_hint=(0.4, None)))
            self.goals_grid.add_widget(fund_row)
            self.goals_grid.add_widget(spacer(dp(6)))

    def create_goal(self):
        name = self.goal_name.text.strip()
        if not name:
            return
        raw = self.goal_target.text.strip().replace(",", ".").replace(" ", "")
        try:
            target = round(float(raw), 2)
        except ValueError:
            return
        if target <= 0:
            return
        self.goals[name] = {"target": target}
        self.save()
        self.goal_name.text = ""
        self.goal_target.text = ""
        self.refresh_goals()

    def fund_goal(self, gname, ti):
        raw = ti.text.strip().replace(",", ".").replace(" ", "")
        try:
            amount = round(float(raw), 2)
        except ValueError:
            return
        if amount <= 0:
            return
        self.records.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "kind": "income", "amount": amount,
            "category": "Цель", "comment": f"цель:{gname}",
        })
        self.save()
        self.refresh_goals()

    def del_goal(self, gname):
        self.goals.pop(gname, None)
        self.save()
        self.refresh_goals()


if __name__ == "__main__":
    DiaryApp().run()
