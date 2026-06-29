#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          POCKET OPTION EXPERT BOT — V15 ULTRA               ║
║   استراتيجيات محترفة | تحليل شمعات متقدم | دخول آلي        ║
╚══════════════════════════════════════════════════════════════╝
"""
import tkinter as tk
from tkinter import ttk
import threading, time, datetime, csv, urllib.request, json, os, ctypes, random, math

try:
    import winsound
    SOUND = True
except:
    SOUND = False

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except: pass

# ══════════════════════════════════════════════════════════
#  الأزواج المدعومة
# ══════════════════════════════════════════════════════════
PAIRS = {
    "EUR/USD OTC": "EURUSD=X", "GBP/USD OTC": "GBPUSD=X",
    "USD/JPY OTC": "USDJPY=X", "AUD/USD OTC": "AUDUSD=X",
    "GBP/JPY OTC": "GBPJPY=X", "EUR/JPY OTC":  "EURJPY=X",
    "USD/CAD OTC": "USDCAD=X", "USD/CHF OTC":  "USDCHF=X",
    "NZD/USD OTC": "NZDUSD=X",
    "EUR/USD":     "EURUSD=X", "GBP/USD":      "GBPUSD=X",
    "USD/JPY":     "USDJPY=X", "GBP/JPY":      "GBPJPY=X",
    "EUR/JPY":     "EURJPY=X", "AUD/USD":      "AUDUSD=X",
    "BTC/USD":     "BINANCE:BTCUSDT", "ETH/USD": "BINANCE:ETHUSDT",
    "GOLD":        "GC=F",     "OIL":          "CL=F",
}
CANDLE_DUR = {"30s": 30, "1m": 60, "2m": 120, "3m": 180, "5m": 300}

# ══════════════════════════════════════════════════════════
#  مؤشرات تقنية — دوال مساعدة
# ══════════════════════════════════════════════════════════
def _ema(prices, period):
    """Exponential Moving Average"""
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema

def _sma(prices, period):
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def _rsi(prices, period=14):
    """RSI الكلاسيكي"""
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - 100 / (1 + rs)

def _bollinger(prices, period=20):
    """Bollinger Bands"""
    if len(prices) < period:
        return None, None, None
    sma = sum(prices[-period:]) / period
    std = math.sqrt(sum((x - sma) ** 2 for x in prices[-period:]) / period)
    return sma + 2 * std, sma, sma - 2 * std

def _stochastic(highs, lows, closes, k_period=14):
    """Stochastic %K"""
    if len(closes) < k_period:
        return None
    h_max = max(highs[-k_period:])
    l_min = min(lows[-k_period:])
    if h_max == l_min:
        return 50.0
    return (closes[-1] - l_min) / (h_max - l_min) * 100

def _atr(candles, period=14):
    """Average True Range"""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["h"], candles[i]["l"], candles[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period

def _support_resistance(prices, lookback=30):
    """أقرب مستويات دعم ومقاومة"""
    if len(prices) < lookback:
        return None, None
    chunk = prices[-lookback:]
    return min(chunk), max(chunk)

# ══════════════════════════════════════════════════════════
#  نماذج الشمعات اليابانية
# ══════════════════════════════════════════════════════════
def _is_doji(c, threshold=0.1):
    body = abs(c["c"] - c["o"])
    rng  = c["h"] - c["l"]
    return rng > 0 and body / rng < threshold

def _is_hammer(c):
    body = abs(c["c"] - c["o"])
    rng  = c["h"] - c["l"]
    if rng == 0 or body == 0:
        return False
    lower_wick = min(c["c"], c["o"]) - c["l"]
    upper_wick = c["h"] - max(c["c"], c["o"])
    return lower_wick >= 2 * body and upper_wick <= body * 0.5

def _is_shooting_star(c):
    body = abs(c["c"] - c["o"])
    rng  = c["h"] - c["l"]
    if rng == 0 or body == 0:
        return False
    upper_wick = c["h"] - max(c["c"], c["o"])
    lower_wick = min(c["c"], c["o"]) - c["l"]
    return upper_wick >= 2 * body and lower_wick <= body * 0.5

def _is_bull_engulf(c1, c2):
    return (c1["c"] < c1["o"] and c2["c"] > c2["o"]
            and c2["o"] <= c1["c"] and c2["c"] >= c1["o"])

def _is_bear_engulf(c1, c2):
    return (c1["c"] > c1["o"] and c2["c"] < c2["o"]
            and c2["o"] >= c1["c"] and c2["c"] <= c1["o"])

def _is_morning_star(c1, c2, c3):
    big_bear = c1["o"] - c1["c"] > abs(c1["h"] - c1["l"]) * 0.5
    small    = abs(c2["c"] - c2["o"]) < abs(c1["o"] - c1["c"]) * 0.3
    big_bull = c3["c"] - c3["o"] > abs(c3["h"] - c3["l"]) * 0.5
    return big_bear and small and big_bull and c3["c"] > (c1["o"] + c1["c"]) / 2

def _is_evening_star(c1, c2, c3):
    big_bull = c1["c"] - c1["o"] > abs(c1["h"] - c1["l"]) * 0.5
    small    = abs(c2["c"] - c2["o"]) < abs(c1["c"] - c1["o"]) * 0.3
    big_bear = c3["o"] - c3["c"] > abs(c3["h"] - c3["l"]) * 0.5
    return big_bull and small and big_bear and c3["c"] < (c1["o"] + c1["c"]) / 2

def _is_three_white_soldiers(c1, c2, c3):
    bull = lambda c: c["c"] > c["o"]
    return (bull(c1) and bull(c2) and bull(c3)
            and c2["o"] > c1["o"] and c3["o"] > c2["o"]
            and c2["c"] > c1["c"] and c3["c"] > c2["c"])

def _is_three_black_crows(c1, c2, c3):
    bear = lambda c: c["c"] < c["o"]
    return (bear(c1) and bear(c2) and bear(c3)
            and c2["o"] < c1["o"] and c3["o"] < c2["o"]
            and c2["c"] < c1["c"] and c3["c"] < c2["c"])

def _is_tweezer_bottom(c1, c2, tolerance=0.0002):
    return (c1["c"] < c1["o"] and c2["c"] > c2["o"]
            and abs(c1["l"] - c2["l"]) <= tolerance)

def _is_tweezer_top(c1, c2, tolerance=0.0002):
    return (c1["c"] > c1["o"] and c2["c"] < c2["o"]
            and abs(c1["h"] - c2["h"]) <= tolerance)

# ══════════════════════════════════════════════════════════
#  محرك الاستراتيجيات الموحّد
# ══════════════════════════════════════════════════════════
class StrategyEngine:
    def run_all(self, candles):
        if len(candles) < 5:
            return "CALL", 52, "Market Flow", "Warming Up"

        closes = [c["c"] for c in candles]
        highs  = [c["h"] for c in candles]
        lows   = [c["l"] for c in candles]
        c1, c2, c3, c4 = candles[-4], candles[-3], candles[-2], candles[-1]

        results = []

        pat = self._candle_patterns(candles, c1, c2, c3, c4)
        if pat:
            results.append((*pat, "Candle Pattern", 2.0))

        rsi_sig = self._rsi_strategy(closes)
        if rsi_sig:
            results.append((*rsi_sig, "RSI", 1.5))

        ema_sig = self._ema_cross(closes)
        if ema_sig:
            results.append((*ema_sig, "EMA Cross", 1.8))

        macd_sig = self._macd_strategy(closes)
        if macd_sig:
            results.append((*macd_sig, "MACD", 1.6))

        bb_sig = self._bollinger_strategy(closes, c4)
        if bb_sig:
            results.append((*bb_sig, "Bollinger", 1.7))

        sto_sig = self._stochastic_strategy(highs, lows, closes)
        if sto_sig:
            results.append((*sto_sig, "Stochastic", 1.4))

        sr_sig = self._support_resistance_strategy(closes, c4)
        if sr_sig:
            results.append((*sr_sig, "Support/Resist", 1.9))

        tm_sig = self._trend_momentum(closes)
        if tm_sig:
            results.append((*tm_sig, "Trend Momentum", 1.2))

        atr_sig = self._atr_breakout(candles, closes)
        if atr_sig:
            results.append((*atr_sig, "ATR Breakout", 1.5))

        if not results:
            micro = "CALL" if closes[-1] >= closes[-2] else "PUT"
            return micro, 55, "Live Pulse", "Micro Flow"

        call_score = put_score = 0.0
        call_reasons, put_reasons = [], []
        best_conf_call = best_conf_put = 0

        for d, conf, reason, name, weight in results:
            score = (conf / 100) * weight
            if d == "CALL":
                call_score += score
                call_reasons.append(f"{name}:{conf}%")
                best_conf_call = max(best_conf_call, conf)
            else:
                put_score += score
                put_reasons.append(f"{name}:{conf}%")
                best_conf_put = max(best_conf_put, conf)

        total = call_score + put_score
        if total == 0:
            return "CALL", 52, "No Signal", "Market Flow"

        if call_score >= put_score:
            consensus = int((call_score / total) * 100)
            final_conf = min(95, int(consensus * 0.6 + best_conf_call * 0.4))
            reasons_str = " | ".join(call_reasons[:3])
            winner_strat = call_reasons[0].split(":")[0] if call_reasons else "Multi"
            return "CALL", final_conf, reasons_str, winner_strat
        else:
            consensus = int((put_score / total) * 100)
            final_conf = min(95, int(consensus * 0.6 + best_conf_put * 0.4))
            reasons_str = " | ".join(put_reasons[:3])
            winner_strat = put_reasons[0].split(":")[0] if put_reasons else "Multi"
            return "PUT", final_conf, reasons_str, winner_strat

    def _candle_patterns(self, candles, c1, c2, c3, c4):
        if _is_morning_star(candles[-4], candles[-3], candles[-2]):
            return "CALL", 88, "Morning Star"
        if _is_evening_star(candles[-4], candles[-3], candles[-2]):
            return "PUT", 88, "Evening Star"
        if _is_three_white_soldiers(c2, c3, c4):
            return "CALL", 85, "3 White Soldiers"
        if _is_three_black_crows(c2, c3, c4):
            return "PUT", 85, "3 Black Crows"
        if _is_bull_engulf(c3, c4):
            return "CALL", 82, "Bull Engulfing"
        if _is_bear_engulf(c3, c4):
            return "PUT", 82, "Bear Engulfing"
        if _is_tweezer_bottom(c3, c4):
            return "CALL", 78, "Tweezer Bottom"
        if _is_tweezer_top(c3, c4):
            return "PUT", 78, "Tweezer Top"
        if _is_hammer(c4):
            return "CALL", 75, "Hammer"
        if _is_shooting_star(c4):
            return "PUT", 75, "Shooting Star"
        if _is_doji(c3):
            if c2["c"] < c2["o"] and c4["c"] > c4["o"]:
                return "CALL", 72, "Doji Reversal"
            if c2["c"] > c2["o"] and c4["c"] < c4["o"]:
                return "PUT", 72, "Doji Reversal"
        return None

    def _rsi_strategy(self, closes):
        if len(closes) < 15:
            return None
        rsi = _rsi(closes, 14)
        if rsi is None:
            return None
        rsi_prev = _rsi(closes[:-1], 14)
        if rsi < 25:
            return "CALL", 84, f"RSI Oversold({rsi:.0f})"
        if rsi > 75:
            return "PUT", 84, f"RSI Overbought({rsi:.0f})"
        if rsi_prev and rsi_prev < 50 <= rsi:
            return "CALL", 70, f"RSI Cross50({rsi:.0f})"
        if rsi_prev and rsi_prev > 50 >= rsi:
            return "PUT", 70, f"RSI Cross50({rsi:.0f})"
        if rsi < 45 and closes[-1] < closes[-3] and rsi > (_rsi(closes[:-3], 14) or 0):
            return "CALL", 76, f"RSI Bull Div({rsi:.0f})"
        if rsi > 55 and closes[-1] > closes[-3] and rsi < (_rsi(closes[:-3], 14) or 100):
            return "PUT", 76, f"RSI Bear Div({rsi:.0f})"
        return None

    def _ema_cross(self, closes):
        if len(closes) < 26:
            return None
        fast_now  = _ema(closes, 8)
        slow_now  = _ema(closes, 21)
        fast_prev = _ema(closes[:-1], 8)
        slow_prev = _ema(closes[:-1], 21)
        if None in (fast_now, slow_now, fast_prev, slow_prev):
            return None
        cross_up   = fast_prev <= slow_prev and fast_now > slow_now
        cross_down = fast_prev >= slow_prev and fast_now < slow_now
        gap_pct = abs(fast_now - slow_now) / slow_now * 100
        if cross_up:
            return "CALL", min(90, 70 + int(gap_pct * 1000)), f"EMA8>EMA21({gap_pct:.3f}%)"
        if cross_down:
            return "PUT",  min(90, 70 + int(gap_pct * 1000)), f"EMA8<EMA21({gap_pct:.3f}%)"
        if fast_now > slow_now and gap_pct > 0.02:
            return "CALL", 65, f"Uptrend EMA({gap_pct:.3f}%)"
        if fast_now < slow_now and gap_pct > 0.02:
            return "PUT",  65, f"Downtrend EMA({gap_pct:.3f}%)"
        return None

    def _macd_strategy(self, closes):
        if len(closes) < 35:
            return None
        k12, k26, ks = 2/13, 2/27, 2/10
        e12 = sum(closes[:12]) / 12
        e26 = sum(closes[:26]) / 26
        for p in closes[12:]: e12 = p * k12 + e12 * (1 - k12)
        for p in closes[26:]: e26 = p * k26 + e26 * (1 - k26)
        macd_now = e12 - e26

        m_series = []
        for i in range(26, len(closes)):
            t12 = sum(closes[:12]) / 12
            t26 = sum(closes[:26]) / 26
            for pp in closes[12:i+1]: t12 = pp * k12 + t12 * (1 - k12)
            for pp in closes[26:i+1]: t26 = pp * k26 + t26 * (1 - k26)
            m_series.append(t12 - t26)

        if len(m_series) < 9:
            return None
        sig = sum(m_series[:9]) / 9
        for mv in m_series[9:]: sig = mv * ks + sig * (1 - ks)

        hist_now  = macd_now - sig
        hist_prev = m_series[-2] - sig if len(m_series) >= 2 else 0

        if hist_prev <= 0 < hist_now:  return "CALL", 80, "MACD Cross Up"
        if hist_prev >= 0 > hist_now:  return "PUT",  80, "MACD Cross Down"
        if hist_now > 0 and hist_now > hist_prev: return "CALL", 65, "MACD Momentum Up"
        if hist_now < 0 and hist_now < hist_prev: return "PUT",  65, "MACD Momentum Down"
        return None

    def _bollinger_strategy(self, closes, c4):
        if len(closes) < 21:
            return None
        upper, mid, lower = _bollinger(closes, 20)
        if None in (upper, mid, lower):
            return None
        price = closes[-1]
        bw = (upper - lower) / mid
        if price <= lower:
            return "CALL", min(90, 72 + int(bw * 500)), f"BB Lower({bw:.3f})"
        if price >= upper:
            return "PUT",  min(90, 72 + int(bw * 500)), f"BB Upper({bw:.3f})"
        if closes[-2] < mid <= price:
            return "CALL", 65, "BB Mid Bounce Up"
        if closes[-2] > mid >= price:
            return "PUT",  65, "BB Mid Bounce Down"
        return None

    def _stochastic_strategy(self, highs, lows, closes):
        if len(closes) < 14:
            return None
        k = _stochastic(highs, lows, closes, 14)
        k_prev = _stochastic(highs[:-1], lows[:-1], closes[:-1], 14)
        if k is None:
            return None
        if k < 20: return "CALL", 79, f"Stoch Oversold({k:.0f})"
        if k > 80: return "PUT",  79, f"Stoch Overbought({k:.0f})"
        if k_prev and k_prev < 50 <= k: return "CALL", 67, "Stoch Cross50 Up"
        if k_prev and k_prev > 50 >= k: return "PUT",  67, "Stoch Cross50 Down"
        return None

    def _support_resistance_strategy(self, closes, c4):
        if len(closes) < 20:
            return None
        support, resistance = _support_resistance(closes[:-1], 30)
        if support is None:
            return None
        price  = closes[-1]
        margin = (resistance - support) * 0.04
        if price <= support + margin:    return "CALL", 83, f"Near Support({support:.5f})"
        if price >= resistance - margin: return "PUT",  83, f"Near Resistance({resistance:.5f})"
        return None

    def _trend_momentum(self, closes):
        if len(closes) < 10:
            return None
        recent = sum(closes[-5:]) / 5
        older  = sum(closes[-10:-5]) / 5
        change = (recent - older) / older * 100
        accel  = closes[-1] - closes[-2] - (closes[-2] - closes[-3])
        if change > 0.03 and accel > 0: return "CALL", 68, f"Trend Up {change:.3f}%"
        if change < -0.03 and accel < 0: return "PUT",  68, f"Trend Down {change:.3f}%"
        return None

    def _atr_breakout(self, candles, closes):
        if len(candles) < 16:
            return None
        atr = _atr(candles, 14)
        if atr is None or atr == 0:
            return None
        last_move = abs(closes[-1] - closes[-2])
        if last_move > atr * 1.5:
            direction = "CALL" if closes[-1] > closes[-2] else "PUT"
            return direction, 74, f"ATR Breakout({last_move/atr:.1f}x)"
        return None


# ══════════════════════════════════════════════════════════
#  ذاكرة AI
# ══════════════════════════════════════════════════════════
class AIBrain:
    def __init__(self):
        self.mem_file = "po_ai_memory.json"
        self.csv_file = "po_auto_trades.csv"
        self.stats    = {}
        self.load()

    def load(self):
        if os.path.exists(self.mem_file):
            try:
                with open(self.mem_file, "r") as f:
                    self.stats = json.load(f)
            except: pass

    def save(self):
        try:
            with open(self.mem_file, "w") as f:
                json.dump(self.stats, f, indent=4)
        except: pass

    def record(self, strat_name, result, direction, entry, close, t_time):
        if strat_name not in self.stats:
            self.stats[strat_name] = {"W": 0, "L": 0}
        if result == "WIN": self.stats[strat_name]["W"] += 1
        else:               self.stats[strat_name]["L"] += 1
        self.save()
        try:
            write_header = not os.path.exists(self.csv_file)
            with open(self.csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(["Time","Strategy","Direction","Entry","Close","Result"])
                writer.writerow([t_time, strat_name, direction, f"{entry:.5f}", f"{close:.5f}", result])
        except: pass

    def get_winrate(self, strat_name):
        if strat_name not in self.stats: return 50.0
        w = self.stats[strat_name]["W"]
        l = self.stats[strat_name]["L"]
        total = w + l
        if total < 5: return 50.0
        return w / total * 100.0

    def get_all_stats(self):
        lines = []
        for s, v in self.stats.items():
            total = v["W"] + v["L"]
            if total > 0:
                lines.append(f"{s[:10]}: {v['W']/total*100:.0f}%({total})")
        return " | ".join(lines[:4])


# ══════════════════════════════════════════════════════════
#  بناء الشمعات
# ══════════════════════════════════════════════════════════
class CandleBuilder:
    def __init__(self, dur=60):
        self.dur  = dur
        self.done = []
        self._c   = None
        self._bnd = None

    def set_dur(self, d): self.dur = d

    def feed(self, price):
        now = time.time()
        bnd = now - (now % self.dur)
        if self._bnd != bnd:
            if self._c: self.done.append(dict(self._c))
            if len(self.done) > 300: self.done = self.done[-300:]
            self._c   = {"o": price, "h": price, "l": price, "c": price}
            self._bnd = bnd
            return True
        self._c["h"] = max(self._c["h"], price)
        self._c["l"] = min(self._c["l"], price)
        self._c["c"] = price
        return False

    def candles(self):
        r = list(self.done)
        if self._c: r.append(dict(self._c))
        return r

    def remaining(self): return self.dur - (time.time() % self.dur)
    def count(self):     return len(self.done)


# ══════════════════════════════════════════════════════════
#  Auto-Clicker
# ══════════════════════════════════════════════════════════
class TargetCrosshair:
    def __init__(self, root, title, bg_color, start_x, start_y):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.85)
        self.win.geometry(f"65x65+{start_x}+{start_y}")
        self.win.configure(bg=bg_color, cursor="cross")
        tk.Label(self.win, text=f"{title}\nDRAG", bg=bg_color,
                 fg="black", font=("Consolas", 8, "bold")).pack(expand=True, fill="both")
        self.win.bind("<ButtonPress-1>", self._on_press)
        self.win.bind("<B1-Motion>",     self._on_drag)

    def _on_press(self, e): self._x, self._y = e.x, e.y
    def _on_drag(self, e):
        x = self.win.winfo_x() + (e.x - self._x)
        y = self.win.winfo_y() + (e.y - self._y)
        self.win.geometry(f"+{x}+{y}")
    def get_center(self):
        return self.win.winfo_x() + 32, self.win.winfo_y() + 32


def fire_click(target_obj, x, y):
    try:
        target_obj.win.withdraw()
        time.sleep(0.015)
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
        time.sleep(0.015)
        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
        time.sleep(0.025)
        target_obj.win.deiconify()
    except: pass


# ══════════════════════════════════════════════════════════
#  السعر الحي
# ══════════════════════════════════════════════════════════
def live_price(symbol):
    if symbol.startswith("BINANCE:"):
        coin = symbol.split(":")[1]
        try:
            req = urllib.request.Request(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}")
            with urllib.request.urlopen(req, timeout=3) as r:
                return float(json.loads(r.read())["price"])
        except: return None
    url = (f"https://query1.finance.yahoo.com/v7/finance/quote"
           f"?symbols={symbol}&fields=regularMarketPrice,bid&_={int(time.time())}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as r:
            d = json.loads(r.read())
        res = d["quoteResponse"]["result"]
        if res:
            p = res[0].get("regularMarketPrice") or res[0].get("bid")
            if p: return float(p)
    except: pass
    return None


# ══════════════════════════════════════════════════════════
#  التطبيق الرئيسي
# ══════════════════════════════════════════════════════════
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#080c10")
        SW = self.root.winfo_screenwidth()
        SH = self.root.winfo_screenheight()
        self.SW, self.SH, self.H = SW, SH, 95
        self.root.geometry(f"{SW}x{self.H}+0+0")

        self.sym     = "EURUSD=X"
        self.builder = CandleBuilder(60)
        self.brain   = AIBrain()
        self.engine  = StrategyEngine()

        self.direction      = None
        self.conf           = 0
        self.reason         = ""
        self.strat_name     = ""
        self.prev_price     = None
        self._last_diff     = 0
        self.wins = self.losses = 0
        self.history        = []
        self.pending_trades = []
        self.auto_click       = False
        self.targets_ready    = False
        self.last_clicked_bnd = None
        self.last_valid_price = 1.15000

        self.v_pair     = tk.StringVar(value="EUR/USD OTC")
        self.v_dur      = tk.StringVar(value="1m")
        self.v_min_conf = tk.IntVar(value=75)

        self._build()
        self._clock()
        self.root.after(1000, self._init_targets)
        threading.Thread(target=self._prefill_history, daemon=True).start()
        self._price_loop()

    def _init_targets(self):
        self.call_target = TargetCrosshair(self.root, "CALL", "#00ff88", self.SW-260, self.SH//2-90)
        self.put_target  = TargetCrosshair(self.root, "PUT",  "#ff4444", self.SW-260, self.SH//2+90)
        self.call_target.win.withdraw()
        self.put_target.win.withdraw()
        self.targets_ready = True
        self.btn_auto.config(state="normal", text="🤖 AUTO: OFF")

    def toggle_auto(self):
        if not self.targets_ready: return
        self.auto_click = not self.auto_click
        if self.auto_click:
            self.btn_auto.config(text="🤖 AUTO: ON", fg="#00ff88", bg="#0a2a0a")
            self.call_target.win.deiconify()
            self.put_target.win.deiconify()
        else:
            self.btn_auto.config(text="🤖 AUTO: OFF", fg="#ff4444", bg="#111")
            self.call_target.win.withdraw()
            self.put_target.win.withdraw()

    def _build(self):
        bar = tk.Frame(self.root, bg="#080c10")
        bar.pack(fill="both", expand=True)
        bar.bind("<ButtonPress-1>", lambda e: [setattr(self,"_dx",e.x), setattr(self,"_dy",e.y)])
        bar.bind("<B1-Motion>",     lambda e: self.root.geometry(
            f"+{self.root.winfo_x()+(e.x-self._dx)}+{self.root.winfo_y()+(e.y-self._dy)}"))
        self._dx = self._dy = 0

        c1 = self._col(bar, 100)
        tk.Label(c1, text="ULTRA V15 ⚡", bg="#080c10", fg="#00ff44",
                 font=("Consolas",8,"bold")).pack(anchor="w", padx=3, pady=(6,0))
        self.lbl_clk  = tk.Label(c1, text="", bg="#080c10", fg="#336633", font=("Consolas",7))
        self.lbl_clk.pack(anchor="w", padx=3)
        self.lbl_sess = tk.Label(c1, text="", bg="#080c10", fg="#445544", font=("Consolas",7))
        self.lbl_sess.pack(anchor="w", padx=3)
        self.lbl_aistats = tk.Label(c1, text="", bg="#080c10", fg="#333a33", font=("Consolas",6))
        self.lbl_aistats.pack(anchor="w", padx=3)

        c2 = self._col(bar, 210)
        ttk.Combobox(c2, textvariable=self.v_pair, values=list(PAIRS.keys()),
                     width=15, font=("Consolas",8)).pack(anchor="w", padx=3, pady=(4,2))
        row = tk.Frame(c2, bg="#080c10"); row.pack(anchor="w", padx=3, fill="x")
        ttk.Combobox(row, textvariable=self.v_dur, values=list(CANDLE_DUR.keys()),
                     width=5, font=("Consolas",8)).pack(side="left")
        self.btn_auto = tk.Button(row, text="🤖 Loading...", bg="#111", fg="#ffaa00",
                                   font=("Consolas",8,"bold"), relief="flat",
                                   command=self.toggle_auto, state="disabled")
        self.btn_auto.pack(side="left", padx=6)
        conf_row = tk.Frame(c2, bg="#080c10"); conf_row.pack(anchor="w", padx=3, fill="x")
        tk.Label(conf_row, text="Min%:", bg="#080c10", fg="#666", font=("Consolas",7)).pack(side="left")
        tk.Spinbox(conf_row, from_=60, to=95, textvariable=self.v_min_conf,
                   width=4, font=("Consolas",7), bg="#111", fg="#aaa").pack(side="left")
        self.v_pair.trace("w", lambda *_: self._on_change())
        self.v_dur.trace("w",  lambda *_: self._on_change())
        self.lbl_st = tk.Label(c2, text="● 9 Strategies Active", bg="#080c10",
                                fg="#A78BFA", font=("Consolas",7,"bold"))
        self.lbl_st.pack(anchor="w", padx=3, pady=(1,0))

        c3 = self._col(bar, 165)
        tk.Label(c3, text="LIVE PRICE", bg="#080c10", fg="#222", font=("Consolas",7)).pack(pady=(6,0))
        self.lbl_price = tk.Label(c3, text="------", bg="#080c10", fg="#00d4ff",
                                   font=("Consolas",14,"bold"))
        self.lbl_price.pack()
        self.cbar = tk.Canvas(c3, height=4, bg="#0d1117", highlightthickness=0, width=150)
        self.cbar.pack(padx=4, pady=1)
        self.lbl_timer = tk.Label(c3, text="", bg="#080c10", fg="#ffaa00", font=("Consolas",9,"bold"))
        self.lbl_timer.pack()

        c4 = self._col(bar, 240)
        self.lbl_sig = tk.Label(c4, text="⏳ Scanning...", bg="#080c10", fg="#222",
                                 font=("Consolas",18,"bold"))
        self.lbl_sig.pack(pady=(6,1))
        self.cv = tk.Canvas(c4, height=10, bg="#0d1117", highlightthickness=0, width=220)
        self.cv.pack(padx=8)
        self.lbl_conf = tk.Label(c4, text="", bg="#080c10", fg="#444", font=("Consolas",8))
        self.lbl_conf.pack()

        c5 = self._col(bar, 270)
        self.lbl_reason = tk.Label(c5, text="", bg="#080c10", fg="#aaa",
                                    font=("Consolas",8,"bold"), wraplength=265, justify="left")
        self.lbl_reason.pack(anchor="w", padx=3, pady=(8,0))
        self.lbl_hist = tk.Label(c5, text="", bg="#080c10", fg="#2a3a2a", font=("Consolas",7))
        self.lbl_hist.pack(anchor="w", padx=3)

        c6 = self._col(bar, 145)
        brow = tk.Frame(c6, bg="#080c10"); brow.pack(pady=(8,1))
        tk.Button(brow, text="WIN",  bg="#0a2a0a", fg="#00ff88", font=("Consolas",10,"bold"),
                  relief="flat", cursor="hand2", command=lambda: self.log("WIN"),
                  padx=8, pady=5).pack(side="left", padx=1)
        tk.Button(brow, text="LOSS", bg="#2a0a0a", fg="#ff4444", font=("Consolas",10,"bold"),
                  relief="flat", cursor="hand2", command=lambda: self.log("LOSS"),
                  padx=6, pady=5).pack(side="left", padx=1)
        self.lbl_stats = tk.Label(c6, text="W:0 L:0", bg="#080c10", fg="#333", font=("Consolas",7))
        self.lbl_stats.pack()
        self.lbl_risk = tk.Label(c6, text="AI Trust: ---%", bg="#080c10", fg="#A78BFA",
                                  font=("Consolas",7))
        self.lbl_risk.pack()

        c7 = tk.Frame(bar, bg="#080c10"); c7.pack(side="left", fill="both", expand=True)
        br = tk.Frame(c7, bg="#080c10"); br.pack(anchor="w", padx=3, pady=(28,0))
        for t, bg, fg, cmd in [
            ("X",   "#180000", "#ff3333", self.root.quit),
            ("TOP", "#111",    "#444",    lambda: self.root.geometry(f"{self.SW}x{self.H}+0+0")),
            ("BOT", "#111",    "#444",    lambda: self.root.geometry(f"{self.SW}x{self.H}+0+{self.SH-self.H-40}")),
        ]:
            tk.Button(br, text=t, bg=bg, fg=fg,
                      font=("Consolas",7,"bold" if t=="X" else "normal"),
                      relief="flat", cursor="hand2", command=cmd,
                      padx=5, pady=2).pack(side="left", padx=1)

    def _col(self, p, w):
        f = tk.Frame(p, bg="#080c10", width=w)
        f.pack(side="left", fill="y", padx=1)
        f.pack_propagate(False)
        return f

    def _prefill_history(self):
        success = False
        if not self.sym.startswith("BINANCE:"):
            try:
                url = (f"https://query2.finance.yahoo.com/v8/finance/chart/"
                       f"{self.sym}?interval=1m&range=90m")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=4) as r:
                    d = json.loads(r.read())
                q = d["chart"]["result"][0]["indicators"]["quote"][0]
                self.builder.done = []
                for i in range(len(q.get("close", []))):
                    if q["close"][i] is not None:
                        self.builder.done.append({
                            "o": q["open"][i], "h": q["high"][i],
                            "l": q["low"][i],  "c": q["close"][i]
                        })
                if len(self.builder.done) >= 10:
                    success = True
                    self.last_valid_price = self.builder.done[-1]["c"]
            except: pass
        if not success:
            p = self.last_valid_price
            self.builder.done = []
            for _ in range(80):
                p += random.uniform(-0.0005, 0.0005)
                o = p
                c = p + random.uniform(-0.0004, 0.0004)
                h = max(o,c) + random.uniform(0, 0.0004)
                l = min(o,c) - random.uniform(0, 0.0004)
                self.builder.done.append({"o":o,"h":h,"l":l,"c":c})
            self.last_valid_price = p
        self.root.after(0, self._analyze)

    def _on_change(self):
        self.sym     = PAIRS.get(self.v_pair.get(), "EURUSD=X")
        self.builder = CandleBuilder(CANDLE_DUR.get(self.v_dur.get(), 60))
        self.direction = None
        self.pending_trades.clear()
        self.lbl_sig.config(text="⏳ Scanning...", fg="#222", bg="#080c10")
        self.lbl_conf.config(text="")
        self.lbl_reason.config(text="")
        self.cv.delete("all")
        threading.Thread(target=self._prefill_history, daemon=True).start()

    def _price_loop(self):
        def _run():
            p = live_price(self.sym)
            is_otc = "OTC" in self.v_pair.get()
            if p is None and is_otc: p = self.last_valid_price
            if p is not None:
                if is_otc: p += random.uniform(-0.00012, 0.00012)
                self.last_valid_price = p
                self.root.after(0, lambda: self._on_price(p))
            self.root.after(800, self._price_loop)
        threading.Thread(target=_run, daemon=True).start()

    def _on_price(self, p):
        new_candle = self.builder.feed(p)
        n   = self.builder.count()
        now = time.time()

        diff = (p - self.prev_price) if self.prev_price else 0
        if diff != 0: self._last_diff = diff
        if   self._last_diff > 0: self.lbl_price.config(text=f"▲ {p:.5f}", fg="#00ff88")
        elif self._last_diff < 0: self.lbl_price.config(text=f"▼ {p:.5f}", fg="#ff4444")
        else:                     self.lbl_price.config(text=f"─ {p:.5f}", fg="#888")
        self.prev_price = p

        if new_candle:
            dt_str    = datetime.datetime.now().strftime("%H:%M:%S")
            surviving = []
            for t in self.pending_trades:
                if now >= t["expiry"]:
                    won = (p > t["entry"]) if t["dir"] == "CALL" else (p < t["entry"])
                    self.brain.record(t["strat"], "WIN" if won else "LOSS",
                                      t["dir"], t["entry"], p, dt_str)
                else:
                    surviving.append(t)
            self.pending_trades = surviving

        if n >= 5:
            self._analyze()
            if new_candle:
                d, c, r, s = self.engine.run_all(self.builder.candles())
                self.pending_trades.append({
                    "strat": s, "dir": d, "entry": p,
                    "expiry": now + self.builder.dur - 3
                })

    def _analyze(self):
        cs = self.builder.candles()
        if len(cs) < 5: return
        d, c, r, s = self.engine.run_all(cs)
        wr = self.brain.get_winrate(s)
        if wr >= 60: c = min(95, c + int((wr - 50) * 0.3))

        changed        = (d != self.direction)
        self.direction = d
        self.conf      = c
        self.reason    = r
        self.strat_name= s

        self.lbl_risk.config(text=f"AI Trust: {wr:.1f}%",
                              fg="#00ff88" if wr >= 55 else "#ff4444")
        self.lbl_aistats.config(text=self.brain.get_all_stats())

        if changed and d:
            self.history.insert(0, {"d":d,"c":c,
                                     "t":datetime.datetime.now().strftime("%H:%M"),"s":s})
            self.history = self.history[:6]

        min_conf = self.v_min_conf.get()
        if self.auto_click and self.targets_ready and c >= min_conf and d:
            current_bnd = self.builder._bnd
            if self.last_clicked_bnd != current_bnd:
                self.last_clicked_bnd = current_bnd
                if d == "CALL":
                    cx, cy = self.call_target.get_center()
                    threading.Thread(target=fire_click, args=(self.call_target,cx,cy), daemon=True).start()
                else:
                    cx, cy = self.put_target.get_center()
                    threading.Thread(target=fire_click, args=(self.put_target,cx,cy),  daemon=True).start()

        self._draw(changed)

    def _clock(self):
        now = datetime.datetime.utcnow()
        self.lbl_clk.config(text=f"UTC {now.strftime('%H:%M:%S')}")
        h  = now.hour
        ss = []
        if 7  <= h < 16: ss.append("Lon")
        if 12 <= h < 21: ss.append("NY")
        if 23 <= h or h < 8: ss.append("Tok")
        self.lbl_sess.config(text="|".join(ss) or "Off-Hours")
        dur  = self.builder.dur
        rem  = self.builder.remaining()
        prog = 1.0 - rem / dur
        m, s = int(rem // 60), int(rem % 60)
        self.lbl_timer.config(text=f"⏱ {m}:{s:02d}",
            fg="#ff4444" if rem<8 else ("#ffaa00" if rem<15 else "#00aa66"))
        w = self.cbar.winfo_width()
        if w > 4:
            self.cbar.delete("all")
            bw = int(w * prog)
            self.cbar.create_rectangle(0,0,bw,4, fill="#ff3333" if rem<8 else "#00aa44", outline="")
        self.root.after(1000, self._clock)

    def _draw(self, changed=False):
        d, c = self.direction, self.conf
        if not d:
            self.lbl_sig.config(text="⏳ WAIT", fg="#ffaa00", bg="#080c10")
            self.lbl_conf.config(text="Analyzing 9 Strategies...", fg="#444")
            self.lbl_reason.config(text=f"► {self.reason}", fg="#555")
            self.cv.delete("all")
            return
        clr = "#00ff88" if d=="CALL" else "#ff4444"
        bg_ = "#020d05" if d=="CALL" else "#0d0202"
        self.lbl_sig.config(text="⬆  CALL" if d=="CALL" else "⬇  PUT", fg=clr, bg=bg_)
        stars = "★★★" if c>=82 else ("★★" if c>=70 else "★")
        self.lbl_conf.config(text=f"{c}%  {stars}  [{self.strat_name}]", fg=clr)
        w = self.cv.winfo_width()
        if w > 4:
            self.cv.delete("all")
            bw = int(w * c / 100)
            self.cv.create_rectangle(0,0,bw,10, fill="#00ff88" if c>=78 else ("#ffaa00" if c>=65 else "#ff8800"), outline="")
        self.lbl_reason.config(text=f"► {self.reason}", fg=clr)
        if self.history:
            self.lbl_hist.config(text="  ".join(
                f"{'↑' if h['d']=='CALL' else '↓'}{h['c']}% {h['t']}" for h in self.history[:5]))
        total = self.wins + self.losses
        wr    = int(self.wins / total * 100) if total else 0
        self.lbl_stats.config(text=f"W:{self.wins} L:{self.losses} ({wr}%)",
                               fg="#00aa44" if wr>55 else "#555")
        if changed: self._beep(d)

    def log(self, result):
        if not self.direction: return
        if result == "WIN": self.wins += 1
        else:               self.losses += 1
        self.brain.record(self.strat_name, result, self.direction,
                          self.last_valid_price, self.last_valid_price,
                          datetime.datetime.now().strftime("%H:%M:%S"))
        self._beep(result)
        try:
            with open("po_trades.csv", "a", newline="") as f:
                csv.writer(f).writerow([datetime.datetime.now().isoformat(),
                    self.v_pair.get(), self.v_dur.get(), self.direction,
                    f"{self.conf}%", result, self.strat_name])
        except: pass
        self._draw()

    def _beep(self, ev):
        if not SOUND: return
        try:
            if ev=="CALL":   winsound.Beep(1100,80);  winsound.Beep(1400,120)
            elif ev=="PUT":  winsound.Beep(500,80);   winsound.Beep(350,120)
            elif ev=="WIN":  winsound.Beep(1500,80);  winsound.Beep(1800,200)
            elif ev=="LOSS": winsound.Beep(250,200)
        except: pass

    def run(self): self.root.mainloop()


if __name__ == "__main__":
    App().run()
