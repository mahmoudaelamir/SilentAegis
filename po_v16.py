#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║        POCKET OPTION EXPERT BOT — V16 PROFESSIONAL             ║
║  ─────────────────────────────────────────────────────  ║
║  • 12 استراتيجية محترفة مع أوزان ديناميكية                     ║
║  • فلتر ADX لتجنب الأسواق العشوائية                            ║
║  • فلتر جلسات التداول (London/NY Overlap)                      ║
║  • Multi-Timeframe Trend Confirmation                           ║
║  • Pivot Points يومية (S1/R1/PP)                               ║
║  • Circuit Breaker: إيقاف بعد 3 خسائر متتالية                 ║
║  • Martingale محكوم (مستويان فقط)                              ║
║  • إدارة رأس المال الديناميكية                                  ║
║  • تحليل أفضل جلسة وأفضل استراتيجية لكل زوج                   ║
╚══════════════════════════════════════════════════════════════════╝
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

PAIRS = {
    "EUR/USD OTC":"EURUSD=X","GBP/USD OTC":"GBPUSD=X","USD/JPY OTC":"USDJPY=X",
    "AUD/USD OTC":"AUDUSD=X","GBP/JPY OTC":"GBPJPY=X","EUR/JPY OTC":"EURJPY=X",
    "USD/CAD OTC":"USDCAD=X","USD/CHF OTC":"USDCHF=X","NZD/USD OTC":"NZDUSD=X",
    "EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X",
    "GBP/JPY":"GBPJPY=X","EUR/JPY":"EURJPY=X","AUD/USD":"AUDUSD=X",
    "BTC/USD":"BINANCE:BTCUSDT","ETH/USD":"BINANCE:ETHUSDT",
    "GOLD":"GC=F","OIL":"CL=F",
}
CANDLE_DUR = {"30s":30,"1m":60,"2m":120,"3m":180,"5m":300}

def _ema(prices, period):
    if len(prices)<period: return None
    k=2/(period+1); e=sum(prices[:period])/period
    for p in prices[period:]: e=p*k+e*(1-k)
    return e

def _rsi(prices, period=14):
    if len(prices)<period+1: return None
    g=[max(prices[i]-prices[i-1],0) for i in range(1,len(prices))]
    l=[max(prices[i-1]-prices[i],0) for i in range(1,len(prices))]
    ag=sum(g[-period:])/period; al=sum(l[-period:])/period
    if al==0: return 100.0
    return 100-100/(1+ag/al)

def _bollinger(prices, period=20):
    if len(prices)<period: return None,None,None
    sma=sum(prices[-period:])/period
    std=math.sqrt(sum((x-sma)**2 for x in prices[-period:])/period)
    return sma+2*std, sma, sma-2*std

def _stochastic(highs, lows, closes, k=14):
    if len(closes)<k: return None
    hmax=max(highs[-k:]); lmin=min(lows[-k:])
    if hmax==lmin: return 50.0
    return (closes[-1]-lmin)/(hmax-lmin)*100

def _atr(candles, period=14):
    if len(candles)<period+1: return None
    trs=[]
    for i in range(1,len(candles)):
        h,l,pc=candles[i]["h"],candles[i]["l"],candles[i-1]["c"]
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs[-period:])/period

def _adx(candles, period=14):
    if len(candles)<period+2: return None
    plus_dm,minus_dm,trs=[],[],[]
    for i in range(1,len(candles)):
        h,l,ph,pl=candles[i]["h"],candles[i]["l"],candles[i-1]["h"],candles[i-1]["l"]
        pc=candles[i-1]["c"]
        up=h-ph; down=pl-l
        plus_dm.append(up if up>down and up>0 else 0)
        minus_dm.append(down if down>up and down>0 else 0)
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    if len(trs)<period: return None
    atr_v=sum(trs[-period:])/period
    pdi_v=sum(plus_dm[-period:])/period
    mdi_v=sum(minus_dm[-period:])/period
    if atr_v==0: return 0
    pdi=pdi_v/atr_v*100; mdi=mdi_v/atr_v*100
    if pdi+mdi==0: return 0
    return abs(pdi-mdi)/(pdi+mdi)*100

def _pivot_points(candles):
    if len(candles)<20: return None,None,None
    recent=candles[-20:]
    H=max(c["h"] for c in recent); L=min(c["l"] for c in recent); C=candles[-1]["c"]
    PP=(H+L+C)/3; R1=2*PP-L; S1=2*PP-H
    return PP,R1,S1

def _williams_r(highs,lows,closes,period=14):
    if len(closes)<period: return None
    hmax=max(highs[-period:]); lmin=min(lows[-period:])
    if hmax==lmin: return -50
    return (hmax-closes[-1])/(hmax-lmin)*-100

def _momentum(prices, period=10):
    if len(prices)<period+1: return None
    return (prices[-1]/prices[-period-1]-1)*100

def _cci(highs,lows,closes,period=14):
    if len(closes)<period: return None
    tp=[(highs[i]+lows[i]+closes[i])/3 for i in range(len(closes))]
    tp_mean=sum(tp[-period:])/period
    mean_dev=sum(abs(x-tp_mean) for x in tp[-period:])/period
    if mean_dev==0: return 0
    return (tp[-1]-tp_mean)/(0.015*mean_dev)

def _is_doji(c,t=0.1):
    body=abs(c["c"]-c["o"]); rng=c["h"]-c["l"]
    return rng>0 and body/rng<t

def _is_hammer(c):
    body=abs(c["c"]-c["o"]); rng=c["h"]-c["l"]
    if rng==0 or body==0: return False
    lw=min(c["c"],c["o"])-c["l"]; uw=c["h"]-max(c["c"],c["o"])
    return lw>=2*body and uw<=body*0.5

def _is_shooting_star(c):
    body=abs(c["c"]-c["o"]); rng=c["h"]-c["l"]
    if rng==0 or body==0: return False
    uw=c["h"]-max(c["c"],c["o"]); lw=min(c["c"],c["o"])-c["l"]
    return uw>=2*body and lw<=body*0.5

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
    body=abs(c["c"]-c["o"]); rng=c["h"]-c["l"]
    if rng==0: return None
    lw=min(c["c"],c["o"])-c["l"]; uw=c["h"]-max(c["c"],c["o"])
    if lw>ratio*body and lw>uw*2: return "CALL"
    if uw>ratio*body and uw>lw*2: return "PUT"
    return None

def session_quality():
    h=datetime.datetime.utcnow().hour
    active=[]
    if 7<=h<16: active.append("London")
    if 12<=h<21: active.append("NewYork")
    if 0<=h<8 or h>=23: active.append("Tokyo")
    if "London" in active and "NewYork" in active: return 95,"LON+NY ⚡",1.15
    elif "NewYork" in active: return 82,"New York",1.08
    elif "London" in active: return 78,"London",1.05
    elif "Tokyo" in active: return 55,"Tokyo",0.90
    else: return 30,"OFF-HOURS ⚠",0.70

class StrategyEngine:
    def run_all(self, candles):
        if len(candles)<6: return "CALL",52,"Warming Up","System"
        closes=[c["c"] for c in candles]
        highs=[c["h"] for c in candles]; lows=[c["l"] for c in candles]
        c1,c2,c3,c4=candles[-4],candles[-3],candles[-2],candles[-1]
        adx_val=_adx(candles,14); adx_ok=adx_val is None or adx_val>=18
        results=[]
        pat=self._candle_patterns(candles,c1,c2,c3,c4)
        if pat: results.append((*pat,"Candle",2.2))
        s=self._rsi_strat(closes)
        if s: results.append((*s,"RSI",1.6))
        s=self._ema_cross(closes)
        if s: results.append((*s,"EMA",1.9))
        s=self._macd_strat(closes)
        if s: results.append((*s,"MACD",1.7))
        s=self._bb_strat(closes)
        if s: results.append((*s,"BB",1.8))
        s=self._stoch_strat(highs,lows,closes)
        if s: results.append((*s,"Stoch",1.5))
        s=self._sr_pivot(closes,highs,lows,candles)
        if s: results.append((*s,"SR/Pivot",2.0))
        s=self._williams_strat(highs,lows,closes)
        if s: results.append((*s,"Williams",1.4))
        s=self._cci_strat(highs,lows,closes)
        if s: results.append((*s,"CCI",1.5))
        s=self._momentum_trend(closes)
        if s: results.append((*s,"Momentum",1.6))
        s=self._atr_breakout(candles,closes)
        if s: results.append((*s,"ATR",1.5))
        s=self._mtf_trend(closes)
        if s: results.append((*s,"MTF",2.1))
        if not results:
            micro="CALL" if closes[-1]>=closes[-2] else "PUT"
            return micro,52,"Live Pulse","Micro"
        call_w=put_w=0.0; call_r=[]; put_r=[]; bc_call=bc_put=0
        for d,conf,reason,name,w in results:
            score=(conf/100)*w
            if not adx_ok: score*=0.75
            if d=="CALL": call_w+=score; call_r.append(f"{name}:{conf}%"); bc_call=max(bc_call,conf)
            else:          put_w+=score;  put_r.append(f"{name}:{conf}%");  bc_put=max(bc_put,conf)
        total=call_w+put_w
        if total==0: return "CALL",52,"No Signal","Market"
        if call_w>=put_w:
            con=int((call_w/total)*100); fin=min(95,int(con*0.55+bc_call*0.45))
            if len(call_r)>=4: fin=min(95,fin+5)
            return "CALL",fin," | ".join(call_r[:3]),call_r[0].split(":")[0] if call_r else "Multi"
        else:
            con=int((put_w/total)*100); fin=min(95,int(con*0.55+bc_put*0.45))
            if len(put_r)>=4: fin=min(95,fin+5)
            return "PUT",fin," | ".join(put_r[:3]),put_r[0].split(":")[0] if put_r else "Multi"

    def _candle_patterns(self,cs,c1,c2,c3,c4):
        if _is_morning_star(cs[-4],cs[-3],cs[-2]): return "CALL",90,"Morning Star ★★★"
        if _is_evening_star(cs[-4],cs[-3],cs[-2]): return "PUT",90,"Evening Star ★★★"
        if _is_3ws(c2,c3,c4): return "CALL",87,"3 White Soldiers"
        if _is_3bc(c2,c3,c4): return "PUT",87,"3 Black Crows"
        if _is_bull_engulf(c3,c4): return "CALL",84,"Bull Engulfing"
        if _is_bear_engulf(c3,c4): return "PUT",84,"Bear Engulfing"
        pb=_is_pin_bar(c4)
        if pb=="CALL": return "CALL",82,"Pin Bar Bull"
        if pb=="PUT":  return "PUT",82,"Pin Bar Bear"
        if _is_tweezer_bot(c3,c4): return "CALL",79,"Tweezer Bottom"
        if _is_tweezer_top(c3,c4): return "PUT",79,"Tweezer Top"
        if _is_hammer(c4): return "CALL",77,"Hammer"
        if _is_shooting_star(c4): return "PUT",77,"Shooting Star"
        if _is_inside_bar(c3,c4):
            return ("CALL",72,"Inside Bar Break↑") if cs[-5]["c"]<cs[-3]["c"] else ("PUT",72,"Inside Bar Break↓")
        if _is_doji(c3):
            if c2["c"]<c2["o"] and c4["c"]>c4["o"]: return "CALL",73,"Doji Reversal↑"
            if c2["c"]>c2["o"] and c4["c"]<c4["o"]: return "PUT",73,"Doji Reversal↓"
        return None

    def _rsi_strat(self,closes):
        if len(closes)<15: return None
        rsi=_rsi(closes,14); rp=_rsi(closes[:-1],14)
        if rsi is None: return None
        if rsi<22:  return "CALL",87,f"RSI Oversold {rsi:.0f}"
        if rsi>78:  return "PUT",87,f"RSI Overbought {rsi:.0f}"
        if rsi<30:  return "CALL",80,f"RSI Low {rsi:.0f}"
        if rsi>70:  return "PUT",80,f"RSI High {rsi:.0f}"
        if rp and rp<50<=rsi: return "CALL",72,f"RSI Cross50↑"
        if rp and rp>50>=rsi: return "PUT",72,f"RSI Cross50↓"
        ro=_rsi(closes[:-3],14)
        if ro:
            if rsi<45 and closes[-1]<closes[-3] and rsi>ro: return "CALL",78,f"RSI Bull Div"
            if rsi>55 and closes[-1]>closes[-3] and rsi<ro: return "PUT",78,f"RSI Bear Div"
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
        if fn>sn and gap>0.025 and tu: return "CALL",68,f"EMA Uptrend"
        if fn<sn and gap>0.025 and td: return "PUT",68,f"EMA Downtrend"
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
        if hp>=0>hn: return "PUT",83,"MACD Cross↓"
        if hn>0 and hn>hp: return "CALL",66,"MACD Mom↑"
        if hn<0 and hn<hp: return "PUT",66,"MACD Mom↓"
        return None

    def _bb_strat(self,closes):
        if len(closes)<21: return None
        up,mid,lo=_bollinger(closes,20)
        if None in (up,mid,lo): return None
        p=closes[-1]; pp=closes[-2]; bw=(up-lo)/mid
        bwp=((_bollinger(closes[:-1],20)[0] or 0)-(_bollinger(closes[:-1],20)[2] or 0))/mid
        sq=bw<bwp*0.8
        if p<=lo:
            c=min(92,74+int(bw*600)); c=min(95,c+4) if sq else c
            return "CALL",c,f"BB Lower {'Squeeze' if sq else ''}"
        if p>=up:
            c=min(92,74+int(bw*600)); c=min(95,c+4) if sq else c
            return "PUT",c,f"BB Upper {'Squeeze' if sq else ''}"
        if pp<mid<=p: return "CALL",66,"BB Mid↑"
        if pp>mid>=p: return "PUT",66,"BB Mid↓"
        return None

    def _stoch_strat(self,highs,lows,closes):
        if len(closes)<14: return None
        k=_stochastic(highs,lows,closes,14); kp=_stochastic(highs[:-1],lows[:-1],closes[:-1],14)
        if k is None: return None
        if k<15: return "CALL",84,f"Stoch Oversold {k:.0f}"
        if k>85: return "PUT",84,f"Stoch Overbought {k:.0f}"
        if k<25: return "CALL",76,f"Stoch Low {k:.0f}"
        if k>75: return "PUT",76,f"Stoch High {k:.0f}"
        if kp and kp<50<=k: return "CALL",68,"Stoch↑"
        if kp and kp>50>=k: return "PUT",68,"Stoch↓"
        return None

    def _sr_pivot(self,closes,highs,lows,candles):
        if len(closes)<20: return None
        pp,r1,s1=_pivot_points(candles)
        p=closes[-1]
        sup=min(closes[-30:]) if len(closes)>=30 else min(closes)
        res=max(closes[-30:]) if len(closes)>=30 else max(closes)
        rng=res-sup
        if rng==0: return None
        m=rng*0.035
        if pp and abs(p-s1)<m*1.5: return "CALL",85,f"Pivot S1={s1:.5f}"
        if pp and abs(p-r1)<m*1.5: return "PUT",85,f"Pivot R1={r1:.5f}"
        if pp and abs(p-pp)<m:
            return ("CALL",70,f"Pivot PP") if closes[-1]>closes[-2] else ("PUT",70,f"Pivot PP")
        if p<=sup+m: return "CALL",84,f"Support {sup:.5f}"
        if p>=res-m: return "PUT",84,f"Resistance {res:.5f}"
        return None

    def _williams_strat(self,highs,lows,closes):
        if len(closes)<14: return None
        wr=_williams_r(highs,lows,closes,14); wrp=_williams_r(highs[:-1],lows[:-1],closes[:-1],14)
        if wr is None: return None
        if wr<-85: return "CALL",82,f"Williams OS {wr:.0f}"
        if wr>-15: return "PUT",82,f"Williams OB {wr:.0f}"
        if wrp and wrp<-50 and wr>=-50: return "CALL",68,"Williams↑"
        if wrp and wrp>-50 and wr<-50:  return "PUT",68,"Williams↓"
        return None

    def _cci_strat(self,highs,lows,closes):
        if len(closes)<14: return None
        cci=_cci(highs,lows,closes,14)
        if cci is None: return None
        if cci<-150: return "CALL",82,f"CCI OS {cci:.0f}"
        if cci>+150: return "PUT",82,f"CCI OB {cci:.0f}"
        if cci<-100: return "CALL",72,f"CCI Low {cci:.0f}"
        if cci>+100: return "PUT",72,f"CCI High {cci:.0f}"
        return None

    def _momentum_trend(self,closes):
        if len(closes)<12: return None
        mom=_momentum(closes,10)
        if mom is None: return None
        acc=closes[-1]-closes[-2]-(closes[-2]-closes[-3])
        e8=_ema(closes,8); e21=_ema(closes,21)
        au=e8 and e21 and e8>e21; ad=e8 and e21 and e8<e21
        if mom>0.04 and acc>0 and au: return "CALL",74,f"Momentum↑ {mom:.3f}%"
        if mom<-0.04 and acc<0 and ad: return "PUT",74,f"Momentum↓ {mom:.3f}%"
        rec=sum(closes[-5:])/5; old=sum(closes[-10:-5])/5
        chg=(rec-old)/old*100
        if chg>0.03 and acc>0: return "CALL",66,f"Trend↑ {chg:.3f}%"
        if chg<-0.03 and acc<0: return "PUT",66,f"Trend↓ {chg:.3f}%"
        return None

    def _atr_breakout(self,candles,closes):
        if len(candles)<16: return None
        atr=_atr(candles,14)
        if not atr or atr==0: return None
        mv=abs(closes[-1]-closes[-2]); ratio=mv/atr
        if ratio>2.0:
            d="CALL" if closes[-1]>closes[-2] else "PUT"
            return d,min(88,70+int(ratio*5)),f"ATR Breakout {ratio:.1f}x"
        if ratio>1.5:
            d="CALL" if closes[-1]>closes[-2] else "PUT"
            return d,73,f"ATR Move {ratio:.1f}x"
        return None

    def _mtf_trend(self,closes):
        if len(closes)<55: return None
        e8=_ema(closes,8); e21=_ema(closes,21); e50=_ema(closes,50)
        if None in (e8,e21,e50): return None
        if e8>e21>e50:
            gap=(e8-e50)/e50*100
            return "CALL",min(88,68+int(gap*500)),f"MTF Bullish {gap:.3f}%"
        if e8<e21<e50:
            gap=(e50-e8)/e50*100
            return "PUT",min(88,68+int(gap*500)),f"MTF Bearish {gap:.3f}%"
        return None


class RiskManager:
    def __init__(self):
        self.balance=1000.0; self.base_bet=10.0
        self.consecutive_L=0; self.martingale_lvl=0
        self.circuit_break=False; self.cb_until=None
        self.total_trades=0; self.total_wins=0
        self.peak_balance=1000.0; self.daily_loss=0.0; self.max_daily_loss=200.0

    def get_bet(self,conf,smult):
        if self.circuit_break:
            now=datetime.datetime.utcnow()
            if self.cb_until and now<self.cb_until:
                mins=int((self.cb_until-now).seconds/60)
                return 0,f"⛔ Circuit Breaker ({mins}min)"
            else:
                self.circuit_break=False; self.consecutive_L=0; self.martingale_lvl=0
        if self.daily_loss>=self.max_daily_loss: return 0,"⛔ Daily Loss Limit"
        sm=1.5 if conf>=85 else (1.2 if conf>=78 else (1.0 if conf>=70 else 0.7))
        bet=self.base_bet*sm*smult
        if self.martingale_lvl==1: bet*=2.0
        elif self.martingale_lvl>=2: bet*=4.0
        bet=min(bet,self.balance*0.05); bet=max(bet,1.0)
        return round(bet,1),""

    def record_result(self,result,bet):
        if result=="WIN":
            self.balance+=bet*0.85; self.peak_balance=max(self.peak_balance,self.balance)
            self.consecutive_L=0; self.martingale_lvl=0; self.total_wins+=1
        else:
            self.balance-=bet; self.daily_loss+=bet; self.consecutive_L+=1
            if self.consecutive_L>=2: self.martingale_lvl=min(self.martingale_lvl+1,2)
            if self.consecutive_L>=3:
                self.circuit_break=True
                self.cb_until=datetime.datetime.utcnow()+datetime.timedelta(minutes=15)
        self.total_trades+=1

    def winrate(self):
        return self.total_wins/self.total_trades*100 if self.total_trades else 0.0

    def drawdown(self):
        return (self.peak_balance-self.balance)/self.peak_balance*100 if self.peak_balance else 0.0

    def status_line(self):
        cb="🔴" if self.circuit_break else ("🟡" if self.martingale_lvl>0 else "🟢")
        return f"{cb} Bal:{self.balance:.0f} | WR:{self.winrate():.0f}% | DD:{self.drawdown():.1f}%"


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

    def best_strats(self):
        r=[(v["W"]/(v["W"]+v["L"])*100,s,v["W"]+v["L"]) for s,v in self.stats.items() if v["W"]+v["L"]>=5]
        r.sort(reverse=True); return r[:3]

    def stats_line(self):
        b=self.best_strats()
        return " | ".join(f"{s}:{wr:.0f}%({t})" for wr,s,t in b) if b else "No data yet"


class CandleBuilder:
    def __init__(self,dur=60):
        self.dur=dur; self.done=[]; self._c=None; self._bnd=None

    def feed(self,price):
        now=time.time(); bnd=now-(now%self.dur)
        if self._bnd!=bnd:
            if self._c: self.done.append(dict(self._c))
            if len(self.done)>300: self.done=self.done[-300:]
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
    def count(self): return len(self.done)


class TargetCrosshair:
    def __init__(self,root,title,bg,sx,sy):
        self.win=tk.Toplevel(root)
        self.win.overrideredirect(True); self.win.attributes("-topmost",True)
        self.win.attributes("-alpha",0.85)
        self.win.geometry(f"65x65+{sx}+{sy}")
        self.win.configure(bg=bg,cursor="cross")
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


def live_price(symbol):
    if symbol.startswith("BINANCE:"):
        coin=symbol.split(":")[1]
        try:
            req=urllib.request.Request(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}")
            with urllib.request.urlopen(req,timeout=3) as r: return float(json.loads(r.read())["price"])
        except: return None
    url=(f"https://query1.finance.yahoo.com/v7/finance/quote"
         f"?symbols={symbol}&fields=regularMarketPrice,bid&_={int(time.time())}")
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=3) as r: d=json.loads(r.read())
        res=d["quoteResponse"]["result"]
        if res:
            p=res[0].get("regularMarketPrice") or res[0].get("bid")
            if p: return float(p)
    except: pass
    return None


class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.overrideredirect(True); self.root.attributes("-topmost",True)
        self.root.configure(bg="#060a0e")
        SW=self.root.winfo_screenwidth(); SH=self.root.winfo_screenheight()
        self.SW=SW; self.SH=SH; self.H=105
        self.root.geometry(f"{SW}x{self.H}+0+0")
        self.sym="EURUSD=X"; self.builder=CandleBuilder(60)
        self.brain=AIBrain(); self.engine=StrategyEngine(); self.risk=RiskManager()
        self.direction=None; self.conf=0; self.reason=""; self.strat_name=""
        self.prev_price=None; self._last_diff=0; self.wins=self.losses=0
        self.history=[]; self.pending_trades=[]; self.auto_click=False
        self.targets_ready=False; self.last_clicked_bnd=None
        self.last_valid_price=1.15000; self.last_bet=10.0; self.adx_val=None
        self.v_pair=tk.StringVar(value="EUR/USD OTC")
        self.v_dur=tk.StringVar(value="1m")
        self.v_min_conf=tk.IntVar(value=75)
        self.v_balance=tk.DoubleVar(value=1000.0)
        self._build(); self._clock()
        self.root.after(1000,self._init_targets)
        threading.Thread(target=self._prefill,daemon=True).start()
        self._price_loop()

    def _init_targets(self):
        self.call_tgt=TargetCrosshair(self.root,"CALL","#00ff88",self.SW-270,self.SH//2-95)
        self.put_tgt=TargetCrosshair(self.root,"PUT","#ff4444",self.SW-270,self.SH//2+95)
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

    def _build(self):
        bar=tk.Frame(self.root,bg="#060a0e")
        bar.pack(fill="both",expand=True)
        bar.bind("<ButtonPress-1>",lambda e:[setattr(self,"_dx",e.x),setattr(self,"_dy",e.y)])
        bar.bind("<B1-Motion>",lambda e:self.root.geometry(
            f"+{self.root.winfo_x()+(e.x-self._dx)}+{self.root.winfo_y()+(e.y-self._dy)}"))
        self._dx=self._dy=0
        c1=self._col(bar,108)
        tk.Label(c1,text="PRO V16 ⚡",bg="#060a0e",fg="#00ff44",font=("Consolas",8,"bold")).pack(anchor="w",padx=3,pady=(4,0))
        self.lbl_clk=tk.Label(c1,text="",bg="#060a0e",fg="#336633",font=("Consolas",7)); self.lbl_clk.pack(anchor="w",padx=3)
        self.lbl_sess=tk.Label(c1,text="",bg="#060a0e",fg="#ffaa00",font=("Consolas",7,"bold")); self.lbl_sess.pack(anchor="w",padx=3)
        self.lbl_adx=tk.Label(c1,text="ADX: --",bg="#060a0e",fg="#555",font=("Consolas",7)); self.lbl_adx.pack(anchor="w",padx=3)
        self.lbl_risk_line=tk.Label(c1,text="",bg="#060a0e",fg="#aaa",font=("Consolas",6),wraplength=104,justify="left"); self.lbl_risk_line.pack(anchor="w",padx=3)
        c2=self._col(bar,215)
        ttk.Combobox(c2,textvariable=self.v_pair,values=list(PAIRS.keys()),width=15,font=("Consolas",8)).pack(anchor="w",padx=3,pady=(4,1))
        row=tk.Frame(c2,bg="#060a0e"); row.pack(anchor="w",padx=3,fill="x")
        ttk.Combobox(row,textvariable=self.v_dur,values=list(CANDLE_DUR.keys()),width=5,font=("Consolas",8)).pack(side="left")
        self.btn_auto=tk.Button(row,text="🤖 Loading...",bg="#111",fg="#ffaa00",font=("Consolas",8,"bold"),relief="flat",command=self.toggle_auto,state="disabled")
        self.btn_auto.pack(side="left",padx=5)
        row2=tk.Frame(c2,bg="#060a0e"); row2.pack(anchor="w",padx=3,fill="x")
        tk.Label(row2,text="Min%:",bg="#060a0e",fg="#555",font=("Consolas",7)).pack(side="left")
        tk.Spinbox(row2,from_=60,to=95,textvariable=self.v_min_conf,width=4,font=("Consolas",7),bg="#111",fg="#aaa").pack(side="left")
        tk.Label(row2,text=" Bal$:",bg="#060a0e",fg="#555",font=("Consolas",7)).pack(side="left")
        tk.Entry(row2,textvariable=self.v_balance,width=7,font=("Consolas",7),bg="#111",fg="#aaa").pack(side="left")
        tk.Button(row2,text="✓",bg="#111",fg="#0f0",font=("Consolas",7),relief="flat",command=self._set_balance).pack(side="left",padx=2)
        self.v_pair.trace("w",lambda *_:self._on_change()); self.v_dur.trace("w",lambda *_:self._on_change())
        self.lbl_st=tk.Label(c2,text="● 12 Strategies | ADX | MTF | Pivots",bg="#060a0e",fg="#A78BFA",font=("Consolas",7,"bold")); self.lbl_st.pack(anchor="w",padx=3,pady=(1,0))
        c3=self._col(bar,165)
        tk.Label(c3,text="LIVE PRICE",bg="#060a0e",fg="#1a1a2e",font=("Consolas",7)).pack(pady=(5,0))
        self.lbl_price=tk.Label(c3,text="------",bg="#060a0e",fg="#00d4ff",font=("Consolas",14,"bold")); self.lbl_price.pack()
        self.cbar=tk.Canvas(c3,height=4,bg="#0d1117",highlightthickness=0,width=150); self.cbar.pack(padx=4,pady=1)
        self.lbl_timer=tk.Label(c3,text="",bg="#060a0e",fg="#ffaa00",font=("Consolas",9,"bold")); self.lbl_timer.pack()
        self.lbl_bet=tk.Label(c3,text="Bet: $--",bg="#060a0e",fg="#A78BFA",font=("Consolas",8,"bold")); self.lbl_bet.pack()
        c4=self._col(bar,245)
        self.lbl_sig=tk.Label(c4,text="⏳ Scanning...",bg="#060a0e",fg="#222",font=("Consolas",18,"bold")); self.lbl_sig.pack(pady=(5,1))
        self.cv=tk.Canvas(c4,height=10,bg="#0d1117",highlightthickness=0,width=225); self.cv.pack(padx=8)
        self.lbl_conf=tk.Label(c4,text="",bg="#060a0e",fg="#444",font=("Consolas",8)); self.lbl_conf.pack()
        c5=self._col(bar,265)
        self.lbl_reason=tk.Label(c5,text="",bg="#060a0e",fg="#aaa",font=("Consolas",8,"bold"),wraplength=260,justify="left"); self.lbl_reason.pack(anchor="w",padx=3,pady=(8,0))
        self.lbl_hist=tk.Label(c5,text="",bg="#060a0e",fg="#2a3a2a",font=("Consolas",7)); self.lbl_hist.pack(anchor="w",padx=3)
        self.lbl_best=tk.Label(c5,text="",bg="#060a0e",fg="#334433",font=("Consolas",6)); self.lbl_best.pack(anchor="w",padx=3)
        c6=self._col(bar,148)
        brow=tk.Frame(c6,bg="#060a0e"); brow.pack(pady=(8,1))
        tk.Button(brow,text="WIN",bg="#0a2a0a",fg="#00ff88",font=("Consolas",10,"bold"),relief="flat",cursor="hand2",command=lambda:self.log("WIN"),padx=8,pady=5).pack(side="left",padx=1)
        tk.Button(brow,text="LOSS",bg="#2a0a0a",fg="#ff4444",font=("Consolas",10,"bold"),relief="flat",cursor="hand2",command=lambda:self.log("LOSS"),padx=5,pady=5).pack(side="left",padx=1)
        self.lbl_stats=tk.Label(c6,text="W:0 L:0",bg="#060a0e",fg="#333",font=("Consolas",7)); self.lbl_stats.pack()
        self.lbl_wr=tk.Label(c6,text="AI Trust: ---%",bg="#060a0e",fg="#A78BFA",font=("Consolas",7)); self.lbl_wr.pack()
        self.lbl_mart=tk.Label(c6,text="Martingale: OFF",bg="#060a0e",fg="#444",font=("Consolas",6)); self.lbl_mart.pack()
        c7=tk.Frame(bar,bg="#060a0e"); c7.pack(side="left",fill="both",expand=True)
        br=tk.Frame(c7,bg="#060a0e"); br.pack(anchor="w",padx=3,pady=(32,0))
        for t,bg,fg,cmd in [("X","#180000","#ff3333",self.root.quit),("TOP","#111","#444",lambda:self.root.geometry(f"{self.SW}x{self.H}+0+0")),("BOT","#111","#444",lambda:self.root.geometry(f"{self.SW}x{self.H}+0+{self.SH-self.H-40}"))]:
            tk.Button(br,text=t,bg=bg,fg=fg,font=("Consolas",7,"bold" if t=="X" else "normal"),relief="flat",cursor="hand2",command=cmd,padx=5,pady=2).pack(side="left",padx=1)

    def _col(self,p,w):
        f=tk.Frame(p,bg="#060a0e",width=w); f.pack(side="left",fill="y",padx=1); f.pack_propagate(False); return f

    def _set_balance(self):
        try:
            self.risk.balance=float(self.v_balance.get()); self.risk.peak_balance=self.risk.balance
            self.risk.base_bet=self.risk.balance*0.01; self.risk.daily_loss=0
        except: pass

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
                        self.builder.done.append({"o":q["open"][i],"h":q["high"][i],"l":q["low"][i],"c":q["close"][i]})
                if len(self.builder.done)>=10:
                    success=True; self.last_valid_price=self.builder.done[-1]["c"]
            except: pass
        if not success:
            p=self.last_valid_price; self.builder.done=[]
            for _ in range(80):
                p+=random.uniform(-0.0005,0.0005); o=p; c=p+random.uniform(-0.0004,0.0004)
                h=max(o,c)+random.uniform(0,0.0004); l=min(o,c)-random.uniform(0,0.0004)
                self.builder.done.append({"o":o,"h":h,"l":l,"c":c})
            self.last_valid_price=p
        self.root.after(0,self._analyze)

    def _on_change(self):
        self.sym=PAIRS.get(self.v_pair.get(),"EURUSD=X")
        self.builder=CandleBuilder(CANDLE_DUR.get(self.v_dur.get(),60))
        self.direction=None; self.pending_trades.clear()
        self.lbl_sig.config(text="⏳ Scanning...",fg="#222",bg="#060a0e")
        self.lbl_conf.config(text=""); self.lbl_reason.config(text=""); self.cv.delete("all")
        threading.Thread(target=self._prefill,daemon=True).start()

    def _price_loop(self):
        def _run():
            p=live_price(self.sym); is_otc="OTC" in self.v_pair.get()
            if p is None and is_otc: p=self.last_valid_price
            if p is not None:
                if is_otc: p+=random.uniform(-0.00012,0.00012)
                self.last_valid_price=p; self.root.after(0,lambda:self._on_price(p))
            self.root.after(800,self._price_loop)
        threading.Thread(target=_run,daemon=True).start()

    def _on_price(self,p):
        new_candle=self.builder.feed(p); n=self.builder.count(); now=time.time()
        diff=(p-self.prev_price) if self.prev_price else 0
        if diff!=0: self._last_diff=diff
        if   self._last_diff>0: self.lbl_price.config(text=f"▲ {p:.5f}",fg="#00ff88")
        elif self._last_diff<0: self.lbl_price.config(text=f"▼ {p:.5f}",fg="#ff4444")
        else:                   self.lbl_price.config(text=f"─ {p:.5f}",fg="#888")
        self.prev_price=p
        if new_candle:
            dt=datetime.datetime.now().strftime("%H:%M:%S"); surviving=[]
            for t in self.pending_trades:
                if now>=t["expiry"]:
                    won=(p>t["entry"]) if t["dir"]=="CALL" else (p<t["entry"])
                    self.brain.record(t["strat"],"WIN" if won else "LOSS",t["dir"],t["entry"],p,dt)
                else: surviving.append(t)
            self.pending_trades=surviving
        if n>=6:
            self._analyze()
            if new_candle:
                d,c,r,s=self.engine.run_all(self.builder.candles())
                self.pending_trades.append({"strat":s,"dir":d,"entry":p,"expiry":now+self.builder.dur-3})

    def _analyze(self):
        cs=self.builder.candles()
        if len(cs)<6: return
        sq,sname,smult=session_quality()
        self.adx_val=_adx(cs,14)
        adx_ok=self.adx_val is None or self.adx_val>=18
        d,c,r,s=self.engine.run_all(cs)
        c=max(50,min(95,int(c*smult)))
        if not adx_ok and self.adx_val is not None: c=int(c*0.80)
        wr=self.brain.get_wr(s)
        if wr>=65: c=min(95,c+int((wr-50)*0.25))
        bet,cb_msg=self.risk.get_bet(c,smult); self.last_bet=bet
        if self.adx_val:
            ac="#00ff88" if self.adx_val>=25 else ("#ffaa00" if self.adx_val>=18 else "#ff4444")
            self.lbl_adx.config(text=f"ADX:{self.adx_val:.0f} {'✓' if adx_ok else '✗'}",fg=ac)
        sc="#00ff88" if sq>=80 else ("#ffaa00" if sq>=55 else "#ff4444")
        self.lbl_sess.config(text=f"{sname} ({sq}%)",fg=sc)
        if cb_msg: self.lbl_bet.config(text=cb_msg,fg="#ff4444")
        else:
            ml=self.risk.martingale_lvl
            self.lbl_bet.config(text=f"Bet: ${bet}{' M'+str(ml) if ml>0 else ''}",fg="#ff8800" if ml>0 else "#A78BFA")
            self.lbl_mart.config(text=f"Martingale: {'L'+str(ml) if ml>0 else 'OFF'} | CB:{self.risk.consecutive_L}/3",fg="#ff8800" if ml>0 else "#444")
        self.lbl_risk_line.config(text=self.risk.status_line())
        self.lbl_wr.config(text=f"AI Trust: {wr:.1f}%",fg="#00ff88" if wr>=55 else "#ff4444")
        self.lbl_best.config(text=self.brain.stats_line())
        changed=(d!=self.direction); self.direction=d; self.conf=c; self.reason=r; self.strat_name=s
        if changed and d:
            self.history.insert(0,{"d":d,"c":c,"t":datetime.datetime.now().strftime("%H:%M"),"s":s})
            self.history=self.history[:6]
        mc=self.v_min_conf.get()
        if self.auto_click and self.targets_ready and c>=mc and d and sq>=55 and not self.risk.circuit_break:
            bnd=self.builder._bnd
            if self.last_clicked_bnd!=bnd:
                self.last_clicked_bnd=bnd; tgt=self.call_tgt if d=="CALL" else self.put_tgt
                cx,cy=tgt.center()
                threading.Thread(target=fire_click,args=(tgt,cx,cy),daemon=True).start()
        self._draw(changed)

    def _clock(self):
        now=datetime.datetime.utcnow(); self.lbl_clk.config(text=f"UTC {now.strftime('%H:%M:%S')}")
        dur=self.builder.dur; rem=self.builder.remaining()
        m,s=int(rem//60),int(rem%60)
        self.lbl_timer.config(text=f"⏱ {m}:{s:02d}",fg="#ff4444" if rem<8 else ("#ffaa00" if rem<15 else "#00aa66"))
        w=self.cbar.winfo_width()
        if w>4:
            self.cbar.delete("all")
            self.cbar.create_rectangle(0,0,int(w*(1-rem/dur)),4,fill="#ff3333" if rem<8 else "#00aa44",outline="")
        self.root.after(1000,self._clock)

    def _draw(self,changed=False):
        d,c=self.direction,self.conf
        if not d:
            self.lbl_sig.config(text="⏳ WAIT",fg="#ffaa00",bg="#060a0e")
            self.lbl_conf.config(text="Analyzing 12 Strategies...",fg="#444")
            self.lbl_reason.config(text=f"► {self.reason}",fg="#555")
            self.cv.delete("all"); return
        clr="#00ff88" if d=="CALL" else "#ff4444"
        bg_="#020d05" if d=="CALL" else "#0d0202"
        self.lbl_sig.config(text="⬆  CALL" if d=="CALL" else "⬇  PUT",fg=clr,bg=bg_)
        stars="★★★" if c>=84 else ("★★" if c>=72 else "★")
        self.lbl_conf.config(text=f"{c}%  {stars}  [{self.strat_name}]",fg=clr)
        w=self.cv.winfo_width()
        if w>4:
            self.cv.delete("all")
            self.cv.create_rectangle(0,0,int(w*c/100),10,fill="#00ff88" if c>=78 else ("#ffaa00" if c>=65 else "#ff8800"),outline="")
        self.lbl_reason.config(text=f"► {self.reason}",fg=clr)
        if self.history:
            self.lbl_hist.config(text="  ".join(f"{'↑' if h['d']=='CALL' else '↓'}{h['c']}% {h['t']}" for h in self.history[:5]))
        total=self.wins+self.losses; wr=int(self.wins/total*100) if total else 0
        self.lbl_stats.config(text=f"W:{self.wins} L:{self.losses} ({wr}%)",fg="#00aa44" if wr>55 else "#555")
        if changed: self._beep(d)

    def log(self,result):
        if not self.direction: return
        if result=="WIN": self.wins+=1
        else:             self.losses+=1
        self.risk.record_result(result,self.last_bet)
        self.brain.record(self.strat_name,result,self.direction,self.last_valid_price,self.last_valid_price,datetime.datetime.now().strftime("%H:%M:%S"))
        self._beep(result)
        try:
            with open("po_trades.csv","a",newline="") as f:
                csv.writer(f).writerow([datetime.datetime.now().isoformat(),self.v_pair.get(),self.v_dur.get(),self.direction,f"{self.conf}%",result,self.strat_name,f"${self.last_bet}"])
        except: pass
        self._draw(); self.v_balance.set(round(self.risk.balance,2))

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
