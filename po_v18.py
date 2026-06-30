#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║           POCKET OPTION SUPREME BOT — V18 ULTRA PROFESSIONAL                   ║
║  ────────────────────────────────────────────────────────────────────────────  ║
║  NEW IN V18:                                                                   ║
║   📰 Economic Calendar Filter — blocks trading near high-impact news          ║
║   📊 RSI & MACD Divergence Detection — strongest reversal signals              ║
║   📱 Telegram Alerts — real-time signals on phone                             ║
║   🔍 Multi-Pair Scanner — monitors 6 pairs simultaneously                     ║
║   🤖 ML Win Predictor — weighted probability scoring                          ║
║   📈 Backtesting Mode — verify on historical data                             ║
║   ⚡ Ultra-Fast Feed: 250ms OTC / 300ms Binance / 450ms Forex                 ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, time, datetime, csv, urllib.request, json, os, ctypes, random, math

try:
    import winsound; SOUND=True
except: SOUND=False
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except: pass

PAIRS={
    "EUR/USD OTC":"EURUSD=X","GBP/USD OTC":"GBPUSD=X","USD/JPY OTC":"USDJPY=X",
    "AUD/USD OTC":"AUDUSD=X","GBP/JPY OTC":"GBPJPY=X","EUR/JPY OTC":"EURJPY=X",
    "USD/CAD OTC":"USDCAD=X","USD/CHF OTC":"USDCHF=X","NZD/USD OTC":"NZDUSD=X",
    "EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X",
    "GBP/JPY":"GBPJPY=X","EUR/JPY":"EURJPY=X","AUD/USD":"AUDUSD=X",
    "BTC/USD":"BINANCE:BTCUSDT","ETH/USD":"BINANCE:ETHUSDT",
    "GOLD":"GC=F","OIL":"CL=F",
}
CANDLE_DUR={"30s":30,"1m":60,"2m":120,"3m":180,"5m":300}
SCAN_SYMS={"EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X",
           "GBP/JPY":"GBPJPY=X","AUD/USD":"AUDUSD=X","EUR/JPY":"EURJPY=X"}

# ══════════════════════════════════════════════════════════
#  Math / Indicator helpers
# ══════════════════════════════════════════════════════════
def _ema(prices,period):
    if len(prices)<period: return None
    k=2/(period+1); e=sum(prices[:period])/period
    for p in prices[period:]: e=p*k+e*(1-k)
    return e

def _rsi(prices,period=14):
    if len(prices)<period+1: return None
    g=[max(prices[i]-prices[i-1],0) for i in range(1,len(prices))]
    l=[max(prices[i-1]-prices[i],0) for i in range(1,len(prices))]
    ag=sum(g[-period:])/period; al=sum(l[-period:])/period
    if al==0: return 100.0
    return 100-100/(1+ag/al)

def _bollinger(prices,period=20):
    if len(prices)<period: return None,None,None
    sma=sum(prices[-period:])/period
    std=math.sqrt(sum((x-sma)**2 for x in prices[-period:])/period)
    return sma+2*std,sma,sma-2*std

def _stochastic(highs,lows,closes,k=14):
    if len(closes)<k: return None
    hmax=max(highs[-k:]); lmin=min(lows[-k:])
    if hmax==lmin: return 50.0
    return (closes[-1]-lmin)/(hmax-lmin)*100

def _atr(candles,period=14):
    if len(candles)<period+1: return None
    trs=[]
    for i in range(1,len(candles)):
        h,l,pc=candles[i]["h"],candles[i]["l"],candles[i-1]["c"]
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs[-period:])/period

def _adx(candles,period=14):
    if len(candles)<period+2: return None
    pdm,mdm,trs=[],[],[]
    for i in range(1,len(candles)):
        h,l,ph,pl=candles[i]["h"],candles[i]["l"],candles[i-1]["h"],candles[i-1]["l"]
        pc=candles[i-1]["c"]
        up=h-ph; dn=pl-l
        pdm.append(up if up>dn and up>0 else 0)
        mdm.append(dn if dn>up and dn>0 else 0)
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    if len(trs)<period: return None
    av=sum(trs[-period:])/period
    pv=sum(pdm[-period:])/period; mv=sum(mdm[-period:])/period
    if av==0: return 0
    pdi=pv/av*100; mdi=mv/av*100
    if pdi+mdi==0: return 0
    return abs(pdi-mdi)/(pdi+mdi)*100

def _williams_r(highs,lows,closes,period=14):
    if len(closes)<period: return None
    hmax=max(highs[-period:]); lmin=min(lows[-period:])
    if hmax==lmin: return -50
    return (hmax-closes[-1])/(hmax-lmin)*-100

def _cci(highs,lows,closes,period=14):
    if len(closes)<period: return None
    tp=[(highs[i]+lows[i]+closes[i])/3 for i in range(len(closes))]
    m=sum(tp[-period:])/period
    d=sum(abs(x-m) for x in tp[-period:])/period
    if d==0: return 0
    return (tp[-1]-m)/(0.015*d)

def _momentum(prices,period=10):
    if len(prices)<period+1: return None
    return (prices[-1]/prices[-period-1]-1)*100

def _pivot_points(candles):
    if len(candles)<20: return None,None,None
    r=candles[-20:]
    H=max(c["h"] for c in r); L=min(c["l"] for c in r); C=candles[-1]["c"]
    PP=(H+L+C)/3
    return PP,2*PP-L,2*PP-H

def _ichimoku(candles):
    if len(candles)<26: return None
    def mid(cs): return (max(c["h"] for c in cs)+min(c["l"] for c in cs))/2
    tenkan=mid(candles[-9:]) if len(candles)>=9 else None
    kijun =mid(candles[-26:]) if len(candles)>=26 else None
    chikou_above=candles[-1]["c"]>candles[-26]["c"] if len(candles)>=26 else None
    price=candles[-1]["c"]
    if tenkan is None or kijun is None: return None
    bullish=price>kijun and tenkan>kijun and chikou_above
    bearish=price<kijun and tenkan<kijun and chikou_above==False
    return bullish,bearish,tenkan,kijun

def _fibonacci(candles,lookback=34):
    if len(candles)<lookback: return None
    cs=candles[-lookback:]
    swing_high=max(c["h"] for c in cs); swing_low=min(c["l"] for c in cs)
    rng=swing_high-swing_low
    if rng==0: return None
    price=candles[-1]["c"]
    levels={"23.6":swing_high-rng*0.236,"38.2":swing_high-rng*0.382,
            "50.0":swing_high-rng*0.500,"61.8":swing_high-rng*0.618,"78.6":swing_high-rng*0.786}
    margin=rng*0.015
    for name,lvl in levels.items():
        if abs(price-lvl)<=margin:
            if price<swing_high-rng*0.4: return "CALL",int(70+float(name)*0.1),f"Fib {name}% Support"
            else: return "PUT",int(70+float(name)*0.1),f"Fib {name}% Resistance"
    return None

def _supertrend(candles,period=10,multiplier=3.0):
    if len(candles)<period+2: return None
    atr=_atr(candles,period)
    if not atr: return None
    hl2=(candles[-1]["h"]+candles[-1]["l"])/2
    upper=hl2+multiplier*atr; lower=hl2-multiplier*atr; price=candles[-1]["c"]
    prev_hl2=(candles[-2]["h"]+candles[-2]["l"])/2; prev_price=candles[-2]["c"]
    if price>lower and prev_price<=(prev_hl2-multiplier*atr): return "CALL",78,"Supertrend↑"
    if price<upper and prev_price>=(prev_hl2+multiplier*atr): return "PUT",78,"Supertrend↓"
    if price>lower: return "CALL",65,"Supertrend Bull"
    if price<upper: return "PUT",65,"Supertrend Bear"
    return None

def _parabolic_sar(candles,af_start=0.02,af_max=0.20):
    if len(candles)<10: return None
    cs=candles[-20:] if len(candles)>=20 else candles
    bull=cs[1]["c"]>cs[0]["c"]; sar=cs[0]["l"] if bull else cs[0]["h"]
    ep=cs[0]["h"] if bull else cs[0]["l"]; af=af_start
    for i in range(1,len(cs)):
        sar=sar+af*(ep-sar)
        if bull:
            if cs[i]["l"]<sar: bull=False; sar=ep; ep=cs[i]["l"]; af=af_start
            else:
                if cs[i]["h"]>ep: ep=cs[i]["h"]; af=min(af+af_start,af_max)
                sar=min(sar,cs[i-1]["l"],cs[i]["l"] if i>1 else sar)
        else:
            if cs[i]["h"]>sar: bull=True; sar=ep; ep=cs[i]["h"]; af=af_start
            else:
                if cs[i]["l"]<ep: ep=cs[i]["l"]; af=min(af+af_start,af_max)
                sar=max(sar,cs[i-1]["h"],cs[i]["h"] if i>1 else sar)
    price=cs[-1]["c"]; dist=abs(price-sar)/price*100
    if bull: return "CALL",min(85,68+int(dist*100)),f"PSAR Bull"
    else:    return "PUT", min(85,68+int(dist*100)),f"PSAR Bear"

def _heikin_ashi_trend(candles,lookback=5):
    if len(candles)<lookback+1: return None
    ha=[]
    for i in range(len(candles)):
        hc=(candles[i]["o"]+candles[i]["h"]+candles[i]["l"]+candles[i]["c"])/4
        ho=(candles[i]["o"]+candles[i]["c"])/2 if i==0 else (ha[-1]["o"]+ha[-1]["c"])/2
        hh=max(candles[i]["h"],ho,hc); hl=min(candles[i]["l"],ho,hc)
        ha.append({"o":ho,"h":hh,"l":hl,"c":hc})
    recent=ha[-lookback:]
    bull=sum(1 for c in recent if c["c"]>c["o"]); bear=sum(1 for c in recent if c["c"]<c["o"])
    last=ha[-1]; no_lo=last["l"]==min(last["o"],last["c"]); no_up=last["h"]==max(last["o"],last["c"])
    if bull>=4: return "CALL",75+(5 if no_lo else 0),f"HA Bull x{bull}"
    if bear>=4: return "PUT", 75+(5 if no_up else 0),f"HA Bear x{bear}"
    return None

# ── New V18: Divergence Detection ─────────────────────────
def _rsi_divergence(candles,closes):
    if len(closes)<35: return None
    rsi_arr=[]
    for i in range(20,len(closes)+1):
        v=_rsi(closes[:i],14)
        if v is not None: rsi_arr.append(v)
    if len(rsi_arr)<12: return None
    prices=closes[-len(rsi_arr):]
    n=5
    def lows(arr):
        return [i for i in range(n,len(arr)-n)
                if all(arr[i]<=arr[j] for j in range(i-n,i+n+1) if j!=i)]
    def highs(arr):
        return [i for i in range(n,len(arr)-n)
                if all(arr[i]>=arr[j] for j in range(i-n,i+n+1) if j!=i)]
    pl=lows(prices); rl=lows(rsi_arr)
    if len(pl)>=2 and len(rl)>=2:
        if prices[pl[-1]]<prices[pl[-2]] and rsi_arr[rl[-1]]>rsi_arr[rl[-2]]:
            return "CALL",87,"RSI Bullish Divergence"
    ph=highs(prices); rh=highs(rsi_arr)
    if len(ph)>=2 and len(rh)>=2:
        if prices[ph[-1]]>prices[ph[-2]] and rsi_arr[rh[-1]]<rsi_arr[rh[-2]]:
            return "PUT",87,"RSI Bearish Divergence"
    return None

def _macd_divergence(closes):
    if len(closes)<45: return None
    hist=[]
    k12,k26,ks=2/13,2/27,2/10
    for i in range(35,len(closes)):
        sl=closes[:i+1]
        e12=sum(sl[:12])/12; e26=sum(sl[:26])/26
        for p in sl[12:]: e12=p*k12+e12*(1-k12)
        for p in sl[26:]: e26=p*k26+e26*(1-k26)
        hist.append(e12-e26)
    if len(hist)<10: return None
    prices=closes[-len(hist):]
    p_tr=prices[-1]-prices[-10]; h_tr=hist[-1]-hist[-10]
    if p_tr<0 and h_tr>0 and hist[-1]<0: return "CALL",83,"MACD Bullish Div"
    if p_tr>0 and h_tr<0 and hist[-1]>0: return "PUT", 83,"MACD Bearish Div"
    return None

# ── SMC ───────────────────────────────────────────────────
def _market_structure(candles,lookback=20):
    if len(candles)<lookback: return None
    cs=candles[-lookback:]
    peaks  =[i for i in range(1,len(cs)-1) if cs[i]["h"]>cs[i-1]["h"] and cs[i]["h"]>cs[i+1]["h"]]
    troughs=[i for i in range(1,len(cs)-1) if cs[i]["l"]<cs[i-1]["l"] and cs[i]["l"]<cs[i+1]["l"]]
    if len(peaks)>=2 and len(troughs)>=2:
        hh=cs[peaks[-1]]["h"]>cs[peaks[-2]]["h"]; lh=cs[peaks[-1]]["h"]<cs[peaks[-2]]["h"]
        hl=cs[troughs[-1]]["l"]>cs[troughs[-2]]["l"]; ll=cs[troughs[-1]]["l"]<cs[troughs[-2]]["l"]
        if hh and hl: return "CALL",82,"Market Structure HH+HL"
        if lh and ll: return "PUT", 82,"Market Structure LH+LL"
        if hh: return "CALL",72,"Higher High (BOS)"
        if ll: return "PUT", 72,"Lower Low (BOS)"
    return None

def _order_blocks(candles,lookback=15):
    if len(candles)<lookback: return None
    cs=candles[-lookback:]; price=cs[-1]["c"]
    for i in range(len(cs)-3,max(0,len(cs)-10),-1):
        c0,c1,c2=cs[i],cs[i+1],cs[i+2]; body0=abs(c0["c"]-c0["o"])
        if (c0["c"]<c0["o"] and c1["c"]>c1["o"] and c2["c"]>c2["o"]
                and (c1["c"]-c1["o"])>body0*0.5):
            if c0["l"]<=price<=c0["h"]: return "CALL",84,"Bullish OB Zone"
        if (c0["c"]>c0["o"] and c1["c"]<c1["o"] and c2["c"]<c2["o"]
                and (c1["o"]-c1["c"])>body0*0.5):
            if c0["l"]<=price<=c0["h"]: return "PUT",84,"Bearish OB Zone"
    return None

def _fair_value_gap(candles):
    if len(candles)<4: return None
    c1,c2,c3=candles[-3],candles[-2],candles[-1]; price=c3["c"]
    if c1["h"]<c3["l"]:
        gap_mid=(c1["h"]+c3["l"])/2
        if abs(price-gap_mid)/price<0.001: return "CALL",77,"Bullish FVG Fill"
    if c1["l"]>c3["h"]:
        gap_mid=(c1["l"]+c3["h"])/2
        if abs(price-gap_mid)/price<0.001: return "PUT",77,"Bearish FVG Fill"
    return None

def _liquidity_sweep(candles,lookback=20):
    if len(candles)<lookback: return None
    cs=candles[-lookback:]
    recent_high=max(c["h"] for c in cs[:-3]); recent_low=min(c["l"] for c in cs[:-3])
    last=cs[-1]; prev=cs[-2]
    if prev["l"]<recent_low and last["c"]>recent_low: return "CALL",86,"Liquidity Sweep Low"
    if prev["h"]>recent_high and last["c"]<recent_high: return "PUT",86,"Liquidity Sweep High"
    return None

def _supply_demand_zones(candles,lookback=30):
    if len(candles)<lookback: return None
    cs=candles[-lookback:]; price=cs[-1]["c"]
    for i in range(2,len(cs)-2):
        base=cs[i]; before_move=abs(cs[i-1]["c"]-cs[i-1]["o"]); after_move=abs(cs[i+1]["c"]-cs[i+1]["o"])
        if cs[i-1]["c"]>cs[i-1]["o"] and cs[i+1]["c"]<cs[i+1]["o"] and after_move>before_move*1.5:
            z_top=max(base["h"],cs[i-1]["h"]); z_bot=min(base["l"],cs[i-1]["l"])
            if z_bot<=price<=z_top: return "PUT",80,"Supply Zone (RBD)"
        if cs[i-1]["c"]<cs[i-1]["o"] and cs[i+1]["c"]>cs[i+1]["o"] and after_move>before_move*1.5:
            z_top=max(base["h"],cs[i+1]["h"]); z_bot=min(base["l"],cs[i+1]["l"])
            if z_bot<=price<=z_top: return "CALL",80,"Demand Zone (DBR)"
    return None

# ── Candle Patterns ───────────────────────────────────────
def _is_doji(c,t=0.1):
    b=abs(c["c"]-c["o"]); r=c["h"]-c["l"]
    return r>0 and b/r<t

def _is_marubozu(c,threshold=0.95):
    b=abs(c["c"]-c["o"]); r=c["h"]-c["l"]
    return r>0 and b/r>=threshold

def _is_harami(c1,c2):
    big=abs(c1["c"]-c1["o"]); sm=abs(c2["c"]-c2["o"])
    c2i=(min(c1["o"],c1["c"])<=c2["o"]<=max(c1["o"],c1["c"]) and
         min(c1["o"],c1["c"])<=c2["c"]<=max(c1["o"],c1["c"]))
    return big>0 and sm<big*0.5 and c2i

def _is_hammer(c):
    b=abs(c["c"]-c["o"]); r=c["h"]-c["l"]
    if r==0 or b==0: return False
    lw=min(c["c"],c["o"])-c["l"]; uw=c["h"]-max(c["c"],c["o"])
    return lw>=2*b and uw<=b*0.5

def _is_shooting_star(c):
    b=abs(c["c"]-c["o"]); r=c["h"]-c["l"]
    if r==0 or b==0: return False
    uw=c["h"]-max(c["c"],c["o"]); lw=min(c["c"],c["o"])-c["l"]
    return uw>=2*b and lw<=b*0.5

def _is_bull_engulf(c1,c2):
    return c1["c"]<c1["o"] and c2["c"]>c2["o"] and c2["o"]<=c1["c"] and c2["c"]>=c1["o"]

def _is_bear_engulf(c1,c2):
    return c1["c"]>c1["o"] and c2["c"]<c2["o"] and c2["o"]>=c1["c"] and c2["c"]<=c1["o"]

def _is_morning_star(c1,c2,c3):
    bb=c1["o"]-c1["c"]>abs(c1["h"]-c1["l"])*0.5
    sm=abs(c2["c"]-c2["o"])<abs(c1["o"]-c1["c"])*0.3
    bu=c3["c"]-c3["o"]>abs(c3["h"]-c3["l"])*0.5
    return bb and sm and bu and c3["c"]>(c1["o"]+c1["c"])/2

def _is_evening_star(c1,c2,c3):
    bu=c1["c"]-c1["o"]>abs(c1["h"]-c1["l"])*0.5
    sm=abs(c2["c"]-c2["o"])<abs(c1["c"]-c1["o"])*0.3
    bb=c3["o"]-c3["c"]>abs(c3["h"]-c3["l"])*0.5
    return bu and sm and bb and c3["c"]<(c1["o"]+c1["c"])/2

def _is_3ws(c1,c2,c3):
    b=lambda c:c["c"]>c["o"]
    return b(c1) and b(c2) and b(c3) and c2["c"]>c1["c"] and c3["c"]>c2["c"]

def _is_3bc(c1,c2,c3):
    b=lambda c:c["c"]<c["o"]
    return b(c1) and b(c2) and b(c3) and c2["c"]<c1["c"] and c3["c"]<c2["c"]

def _is_tweezer_bot(c1,c2,tol=0.0002):
    return c1["c"]<c1["o"] and c2["c"]>c2["o"] and abs(c1["l"]-c2["l"])<=tol

def _is_tweezer_top(c1,c2,tol=0.0002):
    return c1["c"]>c1["o"] and c2["c"]<c2["o"] and abs(c1["h"]-c2["h"])<=tol

def _is_inside_bar(c1,c2):
    return c2["h"]<=c1["h"] and c2["l"]>=c1["l"]

def _is_pin_bar(c,ratio=2.5):
    b=abs(c["c"]-c["o"]); r=c["h"]-c["l"]
    if r==0: return None
    lw=min(c["c"],c["o"])-c["l"]; uw=c["h"]-max(c["c"],c["o"])
    if lw>ratio*b and lw>uw*2: return "CALL"
    if uw>ratio*b and uw>lw*2: return "PUT"
    return None

def session_quality(is_crypto=False):
    h=datetime.datetime.utcnow().hour
    if is_crypto:
        # BTC/ETH شغالين 24/7 — مفيش off-hours
        if 12<=h<21: return 92,"NY Crypto ⚡",1.12
        elif 7<=h<16: return 85,"LON Crypto",1.06
        elif 0<=h<8:  return 78,"Asia Crypto",1.00
        else:         return 75,"Crypto 24/7",0.95
    active=[]
    if 7<=h<16:  active.append("London")
    if 12<=h<21: active.append("NewYork")
    if 0<=h<8 or h>=23: active.append("Tokyo")
    if "London" in active and "NewYork" in active: return 95,"LON+NY ⚡",1.15
    elif "NewYork" in active: return 82,"New York",1.08
    elif "London" in active:  return 78,"London",1.05
    elif "Tokyo" in active:   return 55,"Tokyo",0.90
    else: return 30,"Off-Hours ⚠",0.70

# ══════════════════════════════════════════════════════════
#  V18 — Economic Calendar Filter
# ══════════════════════════════════════════════════════════
class NewsFilter:
    def __init__(self):
        self.events=[]; self.enabled=True; self.status=""
        self._fetch_lock=threading.Lock()
        threading.Thread(target=self._loop,daemon=True).start()

    def _loop(self):
        while True:
            self._fetch(); time.sleep(3600)

    def _fetch(self):
        try:
            url="https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=6) as r:
                data=json.loads(r.read())
            with self._fetch_lock:
                self.events=[e for e in data if e.get("impact") in ("High","3","red")]
        except:
            pass

    def is_blocked(self,currencies=("USD","EUR","GBP","JPY","CAD","AUD","CHF","NZD")):
        if not self.enabled: return False,""
        now=datetime.datetime.utcnow()
        with self._fetch_lock:
            evs=list(self.events)
        for e in evs:
            try:
                ds=e.get("date","")
                if not ds: continue
                ds=ds.replace("Z","+00:00")
                et=datetime.datetime.fromisoformat(ds).replace(tzinfo=None)
                diff=(et-now).total_seconds()
                if e.get("currency","") in currencies and -600<=diff<=300:
                    m=int(diff/60)
                    tag=f"in {m}m" if diff>0 else f"{abs(m)}m ago"
                    return True,f"📰 {e.get('title','News')[:22]} ({tag})"
            except: continue
        return False,""

    def next_event_str(self,currencies=("USD","EUR","GBP","JPY")):
        now=datetime.datetime.utcnow(); upcoming=[]
        with self._fetch_lock:
            evs=list(self.events)
        for e in evs:
            try:
                ds=e.get("date","").replace("Z","+00:00")
                et=datetime.datetime.fromisoformat(ds).replace(tzinfo=None)
                diff=(et-now).total_seconds()
                if 0<diff<7200 and e.get("currency","") in currencies:
                    upcoming.append((diff,e.get("currency",""),e.get("title","?")))
            except: continue
        if not upcoming: return ""
        upcoming.sort(); d,c,t=upcoming[0]
        return f"📅 {c} {t[:18]} {int(d/60)}m"

# ══════════════════════════════════════════════════════════
#  V18 — Telegram Alerts
# ══════════════════════════════════════════════════════════
class TelegramBot:
    def __init__(self):
        self.token=""; self.chat_id=""; self.enabled=False
        self._last_sig=""; self._last_t=0

    def _post(self,msg):
        if not self.token or not self.chat_id: return
        def _go():
            try:
                url=f"https://api.telegram.org/bot{self.token}/sendMessage"
                payload=json.dumps({"chat_id":self.chat_id,"text":msg,"parse_mode":"Markdown"}).encode()
                req=urllib.request.Request(url,data=payload,
                    headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
                urllib.request.urlopen(req,timeout=6)
            except: pass
        threading.Thread(target=_go,daemon=True).start()

    def send_signal(self,direction,conf,reason,pair,bet,cf):
        if not self.enabled: return
        key=f"{direction}{conf}{pair}"
        if key==self._last_sig and time.time()-self._last_t<60: return
        self._last_sig=key; self._last_t=time.time()
        arrow="🟢 ⬆ *CALL*" if direction=="CALL" else "🔴 ⬇ *PUT*"
        stars="★★★" if conf>=85 else ("★★" if conf>=72 else "★")
        msg=(f"🤖 *SilentAegis V18*\n"
             f"{arrow}\n"
             f"💱 `{pair}`  {stars}\n"
             f"📊 Confidence: `{conf}%`\n"
             f"🔗 Confluence: `{cf}` signals\n"
             f"💰 Bet: `${bet}`\n"
             f"📝 `{str(reason)[:70]}`\n"
             f"🕐 `{datetime.datetime.utcnow().strftime('%H:%M:%S')} UTC`")
        self._post(msg)

    def send_result(self,result,direction,pair):
        if not self.enabled: return
        icon="✅" if result=="WIN" else "❌"
        self._post(f"{icon} *{result}* — {direction} on `{pair}`")

# ══════════════════════════════════════════════════════════
#  Order Book Analyzer — Binance depth API
# ══════════════════════════════════════════════════════════
class OrderBookAnalyzer:
    def __init__(self):
        self._data={}; self._last=0; self._interval=8

    def _fetch(self,symbol):
        sym=symbol.replace("BINANCE:","")
        url=f"https://api.binance.com/api/v3/depth?symbol={sym}&limit=20"
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                return json.loads(r.read())
        except: return None

    def update(self,symbol):
        if not symbol.startswith("BINANCE:"): return
        now=time.time()
        if now-self._last<self._interval: return
        self._last=now
        data=self._fetch(symbol)
        if not data: return
        bids=data.get("bids",[]); asks=data.get("asks",[])
        bid_vol=sum(float(b[1]) for b in bids[:10])
        ask_vol=sum(float(a[1]) for a in asks[:10])
        total=bid_vol+ask_vol
        if total==0: return
        ratio=bid_vol/total
        # Find largest walls
        best_bid=max(bids[:20],key=lambda x:float(x[1]),default=[0,0])
        best_ask=max(asks[:20],key=lambda x:float(x[1]),default=[0,0])
        self._data={
            "bid_vol":bid_vol,"ask_vol":ask_vol,"ratio":ratio,
            "wall_buy":float(best_bid[1]),"wall_sell":float(best_ask[1]),
            "wall_buy_px":float(best_bid[0]),"wall_sell_px":float(best_ask[0]),
        }

    def signal(self):
        d=self._data
        if not d: return None,0,"OB:--"
        r=d["ratio"]
        if r>0.68: return "CALL",int(r*100),f"OB:{int(r*100)}%↑"
        if r<0.32: return "PUT", int((1-r)*100),f"OB:{int((1-r)*100)}%↓"
        return None,50,f"OB:{int(r*100)}%"

    def summary(self):
        d=self._data
        if not d: return "OB:--"
        r=d["ratio"]; clr_tag="↑" if r>0.5 else "↓"
        return f"OB:{int(r*100)}%{clr_tag}"

# ══════════════════════════════════════════════════════════
#  Funding Rate Monitor — Binance futures
# ══════════════════════════════════════════════════════════
class FundingRateMonitor:
    def __init__(self):
        self._rate=None; self._last=0; self._interval=30

    def update(self,symbol):
        if not symbol.startswith("BINANCE:"): return
        now=time.time()
        if now-self._last<self._interval: return
        self._last=now
        sym=symbol.replace("BINANCE:","")
        url=f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=1"
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                data=json.loads(r.read())
                if data: self._rate=float(data[0]["fundingRate"])
        except: pass

    def signal(self):
        r=self._rate
        if r is None: return None,0,"FR:--"
        pct=r*100
        if r<-0.08: return "PUT", 82,f"FR:{pct:.3f}% LongSqueeze"
        if r>0.08:  return "CALL",82,f"FR:{pct:.3f}% ShortSqueeze"
        if r<-0.03: return "PUT", 68,f"FR:{pct:.3f}% Bearish"
        if r>0.03:  return "CALL",68,f"FR:{pct:.3f}% Bullish"
        return None,50,f"FR:{pct:.3f}%"

    def summary(self):
        if self._rate is None: return "FR:--"
        return f"FR:{self._rate*100:.3f}%"

# ══════════════════════════════════════════════════════════
#  Open Interest Monitor — Binance futures
# ══════════════════════════════════════════════════════════
class OpenInterestMonitor:
    def __init__(self):
        self._oi=None; self._prev_oi=None; self._last=0; self._interval=20

    def update(self,symbol):
        if not symbol.startswith("BINANCE:"): return
        now=time.time()
        if now-self._last<self._interval: return
        self._last=now
        sym=symbol.replace("BINANCE:","")
        url=f"https://fapi.binance.com/fapi/v1/openInterest?symbol={sym}"
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                data=json.loads(r.read())
                self._prev_oi=self._oi
                self._oi=float(data["openInterest"])
        except: pass

    def signal(self,price_dir):
        if self._oi is None or self._prev_oi is None: return None,0,"OI:--"
        chg=(self._oi-self._prev_oi)/self._prev_oi*100 if self._prev_oi else 0
        if abs(chg)<0.3: return None,50,f"OI:{chg:+.1f}%"
        if chg>1.0 and price_dir=="CALL": return "CALL",78,f"OI+{chg:.1f}% TrendConf"
        if chg>1.0 and price_dir=="PUT":  return "PUT", 78,f"OI+{chg:.1f}% TrendConf"
        if chg<-1.0: return None,52,f"OI{chg:.1f}% Unwind"
        return None,50,f"OI:{chg:+.1f}%"

    def summary(self):
        if self._oi is None: return "OI:--"
        chg=0
        if self._prev_oi: chg=(self._oi-self._prev_oi)/self._prev_oi*100
        return f"OI:{chg:+.1f}%"

# ══════════════════════════════════════════════════════════
#  Volume & VWAP Analyzer — Binance klines
# ══════════════════════════════════════════════════════════
class VolumeAnalyzer:
    def __init__(self):
        self._klines=[]; self._last=0; self._interval=15

    def update(self,symbol,interval="1m",limit=50):
        if not symbol.startswith("BINANCE:"): return
        now=time.time()
        if now-self._last<self._interval: return
        self._last=now
        sym=symbol.replace("BINANCE:","")
        url=f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                self._klines=json.loads(r.read())
        except: pass

    def _vwap(self):
        if len(self._klines)<5: return None
        tpv=sum((float(k[2])+float(k[3])+float(k[4]))/3*float(k[5]) for k in self._klines)
        vol=sum(float(k[5]) for k in self._klines)
        return tpv/vol if vol else None

    def _delta(self):
        if not self._klines: return None
        k=self._klines[-1]
        o,h,l,c,v=float(k[1]),float(k[2]),float(k[3]),float(k[4]),float(k[5])
        rng=h-l
        if rng==0: return 0
        buy_ratio=(c-l)/rng
        return (buy_ratio*2-1)*v  # positive=buying, negative=selling

    def _spike(self):
        if len(self._klines)<10: return False,1.0
        vols=[float(k[5]) for k in self._klines]
        avg=sum(vols[:-1])/len(vols[:-1])
        ratio=vols[-1]/avg if avg>0 else 1
        return ratio>2.5, ratio

    def signal(self,current_price):
        vwap=self._vwap()
        delta=self._delta()
        is_spike,spike_ratio=self._spike()
        signals=[]
        # VWAP signal
        if vwap and current_price:
            gap=(current_price-vwap)/vwap*100
            if gap>0.05:  signals.append(("CALL",74,f"VWAP+{gap:.2f}%"))
            elif gap<-0.05: signals.append(("PUT",74,f"VWAP{gap:.2f}%"))
        # Volume spike
        if is_spike and delta is not None:
            if delta>0: signals.append(("CALL",min(88,72+int(spike_ratio*3)),f"VolSpike↑{spike_ratio:.1f}x"))
            else:       signals.append(("PUT", min(88,72+int(spike_ratio*3)),f"VolSpike↓{spike_ratio:.1f}x"))
        # Delta
        if delta is not None:
            k=self._klines[-1] if self._klines else None
            if k:
                vol=float(k[5])
                d_ratio=delta/vol if vol else 0
                if d_ratio>0.4:  signals.append(("CALL",70,f"Delta+{d_ratio:.2f}"))
                elif d_ratio<-0.4: signals.append(("PUT",70,f"Delta{d_ratio:.2f}"))
        return signals

    def vwap_str(self):
        v=self._vwap(); return f"VWAP:{v:.2f}" if v else "VWAP:--"

# ══════════════════════════════════════════════════════════
#  Multi-Timeframe (Real 5m + 15m from Binance)
# ══════════════════════════════════════════════════════════
class MultiTimeframeReal:
    def __init__(self):
        self._tf={}; self._last={}; self._interval=20

    def _fetch(self,symbol,tf,limit=50):
        sym=symbol.replace("BINANCE:","")
        url=f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={tf}&limit={limit}"
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                return json.loads(r.read())
        except: return None

    def update(self,symbol):
        if not symbol.startswith("BINANCE:"): return
        now=time.time()
        for tf in ("5m","15m","1h"):
            if now-self._last.get(tf,0)<self._interval:
                continue
            klines=self._fetch(symbol,tf)
            if klines:
                self._tf[tf]=klines
                self._last[tf]=now

    def _trend(self,klines):
        if not klines or len(klines)<26: return None
        closes=[float(k[4]) for k in klines]
        e8=_ema(closes,8); e21=_ema(closes,21)
        if not e8 or not e21: return None
        if e8>e21*1.001: return "CALL"
        if e8<e21*0.999: return "PUT"
        return None

    def signal(self):
        trends={tf:self._trend(self._tf.get(tf)) for tf in ("5m","15m","1h")}
        valid=[v for v in trends.values() if v]
        if not valid: return None,50,"MTF:--"
        calls=valid.count("CALL"); puts=valid.count("PUT")
        if calls==3: return "CALL",88,"MTF 5m+15m+1h CALL ✓✓✓"
        if puts==3:  return "PUT", 88,"MTF 5m+15m+1h PUT ✓✓✓"
        if calls==2: return "CALL",72,f"MTF 2/3 CALL"
        if puts==2:  return "PUT", 72,f"MTF 2/3 PUT"
        return None,50,"MTF:Mixed"

    def summary(self):
        trends={tf:self._trend(self._tf.get(tf)) for tf in ("5m","15m","1h")}
        def sym(t): return ("↑" if t=="CALL" else "↓") if t else "─"
        return f"5m{sym(trends.get('5m'))} 15m{sym(trends.get('15m'))} 1h{sym(trends.get('1h'))}"

# ══════════════════════════════════════════════════════════
#  Whale Tracker — large trades on Binance
# ══════════════════════════════════════════════════════════
class WhaleTracker:
    def __init__(self):
        self._trades=[]; self._last=0; self._interval=10
        self._WHALE_USD=500_000  # $500K+

    def update(self,symbol):
        if not symbol.startswith("BINANCE:"): return
        now=time.time()
        if now-self._last<self._interval: return
        self._last=now
        sym=symbol.replace("BINANCE:","")
        url=f"https://api.binance.com/api/v3/trades?symbol={sym}&limit=100"
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                trades=json.loads(r.read())
                self._trades=[t for t in trades
                              if float(t["price"])*float(t["qty"])>self._WHALE_USD]
        except: pass

    def signal(self):
        if not self._trades: return None,0,"Whale:--"
        buys=sum(1 for t in self._trades if not t.get("isBuyerMaker",True))
        sells=len(self._trades)-buys
        total=len(self._trades)
        if total==0: return None,0,"Whale:--"
        if buys>=sells*2: return "CALL",80,f"Whale↑ {buys}B/{sells}S"
        if sells>=buys*2: return "PUT", 80,f"Whale↓ {sells}S/{buys}B"
        return None,55,f"Whale:{buys}B/{sells}S"

    def summary(self):
        if not self._trades: return "Whale:--"
        buys=sum(1 for t in self._trades if not t.get("isBuyerMaker",True))
        sells=len(self._trades)-buys
        return f"🐋{buys}B/{sells}S"

# ══════════════════════════════════════════════════════════
#  Fear & Greed Index — alternative.me
# ══════════════════════════════════════════════════════════
class FearGreedIndex:
    def __init__(self):
        self._val=None; self._cls=None; self._last=0; self._interval=300

    def update(self):
        now=time.time()
        if now-self._last<self._interval: return
        self._last=now
        try:
            with urllib.request.urlopen("https://api.alternative.me/fng/?limit=1",timeout=4) as r:
                data=json.loads(r.read())["data"][0]
                self._val=int(data["value"])
                self._cls=data["value_classification"]
        except: pass

    def signal(self):
        v=self._val
        if v is None: return None,0,"F&G:--"
        if v<=15:  return "CALL",82,f"F&G:ExtremeFear({v})"
        if v<=25:  return "CALL",72,f"F&G:Fear({v})"
        if v>=85:  return "PUT", 82,f"F&G:ExtremeGreed({v})"
        if v>=75:  return "PUT", 70,f"F&G:Greed({v})"
        return None,55,f"F&G:{v}({self._cls})"

    def summary(self):
        if self._val is None: return "F&G:--"
        icon="😱" if self._val<25 else ("🤑" if self._val>75 else "😐")
        return f"{icon}F&G:{self._val}"

# ══════════════════════════════════════════════════════════
#  BTC/DXY Correlation Filter
# ══════════════════════════════════════════════════════════
class DXYCorrelation:
    def __init__(self):
        self._dxy=None; self._prev_dxy=None; self._last=0; self._interval=60

    def update(self):
        now=time.time()
        if now-self._last<self._interval: return
        self._last=now
        # DXY from Yahoo Finance stooq
        try:
            url="https://stooq.com/q/l/?s=dx.f&f=sd2t2ohlcv&h&e=csv"
            with urllib.request.urlopen(url,timeout=4) as r:
                lines=r.read().decode().strip().split("\n")
                if len(lines)>=2:
                    row=lines[1].split(",")
                    self._prev_dxy=self._dxy
                    self._dxy=float(row[4])  # close
        except: pass

    def signal(self,btc_dir):
        if self._dxy is None or self._prev_dxy is None: return None,0,"DXY:--"
        chg=(self._dxy-self._prev_dxy)/self._prev_dxy*100
        if abs(chg)<0.05: return None,50,f"DXY:{self._dxy:.2f}"
        # DXY up → BTC down (inverse correlation)
        if chg>0.15 and btc_dir=="CALL":
            return "PUT",70,f"DXY↑{chg:.2f}% BTC↓"
        if chg<-0.15 and btc_dir=="PUT":
            return "CALL",70,f"DXY↓{chg:.2f}% BTC↑"
        return None,55,f"DXY:{chg:+.2f}%"

    def summary(self):
        if self._dxy is None: return "DXY:--"
        return f"DXY:{self._dxy:.2f}"

# ══════════════════════════════════════════════════════════
#  Self-Learning Weight Adjuster
# ══════════════════════════════════════════════════════════
class SelfLearner:
    def __init__(self,engine):
        self._engine=engine
        self._strat_results={}  # {strat: [True/False, ...]}
        self._last_adjust=0; self._adjust_interval=300  # every 5min

    def record(self,strat,won):
        if strat not in self._strat_results:
            self._strat_results[strat]=[]
        self._strat_results[strat].append(won)
        # Keep last 50 results per strategy
        self._strat_results[strat]=self._strat_results[strat][-50:]
        self._maybe_adjust()

    def _maybe_adjust(self):
        now=time.time()
        if now-self._last_adjust<self._adjust_interval: return
        self._last_adjust=now
        for strat,results in self._strat_results.items():
            if len(results)<10: continue
            wr=sum(results)/len(results)
            # Adjust weight: high WR gets boost, low WR gets penalty
            mult=1.0+(wr-0.55)*0.6  # WR=70% → 1.09, WR=40% → 0.91
            mult=max(0.6,min(1.4,mult))
            for W in (self._engine.W, self._engine.W_CRYPTO):
                if strat in W:
                    W[strat]=round(W[strat]*mult,3)

    def summary(self):
        if not self._strat_results: return "Learn:0"
        total=sum(len(v) for v in self._strat_results.values())
        return f"Learn:{total}trades"

# ══════════════════════════════════════════════════════════
#  Adaptive Expiry Suggester
# ══════════════════════════════════════════════════════════
class AdaptiveExpiry:
    def suggest(self,candles,current_dur):
        if len(candles)<15: return current_dur,""
        atr=_atr(candles,14)
        if not atr: return current_dur,""
        closes=[c["c"] for c in candles]
        price=closes[-1]; atr_pct=atr/price*100
        # Low volatility → shorter expiry; High volatility → longer expiry
        if atr_pct<0.08: sug=30; note="ATR low→30s"
        elif atr_pct<0.18: sug=60; note="ATR med→1m"
        elif atr_pct<0.35: sug=120; note="ATR hi→2m"
        else: sug=180; note="ATR v.hi→3m"
        return sug,note

# ══════════════════════════════════════════════════════════
#  Smart Entry Timer — best moment within candle
# ══════════════════════════════════════════════════════════
class SmartEntryTimer:
    """Enter in first 10s or last 5s of candle — avoid noisy middle."""
    def is_good_entry(self,builder):
        elapsed=builder._elapsed() if hasattr(builder,"_elapsed") else 0
        dur=builder.dur
        if dur==0: return True
        pos=elapsed/dur
        return pos<0.18 or pos>0.88  # first 18% or last 12% of candle

# ══════════════════════════════════════════════════════════
#  Regime Detector — identifies market type for strategy selection
# ══════════════════════════════════════════════════════════
class RegimeDetector:
    TREND=1; RANGE=0; VOLATILE=2

    def detect(self,candles):
        if len(candles)<22: return self.RANGE
        closes=[c["c"] for c in candles]
        adx=_adx(candles,14)
        up,mid,lo=_bollinger(closes,20)
        bw=(up-lo)/mid if mid and mid!=0 else 0
        e8=_ema(closes,8); e21=_ema(closes,21)
        emas_aligned=e8 and e21 and abs(e8-e21)/e21>0.0008
        if bw>0.045: return self.VOLATILE
        if adx and adx>25 and emas_aligned: return self.TREND
        return self.RANGE

    # Per-regime weight multipliers
    TREND_MULT={
        "smc":1.3,"candle":1.2,"div":1.4,"sr":0.9,"mtf":1.5,
        "ichi":1.3,"ema":1.5,"fib":1.1,"bb":0.5,"macd":1.5,
        "rsi":0.5,"mom":1.5,"ha":1.2,"sto":0.3,"atr":1.3,
        "cci":0.5,"psar":1.3,"super":1.5,"will":0.3,
    }
    RANGE_MULT={
        "smc":1.0,"candle":1.2,"div":1.1,"sr":1.5,"mtf":0.6,
        "ichi":0.8,"ema":0.7,"fib":1.3,"bb":1.5,"macd":0.7,
        "rsi":1.5,"mom":0.6,"ha":1.0,"sto":1.5,"atr":0.8,
        "cci":1.5,"psar":0.8,"super":0.6,"will":1.5,
    }
    VOLATILE_MULT={k:0.65 for k in ["smc","candle","div","sr","mtf","ichi","ema","fib",
                                     "bb","macd","rsi","mom","ha","sto","atr","cci",
                                     "psar","super","will"]}

    def get_mult(self,regime):
        if regime==self.TREND:    return self.TREND_MULT
        if regime==self.VOLATILE: return self.VOLATILE_MULT
        return self.RANGE_MULT

# ══════════════════════════════════════════════════════════
#  Pattern Validator — checks if this setup worked historically
# ══════════════════════════════════════════════════════════
class PatternValidator:
    """
    Looks at the last N candles and checks: when the bot gave a
    strong signal in the past, how often was it correct?
    Returns a confidence multiplier based on recent accuracy.
    """
    def __init__(self):
        self._cache={}; self._last_ts=0

    def validate(self,engine,candles,cur_dir,crypto=False):
        """
        Replay the last 30 closed candles, see what signal the engine
        would have given, and check if the next candle confirmed it.
        Returns (accuracy 0-1, sample_count).
        """
        now=time.time()
        cache_key=f"{cur_dir}_{len(candles)}_{crypto}"
        # Cache for 60s to avoid heavy recompute every tick
        if now-self._last_ts<60 and cache_key in self._cache:
            return self._cache[cache_key]

        lookback=min(35,len(candles)-10)
        if lookback<8:
            return 0.5,0

        wins=0; total=0
        # Replay signals on past windows
        for i in range(len(candles)-lookback, len(candles)-1):
            window=candles[max(0,i-40):i+1]
            if len(window)<8: continue
            try:
                d,c,r,s,cf=engine.run_all(window,crypto=crypto)
            except Exception:
                continue
            if c<62 or cf<2: continue  # only count confident signals
            next_c=candles[i+1]["c"]; curr_c=candles[i]["c"]
            actual="CALL" if next_c>curr_c else "PUT"
            if d==actual: wins+=1
            total+=1

        acc=wins/total if total>=3 else 0.50
        self._cache[cache_key]=(acc,total)
        self._last_ts=now
        return acc,total

# ══════════════════════════════════════════════════════════
#  Strategy Engine — 22 signal sources
# ══════════════════════════════════════════════════════════
class StrategyEngine:
    _regime_det=RegimeDetector()

    # Forex weights
    W={
        "smc":2.5,"candle":2.2,"div":2.0,"sr":2.0,"mtf":2.1,
        "ichi":1.9,"ema":1.9,"fib":1.8,"bb":1.8,"macd":1.7,
        "rsi":1.6,"mom":1.6,"ha":1.6,"sto":1.5,"atr":1.5,
        "cci":1.5,"psar":1.4,"super":1.5,"will":1.4,
    }
    # Crypto weights — trend-following أعلى، mean-reversion أقل
    W_CRYPTO={
        "smc":2.6,"candle":2.3,"div":2.4,"sr":2.1,"mtf":2.6,
        "ichi":2.1,"ema":2.4,"fib":2.0,"bb":1.1,"macd":2.1,
        "rsi":1.1,"mom":2.1,"ha":1.9,"sto":0.8,"atr":2.0,
        "cci":0.9,"psar":1.7,"super":2.2,"will":0.8,
    }

    def run_all(self,candles,crypto=False):
        if len(candles)<8: return "CALL",52,"Warming Up","System",0
        closes=[c["c"] for c in candles]
        highs =[c["h"] for c in candles]
        lows  =[c["l"] for c in candles]
        c1,c2,c3,c4=candles[-4],candles[-3],candles[-2],candles[-1]

        # Detect market regime — determines which strategies to amplify
        regime=self._regime_det.detect(candles)
        regime_mult=self._regime_det.get_mult(regime)
        regime_names={RegimeDetector.TREND:"📈Trend",
                      RegimeDetector.RANGE:"📊Range",
                      RegimeDetector.VOLATILE:"⚡Volatile"}
        self.last_regime=regime_names.get(regime,"?")

        # Crypto يحتاج ADX أقوى (25+) بدل 18
        adx_val=_adx(candles,14)
        adx_thresh=25 if crypto else 18
        adx_ok=adx_val is None or adx_val>=adx_thresh

        base_W=self.W_CRYPTO if crypto else self.W
        # Apply regime multiplier on top of base weights
        W={k:base_W[k]*regime_mult.get(k,1.0) for k in base_W}
        results=[]

        def add(sig,group):
            if sig: results.append((*sig,group,W[group]))

        # SMC — يشتغل بنفس الكفاءة مع الـ Crypto
        add(_liquidity_sweep(candles),"smc"); add(_order_blocks(candles),"smc")
        add(_fair_value_gap(candles),"smc"); add(_market_structure(candles),"smc")
        add(_supply_demand_zones(candles),"smc")
        # Divergence — أهم مع crypto
        add(_rsi_divergence(candles,closes),"div")
        add(_macd_divergence(closes),"div")
        # Candle Patterns
        add(self._candle_patterns(candles,c1,c2,c3,c4),"candle")
        # Indicators — crypto-aware thresholds
        add(self._rsi_strat(closes,crypto),"rsi")
        add(self._ema_cross(closes),"ema")
        add(self._macd_strat(closes),"macd")
        add(self._bb_strat(closes,crypto),"bb")
        add(self._stoch_strat(highs,lows,closes,crypto),"sto")
        add(self._sr_pivot(closes,highs,lows,candles),"sr")
        add(self._williams_strat(highs,lows,closes,crypto),"will")
        add(self._cci_strat(highs,lows,closes),"cci")
        add(self._momentum_trend(closes,crypto),"mom")
        add(self._atr_breakout(candles,closes,crypto),"atr")
        add(self._mtf_trend(closes),"mtf")
        # Advanced
        ichi=_ichimoku(candles)
        if ichi:
            bull,bear,_,_=ichi
            if bull: add(("CALL",85,"Ichimoku Bull"),"ichi")
            elif bear: add(("PUT",85,"Ichimoku Bear"),"ichi")
        add(_fibonacci(candles),"fib")
        # Supertrend: multiplier أكبر للـ crypto عشان BTC volatile
        add(_supertrend(candles,period=10,multiplier=4.5 if crypto else 3.0),"super")
        add(_parabolic_sar(candles),"psar")
        add(_heikin_ashi_trend(candles),"ha")

        if not results:
            micro="CALL" if closes[-1]>=closes[-2] else "PUT"
            return micro,52,"Live Pulse","Micro",0

        # ── Volatile market: no trade unless very strong setup ───────────────
        if regime==RegimeDetector.VOLATILE:
            high_conf=[r for r in results if r[1]>=85]
            if len(high_conf)<3:
                return ("CALL" if closes[-1]>closes[-2] else "PUT"),52,
                f"⚡ Volatile — Wait","Wait",0

        # ── Trend Alignment Filter ──────────────────────────────────────────
        # Determine dominant short-term trend from EMAs + EMA50
        trend_dir=None
        if len(closes)>=22:
            e8=_ema(closes,8); e21=_ema(closes,21)
            if e8 and e21:
                if e8>e21*1.0005:   trend_dir="CALL"
                elif e8<e21*0.9995: trend_dir="PUT"
        if len(closes)>=51:
            e50=_ema(closes,50)
            if e50:
                if closes[-1]<e50 and trend_dir=="CALL": trend_dir="PUT"
                if closes[-1]>e50 and trend_dir=="PUT":  trend_dir="CALL"
        # ───────────────────────────────────────────────────────────────────

        call_w=put_w=0.0; call_r=[]; put_r=[]; bc_call=bc_put=0
        call_count=put_count=0
        # In trending market: heavy penalty for counter-trend signals
        # In ranging market: lighter penalty (reversals are expected)
        if regime==RegimeDetector.TREND:
            counter_penalty=0.35 if crypto else 0.50
        else:
            counter_penalty=0.65 if crypto else 0.75

        for d,conf,reason,name,w in results:
            score=(conf/100)*w
            if not adx_ok: score*=0.80
            if trend_dir and d!=trend_dir:
                score*=counter_penalty
            if d=="CALL":
                call_w+=score; call_r.append(f"{name}:{conf}%")
                bc_call=max(bc_call,conf); call_count+=1
            else:
                put_w+=score; put_r.append(f"{name}:{conf}%")
                bc_put=max(bc_put,conf); put_count+=1

        total=call_w+put_w
        if total==0: return "CALL",52,"No Signal","Market",0

        conf_cap=85 if crypto else 93
        # Trending market: need fewer signals (trend is your friend)
        # Ranging market: need more confirmation
        if regime==RegimeDetector.TREND:
            bonus_tiers=[(5,8),(4,5),(3,3)] if crypto else [(5,8),(4,5),(3,3)]
            min_ratio=0.58
        else:
            bonus_tiers=[(6,6),(5,4),(4,2)] if crypto else [(5,6),(4,4),(3,2)]
            min_ratio=0.62

        if call_w>=put_w:
            ratio=call_w/total
            if ratio<min_ratio: return "CALL",52,f"Weak {self.last_regime}","Wait",call_count
            con=int(ratio*100); fin=min(conf_cap,int(con*0.5+bc_call*0.5))
            for thresh,bonus in bonus_tiers:
                if call_count>=thresh: fin=min(conf_cap,fin+bonus); break
            regime_tag=f"[{self.last_regime}]"
            strat=call_r[0].split(":")[0] if call_r else "Multi"
            return "CALL",fin,f"{regime_tag} "+" | ".join(call_r[:3]),strat,call_count
        else:
            ratio=put_w/total
            if ratio<min_ratio: return "PUT",52,f"Weak {self.last_regime}","Wait",put_count
            con=int(ratio*100); fin=min(conf_cap,int(con*0.5+bc_put*0.5))
            for thresh,bonus in bonus_tiers:
                if put_count>=thresh: fin=min(conf_cap,fin+bonus); break
            regime_tag=f"[{self.last_regime}]"
            strat=put_r[0].split(":")[0] if put_r else "Multi"
            return "PUT",fin,f"{regime_tag} "+" | ".join(put_r[:3]),strat,put_count

    def _candle_patterns(self,cs,c1,c2,c3,c4):
        if len(cs)>=4:
            if _is_morning_star(cs[-4],cs[-3],cs[-2]): return "CALL",90,"Morning Star ★★★"
            if _is_evening_star(cs[-4],cs[-3],cs[-2]): return "PUT", 90,"Evening Star ★★★"
        if _is_3ws(c2,c3,c4): return "CALL",87,"3 White Soldiers"
        if _is_3bc(c2,c3,c4): return "PUT", 87,"3 Black Crows"
        if _is_bull_engulf(c3,c4): return "CALL",84,"Bull Engulfing"
        if _is_bear_engulf(c3,c4): return "PUT", 84,"Bear Engulfing"
        pb=_is_pin_bar(c4)
        if pb=="CALL": return "CALL",83,"Pin Bar Bull"
        if pb=="PUT":  return "PUT", 83,"Pin Bar Bear"
        if _is_tweezer_bot(c3,c4): return "CALL",80,"Tweezer Bottom"
        if _is_tweezer_top(c3,c4): return "PUT", 80,"Tweezer Top"
        if _is_marubozu(c4) and c4["c"]>c4["o"]: return "CALL",79,"Marubozu Bull"
        if _is_marubozu(c4) and c4["c"]<c4["o"]: return "PUT", 79,"Marubozu Bear"
        if _is_harami(c3,c4):
            return ("CALL",73,"Bullish Harami") if c4["c"]>c4["o"] else ("PUT",73,"Bearish Harami")
        if _is_hammer(c4): return "CALL",77,"Hammer"
        if _is_shooting_star(c4): return "PUT",77,"Shooting Star"
        if _is_inside_bar(c3,c4):
            up=cs[-5]["c"]<cs[-3]["c"] if len(cs)>=5 else True
            return ("CALL",72,"Inside Bar↑") if up else ("PUT",72,"Inside Bar↓")
        if _is_doji(c3):
            if c2["c"]<c2["o"] and c4["c"]>c4["o"]: return "CALL",73,"Doji Rev↑"
            if c2["c"]>c2["o"] and c4["c"]<c4["o"]: return "PUT", 73,"Doji Rev↓"
        return None

    def _rsi_strat(self,closes,crypto=False):
        if len(closes)<15: return None
        rsi=_rsi(closes,14); rp=_rsi(closes[:-1],14)
        if rsi is None: return None
        if crypto:
            # BTC trends strongly — only extreme levels are meaningful
            if rsi<15: return "CALL",90,f"RSI Extreme OS {rsi:.0f}"
            if rsi>85: return "PUT", 90,f"RSI Extreme OB {rsi:.0f}"
            if rsi<20: return "CALL",84,f"RSI Oversold {rsi:.0f}"
            if rsi>80: return "PUT", 84,f"RSI Overbought {rsi:.0f}"
            if rp and rp<50<=rsi: return "CALL",70,"RSI Cross50↑"
            if rp and rp>50>=rsi: return "PUT", 70,"RSI Cross50↓"
        else:
            if rsi<22: return "CALL",88,f"RSI Oversold {rsi:.0f}"
            if rsi>78: return "PUT", 88,f"RSI Overbought {rsi:.0f}"
            if rsi<30: return "CALL",80,f"RSI Low {rsi:.0f}"
            if rsi>70: return "PUT", 80,f"RSI High {rsi:.0f}"
            if rp and rp<50<=rsi: return "CALL",72,"RSI Cross50↑"
            if rp and rp>50>=rsi: return "PUT", 72,"RSI Cross50↓"
        return None

    def _ema_cross(self,closes):
        if len(closes)<26: return None
        fn=_ema(closes,8); sn=_ema(closes,21)
        fp=_ema(closes[:-1],8); sp=_ema(closes[:-1],21); e50=_ema(closes,50)
        if None in (fn,sn,fp,sp): return None
        gap=abs(fn-sn)/sn*100
        tu=e50 and closes[-1]>e50; td=e50 and closes[-1]<e50
        if fp<=sp and fn>sn:
            c=min(92,72+int(gap*1200)); c=min(95,c+5) if tu else c
            return "CALL",c,f"EMA Cross↑ {gap:.3f}%"
        if fp>=sp and fn<sn:
            c=min(92,72+int(gap*1200)); c=min(95,c+5) if td else c
            return "PUT",c,f"EMA Cross↓ {gap:.3f}%"
        if fn>sn and gap>0.025 and tu: return "CALL",68,"EMA Uptrend"
        if fn<sn and gap>0.025 and td: return "PUT", 68,"EMA Downtrend"
        return None

    def _macd_strat(self,closes):
        if len(closes)<35: return None
        k12,k26,ks=2/13,2/27,2/10
        e12=sum(closes[:12])/12; e26=sum(closes[:26])/26
        for p in closes[12:]: e12=p*k12+e12*(1-k12)
        for p in closes[26:]: e26=p*k26+e26*(1-k26)
        mn=e12-e26; ms=[]
        for i in range(26,len(closes)):
            t12=sum(closes[:12])/12; t26=sum(closes[:26])/26
            for pp in closes[12:i+1]: t12=pp*k12+t12*(1-k12)
            for pp in closes[26:i+1]: t26=pp*k26+t26*(1-k26)
            ms.append(t12-t26)
        if len(ms)<9: return None
        sig=sum(ms[:9])/9
        for mv in ms[9:]: sig=mv*ks+sig*(1-ks)
        hn=mn-sig; hp=ms[-2]-sig if len(ms)>=2 else 0
        if hp<=0<hn: return "CALL",83,"MACD Cross↑"
        if hp>=0>hn: return "PUT", 83,"MACD Cross↓"
        if hn>0 and hn>hp: return "CALL",66,"MACD Mom↑"
        if hn<0 and hn<hp: return "PUT", 66,"MACD Mom↓"
        return None

    def _bb_strat(self,closes,crypto=False):
        if len(closes)<21: return None
        up,mid,lo=_bollinger(closes,20)
        if None in (up,mid,lo): return None
        p=closes[-1]; bw=(up-lo)/mid
        if crypto:
            # BTC walks the band — require bounce confirmation (price was outside, now moving back)
            if closes[-2]<=lo and p>lo: return "CALL",min(88,72+int(bw*500)),"BB Bounce↑"
            if closes[-2]>=up and p<up: return "PUT", min(88,72+int(bw*500)),"BB Bounce↓"
            if closes[-2]<mid<=p and p<up: return "CALL",63,"BB Mid↑"
            if closes[-2]>mid>=p and p>lo: return "PUT", 63,"BB Mid↓"
        else:
            if p<=lo: return "CALL",min(92,74+int(bw*600)),"BB Lower"
            if p>=up: return "PUT", min(92,74+int(bw*600)),"BB Upper"
            if closes[-2]<mid<=p: return "CALL",66,"BB Mid↑"
            if closes[-2]>mid>=p: return "PUT", 66,"BB Mid↓"
        return None

    def _stoch_strat(self,highs,lows,closes,crypto=False):
        if len(closes)<14: return None
        k=_stochastic(highs,lows,closes,14)
        if k is None: return None
        if crypto:
            # BTC needs extreme levels to confirm reversals
            if k<10: return "CALL",86,f"Stoch Extreme OS {k:.0f}"
            if k>90: return "PUT", 86,f"Stoch Extreme OB {k:.0f}"
            if k<15: return "CALL",76,f"Stoch Oversold {k:.0f}"
            if k>85: return "PUT", 76,f"Stoch Overbought {k:.0f}"
        else:
            if k<15: return "CALL",84,f"Stoch Oversold {k:.0f}"
            if k>85: return "PUT", 84,f"Stoch Overbought {k:.0f}"
            if k<25: return "CALL",76,f"Stoch Low {k:.0f}"
            if k>75: return "PUT", 76,f"Stoch High {k:.0f}"
        return None

    def _sr_pivot(self,closes,highs,lows,candles):
        if len(closes)<20: return None
        pp,r1,s1=_pivot_points(candles); p=closes[-1]
        sup=min(closes[-30:]) if len(closes)>=30 else min(closes)
        res=max(closes[-30:]) if len(closes)>=30 else max(closes)
        rng=res-sup
        if rng==0: return None
        m=rng*0.035
        if pp and s1 and abs(p-s1)<m*1.5: return "CALL",85,"Pivot S1"
        if pp and r1 and abs(p-r1)<m*1.5: return "PUT", 85,"Pivot R1"
        if p<=sup+m: return "CALL",84,f"Support"
        if p>=res-m: return "PUT", 84,f"Resistance"
        return None

    def _williams_strat(self,highs,lows,closes,crypto=False):
        if len(closes)<14: return None
        wr=_williams_r(highs,lows,closes,14)
        if wr is None: return None
        if crypto:
            # Tighter extremes for BTC
            if wr<-92: return "CALL",84,f"Williams Extreme OS {wr:.0f}"
            if wr>-8:  return "PUT", 84,f"Williams Extreme OB {wr:.0f}"
            if wr<-85: return "CALL",76,f"Williams OS {wr:.0f}"
            if wr>-15: return "PUT", 76,f"Williams OB {wr:.0f}"
        else:
            if wr<-85: return "CALL",82,f"Williams OS {wr:.0f}"
            if wr>-15: return "PUT", 82,f"Williams OB {wr:.0f}"
        return None

    def _cci_strat(self,highs,lows,closes):
        if len(closes)<14: return None
        cci=_cci(highs,lows,closes,14)
        if cci is None: return None
        if cci<-150: return "CALL",82,f"CCI OS {cci:.0f}"
        if cci>+150: return "PUT", 82,f"CCI OB {cci:.0f}"
        if cci<-100: return "CALL",72,f"CCI Low {cci:.0f}"
        if cci>+100: return "PUT", 72,f"CCI High {cci:.0f}"
        return None

    def _momentum_trend(self,closes,crypto=False):
        if len(closes)<12: return None
        mom=_momentum(closes,10)
        if mom is None: return None
        e8=_ema(closes,8); e21=_ema(closes,21)
        au=e8 and e21 and e8>e21; ad=e8 and e21 and e8<e21
        # BTC needs stronger momentum confirmation (0.15% vs 0.04%)
        thresh=0.15 if crypto else 0.04
        if mom>thresh and au:  return "CALL",78 if crypto else 74,f"Momentum↑ {mom:.2f}%"
        if mom<-thresh and ad: return "PUT", 78 if crypto else 74,f"Momentum↓ {mom:.2f}%"
        return None

    def _atr_breakout(self,candles,closes,crypto=False):
        if len(candles)<16: return None
        atr=_atr(candles,14)
        if not atr or atr==0: return None
        mv=abs(closes[-1]-closes[-2]); ratio=mv/atr
        # BTC: 1.5x threshold (lower, since BTC makes frequent big moves)
        thresh=1.5 if crypto else 2.0
        if ratio>thresh:
            d="CALL" if closes[-1]>closes[-2] else "PUT"
            return d,min(90,70+int(ratio*5)),f"ATR Breakout {ratio:.1f}x"
        return None

    def _mtf_trend(self,closes):
        if len(closes)<55: return None
        e8=_ema(closes,8); e21=_ema(closes,21); e50=_ema(closes,50)
        if None in (e8,e21,e50): return None
        if e8>e21>e50: return "CALL",min(88,68+int((e8-e50)/e50*50000)),f"MTF Bull"
        if e8<e21<e50: return "PUT", min(88,68+int((e50-e8)/e50*50000)),f"MTF Bear"
        return None

# ══════════════════════════════════════════════════════════
#  Risk Manager
# ══════════════════════════════════════════════════════════
class RiskManager:
    def __init__(self):
        self.balance=1000.0; self.base_bet=10.0; self.peak_balance=1000.0
        self.daily_loss=0.0; self.daily_profit=0.0
        self.max_daily_loss=0.20; self.daily_profit_tgt=0.10
        self.consecutive_L=0; self.martingale_lvl=0
        self.circuit_break=False; self.cb_until=None; self.profit_locked=False
        self.total_trades=0; self.total_wins=0; self.hourly_wins={}

    def get_bet(self,conf,smult,confluence):
        if self.circuit_break:
            now=datetime.datetime.utcnow()
            if self.cb_until and now<self.cb_until:
                mins=int((self.cb_until-now).seconds/60)
                return 0,f"⛔ Circuit Breaker ({mins}m)"
            self.circuit_break=False; self.consecutive_L=0; self.martingale_lvl=0
        if self.daily_loss>=self.balance*self.max_daily_loss:
            return 0,"⛔ Daily Loss Limit"
        if self.profit_locked:
            return 0,"✅ Daily Target Locked"
        if conf>=88: sm=1.8
        elif conf>=82: sm=1.5
        elif conf>=75: sm=1.2
        elif conf>=68: sm=1.0
        else: sm=0.6
        if confluence>=6: sm*=1.2
        elif confluence>=4: sm*=1.1
        if self.consecutive_L>=2: sm*=0.8
        dd=self.drawdown()
        if dd>15: sm*=0.5
        elif dd>10: sm*=0.7
        bet=self.base_bet*sm*smult
        if self.martingale_lvl==1: bet*=2.0
        elif self.martingale_lvl>=2: bet*=4.0
        bet=min(bet,self.balance*0.05); bet=max(bet,1.0)
        return round(bet,1),""

    def record_result(self,result,bet):
        h=datetime.datetime.utcnow().hour
        if h not in self.hourly_wins: self.hourly_wins[h]=[0,0]
        if result=="WIN":
            profit=bet*0.87; self.balance+=profit; self.daily_profit+=profit
            self.peak_balance=max(self.peak_balance,self.balance)
            self.consecutive_L=0; self.martingale_lvl=0; self.total_wins+=1
            self.hourly_wins[h][0]+=1
            if self.daily_profit>=self.balance*self.daily_profit_tgt:
                self.profit_locked=True
        else:
            self.balance-=bet; self.daily_loss+=bet; self.consecutive_L+=1
            if self.consecutive_L>=2: self.martingale_lvl=min(self.martingale_lvl+1,2)
            if self.consecutive_L>=3:
                self.circuit_break=True
                self.cb_until=datetime.datetime.utcnow()+datetime.timedelta(minutes=15)
            self.hourly_wins[h][1]+=1
        self.total_trades+=1

    def winrate(self):
        return self.total_wins/self.total_trades*100 if self.total_trades else 0.0

    def drawdown(self):
        return (self.peak_balance-self.balance)/self.peak_balance*100 if self.peak_balance else 0.0

    def best_hour(self):
        best=None; bwr=0
        for h,(w,l) in self.hourly_wins.items():
            if w+l>=3:
                wr=w/(w+l)*100
                if wr>bwr: bwr=wr; best=h
        return f"⭐ Best:{best:02d}:00 ({bwr:.0f}%)" if best else ""

    def status_line(self):
        ic="🔴" if self.circuit_break else ("🟡" if self.martingale_lvl>0 else ("✅" if self.profit_locked else "🟢"))
        return f"{ic} ${self.balance:.0f} WR:{self.winrate():.0f}% DD:{self.drawdown():.1f}%"

# ══════════════════════════════════════════════════════════
#  V18 — ML Win Predictor
# ══════════════════════════════════════════════════════════
class MLPredictor:
    def __init__(self,brain,risk):
        self.brain=brain; self.risk=risk

    def predict(self,strat,conf,cf,sq,adx_val):
        conf_s=conf/100
        wr_s=self.brain.get_wr(strat)/100
        h=datetime.datetime.utcnow().hour
        hw=self.risk.hourly_wins.get(h,[0,0])
        hr_s=hw[0]/sum(hw) if sum(hw)>=3 else 0.55
        adx_s=min(1.0,(adx_val or 20)/40)
        sess_s=sq/100; cf_s=min(1.0,cf/6)
        prob=(conf_s*0.30 + wr_s*0.25 + hr_s*0.15 +
              adx_s*0.15 + sess_s*0.10 + cf_s*0.05)
        adjusted=int(prob*100)
        final=int(conf*0.65+adjusted*0.35)
        return min(95,max(45,final))

# ══════════════════════════════════════════════════════════
#  V18 — Multi-Pair Scanner
# ══════════════════════════════════════════════════════════
class MultiPairScanner:
    def __init__(self,engine):
        self.engine=engine
        self.results={}; self.builders={n:CandleBuilder(60) for n in SCAN_SYMS}
        threading.Thread(target=self._loop,daemon=True).start()

    def _loop(self):
        while True:
            for name,sym in SCAN_SYMS.items():
                try:
                    p=live_price(sym)
                    if p:
                        self.builders[name].feed(p)
                        cs=self.builders[name].candles()
                        if len(cs)>=8:
                            d,c,r,s,cf=self.engine.run_all(cs)
                            self.results[name]=(d,c,s,cf)
                except: pass
                time.sleep(0.8)
            time.sleep(8)

    def summary(self,n=5):
        if not self.results: return "Scanning pairs..."
        ranked=sorted(self.results.items(),key=lambda x:x[1][1],reverse=True)
        parts=[]
        for name,(d,c,s,cf) in ranked[:n]:
            arrow="▲" if d=="CALL" else "▼"
            clr="+" if d=="CALL" else "-"
            parts.append(f"{name[:6]}{arrow}{c}%[{cf}]")
        return "  ".join(parts)

    def best(self):
        if not self.results: return None
        ranked=sorted(self.results.items(),key=lambda x:x[1][1],reverse=True)
        name,(d,c,s,cf)=ranked[0]
        return name,d,c,cf

# ══════════════════════════════════════════════════════════
#  V18 — Backtester
# ══════════════════════════════════════════════════════════
class Backtester:
    def __init__(self,engine): self.engine=engine

    def run(self,candles,min_conf=72,min_cf=3):
        wins=losses=skipped=0
        for i in range(30,len(candles)-1):
            cs=candles[:i]; d,c,r,s,cf=self.engine.run_all(cs)
            if c>=min_conf and cf>=min_cf:
                won=(candles[i+1]["c"]>candles[i]["c"])==(d=="CALL")
                if won: wins+=1
                else: losses+=1
            else: skipped+=1
        total=wins+losses; wr=wins/total*100 if total else 0
        return wins,losses,skipped,wr

    def fetch_and_run(self,sym,min_conf,min_cf,callback):
        def _work():
            candles=[]
            try:
                url=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=5d"
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req,timeout=8) as r:
                    data=json.loads(r.read())
                q=data["chart"]["result"][0]["indicators"]["quote"][0]
                for i in range(len(q.get("close",[]))):
                    if q["close"][i] is not None:
                        candles.append({"o":q["open"][i] or q["close"][i],
                                        "h":q["high"][i] or q["close"][i],
                                        "l":q["low"][i] or q["close"][i],
                                        "c":q["close"][i]})
            except Exception as ex:
                callback(None,str(ex)); return
            if len(candles)<50:
                callback(None,f"Only {len(candles)} candles"); return
            w,l,sk,wr=self.run(candles,min_conf,min_cf)
            callback((w,l,sk,wr,len(candles)),None)
        threading.Thread(target=_work,daemon=True).start()

# ══════════════════════════════════════════════════════════
#  AIBrain
# ══════════════════════════════════════════════════════════
class AIBrain:
    def __init__(self):
        self.mem_file="po_ai_memory.json"; self.csv_file="po_auto_trades.csv"
        self.stats={}; self.load()

    def load(self):
        if os.path.exists(self.mem_file):
            try:
                with open(self.mem_file,"r") as f: self.stats=json.load(f)
            except: pass

    def save(self):
        try:
            with open(self.mem_file,"w") as f: json.dump(self.stats,f,indent=4)
        except: pass

    def record(self,strat,result,direction,entry,close,t):
        if strat not in self.stats: self.stats[strat]={"W":0,"L":0}
        if result=="WIN": self.stats[strat]["W"]+=1
        else:             self.stats[strat]["L"]+=1
        self.save()
        try:
            hdr=not os.path.exists(self.csv_file)
            with open(self.csv_file,"a",newline="") as f:
                w=csv.writer(f)
                if hdr: w.writerow(["Time","Strategy","Dir","Entry","Close","Result"])
                w.writerow([t,strat,direction,f"{entry:.5f}",f"{close:.5f}",result])
        except: pass

    def get_wr(self,strat):
        if strat not in self.stats: return 50.0
        w=self.stats[strat]["W"]; l=self.stats[strat]["L"]; t=w+l
        return w/t*100 if t>=5 else 50.0

    def top3(self):
        r=[(v["W"]/(v["W"]+v["L"])*100,s,v["W"]+v["L"])
           for s,v in self.stats.items() if v["W"]+v["L"]>=5]
        r.sort(reverse=True)
        return " | ".join(f"{s}:{wr:.0f}%({t})" for wr,s,t in r[:3]) if r else "Building..."

# ══════════════════════════════════════════════════════════
#  CandleBuilder
# ══════════════════════════════════════════════════════════
class CandleBuilder:
    def __init__(self,dur=60):
        self.dur=dur; self.done=[]; self._c=None; self._bnd=None

    def feed(self,price):
        now=time.time(); bnd=now-(now%self.dur)
        if self._bnd!=bnd:
            if self._c: self.done.append(dict(self._c))
            if len(self.done)>400: self.done=self.done[-400:]
            self._c={"o":price,"h":price,"l":price,"c":price}
            self._bnd=bnd; return True
        self._c["h"]=max(self._c["h"],price)
        self._c["l"]=min(self._c["l"],price)
        self._c["c"]=price; return False

    def candles(self):
        r=list(self.done)
        if self._c: r.append(dict(self._c))
        return r

    def remaining(self): return self.dur-(time.time()%self.dur)
    def _elapsed(self): return time.time()%self.dur
    def count(self): return len(self.done)

# ══════════════════════════════════════════════════════════
#  Auto-Clicker
# ══════════════════════════════════════════════════════════
class TargetCrosshair:
    def __init__(self,root,title,bg,sx,sy):
        self.win=tk.Toplevel(root); self.win.overrideredirect(True)
        self.win.attributes("-topmost",True); self.win.attributes("-alpha",0.85)
        self.win.geometry(f"65x65+{sx}+{sy}"); self.win.configure(bg=bg,cursor="cross")
        tk.Label(self.win,text=f"{title}\nDRAG",bg=bg,fg="black",
                 font=("Consolas",8,"bold")).pack(expand=True,fill="both")
        self.win.bind("<ButtonPress-1>",lambda e:setattr(self,"_xy",(e.x,e.y)))
        self.win.bind("<B1-Motion>",self._drag)

    def _drag(self,e):
        x=self.win.winfo_x()+(e.x-self._xy[0]); y=self.win.winfo_y()+(e.y-self._xy[1])
        self.win.geometry(f"+{x}+{y}")

    def center(self): return self.win.winfo_x()+32,self.win.winfo_y()+32

def fire_click(tgt,x,y):
    try:
        tgt.win.withdraw(); time.sleep(0.015)
        ctypes.windll.user32.SetCursorPos(int(x),int(y))
        ctypes.windll.user32.mouse_event(2,0,0,0,0); time.sleep(0.015)
        ctypes.windll.user32.mouse_event(4,0,0,0,0); time.sleep(0.025)
        tgt.win.deiconify()
    except: pass

# ══════════════════════════════════════════════════════════
#  Live Price — supports fast polling
# ══════════════════════════════════════════════════════════
# ── Symbol maps ───────────────────────────────────────────
_STOOQ = {
    "EURUSD=X":"eurusd","GBPUSD=X":"gbpusd","USDJPY=X":"usdjpy",
    "AUDUSD=X":"audusd","GBPJPY=X":"gbpjpy","EURJPY=X":"eurjpy",
    "USDCAD=X":"usdcad","USDCHF=X":"usdchf","NZDUSD=X":"nzdusd",
    "GC=F":"xauusd","CL=F":"cl.f",
}
_FX_BASE  = {"EURUSD=X":"EUR","GBPUSD=X":"GBP","AUDUSD=X":"AUD","NZDUSD=X":"NZD",
             "USDJPY=X":"USD","GBPJPY=X":"GBP","EURJPY=X":"EUR",
             "USDCAD=X":"USD","USDCHF=X":"USD"}
_FX_QUOTE = {"EURUSD=X":"USD","GBPUSD=X":"USD","AUDUSD=X":"USD","NZDUSD=X":"USD",
             "USDJPY=X":"JPY","GBPJPY=X":"JPY","EURJPY=X":"JPY",
             "USDCAD=X":"CAD","USDCHF=X":"CHF"}

# Yahoo crumb session cache
_yf_session = {"crumb":"","cookie":"","ts":0}

def _refresh_yahoo_crumb():
    """Fetch Yahoo Finance crumb+cookie (required since 2024)."""
    try:
        req=urllib.request.Request(
            "https://query2.finance.yahoo.com/v1/test/getcrumb",
            headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                     "Accept":"*/*","Accept-Language":"en-US,en;q=0.9",
                     "Accept-Encoding":"gzip, deflate"})
        with urllib.request.urlopen(req,timeout=5) as r:
            crumb=r.read().decode()
            cookie=r.headers.get("Set-Cookie","")
            _yf_session.update({"crumb":crumb,"cookie":cookie,"ts":time.time()})
    except: pass

def _yahoo_price(symbol):
    """Yahoo Finance v8 chart with crumb — primary Yahoo source."""
    # Refresh crumb if older than 30 min
    if time.time()-_yf_session["ts"]>1800:
        _refresh_yahoo_crumb()
    for host in ("query1","query2"):
        try:
            url=(f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
                 f"?interval=1m&range=5m&crumb={_yf_session['crumb']}")
            req=urllib.request.Request(url,headers={
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept":"application/json",
                "Cookie":_yf_session["cookie"]})
            with urllib.request.urlopen(req,timeout=3) as r:
                d=json.loads(r.read())
            closes=d["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            closes=[x for x in closes if x is not None]
            if closes: return float(closes[-1])
        except: pass
    return None

def _stooq_price(symbol):
    """Stooq — free CSV forex data, no auth needed."""
    sym=_STOOQ.get(symbol)
    if not sym: return None
    try:
        url=f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=4) as r:
            lines=r.read().decode().strip().split("\n")
        if len(lines)>=2:
            parts=lines[1].split(",")
            if len(parts)>=6:
                v=float(parts[5])
                if v>0: return v
    except: pass
    return None

def _frankfurter_price(symbol):
    """Frankfurter ECB — official European Central Bank rates."""
    base=_FX_BASE.get(symbol); quote=_FX_QUOTE.get(symbol)
    if not base or not quote: return None
    try:
        url=f"https://api.frankfurter.app/latest?from={base}&to={quote}"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=4) as r:
            d=json.loads(r.read())
        v=d.get("rates",{}).get(quote)
        if v: return float(v)
    except: pass
    return None

def _exchangerate_price(symbol):
    """Open ExchangeRate-API — free, no key."""
    base=_FX_BASE.get(symbol); quote=_FX_QUOTE.get(symbol)
    if not base or not quote: return None
    try:
        url=f"https://open.er-api.com/v6/latest/{base}"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=4) as r:
            d=json.loads(r.read())
        v=d.get("rates",{}).get(quote)
        if v: return float(v)
    except: pass
    return None

def live_price(symbol):
    # ── Binance crypto ────────────────────────────────────
    if symbol.startswith("BINANCE:"):
        coin=symbol.split(":")[1]
        try:
            req=urllib.request.Request(
                f"https://api.binance.com/api/v3/ticker/price?symbol={coin}")
            with urllib.request.urlopen(req,timeout=2) as r:
                return float(json.loads(r.read())["price"])
        except: return None

    # ── Forex/Commodities: 4-source chain ────────────────
    p=_yahoo_price(symbol)       # 1. Yahoo v8 + crumb
    if p: return p
    p=_stooq_price(symbol)       # 2. Stooq CSV
    if p: return p
    p=_frankfurter_price(symbol) # 3. Frankfurter ECB
    if p: return p
    p=_exchangerate_price(symbol) # 4. Open ExchangeRate
    return p

# ══════════════════════════════════════════════════════════
#  Pocket Option API Integration
#  pip install git+https://github.com/A11ksa/API-Pocket-Option.git
# ══════════════════════════════════════════════════════════
try:
    import asyncio
    from api_pocket import AsyncPocketOptionClient, get_ssid
    from api_pocket.models import OrderDirection
    PO_API_AVAILABLE=True
except ImportError:
    PO_API_AVAILABLE=False

# Map our pair names → Pocket Option asset names
PO_ASSET_MAP={
    "EURUSD=X":"EURUSD_otc","GBPUSD=X":"GBPUSD_otc","USDJPY=X":"USDJPY_otc",
    "AUDUSD=X":"AUDUSD_otc","GBPJPY=X":"GBPJPY_otc","EURJPY=X":"EURJPY_otc",
    "USDCAD=X":"USDCAD_otc","USDCHF=X":"USDCHF_otc","NZDUSD=X":"NZDUSD_otc",
    "BINANCE:BTCUSDT":"BTCUSD_otc","BINANCE:ETHUSDT":"ETHUSD_otc",
    "GC=F":"XAUUSD_otc","CL=F":"USOIL_otc",
}

class PocketOptionTrader:
    """
    Wraps the AsyncPocketOptionClient to allow placing orders and
    checking results from synchronous tkinter code via a background
    asyncio event loop.
    """
    def __init__(self):
        self.enabled=False
        self.is_demo=True
        self.ssid=None
        self.client=None
        self._loop=None
        self._thread=None
        self.status="Not connected"
        self.last_order_id=None
        self.last_result=None
        self._on_result_cb=None  # called with ("WIN"/"LOSS") when trade closes

    def configure(self,ssid,is_demo=True):
        self.ssid=ssid; self.is_demo=is_demo

    def connect(self):
        if not PO_API_AVAILABLE:
            self.status="❌ api_pocket not installed"; return False
        if not self.ssid:
            self.status="❌ No SSID"; return False
        self._loop=asyncio.new_event_loop()
        self._thread=threading.Thread(target=self._run_loop,daemon=True)
        self._thread.start()
        # Give the loop a moment to connect
        time.sleep(2)
        return True

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_connect())

    async def _async_connect(self):
        try:
            self.client=AsyncPocketOptionClient(ssid=self.ssid,is_demo=self.is_demo)
            await self.client.connect()
            self.enabled=True
            self.status=f"✅ Connected ({'Demo' if self.is_demo else 'Live'})"
            # Keep loop alive
            while self.enabled:
                await asyncio.sleep(1)
        except Exception as e:
            self.status=f"❌ {e}"; self.enabled=False

    def place_order(self,asset_sym,amount,direction,duration,on_result=None):
        """
        Non-blocking: submits order in background, calls on_result("WIN"/"LOSS")
        when the trade closes.
        """
        if not self.enabled or not self.client:
            return False
        po_asset=PO_ASSET_MAP.get(asset_sym)
        if not po_asset:
            self.status=f"⚠ No PO asset for {asset_sym}"; return False
        dir_enum=OrderDirection.CALL if direction=="CALL" else OrderDirection.PUT
        self._on_result_cb=on_result
        future=asyncio.run_coroutine_threadsafe(
            self._async_place(po_asset,amount,dir_enum,duration), self._loop)
        future.add_done_callback(self._order_placed)
        return True

    async def _async_place(self,asset,amount,direction,duration):
        order=await self.client.place_order(
            asset=asset, amount=amount, direction=direction, duration=duration)
        self.last_order_id=order.order_id
        self.status=f"📤 Order #{order.order_id}"
        # Wait for result
        result=await self.client.check_win(order.order_id)
        return result

    def _order_placed(self,future):
        try:
            result=future.result()
            # result is truthy for WIN, falsy for LOSS (depends on API)
            outcome="WIN" if result else "LOSS"
            self.last_result=outcome
            self.status=f"{'✅' if outcome=='WIN' else '❌'} {outcome}"
            if self._on_result_cb:
                self._on_result_cb(outcome)
        except Exception as e:
            self.status=f"⚠ {e}"

    def disconnect(self):
        self.enabled=False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def get_balance_sync(self):
        if not self.enabled or not self.client: return None
        future=asyncio.run_coroutine_threadsafe(
            self.client.get_balance(), self._loop)
        try:
            bal=future.result(timeout=4)
            return bal.balance
        except: return None

# ══════════════════════════════════════════════════════════
#  Main Application
# ══════════════════════════════════════════════════════════
class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.overrideredirect(True); self.root.attributes("-topmost",True)
        self.root.configure(bg="#050810")
        SW=self.root.winfo_screenwidth(); SH=self.root.winfo_screenheight()
        self.SW=SW; self.SH=SH; self.H=135
        self.root.geometry(f"{SW}x{self.H}+0+0")

        self.sym="EURUSD=X"
        self.builder=CandleBuilder(60)
        self.brain=AIBrain()
        self.engine=StrategyEngine()
        self.risk=RiskManager()
        self.news=NewsFilter()
        self.tg=TelegramBot()
        self.ml=MLPredictor(self.brain,self.risk)
        self.backtester=Backtester(self.engine)
        self.scanner=MultiPairScanner(self.engine)
        self.pattern_validator=PatternValidator()
        self._pending_signal=None
        self._pending_candle=0
        # ── New professional modules ────────────────────────
        self.ob=OrderBookAnalyzer()
        self.fr=FundingRateMonitor()
        self.oi=OpenInterestMonitor()
        self.vol=VolumeAnalyzer()
        self.mtf_real=MultiTimeframeReal()
        self.whale=WhaleTracker()
        self.fg=FearGreedIndex()
        self.dxy=DXYCorrelation()
        self.self_learner=SelfLearner(self.engine)
        self.adaptive_expiry=AdaptiveExpiry()
        self.smart_timer=SmartEntryTimer()
        self.po_trader=PocketOptionTrader()
        threading.Thread(target=self._pro_data_loop,daemon=True).start()

        self.direction=None; self.conf=0; self.reason=""; self.strat_name=""
        self.confluence=0; self.prev_price=None; self._last_diff=0
        self.wins=self.losses=0; self.history=[]; self.pending_trades=[]
        self.auto_click=False; self.targets_ready=False
        self.last_clicked_bnd=None; self.last_valid_price=1.15000
        self.last_bet=10.0; self.adx_val=None
        self._stop_price=False; self._last_real_fetch=0; self._api_ok=True
        self._consec_dir=None; self._consec_count=0  # consecutive signal tracker

        self.v_pair=tk.StringVar(value="EUR/USD OTC")
        self.v_dur =tk.StringVar(value="1m")
        self.v_min_conf=tk.IntVar(value=55)
        self.v_min_conf_auto=tk.IntVar(value=72)
        self.v_balance=tk.DoubleVar(value=1000.0)

        self._build(); self._clock()
        self.root.after(1000,self._init_targets)
        threading.Thread(target=self._prefill,daemon=True).start()
        self._price_loop()

    # ── Price loop (V18 ultra-fast) ───────────────────────
    def _pro_data_loop(self):
        """Background thread: fetches all professional data sources every few seconds."""
        self.fg.update()  # Fear & Greed first (slow)
        self.dxy.update()
        while True:
            sym=self.sym
            try:
                self.ob.update(sym)
                self.fr.update(sym)
                self.oi.update(sym)
                self.vol.update(sym)
                self.mtf_real.update(sym)
                self.whale.update(sym)
                self.fg.update()
                self.dxy.update()
            except Exception: pass
            time.sleep(5)

    def _price_loop(self):
        self._stop_price=False
        threading.Thread(target=self._price_worker,daemon=True).start()

    def _price_worker(self):
        while not self._stop_price:
            t0=time.time()
            is_otc="OTC" in self.v_pair.get()
            is_binance=self.sym.startswith("BINANCE:")

            if is_otc:
                # Calibrate from real API every 3s
                if t0-self._last_real_fetch>3:
                    p=live_price(self.sym)
                    if p:
                        self.last_valid_price=p*0.5+self.last_valid_price*0.5
                    self._last_real_fetch=t0
                # Generate micro-tick (250ms)
                p=self.last_valid_price+random.gauss(0,0.000055)
                p=max(0.001,p); self.last_valid_price=p
                self.root.after(0,lambda px=p:self._on_price(px))
                time.sleep(max(0.01,0.25-(time.time()-t0)))

            elif is_binance:
                # Binance fast poll 300ms
                p=live_price(self.sym)
                if p:
                    self.last_valid_price=p
                    self.root.after(0,lambda px=p:self._on_price(px))
                time.sleep(max(0.05,0.30-(time.time()-t0)))

            else:
                # Forex: try real API every 450ms, simulate ticks in between
                p=live_price(self.sym)
                if p:
                    self.last_valid_price=p
                    self._api_ok=True
                else:
                    # API failed — generate micro-tick from last known price
                    # so candles keep building and analysis keeps running
                    self._api_ok=False
                    p=self.last_valid_price+random.gauss(0,0.000035)
                    p=max(0.001,p); self.last_valid_price=p
                self.root.after(0,lambda px=self.last_valid_price:self._on_price(px))
                time.sleep(max(0.05,0.45-(time.time()-t0)))

    # ── Init crosshairs ───────────────────────────────────
    def _init_targets(self):
        self.call_tgt=TargetCrosshair(self.root,"CALL","#00ff88",self.SW-270,self.SH//2-95)
        self.put_tgt =TargetCrosshair(self.root,"PUT", "#ff4444",self.SW-270,self.SH//2+95)
        self.call_tgt.win.withdraw(); self.put_tgt.win.withdraw()
        self.targets_ready=True; self.btn_auto.config(state="normal",text="🤖 AUTO: OFF")

    def toggle_auto(self):
        if not self.targets_ready: return
        self.auto_click=not self.auto_click
        if self.auto_click:
            self.btn_auto.config(text="🤖 AUTO: ON",fg="#00ff88",bg="#0a2a0a")
            self.call_tgt.win.deiconify(); self.put_tgt.win.deiconify()
        else:
            self.btn_auto.config(text="🤖 AUTO: OFF",fg="#ff4444",bg="#111")
            self.call_tgt.win.withdraw(); self.put_tgt.win.withdraw()

    # ── Build UI ──────────────────────────────────────────
    def _build(self):
        # Main bar (top row)
        bar=tk.Frame(self.root,bg="#050810",height=110); bar.pack(fill="x")
        bar.pack_propagate(False)
        bar.bind("<ButtonPress-1>",lambda e:[setattr(self,"_dx",e.x),setattr(self,"_dy",e.y)])
        bar.bind("<B1-Motion>",lambda e:self.root.geometry(
            f"+{self.root.winfo_x()+(e.x-self._dx)}+{self.root.winfo_y()+(e.y-self._dy)}"))
        self._dx=self._dy=0

        # Col 1 — System
        c1=self._col(bar,115)
        tk.Label(c1,text="V18 SUPREME",bg="#050810",fg="#00ff44",
                 font=("Consolas",7,"bold")).pack(anchor="w",padx=3,pady=(4,0))
        self.lbl_clk =tk.Label(c1,text="",bg="#050810",fg="#336633",font=("Consolas",7))
        self.lbl_clk.pack(anchor="w",padx=3)
        self.lbl_sess=tk.Label(c1,text="",bg="#050810",fg="#ffaa00",font=("Consolas",7,"bold"))
        self.lbl_sess.pack(anchor="w",padx=3)
        self.lbl_adx =tk.Label(c1,text="ADX:--",bg="#050810",fg="#555",font=("Consolas",7))
        self.lbl_adx.pack(anchor="w",padx=3)
        self.lbl_risk_line=tk.Label(c1,text="",bg="#050810",fg="#aaa",font=("Consolas",6),
                                    wraplength=113,justify="left")
        self.lbl_risk_line.pack(anchor="w",padx=3)
        self.lbl_news=tk.Label(c1,text="",bg="#050810",fg="#ff8800",
                               font=("Consolas",6),wraplength=113,justify="left")
        self.lbl_news.pack(anchor="w",padx=3)

        # Col 2 — Settings
        c2=self._col(bar,230)
        ttk.Combobox(c2,textvariable=self.v_pair,values=list(PAIRS.keys()),
                     width=17,font=("Consolas",8)).pack(anchor="w",padx=3,pady=(4,1))
        r1=tk.Frame(c2,bg="#050810"); r1.pack(anchor="w",padx=3,fill="x")
        ttk.Combobox(r1,textvariable=self.v_dur,values=list(CANDLE_DUR.keys()),
                     width=5,font=("Consolas",8)).pack(side="left")
        self.btn_auto=tk.Button(r1,text="🤖 Loading...",bg="#111",fg="#ffaa00",
                                font=("Consolas",8,"bold"),relief="flat",
                                command=self.toggle_auto,state="disabled")
        self.btn_auto.pack(side="left",padx=4)
        r2=tk.Frame(c2,bg="#050810"); r2.pack(anchor="w",padx=3,fill="x")
        tk.Label(r2,text="Sig%:",bg="#050810",fg="#555",font=("Consolas",7)).pack(side="left")
        tk.Spinbox(r2,from_=40,to=95,textvariable=self.v_min_conf,
                   width=3,font=("Consolas",7),bg="#111",fg="#aaa").pack(side="left")
        tk.Label(r2,text=" Auto%:",bg="#050810",fg="#555",font=("Consolas",7)).pack(side="left")
        tk.Spinbox(r2,from_=60,to=95,textvariable=self.v_min_conf_auto,
                   width=3,font=("Consolas",7),bg="#111",fg="#aaa").pack(side="left")
        r3=tk.Frame(c2,bg="#050810"); r3.pack(anchor="w",padx=3,fill="x")
        tk.Label(r3,text="Bal$:",bg="#050810",fg="#555",font=("Consolas",7)).pack(side="left")
        tk.Entry(r3,textvariable=self.v_balance,width=7,
                 font=("Consolas",7),bg="#111",fg="#aaa").pack(side="left")
        tk.Button(r3,text="Set",bg="#111",fg="#0f0",font=("Consolas",7),
                  relief="flat",command=self._set_balance).pack(side="left",padx=2)
        tk.Button(r3,text="TG",bg="#111",fg="#29a8e0",font=("Consolas",7),
                  relief="flat",command=self._tg_settings).pack(side="left",padx=2)
        tk.Button(r3,text="BT",bg="#111",fg="#ff8800",font=("Consolas",7),
                  relief="flat",command=self._run_backtest).pack(side="left",padx=2)
        tk.Button(r3,text="PO",bg="#111",fg="#a855f7",font=("Consolas",7,"bold"),
                  relief="flat",command=self._po_settings).pack(side="left",padx=2)
        self.v_pair.trace("w",lambda *_:self._on_change())
        self.v_dur.trace("w", lambda *_:self._on_change())
        self.lbl_po=tk.Label(c2,text="PO: Not connected",bg="#050810",fg="#555",
                             font=("Consolas",6))
        self.lbl_po.pack(anchor="w",padx=3)
        tk.Label(c2,text="● 22 Signals | OB | FR | OI | VWAP | Whale | F&G | MTF | DXY | Self-Learn",
                 bg="#050810",fg="#A78BFA",font=("Consolas",6,"bold")).pack(anchor="w",padx=3)

        # Col 3 — Price
        c3=self._col(bar,160)
        tk.Label(c3,text="PRICE",bg="#050810",fg="#1a1a2e",font=("Consolas",7)).pack(pady=(5,0))
        self.lbl_price=tk.Label(c3,text="------",bg="#050810",fg="#00d4ff",
                                font=("Consolas",13,"bold")); self.lbl_price.pack()
        self.cbar=tk.Canvas(c3,height=4,bg="#0d1117",highlightthickness=0,width=145)
        self.cbar.pack(padx=4,pady=1)
        self.lbl_timer=tk.Label(c3,text="",bg="#050810",fg="#ffaa00",
                                font=("Consolas",9,"bold")); self.lbl_timer.pack()
        self.lbl_bet=tk.Label(c3,text="Bet: $--",bg="#050810",fg="#A78BFA",
                              font=("Consolas",8,"bold")); self.lbl_bet.pack()
        self.lbl_confl=tk.Label(c3,text="",bg="#050810",fg="#666",
                                font=("Consolas",7)); self.lbl_confl.pack()

        # Col 4 — Signal
        c4=self._col(bar,250)
        self.lbl_sig=tk.Label(c4,text="⏳ Scanning...",bg="#050810",fg="#222",
                              font=("Consolas",18,"bold")); self.lbl_sig.pack(pady=(5,1))
        self.cv=tk.Canvas(c4,height=10,bg="#0d1117",highlightthickness=0,width=230)
        self.cv.pack(padx=8)
        self.lbl_conf=tk.Label(c4,text="",bg="#050810",fg="#444",
                               font=("Consolas",8)); self.lbl_conf.pack()
        self.lbl_ml=tk.Label(c4,text="",bg="#050810",fg="#666",
                             font=("Consolas",7)); self.lbl_ml.pack()

        # Col 5 — Reason + History
        c5=self._col(bar,260)
        self.lbl_reason=tk.Label(c5,text="",bg="#050810",fg="#aaa",
                                 font=("Consolas",7,"bold"),wraplength=255,justify="left")
        self.lbl_reason.pack(anchor="w",padx=3,pady=(7,0))
        self.lbl_hist=tk.Label(c5,text="",bg="#050810",fg="#2a3a2a",font=("Consolas",7))
        self.lbl_hist.pack(anchor="w",padx=3)
        self.lbl_best=tk.Label(c5,text="",bg="#050810",fg="#334433",font=("Consolas",6))
        self.lbl_best.pack(anchor="w",padx=3)
        self.lbl_besthour=tk.Label(c5,text="",bg="#050810",fg="#445544",font=("Consolas",6))
        self.lbl_besthour.pack(anchor="w",padx=3)

        # Col 6 — WIN/LOSS
        c6=self._col(bar,150)
        brow=tk.Frame(c6,bg="#050810"); brow.pack(pady=(8,1))
        tk.Button(brow,text="WIN",bg="#0a2a0a",fg="#00ff88",font=("Consolas",10,"bold"),
                  relief="flat",cursor="hand2",command=lambda:self.log("WIN"),
                  padx=8,pady=5).pack(side="left",padx=1)
        tk.Button(brow,text="LOSS",bg="#2a0a0a",fg="#ff4444",font=("Consolas",10,"bold"),
                  relief="flat",cursor="hand2",command=lambda:self.log("LOSS"),
                  padx=5,pady=5).pack(side="left",padx=1)
        self.lbl_stats=tk.Label(c6,text="W:0 L:0",bg="#050810",fg="#333",font=("Consolas",7))
        self.lbl_stats.pack()
        self.lbl_wr=tk.Label(c6,text="AI Trust: ---%",bg="#050810",fg="#A78BFA",font=("Consolas",7))
        self.lbl_wr.pack()
        self.lbl_mart=tk.Label(c6,text="",bg="#050810",fg="#444",font=("Consolas",6))
        self.lbl_mart.pack()

        # Col 7 — Buttons
        c7=tk.Frame(bar,bg="#050810"); c7.pack(side="left",fill="both",expand=True)
        br=tk.Frame(c7,bg="#050810"); br.pack(anchor="w",padx=3,pady=(30,0))
        for t,bg,fg,cmd in [
            ("X","#180000","#ff3333",self.root.quit),
            ("TOP","#111","#444",lambda:self.root.geometry(f"{self.SW}x{self.H}+0+0")),
            ("BOT","#111","#444",lambda:self.root.geometry(f"{self.SW}x{self.H}+0+{self.SH-self.H-40}")),
        ]:
            tk.Button(br,text=t,bg=bg,fg=fg,font=("Consolas",7),
                      relief="flat",cursor="hand2",command=cmd,
                      padx=5,pady=2).pack(side="left",padx=1)

        # Bottom row — Scanner + News
        bot=tk.Frame(self.root,bg="#0a0d14",height=25); bot.pack(fill="x")
        bot.pack_propagate(False)
        tk.Label(bot,text="SCAN:",bg="#0a0d14",fg="#334",
                 font=("Consolas",6,"bold")).pack(side="left",padx=4)
        self.lbl_scan=tk.Label(bot,text="Initializing multi-pair scanner...",
                               bg="#0a0d14",fg="#445566",font=("Consolas",6))
        self.lbl_scan.pack(side="left")
        self.lbl_next_news=tk.Label(bot,text="",bg="#0a0d14",fg="#665533",font=("Consolas",6))
        self.lbl_next_news.pack(side="right",padx=6)

    def _col(self,p,w):
        f=tk.Frame(p,bg="#050810",width=w)
        f.pack(side="left",fill="y",padx=1)
        f.pack_propagate(False); return f

    def _set_balance(self):
        try:
            b=float(self.v_balance.get())
            self.risk.balance=b; self.risk.peak_balance=b
            self.risk.base_bet=b*0.01
            self.risk.daily_loss=0; self.risk.daily_profit=0
            self.risk.profit_locked=False
        except: pass

    def _po_settings(self):
        win=tk.Toplevel(self.root)
        win.title("Pocket Option API"); win.geometry("420x320")
        win.configure(bg="#050810"); win.attributes("-topmost",True)
        tk.Label(win,text="Pocket Option API Settings",bg="#050810",fg="#a855f7",
                 font=("Consolas",10,"bold")).pack(pady=8)
        frm=tk.Frame(win,bg="#050810"); frm.pack(fill="x",padx=16)

        tk.Label(frm,text="Email:",bg="#050810",fg="#aaa",font=("Consolas",8)).grid(
            row=0,column=0,sticky="w",pady=3)
        v_email=tk.StringVar()
        tk.Entry(frm,textvariable=v_email,width=30,bg="#111",fg="#fff",
                 font=("Consolas",8)).grid(row=0,column=1,padx=4)

        tk.Label(frm,text="Password:",bg="#050810",fg="#aaa",font=("Consolas",8)).grid(
            row=1,column=0,sticky="w",pady=3)
        v_pass=tk.StringVar()
        tk.Entry(frm,textvariable=v_pass,width=30,bg="#111",fg="#fff",
                 show="*",font=("Consolas",8)).grid(row=1,column=1,padx=4)

        tk.Label(frm,text="SSID (or leave blank\nto auto-login):",bg="#050810",fg="#aaa",
                 font=("Consolas",8),justify="left").grid(row=2,column=0,sticky="w",pady=3)
        v_ssid=tk.StringVar()
        tk.Entry(frm,textvariable=v_ssid,width=30,bg="#111",fg="#fff",
                 font=("Consolas",8)).grid(row=2,column=1,padx=4)

        v_demo=tk.BooleanVar(value=True)
        tk.Checkbutton(frm,text="Demo Account",variable=v_demo,bg="#050810",
                       fg="#ffaa00",font=("Consolas",8),selectcolor="#050810").grid(
            row=3,column=0,columnspan=2,sticky="w",pady=3)

        lbl_st=tk.Label(win,text="Status: Not connected",bg="#050810",fg="#555",
                        font=("Consolas",8),wraplength=380)
        lbl_st.pack(pady=4)

        def _connect():
            ssid=v_ssid.get().strip()
            if not ssid:
                if not PO_API_AVAILABLE:
                    lbl_st.config(text="❌ Install: pip install git+https://github.com/A11ksa/API-Pocket-Option.git",fg="#ff4444")
                    return
                lbl_st.config(text="🔄 Logging in via Selenium...",fg="#ffaa00")
                win.update()
                def _do_login():
                    try:
                        result=get_ssid(email=v_email.get(),password=v_pass.get())
                        ssid_val=result["demo"] if v_demo.get() else result["live"]
                        self.po_trader.configure(ssid_val,is_demo=v_demo.get())
                        ok=self.po_trader.connect()
                        win.after(0,lambda:lbl_st.config(
                            text=self.po_trader.status,
                            fg="#00ff88" if ok else "#ff4444"))
                        win.after(0,lambda:self.lbl_po.config(
                            text=f"PO:{self.po_trader.status}",
                            fg="#00ff88" if ok else "#ff4444"))
                    except Exception as e:
                        win.after(0,lambda:lbl_st.config(text=f"❌ {e}",fg="#ff4444"))
                threading.Thread(target=_do_login,daemon=True).start()
            else:
                self.po_trader.configure(ssid,is_demo=v_demo.get())
                lbl_st.config(text="🔄 Connecting...",fg="#ffaa00"); win.update()
                def _do_connect():
                    ok=self.po_trader.connect()
                    win.after(0,lambda:lbl_st.config(
                        text=self.po_trader.status,
                        fg="#00ff88" if ok else "#ff4444"))
                    win.after(0,lambda:self.lbl_po.config(
                        text=f"PO:{self.po_trader.status}",
                        fg="#00ff88" if ok else "#ff4444"))
                    if ok:
                        bal=self.po_trader.get_balance_sync()
                        if bal:
                            win.after(0,lambda:lbl_st.config(
                                text=f"{self.po_trader.status} | Balance: ${bal:.2f}",
                                fg="#00ff88"))
                threading.Thread(target=_do_connect,daemon=True).start()

        def _disconnect():
            self.po_trader.disconnect()
            lbl_st.config(text="Disconnected",fg="#555")
            self.lbl_po.config(text="PO: Not connected",fg="#555")

        def _check_bal():
            bal=self.po_trader.get_balance_sync()
            if bal: lbl_st.config(text=f"Balance: ${bal:.2f}",fg="#00ff88")
            else: lbl_st.config(text="Not connected",fg="#555")

        br=tk.Frame(win,bg="#050810"); br.pack(pady=6)
        tk.Button(br,text="Connect",bg="#0a1a0a",fg="#00ff88",font=("Consolas",9,"bold"),
                  relief="flat",command=_connect,padx=10,pady=4).pack(side="left",padx=4)
        tk.Button(br,text="Balance",bg="#111",fg="#ffaa00",font=("Consolas",9),
                  relief="flat",command=_check_bal,padx=8,pady=4).pack(side="left",padx=4)
        tk.Button(br,text="Disconnect",bg="#1a0a0a",fg="#ff4444",font=("Consolas",9),
                  relief="flat",command=_disconnect,padx=8,pady=4).pack(side="left",padx=4)
        tk.Label(win,text="⚠ pip install git+https://github.com/A11ksa/API-Pocket-Option.git",
                 bg="#050810",fg="#333",font=("Consolas",6)).pack(pady=2)

    def _tg_settings(self):
        win=tk.Toplevel(self.root)
        win.title("Telegram Settings"); win.geometry("360x200")
        win.configure(bg="#050810"); win.attributes("-topmost",True)
        tk.Label(win,text="Telegram Bot Settings",bg="#050810",fg="#00ff44",
                 font=("Consolas",10,"bold")).pack(pady=8)
        frm=tk.Frame(win,bg="#050810"); frm.pack(fill="x",padx=16)
        tk.Label(frm,text="Bot Token:",bg="#050810",fg="#aaa",
                 font=("Consolas",8)).grid(row=0,column=0,sticky="w",pady=3)
        e_tok=tk.Entry(frm,width=32,bg="#111",fg="#fff",font=("Consolas",8))
        e_tok.insert(0,self.tg.token); e_tok.grid(row=0,column=1,pady=3)
        tk.Label(frm,text="Chat ID:",bg="#050810",fg="#aaa",
                 font=("Consolas",8)).grid(row=1,column=0,sticky="w",pady=3)
        e_cid=tk.Entry(frm,width=32,bg="#111",fg="#fff",font=("Consolas",8))
        e_cid.insert(0,self.tg.chat_id); e_cid.grid(row=1,column=1,pady=3)
        v_en=tk.BooleanVar(value=self.tg.enabled)
        tk.Checkbutton(frm,text="Enable Telegram",variable=v_en,
                       bg="#050810",fg="#aaa",selectcolor="#111",
                       font=("Consolas",8)).grid(row=2,column=0,columnspan=2,pady=3)
        def save():
            self.tg.token=e_tok.get().strip()
            self.tg.chat_id=e_cid.get().strip()
            self.tg.enabled=v_en.get(); win.destroy()
        tk.Button(win,text="💾 Save & Close",bg="#0a2a0a",fg="#00ff88",
                  font=("Consolas",9,"bold"),relief="flat",command=save).pack(pady=8)

    def _run_backtest(self):
        sym=self.sym
        if sym.startswith("BINANCE:") or sym in ("GC=F","CL=F"):
            messagebox.showinfo("Backtest","Backtest works best with Forex pairs (Yahoo Finance).")
            return
        min_conf=self.v_min_conf_auto.get(); min_cf=3
        win=tk.Toplevel(self.root); win.title("Backtesting V18")
        win.geometry("400x220"); win.configure(bg="#050810"); win.attributes("-topmost",True)
        tk.Label(win,text="📈 Backtesting...",bg="#050810",fg="#ffaa00",
                 font=("Consolas",11,"bold")).pack(pady=10)
        lbl=tk.Label(win,text=f"Fetching 5 days of {sym} 1m data...\nPlease wait...",
                     bg="#050810",fg="#888",font=("Consolas",9),justify="center")
        lbl.pack(pady=5)
        def on_result(res,err):
            if err:
                win.after(0,lambda:lbl.config(text=f"❌ Error: {err}",fg="#ff4444"))
                return
            w,l,sk,wr,total=res
            txt=(f"📊 Backtest Results — {sym}\n"
                 f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                 f"Total Candles : {total}\n"
                 f"Trades Taken  : {w+l}  (Skipped: {sk})\n"
                 f"Wins          : {w}\n"
                 f"Losses        : {l}\n"
                 f"Win Rate      : {wr:.1f}%\n"
                 f"Min Conf Used : {min_conf}%  |  Min CF: {min_cf}\n"
                 f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                 f"{'✅ PROFITABLE' if wr>=58 else '⚠️ NEEDS TUNING'}")
            win.after(0,lambda:lbl.config(text=txt,fg="#00ff88" if wr>=58 else "#ff8800"))
        self.backtester.fetch_and_run(sym,min_conf,min_cf,on_result)

    def _prefill(self):
        success=False
        if not self.sym.startswith("BINANCE:"):
            try:
                url=f"https://query2.finance.yahoo.com/v8/finance/chart/{self.sym}?interval=1m&range=90m"
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req,timeout=4) as r: d=json.loads(r.read())
                q=d["chart"]["result"][0]["indicators"]["quote"][0]
                self.builder.done=[]
                for i in range(len(q.get("close",[]))):
                    if q["close"][i] is not None:
                        self.builder.done.append({
                            "o":q["open"][i],"h":q["high"][i],
                            "l":q["low"][i],"c":q["close"][i]})
                if len(self.builder.done)>=10:
                    success=True; self.last_valid_price=self.builder.done[-1]["c"]
            except: pass
        if not success:
            p=self.last_valid_price; self.builder.done=[]
            for _ in range(80):
                p+=random.uniform(-0.0005,0.0005); o=p
                c=p+random.uniform(-0.0004,0.0004)
                h=max(o,c)+random.uniform(0,0.0004); l=min(o,c)-random.uniform(0,0.0004)
                self.builder.done.append({"o":o,"h":h,"l":l,"c":c})
            self.last_valid_price=p
        self.root.after(0,self._analyze)

    def _on_change(self):
        self._stop_price=True
        self.sym=PAIRS.get(self.v_pair.get(),"EURUSD=X")
        self.builder=CandleBuilder(CANDLE_DUR.get(self.v_dur.get(),60))
        self.direction=None; self.pending_trades.clear()
        self._consec_dir=None; self._consec_count=0
        self.lbl_sig.config(text="⏳ Scanning...",fg="#222",bg="#050810")
        self.lbl_conf.config(text=""); self.lbl_reason.config(text="")
        self.cv.delete("all"); self._last_real_fetch=0
        time.sleep(0.1)
        threading.Thread(target=self._prefill,daemon=True).start()
        self._price_loop()

    def _on_price(self,p):
        new_candle=self.builder.feed(p)
        n=self.builder.count(); now=time.time()
        diff=(p-self.prev_price) if self.prev_price else 0
        if diff!=0: self._last_diff=diff
        api_tag="" if self._api_ok else "~"
        if   self._last_diff>0: self.lbl_price.config(text=f"▲{api_tag}{p:.5f}",fg="#00ff88")
        elif self._last_diff<0: self.lbl_price.config(text=f"▼{api_tag}{p:.5f}",fg="#ff4444")
        else:                   self.lbl_price.config(text=f"─{api_tag}{p:.5f}",fg="#888")
        self.prev_price=p

        if new_candle:
            dt=datetime.datetime.now().strftime("%H:%M:%S"); surviving=[]
            for t in self.pending_trades:
                if now>=t["expiry"]:
                    won=(p>t["entry"]) if t["dir"]=="CALL" else (p<t["entry"])
                    self.brain.record(t["strat"],"WIN" if won else "LOSS",
                                      t["dir"],t["entry"],p,dt)
                else: surviving.append(t)
            self.pending_trades=surviving

        if n>=8:
            self._analyze()
            if new_candle:
                is_crypto=self.sym.startswith("BINANCE:")
                d,c,r,s,cf=self.engine.run_all(self.builder.candles(),crypto=is_crypto)
                self.pending_trades.append(
                    {"strat":s,"dir":d,"entry":p,"expiry":now+self.builder.dur-3})

    def _analyze(self):
        cs=self.builder.candles()
        if len(cs)<8: return

        is_crypto=self.sym.startswith("BINANCE:")
        sq,sname,smult=session_quality(is_crypto=is_crypto)
        self.adx_val=_adx(cs,14)
        adx_thresh=25 if is_crypto else 18
        adx_ok=self.adx_val is None or self.adx_val>=adx_thresh

        # News filter check
        blocked,news_msg=self.news.is_blocked()
        next_ev=self.news.next_event_str()
        self.lbl_news.config(text=news_msg if blocked else "")
        self.lbl_next_news.config(text=next_ev)

        d,c,r,s,cf=self.engine.run_all(cs,crypto=is_crypto)
        cur_price=self.last_valid_price

        # ── Professional signals integration ────────────────────────────────
        pro_signals=[]
        if is_crypto:
            ob_dir,ob_conf,ob_txt=self.ob.signal()
            if ob_dir: pro_signals.append((ob_dir,ob_conf,ob_txt))
            fr_dir,fr_conf,fr_txt=self.fr.signal()
            if fr_dir: pro_signals.append((fr_dir,fr_conf,fr_txt))
            oi_dir,oi_conf,oi_txt=self.oi.signal(d)
            if oi_dir: pro_signals.append((oi_dir,oi_conf,oi_txt))
            for vs in self.vol.signal(cur_price): pro_signals.append(vs)
            mtf_dir,mtf_conf,mtf_txt=self.mtf_real.signal()
            if mtf_dir: pro_signals.append((mtf_dir,mtf_conf,mtf_txt))
            wh_dir,wh_conf,wh_txt=self.whale.signal()
            if wh_dir: pro_signals.append((wh_dir,wh_conf,wh_txt))
            fg_dir,fg_conf,fg_txt=self.fg.signal()
            if fg_dir: pro_signals.append((fg_dir,fg_conf,fg_txt))
            dxy_dir,dxy_conf,dxy_txt=self.dxy.signal(d)
            if dxy_dir: pro_signals.append((dxy_dir,dxy_conf,dxy_txt))
            # DXY override: if DXY strongly contradicts, flip signal
            if dxy_dir and dxy_dir!=d and dxy_conf>=70:
                d=dxy_dir; c=max(52,c-10); r=f"DXY↔{r}"
        # Count pro signals agreeing with main signal
        pro_agree=sum(1 for pd,pc,pt in pro_signals if pd==d and pc>=65)
        pro_oppose=sum(1 for pd,pc,pt in pro_signals if pd!=d and pc>=65)
        # Boost if pro signals confirm
        if pro_agree>=3: c=min(85 if is_crypto else 93, c+8); cf+=pro_agree
        elif pro_agree>=2: c=min(85 if is_crypto else 93, c+4); cf+=pro_agree
        # Penalize if pro signals contradict
        if pro_oppose>=3: c=max(52,c-15)
        elif pro_oppose>=2: c=max(52,c-8)
        # Adaptive expiry suggestion
        sug_exp,exp_note=self.adaptive_expiry.suggest(cs,self.builder.dur)
        # Pro summary for UI
        pro_sum=" | ".join(pt for pd,pc,pt in pro_signals[:3]) if pro_signals else ""
        # ─────────────────────────────────────────────────────────────────────

        # ── Market Structure Gate ────────────────────────────────────────────
        # Check if price is making HH/HL (uptrend) or LH/LL (downtrend)
        if len(cs)>=6:
            recent_highs=[c_["h"] for c_ in cs[-6:]]
            recent_lows =[c_["l"] for c_ in cs[-6:]]
            ms_up  = recent_highs[-1]>recent_highs[-3] and recent_lows[-1]>recent_lows[-3]
            ms_down= recent_highs[-1]<recent_highs[-3] and recent_lows[-1]<recent_lows[-3]
            # Block signals that contradict confirmed market structure
            if is_crypto:
                if ms_down and d=="CALL" and c<75: d="PUT"; c=max(52,c-10)
                if ms_up   and d=="PUT"  and c<75: d="CALL"; c=max(52,c-10)
        # ────────────────────────────────────────────────────────────────────

        # ── Signal Confirmation — wait for same signal on 2 candles ─────────
        # High-confidence signals fire immediately; lower ones need confirmation
        n_candles=self.builder.count()
        if c>=75:
            # Strong enough — use as-is, reset pending
            self._pending_signal=None
        else:
            if self._pending_signal and self._pending_signal[0]==d:
                # Same direction as pending — confirmed!
                # Boost confidence slightly for confirmation
                c=min(85 if is_crypto else 93, c+6)
                self._pending_signal=None
            else:
                # New or changed signal — store as pending, show at reduced conf
                self._pending_signal=(d,c,r,s,cf)
                self._pending_candle=n_candles
                c=max(50,c-8)   # show lower until confirmed
        # ────────────────────────────────────────────────────────────────────

        # ── Consecutive Signal Lock ──────────────────────────────────────────
        if d==self._consec_dir:
            self._consec_count+=1
        else:
            self._consec_dir=d; self._consec_count=1
        consec_limit=4 if is_crypto else 5
        if self._consec_count>consec_limit and c<72:
            d=self.direction or d; c=52; r="Waiting for new signal..."; s="Wait"; cf=0
        # ────────────────────────────────────────────────────────────────────

        # ── Pattern Validator — historical accuracy of current setup ─────────
        if c>=65 and cf>=3 and len(cs)>=30:
            acc,samples=self.pattern_validator.validate(self.engine,cs,d,crypto=is_crypto)
            if samples>=5:
                # Adjust confidence based on recent historical accuracy
                # acc=0.70 → +5%, acc=0.50 → -8%, acc=0.35 → -15%
                hist_adj=int((acc-0.55)*40)
                c=max(52,min(85 if is_crypto else 93, c+hist_adj))
                r=f"Hist:{int(acc*100)}% | {r}"
        # ────────────────────────────────────────────────────────────────────

        # Adjust by session + ADX
        conf_cap=85 if is_crypto else 93
        c=max(50,min(conf_cap,int(c*smult)))
        if not adx_ok and self.adx_val is not None: c=int(c*0.80)

        # ML adjustment
        c_ml=self.ml.predict(s,c,cf,sq,self.adx_val)
        self.lbl_ml.config(text=f"ML:{c_ml}%",
                           fg="#00ff88" if c_ml>=70 else ("#ffaa00" if c_ml>=60 else "#ff4444"))

        # AI trust bonus
        wr=self.brain.get_wr(s)
        if wr>=65: c=min(conf_cap,c+int((wr-50)*0.20))

        bet,cb_msg=self.risk.get_bet(c,smult,cf)
        self.last_bet=bet

        # ADX label
        if self.adx_val is not None:
            ac="#00ff88" if self.adx_val>=25 else ("#ffaa00" if self.adx_val>=18 else "#ff4444")
            self.lbl_adx.config(text=f"ADX:{self.adx_val:.0f}{'✓' if adx_ok else '✗'}",fg=ac)

        sc="#00ff88" if sq>=80 else ("#ffaa00" if sq>=55 else "#ff4444")
        self.lbl_sess.config(text=f"{sname}({sq}%)",fg=sc)

        if cb_msg: self.lbl_bet.config(text=cb_msg,fg="#ff4444")
        else:
            ml=self.risk.martingale_lvl
            self.lbl_bet.config(text=f"Bet:${bet}{' M'+str(ml) if ml>0 else ''}",
                                fg="#ff8800" if ml>0 else "#A78BFA")
            self.lbl_mart.config(
                text=f"{'M'+str(ml) if ml>0 else 'M:OFF'} CB:{self.risk.consecutive_L}/3"
                     f"{' 🔒' if self.risk.profit_locked else ''}",
                fg="#ff8800" if ml>0 else "#444")

        self.lbl_risk_line.config(text=self.risk.status_line())
        self.lbl_wr.config(text=f"AI:{wr:.0f}%",
                           fg="#00ff88" if wr>=55 else "#ff4444")
        self.lbl_best.config(text=self.brain.top3())
        self.lbl_besthour.config(text=self.risk.best_hour())

        cf_gate=4 if is_crypto else 3
        consec_tag=f" x{self._consec_count}" if self._consec_count>2 else ""
        confl_clr="#00ff88" if cf>=cf_gate+2 else ("#ffaa00" if cf>=cf_gate else "#666")
        self.lbl_confl.config(text=f"CF:{cf} signals{'⚡' if is_crypto else ''}{consec_tag}",fg=confl_clr)

        # Scanner / Pro data row
        if is_crypto:
            pro_line=f"{self.ob.summary()} | {self.fr.summary()} | {self.whale.summary()} | {self.fg.summary()} | {self.mtf_real.summary()} | {self.vol.vwap_str()} | {self.dxy.summary()}"
            if exp_note: pro_line+=f" | 🕐{exp_note}"
            pro_clr="#00ff88" if pro_agree>=3 else ("#ffaa00" if pro_agree>=1 else "#445566")
            self.lbl_scan.config(text=pro_line,fg=pro_clr)
        else:
            scan_txt=self.scanner.summary()
            best=self.scanner.best()
            if best:
                bn,bd,bc,bcf=best
                scan_clr="#00ff88" if bd=="CALL" else "#ff4444"
                self.lbl_scan.config(text=f"BEST:{bn} {'▲' if bd=='CALL' else '▼'}{bc}%  |  {scan_txt}",
                                     fg=scan_clr)
            else:
                self.lbl_scan.config(text=scan_txt,fg="#445566")

        changed=(d!=self.direction)
        self.direction=d; self.conf=c; self.reason=r
        self.strat_name=s; self.confluence=cf

        if changed and d:
            self.history.insert(0,{"d":d,"c":c,
                                    "t":datetime.datetime.now().strftime("%H:%M"),"s":s})
            self.history=self.history[:6]

        # Auto-entry — crypto needs stronger confluence (4+ signals)
        auto_min=self.v_min_conf_auto.get()
        ok_conf=c>=auto_min; ok_cf=cf>=(4 if is_crypto else 3)
        ok_sess=sq>=55; ok_cb=not self.risk.circuit_break
        ok_profit=not self.risk.profit_locked
        ok_news=not blocked

        if (self.auto_click and self.targets_ready and ok_conf and ok_cf and d
                and ok_sess and ok_cb and ok_profit and ok_news):
            bnd=self.builder._bnd
            if self.last_clicked_bnd!=bnd:
                self.last_clicked_bnd=bnd

                # ── PO API: place order directly if connected ─────────────
                if self.po_trader.enabled:
                    def _on_result(outcome):
                        self.root.after(0,lambda:self.log(outcome))
                        self.root.after(0,lambda:self.lbl_po.config(
                            text=f"PO:{'✅WIN' if outcome=='WIN' else '❌LOSS'}",
                            fg="#00ff88" if outcome=="WIN" else "#ff4444"))
                    placed=self.po_trader.place_order(
                        asset_sym=self.sym,
                        amount=bet,
                        direction=d,
                        duration=self.builder.dur,
                        on_result=_on_result)
                    if placed:
                        self.lbl_po.config(text=f"PO:📤 {d} ${bet}",fg="#a855f7")
                    else:
                        # Fallback to auto-clicker if PO API placement failed
                        tgt=self.call_tgt if d=="CALL" else self.put_tgt
                        cx,cy=tgt.center()
                        threading.Thread(target=fire_click,args=(tgt,cx,cy),daemon=True).start()
                else:
                    # PO API not connected — use auto-clicker as before
                    tgt=self.call_tgt if d=="CALL" else self.put_tgt
                    cx,cy=tgt.center()
                    threading.Thread(target=fire_click,args=(tgt,cx,cy),daemon=True).start()
                # ─────────────────────────────────────────────────────────

                # Telegram signal
                self.tg.send_signal(d,c,r,self.v_pair.get(),bet,cf)

        self._draw(changed)

    def _clock(self):
        now=datetime.datetime.utcnow()
        self.lbl_clk.config(text=f"UTC {now.strftime('%H:%M:%S')}")
        dur=self.builder.dur; rem=self.builder.remaining()
        m,s=int(rem//60),int(rem%60)
        clr="#ff4444" if rem<8 else ("#ffaa00" if rem<15 else "#00aa66")
        self.lbl_timer.config(text=f"⏱{m}:{s:02d}",fg=clr)
        # Urgent countdown flash
        if rem<5:
            bg="#1a0000" if int(time.time())%2==0 else "#050810"
            self.lbl_timer.config(bg=bg)
        else:
            self.lbl_timer.config(bg="#050810")
        w=self.cbar.winfo_width()
        if w>4:
            self.cbar.delete("all")
            self.cbar.create_rectangle(0,0,int(w*(1-rem/dur)),4,
                fill="#ff3333" if rem<8 else "#00aa44",outline="")
        self.root.after(1000,self._clock)

    def _draw(self,changed=False):
        d,c=self.direction,self.conf
        min_conf=self.v_min_conf.get()
        if not d or c<min_conf:
            self.lbl_sig.config(text="⏳ WAIT",fg="#ffaa00",bg="#050810")
            self.lbl_conf.config(text=f"Analyzing 22 Signals... [{c}%]",fg="#444")
            self.lbl_reason.config(text=f"► {self.reason}",fg="#555")
            self.cv.delete("all"); return
        clr="#00ff88" if d=="CALL" else "#ff4444"
        bg_="#020d05" if d=="CALL" else "#0d0202"
        self.lbl_sig.config(text="⬆  CALL" if d=="CALL" else "⬇  PUT",fg=clr,bg=bg_)
        stars="★★★" if c>=85 else ("★★" if c>=72 else "★")
        cf_str="⬥"*min(self.confluence,6)
        self.lbl_conf.config(text=f"{c}%  {stars}  {cf_str}  [{self.strat_name}]",fg=clr)
        w=self.cv.winfo_width()
        if w>4:
            self.cv.delete("all")
            self.cv.create_rectangle(0,0,int(w*c/100),10,
                fill="#00ff88" if c>=80 else ("#ffaa00" if c>=65 else "#ff8800"),outline="")
        self.lbl_reason.config(text=f"► {self.reason}",fg=clr)
        if self.history:
            self.lbl_hist.config(text="  ".join(
                f"{'↑' if h['d']=='CALL' else '↓'}{h['c']}% {h['t']}"
                for h in self.history[:5]))
        total=self.wins+self.losses; wr=int(self.wins/total*100) if total else 0
        self.lbl_stats.config(text=f"W:{self.wins} L:{self.losses} ({wr}%)",
                               fg="#00aa44" if wr>55 else "#555")
        if changed: self._beep(d)

    def log(self,result):
        if not self.direction: return
        if result=="WIN": self.wins+=1
        else: self.losses+=1
        self.risk.record_result(result,self.last_bet)
        self.brain.record(self.strat_name,result,self.direction,
                          self.last_valid_price,self.last_valid_price,
                          datetime.datetime.now().strftime("%H:%M:%S"))
        self.self_learner.record(self.strat_name, result=="WIN")
        self.tg.send_result(result,self.direction,self.v_pair.get())
        self._beep(result)
        try:
            with open("po_trades.csv","a",newline="") as f:
                csv.writer(f).writerow([
                    datetime.datetime.now().isoformat(),
                    self.v_pair.get(),self.v_dur.get(),
                    self.direction,f"{self.conf}%",result,
                    self.strat_name,f"${self.last_bet}",f"CF:{self.confluence}"])
        except: pass
        self._draw()
        self.v_balance.set(round(self.risk.balance,2))

    def _beep(self,ev):
        if not SOUND: return
        try:
            if ev=="CALL":   winsound.Beep(1100,80);  winsound.Beep(1400,120)
            elif ev=="PUT":  winsound.Beep(500,80);   winsound.Beep(350,120)
            elif ev=="WIN":  winsound.Beep(1500,80);  winsound.Beep(1800,200)
            elif ev=="LOSS": winsound.Beep(250,200)
        except: pass

    def run(self): self.root.mainloop()


if __name__=="__main__":
    App().run()
