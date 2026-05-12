//+------------------------------------------------------------------+
//|                                                  fib_090_ea.mq5  |
//|                                Fibonacci 0.900 mean-reversion EA  |
//|                                                                   |
//|  STRATEGY                                                         |
//|  ========                                                         |
//|  - Identify a range over `Lookback` bars (highest high - lowest)  |
//|  - Compute Fib 0.900 retracement of that range                    |
//|  - LONG when price touches the 0.900 level from above             |
//|  - Exit on TP at midline (0.500) or SL beyond range extreme       |
//|                                                                   |
//|  Mirrors the Python backtester in elitebot/combined_backtest/     |
//|  Use with `every_tick_real` model for honest fill simulation.     |
//+------------------------------------------------------------------+
#property copyright   "Florent Morel 2026"
#property version     "1.00"
#property strict
#property description "Fib 0.900 mean-reversion — companion to mcp-mt5-strategie-server"

#include <Trade/Trade.mqh>

//--- inputs (exposed to Strategy Tester and optimizer)
input int    Lookback     = 20;        // bars used to define the range
input double FibLevel     = 0.900;     // entry retracement
input double FibExit      = 0.500;     // exit retracement (TP)
input double LotSize      = 0.10;      // fixed lot
input int    SlippageBuf  = 20;        // points
input int    MagicNumber  = 909090;    // magic for this EA
input bool   LongOnly     = true;      // disable shorts (mirrors Python)

//--- handles
CTrade   trade;

//+------------------------------------------------------------------+
//| Init                                                              |
//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(SlippageBuf);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("FibEA init — Lookback=%d FibLevel=%.3f", Lookback, FibLevel);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Helpers                                                           |
//+------------------------------------------------------------------+
bool RangeOver(int bars, double &hi, double &lo)
  {
   double h[]; double l[];
   if(CopyHigh(_Symbol, _Period, 1, bars, h) <= 0) return false;
   if(CopyLow (_Symbol, _Period, 1, bars, l) <= 0) return false;
   hi = h[ArrayMaximum(h)];
   lo = l[ArrayMinimum(l)];
   return (hi > lo);
  }

bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; --i)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == MagicNumber &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| OnTick — fires on every tick when `every_tick_real` is active     |
//+------------------------------------------------------------------+
void OnTick()
  {
   // 1 bar at a time logic, but check on every tick for fill precision
   static datetime last_bar_time = 0;
   datetime cur_bar = (datetime)SeriesInfoInteger(_Symbol, _Period, SERIES_LASTBAR_DATE);
   bool is_new_bar = (cur_bar != last_bar_time);
   last_bar_time = cur_bar;

   if(HasOpenPosition())
      return;

   double hi, lo;
   if(!RangeOver(Lookback, hi, lo))
      return;

   double range = hi - lo;
   double entry_level = hi - FibLevel * range;       // 0.900 retr.
   double exit_level  = hi - FibExit  * range;       // 0.500 retr.

   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
      return;

   // LONG : price touched 0.900 level from above (bid <= entry)
   if(t.bid <= entry_level && t.bid >= lo)
     {
      double sl = lo - range * 0.05;   // 5% buffer below range
      double tp = exit_level;
      trade.Buy(LotSize, _Symbol, t.ask, sl, tp,
                StringFormat("Fib %.3f LB=%d", FibLevel, Lookback));
      return;
     }

   // SHORT (mirror) — only if LongOnly = false
   if(!LongOnly)
     {
      double entry_short = lo + FibLevel * range;
      double exit_short  = lo + FibExit  * range;
      if(t.ask >= entry_short && t.ask <= hi)
        {
         double sl = hi + range * 0.05;
         double tp = exit_short;
         trade.Sell(LotSize, _Symbol, t.bid, sl, tp,
                    StringFormat("Fib SHORT %.3f LB=%d", FibLevel, Lookback));
        }
     }
  }

//+------------------------------------------------------------------+
//| Deinit                                                            |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   PrintFormat("FibEA deinit — reason=%d", reason);
  }
//+------------------------------------------------------------------+
