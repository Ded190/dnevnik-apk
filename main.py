# -*- coding: utf-8 -*-
"""
Дневник расходов — Android-приложение на Kivy.
Сборка: buildozer android debug (см. buildozer.spec и .github/workflows/build.yml)
"""
import hashlib
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
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.uix.floatlayout import FloatLayout
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.utils import get_color_from_hex

# ---- палитры: светлая (крем) и тёмная (кофе) ----
THEME_LIGHT = dict(bg="#FBF7F1", card="#FFFFFF", accent="#E9734F",
                   green="#5FA46B", text="#3D3229", muted="#9A8B7A",
                   soft="#FBE9E0", softg="#E6F0E7", chip="#F3E9DE",
                   chsel="#E9734F", track="#F1E7DC", field="#F7F1EA")
THEME_DARK = dict(bg="#2A211A", card="#3A2E24", accent="#E8835F",
                  green="#7CB88A", text="#F2E9DF", muted="#B4A390",
                  soft="#463528", softg="#37432F", chip="#4A3B2F",
                  chsel="#E8835F", track="#4A3B2F", field="#463829")

PAL = {k: get_color_from_hex(v) for k, v in THEME_LIGHT.items()}

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
        base = f"{d.day} {MONTHS[d.month - 1]}"
        t = r.get("time", "")
        return f"{base}, {t}" if t else base
    except (ValueError, TypeError, KeyError):
        return str(r.get("date", ""))


class Card(BoxLayout):
    """Карточка со скруглёнными углами."""
    def __init__(self, bg=None, radius=dp(20), **kw):
        super().__init__(**kw)
        bg = bg if bg is not None else PAL["card"]
        with self.canvas.before:
            Color(*bg)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size,
                                        radius=[radius])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size


class SoftButton(Button):
    """Кнопка-пилюля со скруглёнными углами и мягким нажатием."""
    def __init__(self, bg=None, radius=dp(24), **kw):
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        super().__init__(**kw)
        self.background_color = (0, 0, 0, 0)   # рисуем сами
        self._bg = bg if bg is not None else PAL["accent"]
        self._radius = radius
        with self.canvas.before:
            self._col = Color(*self._bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[radius])
        self.bind(pos=self._upd, size=self._upd)
        self.bind(on_press=self._press, on_release=self._release)

    def _upd(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        r = self._radius
        if self.height:
            r = min(r, self.height / 2.0)
        self._rect.radius = [r]

    def _press(self, *a):
        self._col.rgba = blend(self._bg)

    def _release(self, *a):
        self._col.rgba = self._bg


class CrossButton(SoftButton):
    """Кнопка-крестик: крестик нарисован линиями, а не символом шрифта."""
    def __init__(self, cb=None, cross_color=None, **kw):
        self._cross = (cross_color if cross_color is not None else PAL["muted"])
        kw.setdefault("text", "")
        super().__init__(**kw)
        with self.canvas.after:
            Color(*self._cross)
            self._l1 = Line(points=[], width=dp(2), cap="round")
            self._l2 = Line(points=[], width=dp(2), cap="round")
        self.bind(pos=self._upd_cross, size=self._upd_cross)
        if cb is not None:
            self.bind(on_release=lambda inst: cb())

    def _upd_cross(self, *a):
        cx, cy = self.center_x, self.center_y
        r = min(self.width, self.height) * 0.3
        self._l1.points = (cx - r, cy - r, cx + r, cy + r)
        self._l2.points = (cx - r, cy + r, cx + r, cy - r)


def make_cross(cb, bg=None, color=None, size=dp(40), **kw):
    kw.setdefault("size_hint", (None, None))
    kw.setdefault("size", (size, size))
    return CrossButton(cb=cb,
                       bg=bg if bg is not None else PAL["chip"],
                       cross_color=color if color is not None else PAL["muted"],
                       radius=dp(size / 2.0), **kw)


class GoalBar(Widget):
    """Прогресс-полоса цели."""
    def __init__(self, pct=0, color=None, **kw):
        super().__init__(**kw)
        self._pct = max(0, min(100, pct))
        self._color = color if color is not None else PAL["green"]
        with self.canvas:
            Color(*PAL["track"])
            self._track = RoundedRectangle(pos=self.pos, size=self.size,
                                           radius=[dp(10)])
            self._fillcol = Color(*self._color)
            self._fill = RoundedRectangle(pos=self.pos, size=(0, 0),
                                          radius=[dp(10)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._track.pos = self.pos
        self._track.size = self.size
        r = min(dp(10), self.height / 2.0 if self.height else dp(10))
        self._track.radius = [r]
        w = self.width * self._pct / 100.0
        if w < dp(2):
            self._fill.size = (0, 0)
        else:
            self._fill.pos = self.pos
            self._fill.size = (w, self.height)
            self._fill.radius = [r]

    def set_pct(self, pct):
        self._pct = max(0, min(100, pct))
        self._upd()

    def set_color(self, color):
        self._color = color
        self._fillcol.rgba = color


def make_label(text, size=dp(16), color=None, bold=False, halign="left", **kw):
    lbl = Label(text=text, font_size=size,
                color=color if color is not None else PAL["text"],
                halign=halign, valign="middle", markup=True, **kw)
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    return lbl


def make_btn(text, cb, bg=None, height=dp(52), size_hint=(1, None),
             color=(1, 1, 1, 1), font_size=dp(17), size=None):
    kw = {}
    if size is not None:
        kw["size"] = size
    b = SoftButton(text=text, background_color=(0, 0, 0, 0), bg=bg,
                   radius=dp(height / 2.0), font_size=font_size, color=color,
                   size_hint=size_hint, height=height, **kw)
    b.bind(on_release=lambda inst: cb())
    return b


def make_input(**kw):
    kw.setdefault("background_color", PAL["field"])
    kw.setdefault("foreground_color", PAL["text"])
    kw.setdefault("hint_text_color", PAL["muted"])
    kw.setdefault("cursor_color", PAL["accent"])
    return TextInput(**kw)


def spacer(h=dp(10)):
    return BoxLayout(size_hint=(1, None), height=h)


def scroll_column():
    grid = GridLayout(cols=1, spacing=dp(10), padding=[dp(4), dp(4)],
                      size_hint=(1, None))
    grid.bind(minimum_height=grid.setter("height"))
    sv = ScrollView()
    sv.add_widget(grid)
    return sv, grid


def empty_note(text, height=dp(84)):
    card = Card(radius=dp(20), padding=dp(16),
                size_hint=(1, None), height=height)
    card.add_widget(make_label(text, dp(15), PAL["muted"], halign="center",
                               size_hint=(1, 1)))
    return card


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
        self.theme = d.get("theme", "light")
        self.budget = d.get("budget", None)
        custom = d.get("custom_cats", {}) or {}
        self.custom = {"expense": custom.get("expense", []),
                       "income": custom.get("income", [])}
        self.pin_hash = d.get("pin_hash", "")

    def save(self):
        path = self.data_file()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"records": self.records, "goals": self.goals,
                       "theme": self.theme, "budget": self.budget,
                       "custom_cats": self.custom, "pin_hash": self.pin_hash},
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
        self.load()
        if self.theme == "dark":
            global PAL
            PAL.clear()
            PAL.update({k: get_color_from_hex(v) for k, v in THEME_DARK.items()})
        Window.clearcolor = PAL["bg"]
        Window.softinput_mode = "below_target"
        self.pending_kind = "expense"
        self.sel_cat = CATS_EXPENSE[-1]
        self._must_lock = False

        sm = ScreenManager()
        self.sm = sm
        self.rebuild_ui()
        return sm

    def rebuild_ui(self):
        """Пересобрать экраны (при смене темы)."""
        self.sm.clear_widgets()
        self.home = self.make_home("home")
        self.add_scr = self.make_add("add")
        self.rep_scr = self.make_report("report")
        self.goals_scr = self.make_goals("goals")
        self.backup_scr = self.make_backup("backup")
        self.settings_scr = self.make_settings("settings")
        for s in (self.home, self.add_scr, self.rep_scr,
                  self.goals_scr, self.backup_scr, self.settings_scr):
            self.sm.add_widget(s)
        self.sm.current = "home"
        self.refresh_home()

    def switch_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        global PAL
        pal = THEME_DARK if self.theme == "dark" else THEME_LIGHT
        PAL.clear()
        PAL.update({k: get_color_from_hex(v) for k, v in pal.items()})
        self.save()
        Window.clearcolor = PAL["bg"]
        self.rebuild_ui()

    def go(self, name):
        self.root.current = name

    # ---------- ПИН-КОД И БЛОКИРОВКА ----------
    def on_start(self):
        if self.pin_hash:
            self.show_lock()

    def on_pause(self):
        self._must_lock = bool(self.pin_hash)
        return True

    def on_resume(self):
        if self._must_lock:
            self._must_lock = False
            self.show_lock()

    def pin_ok(self, pin):
        return hashlib.sha256(pin.encode("utf-8")).hexdigest() == self.pin_hash

    def pin_view(self, title, on_done, auto_dismiss=True):
        view = ModalView(size_hint=(0.85, None), height=dp(210),
                         background="", background_color=(0, 0, 0, 0),
                         auto_dismiss=auto_dismiss)
        card = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                    orientation="vertical")
        card.add_widget(make_label(f"[b]{title}[/b]", dp(17), halign="center"))
        ti = make_input(password=True, multiline=False, input_filter="int",
                        size_hint=(1, None), height=dp(48),
                        hint_text="Цифры пин-кода")
        msg = make_label("", dp(14), PAL["accent"], halign="center")
        card.add_widget(ti)
        card.add_widget(msg)
        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        if auto_dismiss:
            row.add_widget(make_btn("Отмена", view.dismiss, PAL["chip"],
                                    dp(44), color=PAL["text"], font_size=dp(15)))
        row.add_widget(make_btn("ОК",
                                lambda: on_done(view, ti.text.strip(), msg),
                                PAL["accent"], dp(44), font_size=dp(15)))
        card.add_widget(row)
        view.add_widget(card)
        view.open()

    def show_lock(self):
        self.pin_view("Введите пин-код", self._check_lock, auto_dismiss=False)

    def _check_lock(self, view, pin, msg):
        if self.pin_ok(pin):
            view.dismiss()
        else:
            msg.text = "Неверный пин-код."

    def set_pin(self):
        if self.pin_hash:
            self.pin_view("Введите текущий пин", self._pin_old_ok)
        else:
            self.pin_view("Придумайте пин-код", self._pin_new1)

    def _pin_old_ok(self, view, pin, msg):
        if self.pin_ok(pin):
            view.dismiss()
            self.pin_view("Новый пин-код", self._pin_new1)
        else:
            msg.text = "Неверный пин-код."

    def _pin_new1(self, view, pin, msg):
        if not pin:
            msg.text = "Введите цифры пин-кода."
            return
        self._newpin = pin
        view.dismiss()
        self.pin_view("Повторите пин-код", self._pin_new2)

    def _pin_new2(self, view, pin, msg):
        if pin == self._newpin:
            self.pin_hash = hashlib.sha256(pin.encode("utf-8")).hexdigest()
            self.save()
            view.dismiss()
            self.refresh_settings()
        else:
            msg.text = "Не совпало. Введите первый пин заново."

    def remove_pin(self):
        if self.pin_hash:
            self.pin_view("Отключить блокировку?\nВведите пин", self._pin_remove)

    def _pin_remove(self, view, pin, msg):
        if self.pin_ok(pin):
            self.pin_hash = ""
            self.save()
            view.dismiss()
            self.refresh_settings()
        else:
            msg.text = "Неверный пин-код."

    # ---------- БЮДЖЕТ НА МЕСЯЦ ----------
    def edit_budget(self):
        view = ModalView(size_hint=(0.85, None), height=dp(210),
                         background="", background_color=(0, 0, 0, 0),
                         auto_dismiss=True)
        card = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                    orientation="vertical")
        card.add_widget(make_label("[b]Бюджет на месяц[/b]", dp(17),
                                   halign="center"))
        card.add_widget(make_label("Сколько можно потратить за месяц",
                                   dp(13), PAL["muted"], halign="center"))
        ti = make_input(multiline=False, input_filter="float",
                        size_hint=(1, None), height=dp(48),
                        hint_text="Лимит, руб.")
        if self.budget:
            ti.text = f"{self.budget:g}"
        card.add_widget(ti)
        row1 = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        row1.add_widget(make_btn("Сохранить",
                                 lambda: self._save_budget(view, ti),
                                 PAL["accent"], dp(44), font_size=dp(15)))
        row1.add_widget(make_btn("Убрать лимит",
                                 lambda: self._del_budget(view),
                                 PAL["chip"], dp(44), color=PAL["text"],
                                 font_size=dp(15)))
        card.add_widget(row1)
        view.add_widget(card)
        view.open()

    def _save_budget(self, view, ti):
        raw = ti.text.strip().replace(",", ".").replace(" ", "")
        try:
            val = round(float(raw), 2)
        except ValueError:
            val = None
        self.budget = val if (val and val > 0) else None
        self.save()
        view.dismiss()
        self.refresh_home()

    def _del_budget(self, view):
        self.budget = None
        self.save()
        view.dismiss()
        self.refresh_home()

    # ---------- НАСТРОЙКИ ----------
    def make_settings(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(10))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                PAL["chip"], dp(52), size_hint=(None, 1),
                                color=PAL["text"]))
        top.add_widget(make_label("[b]Настройки[/b]", dp(22)))
        root.add_widget(top)

        c1 = Card(radius=dp(20), padding=dp(14), spacing=dp(10),
                  size_hint=(1, None), height=dp(150))
        c1.add_widget(make_label("[b]Тема оформления[/b]", dp(16)))
        self.btn_theme = make_btn("Тема: светлая", self.switch_theme,
                                  PAL["chip"], dp(46), color=PAL["text"],
                                  font_size=dp(15))
        c1.add_widget(self.btn_theme)
        root.add_widget(c1)

        c2 = Card(radius=dp(20), padding=dp(14), spacing=dp(10),
                  size_hint=(1, None), height=dp(160))
        c2.add_widget(make_label("[b]Блокировка приложения[/b]", dp(16)))
        self.pin_status = make_label("", dp(13), PAL["muted"])
        c2.add_widget(self.pin_status)
        prow = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.btn_pin_set = make_btn("Установить", self.set_pin, PAL["green"],
                                    dp(44), font_size=dp(15))
        prow.add_widget(self.btn_pin_set)
        prow.add_widget(make_btn("Убрать пин", self.remove_pin, PAL["chip"],
                                 dp(44), color=PAL["text"], font_size=dp(15)))
        c2.add_widget(prow)
        root.add_widget(c2)

        c3 = Card(radius=dp(20), padding=dp(14), spacing=dp(10),
                  size_hint=(1, None), height=dp(150))
        c3.add_widget(make_label("[b]Копия данных[/b]", dp(16)))
        c3.add_widget(make_label("Отправить всю историю одним текстом или "
                                 "восстановить из копии.", dp(13), PAL["muted"]))
        c3.add_widget(make_btn("Открыть", lambda: self.go("backup"),
                               PAL["accent"], dp(44), font_size=dp(15)))
        root.add_widget(c3)

        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.refresh_settings())
        return scr

    def refresh_settings(self):
        if getattr(self, "pin_status", None) is None:
            return
        self.pin_status.text = ("Включён: приложение спросит пин при запуске "
                                "и выходе из фона." if self.pin_hash
                                else "Не задан. Пин защищает дневник от "
                                     "посторонних глаз.")
        self.btn_pin_set.text = "Изменить" if self.pin_hash else "Установить"
        self.btn_theme.text = ("Тема: тёмная" if self.theme == "dark"
                               else "Тема: светлая")

    # ---------- ГЛАВНЫЙ ЭКРАН ----------
    def make_home(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        self.lbl_greet = make_label("", dp(14), PAL["muted"])
        root.add_widget(self.lbl_greet)

        card = Card(bg=PAL["soft"], radius=dp(24), padding=dp(18), spacing=dp(4),
                    size_hint=(1, None), height=dp(112))
        card.add_widget(make_label("Баланс", dp(13), PAL["muted"]))
        self.lbl_balance = make_label("", dp(30), PAL["text"])
        card.add_widget(self.lbl_balance)
        self.lbl_today = make_label("", dp(14), PAL["muted"])
        card.add_widget(self.lbl_today)
        root.add_widget(card)

        self.budget_holder = self.make_budget_card()
        root.add_widget(self.budget_holder)

        grid = GridLayout(cols=2, spacing=dp(10), size_hint=(1, None),
                          height=dp(54) * 2 + dp(10))
        grid.add_widget(make_btn("+ Расход", lambda: self.open_add("expense"),
                                 PAL["accent"], dp(54)))
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
                    spacing=dp(4), size_hint=(1, 1),
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
            bar_col = PAL["green"] if pct < 80 else PAL["accent"]
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
            col = PAL["accent"] if r["kind"] == "expense" else PAL["green"]
            cmt = f' · {r["comment"]}' if r.get("comment") else ""
            card = Card(radius=dp(16), padding=dp(12), spacing=dp(2),
                        size_hint=(1, None), height=dp(78))
            row = BoxLayout(size_hint=(1, None), height=dp(34), spacing=dp(4))
            row.add_widget(make_label(f"[b]{sign}{rub(r['amount'])}[/b]",
                                      dp(17), col, size_hint=(0.42, 1)))
            row.add_widget(make_label(r["category"], dp(14), PAL["muted"],
                                      halign="right", size_hint=(0.44, 1)))
            row.add_widget(make_cross(lambda ii=idx: self.confirm_delete(ii),
                                      bg=PAL["chip"], color=PAL["accent"],
                                      size=dp(40), size_hint=(None, 1)))
            card.add_widget(row)
            card.add_widget(make_label(f"{fmt_when(r)}{cmt}",
                                       dp(13), PAL["muted"]))
            self.home_grid.add_widget(card)

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
                                PAL["accent"], dp(44), font_size=dp(15)))
        card.add_widget(row)
        view.add_widget(card)
        view.open()

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
                                color=PAL["text"]))
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

        self.comment_input = make_input(font_size=dp(17), multiline=False,
                                        size_hint=(1, None), height=dp(48),
                                        hint_text="Комментарий (можно пусто)")
        root.add_widget(self.comment_input)

        root.add_widget(make_btn("Сохранить", self.save_record))
        self.add_msg = make_label("", dp(15), PAL["accent"])
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
                           color=(1, 1, 1, 1) if c == self.sel_cat else PAL["text"],
                           size_hint=(1, None), height=dp(44))
            b.bind(on_release=lambda inst, cat=c: self.pick_cat(cat))
            self.cats_grid.add_widget(b)
        plus = SoftButton(text="+ Своя", font_size=dp(15), bg=PAL["chip"],
                          radius=dp(22), color=PAL["muted"],
                          size_hint=(1, None), height=dp(44))
        plus.bind(on_release=lambda inst: self.add_cat_modal())
        self.cats_grid.add_widget(plus)

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
        view.open()

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
                                color=PAL["text"]))
        top.add_widget(make_label("[b]Отчёты[/b]", dp(22)))
        root.add_widget(top)

        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        for t, d in [("Сегодня", 1), ("Неделя", 7), ("Месяц", 31), ("Всё", None)]:
            row.add_widget(make_btn(t, lambda dd=d: self.show_report(dd),
                                    PAL["chip"], dp(44), color=PAL["text"],
                                    font_size=dp(14)))
        root.add_widget(row)

        self.report_scroll, self.report_grid = scroll_column()
        root.add_widget(self.report_scroll)
        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.show_report(7))
        return scr

    def show_report(self, days):
        recs = self.period_records(days)
        title = {1: "Сегодня", 7: "За неделю", 31: "За месяц",
                 None: "За всё время"}[days]
        self.report_grid.clear_widgets()
        if not recs:
            self.report_grid.add_widget(empty_note(f"{title}\nЗаписей нет."))
            return
        inc, exp = self.totals(recs)

        head = Card(radius=dp(20), padding=dp(16), spacing=dp(6),
                    size_hint=(1, None), height=dp(176))
        head.add_widget(make_label(f"[b]{title}[/b]", dp(20)))
        for name, val, col in [("Доходы", inc, PAL["green"]),
                               ("Расходы", exp, PAL["accent"]),
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
                            size_hint=(1, None), height=dp(76))
                top = BoxLayout(size_hint=(1, None), height=dp(26))
                top.add_widget(make_label(cat, dp(15), size_hint=(0.6, 1)))
                top.add_widget(make_label(rub(s), dp(15), PAL["muted"],
                                          halign="right", size_hint=(0.4, 1)))
                card.add_widget(top)
                card.add_widget(GoalBar(s / mx * 100, color=PAL["accent"],
                                        size_hint=(1, None), height=dp(10)))
                self.report_grid.add_widget(card)

    # ---------- ЦЕЛИ ----------
    def make_goals(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(10))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                PAL["chip"], dp(52), size_hint=(None, 1),
                                color=PAL["text"]))
        top.add_widget(make_label("[b]Цели[/b]", dp(22)))
        root.add_widget(top)

        self.goals_scroll, self.goals_grid = scroll_column()
        root.add_widget(self.goals_scroll)

        bottom = Card(radius=dp(20), padding=dp(14), spacing=dp(10),
                      size_hint=(1, None), height=dp(214))
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

    def refresh_goals(self):
        self.goals_grid.clear_widgets()
        if not self.goals:
            self.goals_grid.add_widget(empty_note(
                "Целей пока нет.\nСоздайте первую внизу — и откладывайте понемногу.",
                height=dp(92)))
            return
        for gname, g in self.goals.items():
            saved = sum(r["amount"] for r in self.records
                        if r["kind"] == "income" and r.get("comment") == f"цель:{gname}")
            pct = min(100, saved / g["target"] * 100) if g["target"] else 0

            card = Card(radius=dp(18), padding=dp(14), spacing=dp(10),
                        size_hint=(1, None), height=dp(196))
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

    # ---------- КОПИЯ ДАННЫХ ----------
    def make_backup(self, name):
        scr = Screen(name=name)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(10))
        top.add_widget(make_btn("←", lambda: self.go("home"),
                                PAL["chip"], dp(52), size_hint=(None, 1),
                                color=PAL["text"]))
        top.add_widget(make_label("[b]Копия данных[/b]", dp(22)))
        root.add_widget(top)

        card1 = Card(radius=dp(20), padding=dp(14), spacing=dp(8),
                     size_hint=(1, None), height=dp(150))
        card1.add_widget(make_label("Сохранить копию", dp(15), PAL["muted"]))
        card1.add_widget(make_label(
            "Вся история — одним текстом. Отправьте его «в сохранённые сообщения» "
            "или в заметки — так копия не потеряется.",
            dp(13), PAL["muted"]))
        card1.add_widget(make_btn("Отправить копию", self.send_backup,
                                  PAL["green"], dp(46)))
        root.add_widget(card1)

        card2 = Card(radius=dp(20), padding=dp(14), spacing=dp(8),
                     size_hint=(1, None), height=dp(220))
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
    DiaryApp().run()
