# -*- coding: utf-8 -*-
"""
Дневник расходов — Android-приложение на Kivy.
Версия: 1.1 (код v7). Версия видна внизу «Настройки».
Версия: 1.1.1 (код v7-fix): экран ошибки с traceback при падении запуска,
защитные обёртки on_start/стартовых вызовов. База — v7.
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

APP_VERSION = "1.1.1 (v7-fix)"

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
    """Кнопка-крестик: кружок с ободком и чётким крестом внутри."""
    def __init__(self, cb=None, cross_color=None, **kw):
        self._cross = (cross_color if cross_color is not None else PAL["muted"])
        kw.setdefault("text", "")
        super().__init__(**kw)
        with self.canvas.after:
            self._ringcol = Color(*blend(self._cross, 0.45))
            self._ring = Line(circle=[], width=dp(1.4), cap="round")
            Color(*self._cross)
            self._l1 = Line(points=[], width=dp(2.4), cap="round")
            self._l2 = Line(points=[], width=dp(2.4), cap="round")
        self.bind(pos=self._upd_cross, size=self._upd_cross)
        if cb is not None:
            self.bind(on_release=lambda inst: cb())

    def _upd_cross(self, *a):
        cx, cy = self.center_x, self.center_y
        d = min(self.width, self.height)
        self._ring.circle = (cx, cy, max(dp(2), d / 2.0 - dp(1)))
        r = d * 0.22
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
        self.notify = bool(d.get("notify", False))

    def save(self):
        path = self.data_file()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"records": self.records, "goals": self.goals,
                       "theme": self.theme, "budget": self.budget,
                       "custom_cats": self.custom, "pin_hash": self.pin_hash,
                       "notify": self.notify},
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
        self.hist = []
        self.open_modals = []
        self._reminders = []

        sm = ScreenManager()
        self.sm = sm
        self.rebuild_ui()
        if self.pin_hash:
            self.sm.current = "lock"
        try:
            Window.bind(on_keyboard=self.on_keyboard)
            Clock.schedule_interval(self._tick_reminders, 900)
            self.check_reminders()
        except Exception:
            pass
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
        self.lock_scr = self.make_lock_screen()
        self.sm.add_widget(self.lock_scr)
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
        cur = self.sm.current
        if cur != name and cur != "lock":
            self.hist.append(cur)
            if len(self.hist) > 12:
                del self.hist[:-12]
        self.sm.current = name

    def go_back(self):
        if self.hist:
            self.sm.current = self.hist.pop()
        elif self.sm.current != "home":
            self.sm.current = "home"
        else:
            self._minimize()

    def _minimize(self):
        """Свернуть приложение вместо закрытия (кнопка «назад» на главном)."""
        try:
            from jnius import autoclass
            Activity = autoclass("org.kivy.android.PythonActivity")
            Activity.mActivity.moveTaskToBack(True)
        except Exception:
            return False
        return True

    def on_keyboard(self, win, key, *args):
        """Системная кнопка «назад»: идти назад, а не закрывать приложение."""
        if key != 27:
            return False
        if self.sm.current == "lock":
            return True
        if self.open_modals:
            return False
        if self.sm.current != "home":
            self.go_back()
            return True
        return self._minimize()

    def open_view(self, view):
        """Открыть модальное окно, запомнив его для кнопки «назад»."""
        self.open_modals.append(view)

        def _gone(*a):
            if view in self.open_modals:
                self.open_modals.remove(view)
        view.bind(on_dismiss=_gone)
        view.open()

    # ---------- ПИН-КОД И БЛОКИРОВКА ----------
    def on_start(self):
        try:
            if self.pin_hash and self.sm.current != "lock":
                self.show_lock()
            if self.notify:
                self._ask_notif_permission()
        except Exception:
            pass

    def _ask_notif_permission(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.POST_NOTIFICATIONS])
        except Exception:
            pass

    def push_notify(self, title, message):
        """Системное уведомление (работает, когда приложение запущено)."""
        try:
            from plyer import notification as plyer_notif
            plyer_notif.notify(title=title, message=message,
                               app_name="Дневник расходов", app_icon="",
                               timeout=15)
            return True
        except Exception:
            return False

    def _tick_reminders(self, *a):
        if self.notify:
            self.check_reminders(push=True)

    def reminder_list(self):
        """Цели, по графику которых сегодня пора отложить: [(имя, сумма)]."""
        out = []
        today = datetime.now().date()
        for gname, g in self.goals.items():
            plan = g.get("plan")
            if not plan or not plan.get("amount"):
                continue
            try:
                start = datetime.strptime(plan["start"], "%Y-%m-%d").date()
            except (ValueError, TypeError, KeyError):
                continue
            if today < start:
                continue
            freq = plan.get("freq", "day")
            if freq == "day":
                due = True
            elif freq == "week":
                due = (today - start).days % 7 == 0
            else:
                last = calendar.monthrange(today.year, today.month)[1]
                due = today.day == min(start.day, last)
            if not due:
                continue
            t = today.strftime("%Y-%m-%d")
            got = sum(r["amount"] for r in self.records
                      if r["kind"] == "income"
                      and r.get("comment") == f"цель:{gname}"
                      and r["date"] == t)
            if got >= plan["amount"]:
                continue
            out.append((gname, plan["amount"]))
        return out

    def check_reminders(self, push=False):
        dues = self.reminder_list()
        self._reminders = dues
        self.refresh_home_banner()
        if not push:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        for gname, amount in dues:
            plan = (self.goals.get(gname) or {}).get("plan") or {}
            if plan.get("last_notified") == today:
                continue
            if self.push_notify("Дневник расходов",
                                f"Пора отложить {rub(amount)} на цель «{gname}»"):
                plan["last_notified"] = today
                self.save()

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
        msg = make_label("", dp(14), PAL["danger"], halign="center")
        card.add_widget(ti)
        card.add_widget(msg)
        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        if auto_dismiss:
            row.add_widget(make_btn("Отмена", view.dismiss, PAL["chip"],
                                    dp(44), color=PAL["text"], font_size=dp(15)))
        row.add_widget(make_btn("ОК",
                                lambda: on_done(view, ti.text.strip(), msg),
                                PAL["accent"], dp(44), color=PAL["accentfg"],
                                font_size=dp(15)))
        card.add_widget(row)
        view.add_widget(card)
        self.open_view(view)

    def make_lock_screen(self):
        """Непрозрачный экран блокировки: суммы и траты за ним не видны."""
        scr = Screen(name="lock")
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(12))
        root.add_widget(Widget())
        card = Card(radius=dp(24), padding=dp(18), spacing=dp(12),
                    orientation="vertical", size_hint=(1, None), height=dp(320))
        card.add_widget(make_label("[b]Дневник заблокирован[/b]", dp(20),
                                   halign="center"))
        card.add_widget(make_label("Введите пин-код, чтобы открыть дневник",
                                   dp(14), PAL["muted"], halign="center"))
        self.lock_input = make_input(password=True, multiline=False,
                                     input_filter="int", size_hint=(1, None),
                                     height=dp(52), hint_text="Цифры пин-кода")
        card.add_widget(self.lock_input)
        self.lock_msg = make_label("", dp(14), PAL["danger"], halign="center")
        card.add_widget(self.lock_msg)
        card.add_widget(make_btn("Разблокировать", self.unlock_try,
                                 PAL["accent"], dp(50), color=PAL["accentfg"]))
        root.add_widget(card)
        root.add_widget(Widget())
        scr.add_widget(root)
        return scr

    def show_lock(self):
        if self.sm.current != "lock":
            self._before_lock = self.sm.current
        self.sm.current = "lock"

    def unlock_try(self):
        pin = self.lock_input.text.strip()
        if self.pin_ok(pin):
            self.lock_input.text = ""
            self.lock_msg.text = ""
            self.sm.current = getattr(self, "_before_lock", "home") or "home"
        else:
            self.lock_msg.text = "Неверный пин-код."

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
                                 PAL["accent"], dp(44), color=PAL["accentfg"],
                                 font_size=dp(15)))
        row1.add_widget(make_btn("Убрать лимит",
                                 lambda: self._del_budget(view),
                                 PAL["chip"], dp(44), color=PAL["text"],
                                 font_size=dp(15)))
        card.add_widget(row1)
        view.add_widget(card)
        self.open_view(view)
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
                                color=PAL["text"],
                                size=(dp(52), dp(52))))
        top.add_widget(make_label("[b]Настройки[/b]", dp(22)))
        root.add_widget(top)

        scroll, col = scroll_column()
        root.add_widget(scroll)
        root = col

        c1 = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                  orientation="vertical", size_hint=(1, None), height=dp(120))
        c1.add_widget(make_label("[b]Тема оформления[/b]", dp(16)))
        self.btn_theme = make_btn("Тема: светлая", self.switch_theme,
                                  PAL["chip"], dp(46), color=PAL["text"],
                                  font_size=dp(15))
        c1.add_widget(self.btn_theme)
        root.add_widget(c1)

        c2 = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                  orientation="vertical", size_hint=(1, None), height=dp(170))
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

        c3 = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                  orientation="vertical", size_hint=(1, None), height=dp(170))
        c3.add_widget(make_label("[b]Копия данных[/b]", dp(16)))
        c3.add_widget(make_label("Отправить всю историю одним текстом или "
                                 "восстановить из копии.", dp(13), PAL["muted"]))
        c3.add_widget(make_btn("Открыть", lambda: self.go("backup"),
                               PAL["accent"], dp(44), color=PAL["accentfg"],
                               font_size=dp(15)))
        root.add_widget(c3)

        c4 = Card(radius=dp(20), padding=dp(16), spacing=dp(10),
                  orientation="vertical", size_hint=(1, None), height=dp(166))
        c4.add_widget(make_label("[b]Напоминания[/b]", dp(16)))
        c4.add_widget(make_label("Напомнят отложить деньги по графику накоплений. "
                                 "График включается на карточке цели.",
                                 dp(13), PAL["muted"]))
        self.btn_notify = make_btn("Напоминания: выкл", self.toggle_notify,
                                   PAL["chip"], dp(44), color=PAL["text"],
                                   font_size=dp(15))
        c4.add_widget(self.btn_notify)
        root.add_widget(c4)

        root.add_widget(make_label(f"Дневник расходов · версия {APP_VERSION}",
                                   dp(12), PAL["muted"], halign="center",
                                   size_hint=(1, None), height=dp(28)))

        scr.add_widget(root)
        scr.bind(on_enter=lambda *a: self.refresh_settings())
        return scr

    def toggle_notify(self):
        self.notify = not self.notify
        self.save()
        self.refresh_settings()
        if self.notify:
            self._ask_notif_permission()
            self.check_reminders(push=True)

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
        self.btn_notify.text = ("Напоминания: вкл" if self.notify
                                else "Напоминания: выкл")

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
