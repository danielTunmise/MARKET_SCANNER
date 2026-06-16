import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, TrendingUp, TrendingDown, Terminal, CheckSquare, Square, Clock } from 'lucide-react';

// --- Helper Components ---

const TradeLedger = ({ activeTrades, tradeHistory }) => {
  const getStatusBadge = (status) => {
    if (status === 'ACTIVE') {
      return (
        <span className="text-xs font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded-full px-2 py-1 whitespace-nowrap">
          {status}
        </span>
      );
    }
    if (status.includes('WIN')) {
      return (
        <span className="text-xs font-bold bg-green-500/20 text-green-300 border border-green-500/30 rounded-full px-2 py-1 whitespace-nowrap">
          {status}
        </span>
      );
    }
    if (status.includes('LOSS')) {
      return (
        <span className="text-xs font-bold bg-red-500/20 text-red-300 border border-red-500/30 rounded-full px-2 py-1 whitespace-nowrap">
          {status}
        </span>
      );
    }
    return null;
  };

  const tradeRow = (trade) => (
    <div className="grid grid-cols-5 gap-4 items-center">
      <span className={`font-mono ${trade.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
        {trade.asset} {trade.direction}
      </span>
      <span className="font-mono text-gray-300">{trade.entry.toFixed(2)}</span>
      <span className="font-mono text-red-400">{trade.sl.toFixed(2)}</span>
      <span className="font-mono text-green-400">{trade.tp.toFixed(2)}</span>
      <div className="flex justify-end">
        {getStatusBadge(trade.status)}
      </div>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.6, duration: 0.5 }}
      className="bg-gray-800/50 backdrop-blur-sm rounded-lg shadow-lg p-6 border border-gray-700"
    >
      <h2 className="text-xl font-semibold text-white mb-4">
        Live Forward Testing Ledger
      </h2>

      {/* Active Trades Section */}
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-300 mb-3 border-b border-gray-700 pb-2">Active Trades</h3>
        <div className="space-y-3 p-2">
          {activeTrades && activeTrades.length > 0 ? (
            <>
              <div className="grid grid-cols-5 gap-4 text-sm text-gray-500 font-semibold">
                <span>Asset</span>
                <span>Entry</span>
                <span>Stop Loss</span>
                <span>Take Profit</span>
                <span className="text-right">Status</span>
              </div>
              <AnimatePresence>
                {activeTrades.map((trade) => (
                  <motion.div
                    key={trade.id}
                    layout
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="bg-gray-900/50 rounded-md p-3"
                  >
                    {tradeRow(trade)}
                  </motion.div>
                ))}
              </AnimatePresence>
            </>
          ) : (
            <p className="text-gray-500 italic text-center py-4">No active trades</p>
          )}
        </div>
      </div>

      {/* Trade History Section */}
      <div>
        <h3 className="text-lg font-medium text-gray-300 mb-3 border-b border-gray-700 pb-2">History</h3>
        <div className="space-y-3 p-2">
          {tradeHistory && tradeHistory.length > 0 ? (
            <>
              <div className="grid grid-cols-5 gap-4 text-sm text-gray-500 font-semibold">
                <span>Asset</span>
                <span>Entry</span>
                <span>Stop Loss</span>
                <span>Take Profit</span>
                <span className="text-right">Status</span>
              </div>
              <AnimatePresence>
                {tradeHistory.map((trade) => (
                  <motion.div
                    key={trade.id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="bg-gray-900/50 rounded-md p-3 opacity-80"
                  >
                    {tradeRow(trade)}
                  </motion.div>
                ))}
              </AnimatePresence>
            </>
          ) : (
            <p className="text-gray-500 italic text-center py-4">Awaiting first setup...</p>
          )}
        </div>
      </div>
    </motion.div>
  );
};


// --- Main App Component ---

function App() {
  const [marketData, setMarketData] = useState({
    spy_trend: 0,
    qqq_trend: 0,
    shared_trend: 0,
    spy_active_fvgs: [],
    qqq_active_fvgs: [],
    execution_alerts: [],
    active_trades: [],
    trade_history: [],
  });
  
  const [timeToOpen, setTimeToOpen] = useState('00:00:00');
  const [timerLabel, setTimerLabel] = useState('to NY Open');
  const [isMarketOpen, setIsMarketOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('wss://market-scanner-7x1d.onrender.com/ws');

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setMarketData(prev => ({ ...prev, ...data }));
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, []);

  // New York Session Open/Close Countdown Timer
  useEffect(() => {
    const updateTimer = () => {
      const now = new Date();
      // Get the current time adjusted for New York
      const nyTime = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
      
      const targetTime = new Date(nyTime);

      const currentHour = nyTime.getHours();
      const currentMinute = nyTime.getMinutes();
      const isWeekend = nyTime.getDay() === 0 || nyTime.getDay() === 6;
      const isMarketOpenNow = !isWeekend && (currentHour > 9 || (currentHour === 9 && currentMinute >= 30)) && currentHour < 16;
      
      setIsMarketOpen(isMarketOpenNow);

      if (isMarketOpenNow) {
        targetTime.setHours(16, 0, 0, 0);
        setTimerLabel('to NY Close');
      } else {
        targetTime.setHours(9, 30, 0, 0);

        // If it's past 9:30 AM EST, count down to 9:30 AM EST tomorrow
        if (nyTime > targetTime) {
          targetTime.setDate(targetTime.getDate() + 1);
        }
        
        // Skip weekends
        while (targetTime.getDay() === 0 || targetTime.getDay() === 6) {
          targetTime.setDate(targetTime.getDate() + 1);
        }
        
        setTimerLabel('to NY Open');
      }

      const diff = targetTime - nyTime;
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff / 1000 / 60) % 60);
      const seconds = Math.floor((diff / 1000) % 60);

      setTimeToOpen(
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      );
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, []);

  const TrendIcon = ({ trend }) => {
    if (trend === 1) return <TrendingUp className="text-green-400" />;
    if (trend === -1) return <TrendingDown className="text-red-400" />;
    return <Activity className="text-gray-400" />;
  };

  const checklistItems = [
    'New York session open',
    'Identify the current trend',
    'Wait for fvg to get filled',
    'Wait for an ifvg on the 1m time frame'
  ];

  const step1 = isMarketOpen;
  const step2 = step1 && marketData.shared_trend !== 0;
  const hasTappedFvg = marketData.spy_active_fvgs?.some(f => f.status.includes('TAPPED')) || marketData.qqq_active_fvgs?.some(f => f.status.includes('TAPPED'));
  const step3 = step2 && hasTappedFvg;
  const step4 = step3 && marketData.execution_alerts?.length > 0;
  const automatedChecklist = [step1, step2, step3, step4];

  const checkedCount = automatedChecklist.filter(Boolean).length;
  const progress = Math.round((checkedCount / 4) * 100);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8 font-sans">
      {/* Header */}
      <div className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">TUNMISE's ASSISTANT</h1>
          <p className="text-gray-400 mt-1">SETUP FINDER</p>
        </div>
        <div className="flex items-center gap-2 bg-gray-800 px-4 py-2 rounded-full">
          <div className={`w-3 h-3 rounded-full animate-pulse ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="font-semibold">{isConnected ? 'System Live' : 'Disconnected'}</span>
        </div>
      </div>
      <main className="max-w-7xl mx-auto space-y-6">
        {/* Main Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          
          {/* SPY Card */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-2xl p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-blue-400">S & P 500</h2>
              <div className="flex items-center gap-2 text-lg font-bold bg-gray-900 px-3 py-1 rounded-lg">
                <TrendIcon trend={marketData.spy_trend} />
                {marketData.spy_trend === 1 ? 'BULLISH' : marketData.spy_trend === -1 ? 'BEARISH' : 'NONE'}
              </div>
            </div>
            <div className="space-y-3">
              <h3 className="text-gray-400 text-sm font-semibold uppercase tracking-wider">Active 5m FVGs</h3>
              {(!isMarketOpen || marketData.shared_trend === 0) ? (
                <p className="text-gray-500 italic">Awaiting trend alignment...</p>
              ) : marketData.spy_active_fvgs?.length === 0 ? (
                <p className="text-gray-500 italic">No untouched gaps.</p>
              ) : (
                marketData.spy_active_fvgs?.map((fvg, i) => (
                  <div key={i} className="bg-gray-900 p-3 rounded-lg border border-gray-700 flex justify-between items-center">
                    <div>
                      <span className={`block font-bold ${fvg.type === 'BULLISH' ? 'text-green-400' : 'text-red-400'}`}>{fvg.type}</span>
                      <span className="text-xs text-gray-500">{fvg.status}</span>
                    </div>
                    <span className="font-mono text-sm bg-gray-800 px-2 py-1 rounded">{fvg.gap}</span>
                  </div>
                ))
              )}
            </div>
          </motion.div>

          {/* QQQ Card */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="bg-gray-800 border border-gray-700 rounded-2xl p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-purple-400">NASDAQ</h2>
              <div className="flex items-center gap-2 text-lg font-bold bg-gray-900 px-3 py-1 rounded-lg">
                <TrendIcon trend={marketData.qqq_trend} />
                {marketData.qqq_trend === 1 ? 'BULLISH' : marketData.qqq_trend === -1 ? 'BEARISH' : 'NONE'}
              </div>
            </div>
            <div className="space-y-3">
              <h3 className="text-gray-400 text-sm font-semibold uppercase tracking-wider">Active 5m FVGs</h3>
              {(!isMarketOpen || marketData.shared_trend === 0) ? (
                <p className="text-gray-500 italic">Awaiting trend alignment...</p>
              ) : marketData.qqq_active_fvgs?.length === 0 ? (
                <p className="text-gray-500 italic">No untouched gaps.</p>
              ) : (
                marketData.qqq_active_fvgs?.map((fvg, i) => (
                  <div key={i} className="bg-gray-900 p-3 rounded-lg border border-gray-700 flex justify-between items-center">
                    <div>
                      <span className={`block font-bold ${fvg.type === 'BULLISH' ? 'text-green-400' : 'text-red-400'}`}>{fvg.type}</span>
                      <span className="text-xs text-gray-500">{fvg.status}</span>
                    </div>
                    <span className="font-mono text-sm bg-gray-800 px-2 py-1 rounded">{fvg.gap}</span>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </div>

        {/* Alignment Status Bar */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`p-4 rounded-xl text-center font-bold text-lg mb-6 border ${marketData.shared_trend === 0 ? 'bg-gray-800 border-gray-700 text-gray-400' : marketData.shared_trend === 1 ? 'bg-green-900/30 border-green-500 text-green-400' : 'bg-red-900/30 border-red-500 text-red-400'}`}>
          {marketData.shared_trend === 0 ? '⚠ Waiting for Trend Alignment...' : `✅ SYSTEM ALIGNED: ${marketData.shared_trend === 1 ? 'BULLISH' : 'BEARISH'} TREND`}
        </motion.div>

        {/* Pre-Trade Checklist & Timer */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="bg-gray-800 border border-gray-700 rounded-2xl p-6 mb-6">
          <div className="flex justify-between items-center mb-6 border-b border-gray-700 pb-4">
            <h2 className="text-xl font-bold text-white">Pre-Trade Checklist</h2>
            <div className="flex items-center gap-2 text-cyan-400 bg-gray-900 px-3 py-1.5 rounded-lg border border-gray-700">
              <Clock size={18} />
              <span className="font-mono font-bold tracking-wider">{timeToOpen}</span>
              <span className="text-xs text-gray-500 ml-1 uppercase">{timerLabel}</span>
            </div>
          </div>
          
          <div className="space-y-2 mb-6">
            {checklistItems.map((text, i) => {
              const isChecked = automatedChecklist[i];
              const isDisabled = i > 0 && !automatedChecklist[i - 1];
              return (
                <div 
                  key={i} 
                  className={`flex items-center gap-3 bg-gray-900 border border-gray-700 rounded-lg p-3 ${isDisabled ? 'opacity-50' : ''}`}
                >
                  {isChecked ? <CheckSquare className="text-cyan-400 shrink-0" /> : <Square className="text-gray-500 shrink-0" />}
                  <span className={`text-sm select-none ${isChecked ? 'text-gray-400 line-through' : 'text-gray-200'}`}>{text}</span>
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-4 pt-4 border-t border-gray-700">
            <div className="flex items-center gap-3 flex-1">
              <div className="flex-1 h-3 bg-gray-900 rounded-full overflow-hidden border border-gray-700">
                <div className="h-full bg-cyan-500 transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
              </div>
              <span className="text-cyan-400 font-bold font-mono text-sm min-w-[80px] text-right">{progress}% READY</span>
            </div>
            <div
              className={`px-6 py-2 rounded-lg font-bold transition-all text-center ${
                step4 
                  ? 'bg-cyan-500 text-gray-900 shadow-[0_0_15px_rgba(6,182,212,0.4)]' 
                  : 'bg-gray-700 text-gray-500'
              }`}
            >
              {step4 ? 'CRITERIA MET - ALGO EXECUTING' : 'AWAITING CRITERIA'}
            </div>
          </div>
        </motion.div>

        {/* Trade Ledger */}
        <TradeLedger 
          activeTrades={marketData.active_trades} 
          tradeHistory={marketData.trade_history} 
        />

        {/* Execution Log */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="bg-gray-800 border border-gray-700 rounded-2xl p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Terminal className="text-gray-400" />
            <h2 className="text-xl font-bold text-white">Execution Log</h2>
          </div>
          <div className="bg-gray-900 rounded-lg p-4 min-h-[100px] font-mono text-sm space-y-2 border border-gray-800">
            {marketData.execution_alerts?.length === 0 ? (
              <p className="text-gray-600">Waiting for 1m IFVG trigger...</p>
            ) : (
              marketData.execution_alerts?.map((alert, i) => (
                <div key={i} className="text-green-400 border-l-2 border-green-500 pl-3 py-1">
                  {alert}
                </div>
              ))
            )}
          </div>
        </motion.div>
      </main>
    </div>
  );
}

export default App;