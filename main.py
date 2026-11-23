# -*- coding: utf-8 -*-
"""
Дневник расходов — Android-приложение на Kivy.
Версия: 1.1 (код v7). Версия видна внизу «Настройки».
Версия: 1.1.1 (код v7-fix2): фикс двойного добавления контейнера настроек
в ScrollView (WidgetException из сборки 17). База — v7-fix.
Версия 7 (яндекс-стиль): жёлто-красная палитра, крестики в виде аккуратных кружков, системная кнопка «назад» ходит по экранам и сворачивает приложение вместо закрытия, непрозрачный экран пин-кода (суммы за ним не видны), напоминания о накоплениях и график откладывания для целей.
"""
import hashlib
import json
import math
import os
import calendar
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.uix.floatlayout import FloatLayout
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.utils import get_color_from_hex

# ---- палитры: светлая (крем) и тёмная (кофе) ----
THEME_LIGHT = dict(bg="#F6F7F8", card="#FFFFFF",
                   accent="#FFCC00", accentfg="#21201F", danger="#FC3F1D",
                   green="#1F9E52", text="#21201F", muted="#8C8C8C",
                   soft="#FFF7D6", softg="#E6F7EC", chip="#EEF0F2",
                   chsel="#FFCC00", chselfg="#21201F",
                   track="#E9EBED", field="#F2F3F5")
THEME_DARK = dict(bg="#1C1C1E", card="#2A2A2C",
                  accent="#FFCC00", accentfg="#21201F", danger="#FF6B54",
                  green="#4CC38A", text="#F4F4F4", muted="#A0A0A2",
                  soft="#33312A", softg="#26362C", chip="#35353A",
                  chsel="#FFCC00", chselfg="#21201F",
                  track="#3A3A3E", field="#2E2E31")

PAL = {k: get_color_from_hex(v) for k, v in THEME_LIGHT.items()}

APP_VERSION = "1.1.1 (v7-fix2)"

CATS_EXPENSE = ["Еда", "Транспорт", "Дом", "Здоровье", "Связь", "Одежда", "Развлечения", "Прочее"]
CATS_INCOME = ["Зарплата", "Подработка", "Подарок", "Прочее"]


def all_cats(kind, custom):
    return (CATS_EXPENSE if kind == "expense" else CATS_INCOME) + custom[kind]

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг",
            "пятница", "суббота", "воскресенье"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def rub(x):
    return f"{x:,.2f}".replace(",", " ") + " руб."


def blend(color, t=0.16):
    """Слегка осветлить цвет — эффект нажатия."""
    return tuple(ch + (1 - ch) * t for ch in color[:3]) + (1.0,)


def human_date(now=None):
    now = now or datetime.now()
    return f"{WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]}"


def greeting(now=None):
    h = (now or datetime.now()).hour
    if 5 <= h < 12:
        return "Доброе утро"
    if 12 <= h < 18:
        return "Добрый день"
    if 18 <= h < 23:
        return "Добрый вечер"
    return "Доброй ночи"


def fmt_when(r):
    """Дата и время записи по-человечески: «21 ноября, 14:35»."""
    try:
        d = datetime.strptime(r["date"], "%Y-%m-%d")
        base = f"{d.day} {MONTHS[d.month
    # ---------- ГЛАВНЫЙ ЭКРАН ----------
    def make_home(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        self.lbl_greet = make_label("", dp(14), PAL["muted"])
        root.add_widget(self.lbl_greet)

        card = Card(bg=PAL["soft"], radius=dp(24), padding=dp(18), spacing=dp(4),
                    orientation="vertical", size_hint=(1, None), height=dp(124))
        card.add_widget(make_label("Баланс", dp(13), PAL["muted"]))
        self.lbl_balance = make_label("", dp(30), PAL["text"])
        card.add_widget(self.lbl_balance)
        self.lbl_today = make_label("", dp(14), PAL["muted"])
        card.add_widget(self.lbl_today)
        root.add_widget(card)

        self.budget_holder = self.make_budget_card()
        root.add_widget(self.budget_holder)
        self.remind_holder = BoxLayout(size_hint=(1, None), height=0)
        root.add_widget(self.remind_holder)

        grid = GridLayout(cols=2, spacing=dp(10), size_hint=(1, None),
                          height=dp(54) * 2 + dp(10))
        grid.add_widget(make_btn("+ Расход", lambda: self.open_add("expense"),
                                 PAL["accent"], dp(54), color=PAL["accentfg"]))
        grid.add_widget(make_btn("+ Доход", lambda: self.open_add("income"),
                                 PAL["green"], dp(54)))
        grid.add_widget(make_btn("Отчёты", lambda: self.go("report"),
                                 PAL["chip"], dp(54), color=PAL["text"]))
        grid.add_widget(make_btn("Цели", lambda: self.go("goals"),
                                 PAL["chip"], dp(54), color=PAL["text"]))
        root.add_widget(grid)

        root.add_widget(make_btn("Настройки", lambda: self.go("settings"),
                                 PAL["chip"], dp(44), color=PAL["text"],
                                 font_size=dp(15)))

        root.add_widget(make_label("Последние записи", dp(15), PAL["muted"]))
        self.home_scroll, self.home_grid = scroll_column()
        root.add_widget(self.home_scroll)

        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.refresh_home())
        return scr

    def make_budget_card(self):
        holder = FloatLayout(size_hint=(1, None), height=dp(100))
        card = Card(bg=PAL["soft"], radius=dp(20), padding=dp(14),
                    spacing=dp(4), orientation="vertical", size_hint=(1, 1),
                    pos_hint={"x": 0, "y": 0})
        self.budget_lbl_big = make_label("", dp(18))
        card.add_widget(self.budget_lbl_big)
        self.budget_lbl_sub = make_label("", dp(13), PAL["muted"])
        card.add_widget(self.budget_lbl_sub)
        self.budget_bar = GoalBar(0, size_hint=(1, None), height=dp(10))
        card.add_widget(self.budget_bar)
        overlay = Button(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0))
        overlay.bind(on_release=lambda inst: self.edit_budget())
        holder.add_widget(card)
        holder.add_widget(overlay)
        return holder

    def refresh_home(self):
        now = datetime.now()
        self.lbl_greet.text = f"{greeting(now)} · {human_date(now)}"

        month = now.strftime("%Y-%m")
        m_exp = sum(r["amount"] for r in self.records
                    if r["kind"] == "expense" and r["date"].startswith(month))
        if self.budget:
            left = self.budget - m_exp
            pct = m_exp / self.budget * 100
            self.budget_lbl_sub.text = (f"Потрачено за месяц: {rub(m_exp)} "
                                        f"из {rub(self.budget)}")
            if left >= 0:
                self.budget_lbl_big.text = f"[b]Осталось: {rub(left)}[/b]"
            else:
                self.budget_lbl_big.text = f"[b]Перерасход: {rub(-left)}[/b]"
            bar_col = PAL["green"] if pct < 80 else PAL["danger"]
            self.budget_lbl_big.color = bar_col
            self.budget_bar.set_pct(pct)
            self.budget_bar.set_color(bar_col)
        else:
            self.budget_lbl_big.text = "[b]Бюджет не задан[/b]"
            self.budget_lbl_big.color = PAL["text"]
            self.budget_lbl_sub.text = "Нажмите, чтобы задать лимит на месяц"
            self.budget_bar.set_pct(0)

        inc, exp = self.totals(self.records)
        self.lbl_balance.text = f"[b]{rub(inc - exp)}[/b]"
        today = now.strftime("%Y-%m-%d")
        t_exp = sum(r["amount"] for r in self.records
                    if r["kind"] == "expense" and r["date"] == today)
        self.lbl_today.text = (f"Расходов сегодня: {rub(t_exp)}   "
                               f"Записей: {len(self.records)}")

        self._reminders = self.reminder_list()
        self.home_grid.clear_widgets()
        if not self.records:
            self.home_grid.add_widget(empty_note(
                "Пока тихо.\nНажмите «+ Расход» или «+ Доход».\nКаждая запись — шаг к цели."))
            return
        visible = self.records[-12:]
        offset = len(self.records) - len(visible)
        for i, r in enumerate(reversed(visible)):
            idx = len(self.records) - 1 - i
            sign = "−" if r["kind"] == "expense" else "+"
            col = PAL["danger"] if r["kind"] == "expense" else PAL["green"]
            cmt = f' · {r["comment"]}' if r.get("comment") else ""
            card = Card(radius=dp(16), padding=dp(12), spacing=dp(2),
                        orientation="vertical",
                        size_hint=(1, None), height=dp(78))
            row = BoxLayout(size_hint=(1, None), height=dp(34), spacing=dp(4))
            row.add_widget(make_label(f"[b]{sign}{rub(r['amount'])}[/b]",
                                      dp(17), col, size_hint=(0.42, 1)))
            row.add_widget(make_label(r["category"], dp(14), PAL["muted"],
                                      halign="right", size_hint=(0.44, 1)))
            row.add_widget(make_cross(lambda ii=idx: self.confirm_delete(ii),
                                      bg=PAL["chip"], color=PAL["danger"],
                                      size=dp(40), size_hint=(None, 1)))
            card.add_widget(row)
            card.add_widget(make_label(f"{fmt_when(r)}{cmt}",
                                       dp(13), PAL["muted"]))
            self.home_grid.add_widget(card)
        self.refresh_home_banner()

    def refresh_home_banner(self):
        """Карточка «пора отложить» на главном экране."""
        if getattr(self, "remind_holder", None) is None:
            return
        self.remind_holder.clear_widgets()
        dues = getattr(self, "_reminders", [])
        if not dues:
            self.remind_holder.height = 0
            return
        gname, amount = dues[0]
        more = f" (и ещё {len(dues) - 1})" if len(dues) > 1 else ""
        card = Card(bg=PAL["soft"], radius=dp(18), padding=dp(12), spacing=dp(4),
                    orientation="vertical", size_hint=(1, None), height=dp(94))
        card.add_widget(make_label("[b]Пора отложить[/b]", dp(15)))
        card.add_widget(make_label(f"По графику сегодня: {rub(amount)} на «{gname}»{more}",
                                   dp(13), PAL["muted"]))
        card.add_widget(make_btn("Открыть цели", lambda: self.go("goals"),
                                 PAL["accent"], dp(38), color=PAL["accentfg"],
                                 font_size=dp(13)))
        self.remind_holder.add_widget(card)
        self.remind_holder.height = dp(94)

    def confirm_delete(self, idx):
        if not (0 <= idx < len(self.records)):
            return
        r = self.records[idx]
        view = ModalView(size_hint=(0.85, None), height=dp(170),
                         background="", background_color=(0, 0, 0, 0),
                         auto_dismiss=True)
        card = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                    orientation="vertical")
        card.add_widget(make_label("[b]Удалить запись?[/b]", dp(17),
                                   PAL["text"], halign="center"))
        card.add_widget(make_label(f"{fmt_when(r)} · {r['category']} · {rub(r['amount'])}",
                                   dp(14), PAL["muted"], halign="center"))
        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        row.add_widget(make_btn("Оставить", view.dismiss, PAL["chip"], dp(44),
                                color=PAL["text"], font_size=dp(15)))
        row.add_widget(make_btn("Удалить", lambda: self.do_delete(idx, view),
                                PAL["danger"], dp(44), font_size=dp(15)))
        card.add_widget(row)
        view.add_widget(card)
        self.open_view(view)

    def do_delete(self, idx, view):
        if 0 <= idx < len(self.records):
            self.records.pop(idx)
            self.save()
            self.refresh_home()
        view.dismiss()

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
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))

        top = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(10))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                PAL["chip"], dp(52), size_hint=(None, 1),
                                color=PAL["text"],
                                size=(dp(52), dp(52))))
        self.add_title = make_label("[b]Новый расход[/b]", dp(22))
        top.add_widget(self.add_title)
        root.add_widget(top)

        self.amount_input = make_input(font_size=dp(26), multiline=False,
                                       input_filter="float",
                                       size_hint=(1, None), height=dp(60),
                                       hint_text="Сумма")
        root.add_widget(self.amount_input)

        qrow = BoxLayout(size_hint=(1, None), height=dp(42), spacing=dp(8))
        for t, v in [("+100", 100), ("+500", 500), ("+1000", 1000), ("Сброс", None)]:
            qrow.add_widget(make_btn(t, lambda vv=v: self.quick_sum(vv),
                                     PAL["chip"], dp(42), color=PAL["text"],
                                     font_size=dp(14)))
        root.add_widget(qrow)

        root.add_widget(make_label("Категория", dp(14), PAL["muted"]))
        self.cats_grid = GridLayout(cols=4, spacing=dp(8), size_hint=(1, None))
        self.cats_grid.bind(minimum_height=self.cats_grid.setter("height"))
        root.add_widget(self.cats_grid)
        self.btn_own_cat = make_btn("+ Своя категория", self.add_cat_modal,
                                    PAL["chip"], dp(44), color=PAL["muted"],
                                    font_size=dp(14))
        root.add_widget(self.btn_own_cat)

        self.comment_input = make_input(font_size=dp(17), multiline=False,
                                        size_hint=(1, None), height=dp(48),
                                        hint_text="Комментарий (можно пусто)")
        root.add_widget(self.comment_input)

        root.add_widget(make_btn("Сохранить", self.save_record,
                                 color=PAL["accentfg"]))
        self.add_msg = make_label("", dp(15), PAL["danger"])
        root.add_widget(self.add_msg)

        scr.add_widget(root)
        return scr

    def quick_sum(self, add):
        if add is None:
            self.amount_input.text = ""
            return
        raw = self.amount_input.text.strip().replace(",", ".").replace(" ", "")
        try:
            cur = float(raw) if raw else 0.0
        except ValueError:
            cur = 0.0
        self.amount_input.text = f"{cur + add:g}"

    def rebuild_cats(self):
        cats = all_cats(self.pending_kind, self.custom)
        if self.sel_cat not in cats:
            self.sel_cat = cats[-1]
        self.cats_grid.clear_widgets()
        for c in cats:
            b = SoftButton(text=c, font_size=dp(15), bg=PAL["chsel"],
                           radius=dp(22),
                           color=(PAL["chselfg"] if c == self.sel_cat
                                  else PAL["text"]),
                           size_hint=(1, None), height=dp(44))
            b.bind(on_release=lambda inst, cat=c: self.pick_cat(cat))
            self.cats_grid.add_widget(b)

    def add_cat_modal(self):
        view = ModalView(size_hint=(0.85, None), height=dp(170),
                         background="", background_color=(0, 0, 0, 0),
                         auto_dismiss=True)
        card = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                    orientation="vertical")
        card.add_widget(make_label("[b]Новая категория[/b]", dp(17),
                                   halign="center"))
        ti = make_input(font_size=dp(16), multiline=False,
                        size_hint=(1, None), height=dp(46),
                        hint_text="Название категории")
        card.add_widget(ti)
        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        row.add_widget(make_btn("Отмена", view.dismiss, PAL["chip"], dp(44),
                                color=PAL["text"], font_size=dp(15)))
        row.add_widget(make_btn("Добавить", lambda: self._add_cat(view, ti),
                                PAL["green"], dp(44), font_size=dp(15)))
        card.add_widget(row)
        view.add_widget(card)
        self.open_view(view)

    def _add_cat(self, view, ti):
        name = ti.text.strip()
        if not name:
            view.dismiss()
            return
        if name not in self.custom[self.pending_kind]:
            self.custom[self.pending_kind].append(name)
            self.save()
        self.sel_cat = name
        view.dismiss()
        self.rebuild_cats()

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
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(10))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                PAL["chip"], dp(52), size_hint=(None, 1),
                                color=PAL["text"],
                                size=(dp(52), dp(52))))
        top.add_widget(make_label("[b]Отчёты[/b]", dp(22)))
        root.add_widget(top)

        self.rep_days = 7
        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.rep_btns = {}
        for t, d in [("Сегодня", 1), ("Неделя", 7), ("Месяц", 31), ("Всё", None)]:
            b = make_btn(t, lambda dd=d: self.show_report(dd),
                         PAL["chip"], dp(44), color=PAL["text"],
                         font_size=dp(14))
            self.rep_btns[d] = b
            row.add_widget(b)
        root.add_widget(row)

        self.report_scroll, self.report_grid = scroll_column()
        root.add_widget(self.report_scroll)
        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.show_report(7))
        return scr

    def show_report(self, days):
        self.rep_days = days
        for d, b in getattr(self, "rep_btns", {}).items():
            if d == days:
                b._bg = PAL["chsel"]
                b._col.rgba = PAL["chsel"]
                b.color = PAL["chselfg"]
            else:
                b._bg = PAL["chip"]
                b._col.rgba = PAL["chip"]
                b.color = PAL["text"]
        recs = self.period_records(days)
        title = {1: "Сегодня", 7: "За неделю", 31: "За месяц",
                 None: "За всё время"}[days]
        self.report_grid.clear_widgets()
        if not recs:
            self.report_grid.add_widget(empty_note(f"{title}\nЗаписей нет."))
            return
        inc, exp = self.totals(recs)

        head = Card(radius=dp(20), padding=dp(16), spacing=dp(6),
                    orientation="vertical", size_hint=(1, None), height=dp(176))
        head.add_widget(make_label(f"[b]{title}[/b]", dp(20)))
        for name, val, col in [("Доходы", inc, PAL["green"]),
                               ("Расходы", exp, PAL["danger"]),
                               ("Остаток", inc - exp, PAL["text"])]:
            row = BoxLayout(size_hint=(1, None), height=dp(30))
            row.add_widget(make_label(name, dp(15), PAL["muted"],
                                      size_hint=(0.5, 1)))
            row.add_widget(make_label(rub(val), dp(16), col, halign="right",
                                      size_hint=(0.5, 1)))
            head.add_widget(row)
        self.report_grid.add_widget(head)

        by_cat = {}
        for r in recs:
            if r["kind"] == "expense":
                by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]
        if by_cat:
            self.report_grid.add_widget(make_label("Куда уходило", dp(15),
                                                   PAL["muted"]))
            mx = max(by_cat.values())
            for cat, s in sorted(by_cat.items(), key=lambda x: -x[1]):
                card = Card(radius=dp(16), padding=dp(12), spacing=dp(6),
                            orientation="vertical",
                            size_hint=(1, None), height=dp(76))
                top = BoxLayout(size_hint=(1, None), height=dp(26))
                top.add_widget(make_label(cat, dp(15), size_hint=(0.6, 1)))
                top.add_widget(make_label(rub(s), dp(15), PAL["muted"],
                                          halign="right", size_hint=(0.4, 1)))
                card.add_widget(top)
                card.add_widget(GoalBar(s / mx * 100, color=PAL["danger"],
                                        size_hint=(1, None), height=dp(10)))
                self.report_grid.add_widget(card)

    # ---------- ЦЕЛИ ----------
    def make_goals(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(10))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                PAL["chip"], dp(52), size_hint=(None, 1),
                                color=PAL["text"],
                                size=(dp(52), dp(52))))
        top.add_widget(make_label("[b]Цели[/b]", dp(22)))
        root.add_widget(top)

        self.goals_scroll, self.goals_grid = scroll_column()
        root.add_widget(self.goals_scroll)

        bottom = Card(radius=dp(20), padding=dp(14), spacing=dp(10),
                      orientation="vertical", size_hint=(1, None),
                      height=dp(230))
        bottom.add_widget(make_label("Новая цель", dp(14), PAL["muted"]))
        self.goal_name = make_input(font_size=dp(17), multiline=False,
                                    size_hint=(1, None), height=dp(46),
                                    hint_text="Название (например, Отпуск)")
        self.goal_target = make_input(font_size=dp(17), multiline=False,
                                      input_filter="float",
                                      size_hint=(1, None), height=dp(46),
                                      hint_text="Нужная сумма")
        bottom.add_widget(self.goal_name)
        bottom.add_widget(self.goal_target)
        bottom.add_widget(make_btn("Создать цель", self.create_goal,
                                   PAL["green"], dp(48)))
        root.add_widget(bottom)

        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.refresh_goals())
        return scr

    def goal_saved(self, gname):
        return sum(r["amount"] for r in self.records
                   if r["kind"] == "income"
                   and r.get("comment") == f"цель:{gname}")

    def refresh_goals(self):
        self.goals_grid.clear_widgets()
        if not self.goals:
            self.goals_grid.add_widget(empty_note(
                "Целей пока нет.\nСоздайте первую внизу — и откладывайте понемногу.",
                height=dp(92)))
            return
        for gname, g in self.goals.items():
            saved = self.goal_saved(gname)
            pct = min(100, saved / g["target"] * 100) if g["target"] else 0
            plan = g.get("plan") or {}
            due_now = any(d[0] == gname
                          for d in getattr(self, "_reminders", []))

            card = Card(radius=dp(18), padding=dp(14), spacing=dp(10),
                        orientation="vertical",
                        size_hint=(1, None),
                        height=dp(196) + (dp(76) if plan else dp(46))
                        + (dp(20) if plan and due_now else 0))
            head = BoxLayout(size_hint=(1, None), height=dp(38))
            head.add_widget(make_label(f"[b]{gname}[/b]", dp(20),
                                       size_hint=(0.78, 1)))
            head.add_widget(make_cross(lambda gn=gname: self.del_goal(gn),
                                       bg=PAL["soft"], color=PAL["muted"],
                                       size=dp(36)))
            card.add_widget(head)

            info = BoxLayout(size_hint=(1, None), height=dp(26))
            info.add_widget(make_label(f"{rub(saved)} из {rub(g['target'])}",
                                       dp(14), PAL["muted"],
                                       size_hint=(0.62, 1)))
            info.add_widget(make_label(f"[b]{pct:.0f}%[/b]", dp(16),
                                       PAL["green"], halign="right",
                                       size_hint=(0.38, 1)))
            card.add_widget(info)
            card.add_widget(GoalBar(pct, size_hint=(1, None), height=dp(12)))

            fund_row = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(8))
            ti = make_input(font_size=dp(16), multiline=False,
                            input_filter="float", size_hint=(0.55, None),
                            height=dp(48), hint_text="Сколько отложить")
            fund_row.add_widget(ti)
            fund_row.add_widget(make_btn("Отложить",
                                         lambda gn=gname, t=ti: self.fund_goal(gn, t),
                                         PAL["green"], dp(48),
                                         size_hint=(0.45, None),
                                         font_size=dp(15)))
            card.add_widget(fund_row)

            if plan:
                try:
                    end = datetime.strptime(plan["date"], "%Y-%m-%d")
                    end_s = end.strftime("%d.%m.%Y")
                except (ValueError, TypeError):
                    end_s = "?"
                words = {"day": "каждый день", "week": "каждую неделю",
                         "month": "каждый месяц"}
                card.add_widget(make_label(
                    f"План: по {rub(plan['amount'])} {words.get(plan.get('freq'), '')} до {end_s}",
                    dp(13), PAL["muted"], size_hint=(1, None), height=dp(18)))
                if due_now:
                    card.add_widget(make_label(
                        f"Сегодня по плану: {rub(plan['amount'])}",
                        dp(14), PAL["danger"], size_hint=(1, None),
                        height=dp(20)))
                prow = BoxLayout(size_hint=(1, None), height=dp(38), spacing=dp(8))
                prow.add_widget(make_btn("Изменить график",
                                         lambda gn=gname: self.edit_plan(gn),
                                         PAL["chip"], dp(38), color=PAL["text"],
                                         font_size=dp(13),
                                         size_hint=(0.6, None)))
                prow.add_widget(make_btn("Убрать график",
                                         lambda gn=gname: self._del_plan(gn),
                                         PAL["chip"], dp(38), color=PAL["muted"],
                                         font_size=dp(13),
                                         size_hint=(0.4, None)))
                card.add_widget(prow)
            else:
                card.add_widget(make_btn("График накоплений",
                                         lambda gn=gname: self.edit_plan(gn),
                                         PAL["chip"], dp(40), color=PAL["text"],
                                         font_size=dp(14)))
            self.goals_grid.add_widget(card)

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

    # ---------- ГРАФИК НАКОПЛЕНИЙ ----------
    def edit_plan(self, gname):
        g = self.goals.get(gname)
        if not g:
            return
        plan = g.get("plan") or {}
        view = ModalView(size_hint=(0.92, None), height=dp(398),
                         background="", background_color=(0, 0, 0, 0),
                         auto_dismiss=True)
        card = Card(radius=dp(20), padding=dp(16), spacing=dp(8),
                    orientation="vertical")
        card.add_widget(make_label(f"[b]График: {gname}[/b]", dp(17),
                                   halign="center"))
        saved = self.goal_saved(gname)
        card.add_widget(make_label(f"Накоплено {rub(saved)} из {rub(g['target'])}",
                                   dp(13), PAL["muted"], halign="center"))
        ti_date = make_input(font_size=dp(16), multiline=False,
                             size_hint=(1, None), height=dp(44),
                             hint_text="К какой дате: 01.01.2027")
        if plan.get("date"):
            try:
                ti_date.text = datetime.strptime(
                    plan["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
            except ValueError:
                pass
        card.add_widget(ti_date)

        self._plan_freq = plan.get("freq", "month")
        frow = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(6))
        self._freq_btns = {}
        for f, t in (("day", "Каждый день"), ("week", "Каждую неделю"),
                     ("month", "Каждый месяц")):
            b = SoftButton(text=t, font_size=dp(12), bg=PAL["chip"],
                           radius=dp(20), color=PAL["text"],
                           size_hint=(1, None), height=dp(40))
            b.bind(on_release=lambda inst, ff=f: self._pick_freq(ff))
            self._freq_btns[f] = b
            frow.add_widget(b)
        card.add_widget(frow)

        ti_amt = make_input(font_size=dp(16), multiline=False,
                            input_filter="float", size_hint=(1, None),
                            height=dp(44),
                            hint_text="Сколько откладывать за раз, руб.")
        card.add_widget(ti_amt)
        msg = make_label("", dp(13), PAL["danger"], halign="center")
        card.add_widget(msg)

        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        if plan:
            row.add_widget(make_btn("Убрать график",
                                    lambda: self._del_plan(gname, view),
                                    PAL["chip"], dp(44), color=PAL["text"],
                                    font_size=dp(13), size_hint=(0.45, None)))
        row.add_widget(make_btn("Сохранить",
                                lambda: self._save_plan(gname, view, ti_date,
                                                        ti_amt, msg),
                                PAL["accent"], dp(44), color=PAL["accentfg"],
                                font_size=dp(15), size_hint=(0.55, None)))
        card.add_widget(row)
        view.add_widget(card)
        self.open_view(view)
        self._pick_freq(self._plan_freq, prefill=(ti_amt, g, plan, saved))

    def _pick_freq(self, freq, prefill=None):
        self._plan_freq = freq
        for f, b in self._freq_btns.items():
            sel = (f == freq)
            b._bg = PAL["chsel"] if sel else PAL["chip"]
            b._col.rgba = b._bg
            b.color = PAL["chselfg"] if sel else PAL["text"]
        if prefill is None:
            return
        ti_amt, g, plan, saved = prefill
        amt = self.suggest_amount(g, saved, freq, plan)
        if amt:
            ti_amt.text = f"{amt:g}"

    def suggest_amount(self, g, saved, freq, plan):
        """Сколько откладывать за раз, чтобы успеть к дате."""
        remaining = max(0.0, g["target"] - saved)
        if remaining <= 0:
            return None
        end = None
        if plan.get("date"):
            try:
                end = datetime.strptime(plan["date"], "%Y-%m-%d").date()
            except ValueError:
                end = None
        if not end:
            return None
        days = (end - datetime.now().date()).days
        if days <= 0:
            return round(remaining)
        if freq == "day":
            n = days
        elif freq == "week":
            n = max(1, days // 7)
        else:
            n = max(1, round(days / 30.44))
        raw = remaining / n
        step = 10 if raw < 1000 else 50 if raw < 5000 else 100
        return int(math.ceil(raw / step) * step)

    def _save_plan(self, gname, view, ti_date, ti_amt, msg):
        raw = ti_date.text.strip()
        try:
            end = datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            msg.text = "Дата в формате ДД.ММ.ГГГГ, например 01.01.2027."
            return
        if end <= datetime.now().date():
            msg.text = "Дата должна быть в будущем."
            return
        rawa = ti_amt.text.strip().replace(",", ".").replace(" ", "")
        try:
            amount = round(float(rawa), 2)
        except ValueError:
            msg.text = "Введите сумму числом."
            return
        if amount <= 0:
            msg.text = "Сумма должна быть больше нуля."
            return
        g = self.goals[gname]
        old = g.get("plan") or {}
        g["plan"] = {"freq": self._plan_freq,
                     "date": end.strftime("%Y-%m-%d"),
                     "amount": amount,
                     "start": old.get("start") or datetime.now().strftime("%Y-%m-%d")}
        self.save()
        view.dismiss()
        self.refresh_goals()
        self.check_reminders()

    def _del_plan(self, gname, view):
        g = self.goals.get(gname)
        if g:
            g.pop("plan", None)
            self.save()
        view.dismiss()
        self.refresh_goals()
        self.check_reminders()

    # ---------- КОПИЯ ДАННЫХ ----------
    def make_backup(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(10))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                PAL["chip"], dp(52), size_hint=(None, 1),
                                color=PAL["text"],
                                size=(dp(52), dp(52))))
        top.add_widget(make_label("[b]Копия данных[/b]", dp(22)))
        root.add_widget(top)

        card1 = Card(radius=dp(20), padding=dp(14), spacing=dp(8),
                     orientation="vertical", size_hint=(1, None),
                     height=dp(170))
        card1.add_widget(make_label("Сохранить копию", dp(15), PAL["muted"]))
        card1
        card1.add_widget(make_label("Сохранить копию", dp(15), PAL["muted"]))
        card1.add_widget(make_label(
            "Вся история — одним текстом. Отправьте его «в сохранённые сообщения» "
            "или в заметки — так копия не потеряется.",
            dp(13), PAL["muted"]))
        card1.add_widget(make_btn("Отправить копию", self.send_backup,
                                  PAL["green"], dp(46)))
        root.add_widget(card1)

        card2 = Card(radius=dp(20), padding=dp(14), spacing=dp(8),
                     orientation="vertical", size_hint=(1, None),
                     height=dp(230))
        card2.add_widget(make_label("Восстановить из копии", dp(15), PAL["muted"]))
        self.backup_input = make_input(font_size=dp(13), multiline=True,
                                       size_hint=(1, None), height=dp(88),
                                       hint_text="Вставьте текст копии сюда")
        card2.add_widget(self.backup_input)
        card2.add_widget(make_btn("Восстановить", self.restore_backup,
                                  PAL["accent"], dp(46)))
        self.backup_msg = make_label("", dp(14), PAL["accent"])
        card2.add_widget(self.backup_msg)
        root.add_widget(card2)

        scr.add_widget(root)
        return scr

    def send_backup(self):
        text = json.dumps({"records": self.records, "goals": self.goals,
                           "theme": self.theme, "budget": self.budget,
                           "custom_cats": self.custom},
                          ensure_ascii=False, indent=2)
        ok = False
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            JString = autoclass("java.lang.String")
            Activity = autoclass("org.kivy.android.PythonActivity")
            i = Intent()
            i.setAction(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_TEXT, JString(text))
            chooser = Intent.createChooser(i, JString("Копия дневника"))
            Activity.mActivity.startActivity(chooser)
            ok = True
        except Exception:
            pass
        if ok:
            self.backup_msg.text = ("Открыл выбор приложений — сохраните копию "
                                    "в «Файлы», «Диск» или себе в мессенджер.")
        else:
            try:
                path = (self.data_file() +
                        datetime.now().strftime(".backup-%Y%m%d-%H%M%S"))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.backup_msg.text = "Копия сохранена: " + path
            except Exception:
                self.backup_msg.text = "Не получилось сохранить копию."

    def restore_backup(self):
        raw = self.backup_input.text.strip()
        if not raw:
            self.backup_msg.text = "Вставьте текст копии."
            return
        try:
            d = json.loads(raw)
            records = d.get("records", [])
            goals = d.get("goals", {})
            if not isinstance(records, list) or not isinstance(goals, dict):
                raise ValueError
            for r in records:
                if not isinstance(r, dict) or "amount" not in r or "date" not in r:
                    raise ValueError
        except Exception:
            self.backup_msg.text = "Не похоже на копию дневника. Проверьте текст."
            return
        self.records = records
        self.goals = goals
        if "budget" in d:
            self.budget = d["budget"]
        custom = d.get("custom_cats") or {}
        self.custom = {"expense": custom.get("expense", []),
                       "income": custom.get("income", [])}
        self.save()
        self.refresh_home()
        self.backup_msg.text = (f"Восстановлено! Записей: {len(records)}, "
                                f"целей: {len(goals)}.")


if __name__ == "__main__":
    import traceback as _tb
    try:
        DiaryApp().run()
    except Exception:
        _text = _tb.format_exc()
        try:
            import os as _os
            with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                    "crash_log.txt"), "w", encoding="utf-8") as _f:
                _f.write(_text)
        except Exception:
            pass
        try:
            from kivy.app import App as _ErrApp
            from kivy.uix.label import Label as _ErrLabel
            from kivy.uix.scrollview import ScrollView as _ErrScroll
            from kivy.uix.boxlayout import BoxLayout as _ErrBox
            from kivy.core.window import Window as _ErrWin

            class _CrashWindow(_ErrApp):
                def build(self):
                    self.title = "Ошибка запуска"
                    _ErrWin.clearcolor = (0.17, 0.15, 0.13, 1)
                    root = _ErrBox(orientation="vertical", padding=12, spacing=8)
                    head = _ErrLabel(
                        text="Ошибка запуска. Пришлите скриншот этого текста Алисе.",
                        color=(1, 0.93, 0.7, 1), font_size="16sp",
                        size_hint=(1, None), height=48, halign="center")
                    head.bind(size=lambda w, s: setattr(w, "text_size", s))
                    root.add_widget(head)
                    sv = _ErrScroll()
                    body = _ErrLabel(text=_text, color=(1, 1, 1, 1), font_size="13sp",
                                     size_hint=(1, None), halign="left")
                    body.bind(width=lambda w, s: setattr(w, "text_size", (w.width, None)))
                    body.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
                    sv.add_widget(body)
                    root.add_widget(sv)
                    return root

            _CrashWindow().run()
        except Exception:
            pass
