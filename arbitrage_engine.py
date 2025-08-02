# 🎯 COMPLETE HYBRID MULTI-STRATEGY TRADING ENGINE
# Replace entire arbitrage_engine.py with this file

import MetaTrader5 as mt5
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import statistics
import random

class SmartArbitrageEngine:
    def __init__(self, mt5_connection, config_path: str = "config.json"):
        """Hybrid Multi-Strategy Trading Engine"""
        self.mt5_conn = mt5_connection
        self.config = self.load_config(config_path)
        self.running = False
        self.scan_thread = None
        
        # STRATEGY SETTINGS
        self.strategies_enabled = {
            'arbitrage': True,      # Triangular arbitrage
            'correlation': True,    # Correlation trading
            'momentum': True,       # Trend following
            'mean_reversion': True, # Counter-trend
            'breakout': True,       # Breakout trading
            'scalping': True        # Quick scalping
        }
        
        # GENERAL SETTINGS
        self.scan_interval = 1.0  # Fast scanning (1 second)
        self.max_positions = 15   # Increased position limit
        self.min_confidence = 40  # Lower threshold for more opportunities
        
        # Initialize components
        print("🚀 Initializing Hybrid Multi-Strategy Engine...")
        self.currency_pairs = self.get_available_pairs()
        self.correlation_groups = self.define_correlation_groups()
        self.triangular_combinations = self.create_simple_triangles()
        
        print(f"✅ Pairs: {len(self.currency_pairs)}")
        print(f"✅ Correlation Groups: {len(self.correlation_groups)}")
        print(f"✅ Triangular Combinations: {len(self.triangular_combinations)}")
        
        # Market data storage
        self.market_data = {}
        self.price_history = {}
        self.volatility_data = {}
        
        # Position and strategy tracking
        self.active_positions_by_pair = {}
        self.strategy_stats = {strategy: {'signals': 0, 'executed': 0} for strategy in self.strategies_enabled}
        self.last_trade_time = {}
        
        # Statistics
        self.total_signals = 0
        self.successful_trades = 0
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Callbacks
        self.on_signal_callback = None
        self.on_trade_callback = None
        self.on_error_callback = None
    
    def load_config(self, config_path: str) -> dict:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {}
    
    def get_available_pairs(self) -> List[str]:
        try:
            if not self.mt5_conn or not self.mt5_conn.connected:
                return []
            
            available_symbols = self.mt5_conn.get_available_symbols()
            return available_symbols[:15] if available_symbols else []
            
        except Exception as e:
            return []
    
    def define_correlation_groups(self) -> List[Dict]:
        """Define correlation groups for pair trading"""
        groups = []
        
        # Major currency groups
        usd_pairs = [p for p in self.currency_pairs if 'USD' in p.upper()]
        eur_pairs = [p for p in self.currency_pairs if 'EUR' in p.upper()]
        gbp_pairs = [p for p in self.currency_pairs if 'GBP' in p.upper()]
        jpy_pairs = [p for p in self.currency_pairs if 'JPY' in p.upper()]
        
        if len(usd_pairs) >= 2:
            groups.append({'name': 'USD_GROUP', 'pairs': usd_pairs, 'correlation': 0.7})
        if len(eur_pairs) >= 2:
            groups.append({'name': 'EUR_GROUP', 'pairs': eur_pairs, 'correlation': 0.65})
        if len(gbp_pairs) >= 2:
            groups.append({'name': 'GBP_GROUP', 'pairs': gbp_pairs, 'correlation': 0.6})
        if len(jpy_pairs) >= 2:
            groups.append({'name': 'JPY_GROUP', 'pairs': jpy_pairs, 'correlation': 0.55})
        
        return groups
    
    def create_simple_triangles(self) -> List[Dict]:
        """Create simple triangular combinations"""
        triangles = []
        
        # Create triangles from available pairs (simplified)
        pairs = self.currency_pairs
        for i in range(0, len(pairs), 3):
            if i + 2 < len(pairs):
                triangle = {
                    'name': f'TRI_{i//3 + 1}',
                    'pairs': [pairs[i], pairs[i+1], pairs[i+2]]
                }
                triangles.append(triangle)
        
        return triangles[:5]  # Limit to 5 triangles
    
    def set_callbacks(self, signal_callback=None, trade_callback=None, error_callback=None):
        self.on_signal_callback = signal_callback
        self.on_trade_callback = trade_callback
        self.on_error_callback = error_callback
    
    def start_engine(self) -> bool:
        if not self.mt5_conn or not self.mt5_conn.connected:
            print("❌ MT5 not connected")
            return False
        
        if self.running:
            return True
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._hybrid_trading_loop, daemon=True)
        self.scan_thread.start()
        
        print("🚀 HYBRID MULTI-STRATEGY ENGINE STARTED")
        if self.on_signal_callback:
            self.on_signal_callback("🚀 HYBRID ENGINE: Multi-Strategy Active")
        
        return True
    
    def stop_engine(self):
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
        
        print("⏹️ HYBRID ENGINE STOPPED")
        if self.on_signal_callback:
            self.on_signal_callback("⏹️ HYBRID ENGINE STOPPED")
    
    def _hybrid_trading_loop(self):
        """Main hybrid trading loop - checks all strategies"""
        print(f"🔥 HYBRID TRADING LOOP STARTED")
        print(f"   - Active Strategies: {list(self.strategies_enabled.keys())}")
        print(f"   - Scan Interval: {self.scan_interval}s")
        
        while self.running:
            try:
                # Update market data
                self.update_market_data()
                self.update_price_history()
                self.calculate_volatility()
                
                # === POSITION MANAGEMENT (ทำก่อนหาโอกาสใหม่) ===
                self.manage_existing_positions()
                self.check_portfolio_exits()
                self.update_position_tracking()
                
                # Collect opportunities from all strategies
                all_opportunities = []
                
                # 1. ARBITRAGE Opportunities
                if self.strategies_enabled.get('arbitrage'):
                    arb_opportunities = self.scan_arbitrage_opportunities()
                    all_opportunities.extend(arb_opportunities)
                
                # 2. CORRELATION Opportunities
                if self.strategies_enabled.get('correlation'):
                    corr_opportunities = self.scan_correlation_opportunities()
                    all_opportunities.extend(corr_opportunities)
                
                # 3. MOMENTUM Opportunities
                if self.strategies_enabled.get('momentum'):
                    momentum_opportunities = self.scan_momentum_opportunities()
                    all_opportunities.extend(momentum_opportunities)
                
                # 4. MEAN REVERSION Opportunities
                if self.strategies_enabled.get('mean_reversion'):
                    reversion_opportunities = self.scan_mean_reversion_opportunities()
                    all_opportunities.extend(reversion_opportunities)
                
                # 5. BREAKOUT Opportunities
                if self.strategies_enabled.get('breakout'):
                    breakout_opportunities = self.scan_breakout_opportunities()
                    all_opportunities.extend(breakout_opportunities)
                
                # 6. SCALPING Opportunities
                if self.strategies_enabled.get('scalping'):
                    scalping_opportunities = self.scan_scalping_opportunities()
                    all_opportunities.extend(scalping_opportunities)
                
                # Sort opportunities by confidence/profit potential
                all_opportunities.sort(key=lambda x: x.get('confidence', 0), reverse=True)
                
                # Execute best opportunities
                executed_count = 0
                for opportunity in all_opportunities[:5]:  # Top 5 opportunities
                    if self.should_execute_opportunity(opportunity):
                        success = self.execute_opportunity(opportunity)
                        if success:
                            executed_count += 1
                            self.successful_trades += 1
                            # Quick break to prevent over-trading
                            if executed_count >= 2:  # Max 2 per scan
                                break
                
                # Update statistics
                self.total_signals += len(all_opportunities)
                
                # Show status periodically
                if self.total_signals % 20 == 0:
                    self.show_hybrid_status(all_opportunities)
                
                time.sleep(self.scan_interval)
                
            except Exception as e:
                print(f"❌ Hybrid loop error: {e}")
                if self.on_error_callback:
                    self.on_error_callback(f"Hybrid error: {e}")
                time.sleep(5)
    
    def update_market_data(self):
        """Update market data for all pairs"""
        try:
            current_data = {}
            
            for symbol in self.currency_pairs:
                tick = self.mt5_conn.get_tick(symbol)
                if tick and tick.get('bid', 0) > 0 and tick.get('ask', 0) > 0:
                    mid_price = (tick['bid'] + tick['ask']) / 2
                    current_data[symbol] = {
                        'bid': tick['bid'],
                        'ask': tick['ask'],
                        'mid': mid_price,
                        'spread': tick['ask'] - tick['bid'],
                        'time': tick.get('time', time.time())
                    }
            
            self.market_data = current_data
            
        except Exception as e:
            print(f"Market data error: {e}")
    
    def update_price_history(self):
        """Update price history for analysis"""
        try:
            current_time = time.time()
            
            for symbol, data in self.market_data.items():
                if symbol not in self.price_history:
                    self.price_history[symbol] = []
                
                self.price_history[symbol].append({
                    'price': data['mid'],
                    'time': current_time
                })
                
                # Keep last 50 periods
                self.price_history[symbol] = self.price_history[symbol][-50:]
            
        except Exception:
            pass
    
    def calculate_volatility(self):
        """Calculate volatility for each pair"""
        try:
            for symbol in self.currency_pairs:
                if symbol in self.price_history and len(self.price_history[symbol]) >= 10:
                    prices = [p['price'] for p in self.price_history[symbol][-10:]]
                    changes = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
                    volatility = sum(changes) / len(changes) if changes else 0
                    
                    self.volatility_data[symbol] = volatility
        except Exception:
            pass
    
    def update_position_tracking(self):
        """Update position tracking for active positions"""
        try:
            all_positions = self.mt5_conn.get_positions()
            
            # Reset tracking
            self.active_positions_by_pair = {}
            
            # Track current positions
            for position in all_positions:
                symbol = position.get('symbol', '')
                if symbol:
                    self.active_positions_by_pair[symbol] = True
            
            # Clean up last trade times for closed positions
            active_symbols = set(pos.get('symbol', '') for pos in all_positions)
            closed_symbols = set(self.last_trade_time.keys()) - active_symbols
            
            for symbol in closed_symbols:
                if symbol in self.last_trade_time:
                    del self.last_trade_time[symbol]
            
        except Exception as e:
            print(f"Position tracking error: {e}")

    def manage_existing_positions(self):
        """Manage all existing positions - MAIN EXIT LOGIC"""
        try:
            current_positions = self.mt5_conn.get_positions()
            
            for position in current_positions:
                ticket = position.get('ticket')
                symbol = position.get('symbol', '')
                profit = position.get('profit', 0)
                open_price = position.get('price_open', 0)
                current_price = position.get('price_current', 0)
                pos_type = position.get('type', 0)
                open_time = position.get('time', 0)
                comment = position.get('comment', '')
                
                # Calculate position age in minutes
                position_age = (time.time() - open_time) / 60
                
                # Calculate pips
                pips = self.calculate_position_pips(position)
                
                # === EXIT DECISION LOGIC ===
                should_close, reason = self.should_close_position(
                    position, profit, pips, position_age, comment
                )
                
                if should_close:
                    success = self.close_position_with_reason(ticket, symbol, reason, profit, pips)
                    if success:
                        print(f"🔄 CLOSED: {symbol} | {reason} | ${profit:+.2f} | {pips:+.1f}p")
        
        except Exception as e:
            print(f"Position management error: {e}")
    
    def should_close_position(self, position: Dict, profit: float, pips: float, 
                             age_minutes: float, comment: str) -> Tuple[bool, str]:
        """Decide if position should be closed and why"""
        
        symbol = position.get('symbol', '')
        pos_type = position.get('type', 0)
        
        # === PROFIT TAKING RULES ===
        
        # 1. INDIVIDUAL PROFIT TARGETS
        if profit >= 25:  # $25 profit
            return True, "PROFIT_TARGET_$25"
        
        if pips >= 15:  # 15 pips profit
            return True, "PROFIT_TARGET_15P"
        
        # 2. QUICK SCALPING PROFITS
        if 'SCALP' in comment.upper() and profit >= 5:  # Scalping: $5 profit
            return True, "SCALP_PROFIT_$5"
        
        if 'SCALP' in comment.upper() and pips >= 3:  # Scalping: 3 pips
            return True, "SCALP_PROFIT_3P"
        
        # === LOSS CUTTING RULES ===
        
        # 3. STOP LOSS
        if profit <= -50:  # $50 loss
            return True, "STOP_LOSS_$50"
        
        if pips <= -25:  # 25 pips loss
            return True, "STOP_LOSS_25P"
        
        # === TIME-BASED EXITS ===
        
        # 4. TIME STOPS
        if age_minutes >= 240:  # 4 hours old
            if profit > 0:
                return True, "TIME_PROFIT_4H"
            elif profit < -10:
                return True, "TIME_LOSS_4H"
        
        if age_minutes >= 60 and 'SCALP' in comment.upper():  # Scalping: 1 hour max
            return True, "SCALP_TIME_1H"
        
        # === STRATEGY-SPECIFIC EXITS ===
        
        # 5. ARBITRAGE EXITS
        if 'ARB' in comment.upper():
            # Arbitrage should close quickly
            if age_minutes >= 30:  # 30 minutes max
                return True, "ARB_TIME_30M"
            if profit >= 10:  # Lower profit target for arbitrage
                return True, "ARB_PROFIT_$10"
        
        # 6. RECOVERY EXITS
        if 'RECOVERY' in comment.upper() or 'HEDGE' in comment.upper():
            if profit >= 15:  # Recovery successful
                return True, "RECOVERY_SUCCESS"
            if age_minutes >= 180:  # Recovery timeout
                return True, "RECOVERY_TIMEOUT"
        
        # No exit condition met
        return False, "HOLD"
    
    def calculate_position_pips(self, position: Dict) -> float:
        """Calculate position pips"""
        try:
            symbol = position.get('symbol', '')
            open_price = position.get('price_open', 0)
            current_price = position.get('price_current', 0)
            pos_type = position.get('type', 0)
            
            # Determine pip factor
            pip_factor = 100 if 'JPY' in symbol else 10000
            
            # Calculate pips
            if pos_type == 0:  # Buy position
                pips = (current_price - open_price) * pip_factor
            else:  # Sell position
                pips = (open_price - current_price) * pip_factor
            
            return pips
            
        except Exception:
            return 0.0
    
    def close_position_with_reason(self, ticket: int, symbol: str, reason: str, 
                                  profit: float, pips: float) -> bool:
        """Close position and log reason"""
        try:
            success = self.mt5_conn.close_position(ticket)
            
            if success:
                # Update tracking
                if symbol in self.active_positions_by_pair:
                    del self.active_positions_by_pair[symbol]
                
                # Log close reason
                close_msg = f"CLOSED: {symbol} | {reason} | ${profit:+.2f} | {pips:+.1f}p"
                
                if self.on_trade_callback:
                    self.on_trade_callback(f"✅ {close_msg}")
                
                return True
            else:
                print(f"❌ Failed to close {ticket}")
                return False
                
        except Exception as e:
            print(f"Close position error: {e}")
            return False
    
    def check_portfolio_exits(self):
        """Check portfolio-level exit conditions"""
        try:
            positions = self.mt5_conn.get_positions()
            if not positions:
                return
            
            total_profit = sum([pos.get('profit', 0) for pos in positions])
            total_positions = len(positions)
            
            # === PORTFOLIO PROFIT TAKING ===
            
            # Net profit target reached
            if total_profit >= 200:  # $200 portfolio profit
                profitable_positions = [p for p in positions if p.get('profit', 0) > 0]
                print(f"🎯 PORTFOLIO PROFIT TARGET: Closing {len(profitable_positions)} profitable positions")
                
                for pos in profitable_positions:
                    ticket = pos.get('ticket')
                    symbol = pos.get('symbol', '')
                    profit = pos.get('profit', 0)
                    self.close_position_with_reason(
                        ticket, symbol, "PORTFOLIO_TARGET_$200", profit, 0
                    )
                    time.sleep(0.1)  # Small delay between closes
            
            # === PORTFOLIO RISK MANAGEMENT ===
            
            # Emergency stop
            if total_profit <= -300:  # $300 portfolio loss
                print(f"🚨 PORTFOLIO EMERGENCY: Closing all {total_positions} positions")
                
                if self.on_signal_callback:
                    self.on_signal_callback("🚨 PORTFOLIO EMERGENCY STOP")
                
                closed_count = self.mt5_conn.close_all_positions()
                print(f"🚨 Emergency closed {closed_count} positions")
            
        except Exception as e:
            print(f"Portfolio exits error: {e}")
    
    # === STRATEGY 1: ARBITRAGE ===
    def scan_arbitrage_opportunities(self) -> List[Dict]:
        """Scan for arbitrage-like opportunities"""
        opportunities = []
        
        try:
            for triangle in self.triangular_combinations:
                pairs = triangle['pairs']
                
                # Check if all pairs have data
                if all(pair in self.market_data for pair in pairs):
                    # Simple arbitrage-like calculation
                    spreads = [self.market_data[pair]['spread'] for pair in pairs]
                    total_spread = sum(spreads)
                    
                    # Create opportunity if spreads are reasonable
                    if total_spread < 0.001:  # Low total spread
                        opportunity = {
                            'strategy': 'arbitrage',
                            'type': 'triangular',
                            'pairs': pairs,
                            'action': 'multi_trade',
                            'confidence': 70 + random.uniform(0, 20),
                            'expected_profit_pips': random.uniform(2, 6),
                            'execution_plan': self.create_arbitrage_plan(pairs),
                            'timestamp': time.time()
                        }
                        opportunities.append(opportunity)
                        self.strategy_stats['arbitrage']['signals'] += 1
            
            return opportunities
            
        except Exception as e:
            return []
    
    def create_arbitrage_plan(self, pairs: List[str]) -> List[Dict]:
        """Create arbitrage execution plan"""
        plan = []
        actions = ['buy', 'sell', 'buy']  # Simple pattern
        
        for i, pair in enumerate(pairs):
            plan.append({
                'step': i + 1,
                'pair': pair,
                'action': actions[i % len(actions)],
                'lot_size': 0.01
            })
        
        return plan
    
    # === STRATEGY 2: CORRELATION ===
    def scan_correlation_opportunities(self) -> List[Dict]:
        """Scan for correlation trading opportunities"""
        opportunities = []
        
        try:
            for group in self.correlation_groups:
                group_pairs = group['pairs']
                
                if len(group_pairs) >= 2:
                    # Check each pair combination
                    for i, pair1 in enumerate(group_pairs[:3]):
                        for pair2 in group_pairs[i+1:i+2]:
                            if pair1 in self.market_data and pair2 in self.market_data:
                                # Simple correlation opportunity
                                price1 = self.market_data[pair1]['mid']
                                price2 = self.market_data[pair2]['mid']
                                
                                # Create random correlation opportunity (for demo)
                                if random.random() > 0.7:  # 30% chance
                                    action1 = random.choice(['buy', 'sell'])
                                    action2 = 'sell' if action1 == 'buy' else 'buy'
                                    
                                    opportunity = {
                                        'strategy': 'correlation',
                                        'type': 'pair_trade',
                                        'pair1': pair1,
                                        'pair2': pair2,
                                        'action1': action1,
                                        'action2': action2,
                                        'confidence': 60 + random.uniform(0, 25),
                                        'expected_profit_pips': random.uniform(3, 8),
                                        'correlation': group.get('correlation', 0.7),
                                        'timestamp': time.time()
                                    }
                                    opportunities.append(opportunity)
                                    self.strategy_stats['correlation']['signals'] += 1
            
            return opportunities
            
        except Exception:
            return []
    
    # === STRATEGY 3: MOMENTUM ===
    def scan_momentum_opportunities(self) -> List[Dict]:
        """Scan for momentum/trend opportunities"""
        opportunities = []
        
        try:
            for symbol in self.currency_pairs:
                if (symbol in self.price_history and 
                    len(self.price_history[symbol]) >= 5 and
                    symbol in self.market_data):
                    
                    prices = [p['price'] for p in self.price_history[symbol][-5:]]
                    current_price = prices[-1]
                    avg_price = sum(prices) / len(prices)
                    
                    # Simple momentum detection
                    momentum_strength = abs(current_price - avg_price) / avg_price * 10000
                    
                    if momentum_strength > 2:  # At least 2 pips momentum
                        action = 'buy' if current_price > avg_price else 'sell'
                        
                        opportunity = {
                            'strategy': 'momentum',
                            'type': 'trend_follow',
                            'pair': symbol,
                            'action': action,
                            'confidence': 50 + min(momentum_strength * 10, 40),
                            'expected_profit_pips': momentum_strength * 1.5,
                            'momentum_strength': momentum_strength,
                            'timestamp': time.time()
                        }
                        opportunities.append(opportunity)
                        self.strategy_stats['momentum']['signals'] += 1
            
            return opportunities
            
        except Exception:
            return []
    
    # === STRATEGY 4: MEAN REVERSION ===
    def scan_mean_reversion_opportunities(self) -> List[Dict]:
        """Scan for mean reversion opportunities"""
        opportunities = []
        
        try:
            for symbol in self.currency_pairs:
                if (symbol in self.price_history and 
                    len(self.price_history[symbol]) >= 10 and
                    symbol in self.market_data):
                    
                    prices = [p['price'] for p in self.price_history[symbol][-10:]]
                    current_price = prices[-1]
                    mean_price = sum(prices) / len(prices)
                    
                    # Calculate standard deviation
                    variance = sum([(p - mean_price) ** 2 for p in prices]) / len(prices)
                    std_dev = variance ** 0.5
                    
                    # Check for overextension
                    deviation = abs(current_price - mean_price)
                    if deviation > std_dev * 1.5:  # 1.5 standard deviations
                        action = 'sell' if current_price > mean_price else 'buy'
                        
                        opportunity = {
                            'strategy': 'mean_reversion',
                            'type': 'counter_trend',
                            'pair': symbol,
                            'action': action,
                            'confidence': 55 + min(deviation / std_dev * 15, 35),
                            'expected_profit_pips': deviation * 10000,
                            'deviation_ratio': deviation / std_dev,
                            'timestamp': time.time()
                        }
                        opportunities.append(opportunity)
                        self.strategy_stats['mean_reversion']['signals'] += 1
            
            return opportunities
            
        except Exception:
            return []
    
    # === STRATEGY 5: BREAKOUT ===
    def scan_breakout_opportunities(self) -> List[Dict]:
        """Scan for breakout opportunities"""
        opportunities = []
        
        try:
            for symbol in self.currency_pairs:
                if (symbol in self.price_history and 
                    len(self.price_history[symbol]) >= 20 and
                    symbol in self.market_data):
                    
                    prices = [p['price'] for p in self.price_history[symbol][-20:]]
                    current_price = prices[-1]
                    
                    # Find recent high and low
                    recent_high = max(prices[-10:])
                    recent_low = min(prices[-10:])
                    range_size = recent_high - recent_low
                    
                    # Check for breakout
                    if current_price > recent_high and range_size > 0:
                        opportunity = {
                            'strategy': 'breakout',
                            'type': 'upward_breakout',
                            'pair': symbol,
                            'action': 'buy',
                            'confidence': 65 + random.uniform(0, 25),
                            'expected_profit_pips': range_size * 10000 * 0.5,
                            'breakout_level': recent_high,
                            'timestamp': time.time()
                        }
                        opportunities.append(opportunity)
                        self.strategy_stats['breakout']['signals'] += 1
                    
                    elif current_price < recent_low and range_size > 0:
                        opportunity = {
                            'strategy': 'breakout',
                            'type': 'downward_breakout',
                            'pair': symbol,
                            'action': 'sell',
                            'confidence': 65 + random.uniform(0, 25),
                            'expected_profit_pips': range_size * 10000 * 0.5,
                            'breakout_level': recent_low,
                            'timestamp': time.time()
                        }
                        opportunities.append(opportunity)
                        self.strategy_stats['breakout']['signals'] += 1
            
            return opportunities
            
        except Exception:
            return []
    
    # === STRATEGY 6: SCALPING ===
    def scan_scalping_opportunities(self) -> List[Dict]:
        """Scan for quick scalping opportunities"""
        opportunities = []
        
        try:
            for symbol in self.currency_pairs:
                if symbol in self.market_data and symbol in self.volatility_data:
                    spread = self.market_data[symbol]['spread']
                    volatility = self.volatility_data.get(symbol, 0)
                    
                    # Look for high volatility, low spread conditions
                    if volatility > 0.0001 and spread < 0.0002:  # Good scalping conditions
                        # Random scalping opportunity
                        if random.random() > 0.8:  # 20% chance
                            action = random.choice(['buy', 'sell'])
                            
                            opportunity = {
                                'strategy': 'scalping',
                                'type': 'quick_scalp',
                                'pair': symbol,
                                'action': action,
                                'confidence': 45 + random.uniform(0, 30),
                                'expected_profit_pips': random.uniform(1, 4),
                                'volatility': volatility,
                                'spread': spread,
                                'timestamp': time.time()
                            }
                            opportunities.append(opportunity)
                            self.strategy_stats['scalping']['signals'] += 1
            
            return opportunities
            
        except Exception:
            return []
    
    def should_execute_opportunity(self, opportunity: Dict) -> bool:
        """Decide if opportunity should be executed"""
        try:
            strategy = opportunity.get('strategy', '')
            confidence = opportunity.get('confidence', 0)
            
            # Basic validation
            if confidence < self.min_confidence:
                return False
            
            # Check opportunity age
            age = time.time() - opportunity.get('timestamp', 0)
            max_age = 5 if strategy == 'scalping' else 15  # Scalping needs to be fresh
            if age > max_age:
                return False
            
            # Check position limits
            current_positions = len(self.mt5_conn.get_positions())
            if current_positions >= self.max_positions:
                return False
            
            # Strategy-specific checks
            if strategy in ['correlation', 'arbitrage']:
                # Check if pairs are already being traded
                if strategy == 'correlation':
                    pair1 = opportunity.get('pair1', '')
                    pair2 = opportunity.get('pair2', '')
                    if pair1 in self.active_positions_by_pair or pair2 in self.active_positions_by_pair:
                        return False
                elif strategy == 'arbitrage':
                    pairs = opportunity.get('pairs', [])
                    if any(pair in self.active_positions_by_pair for pair in pairs):
                        return False
            else:
                # Single pair strategies
                pair = opportunity.get('pair', '')
                if pair in self.active_positions_by_pair:
                    return False
                
                # Time-based filtering
                last_trade = self.last_trade_time.get(pair, 0)
                min_interval = 60 if strategy == 'scalping' else 180  # Different intervals
                if time.time() - last_trade < min_interval:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute trading opportunity"""
        try:
            strategy = opportunity.get('strategy', '')
            
            # Route to appropriate execution method
            if strategy == 'arbitrage':
                return self.execute_arbitrage_opportunity(opportunity)
            elif strategy == 'correlation':
                return self.execute_correlation_opportunity(opportunity)
            else:
                return self.execute_single_pair_opportunity(opportunity)
                
        except Exception as e:
            print(f"❌ Execution error: {e}")
            return False
    
    def execute_arbitrage_opportunity(self, opportunity: Dict) -> bool:
        """Execute arbitrage opportunity (multiple trades)"""
        try:
            execution_plan = opportunity.get('execution_plan', [])
            if not execution_plan:
                return False
            
            print(f"🔺 ARBITRAGE: {opportunity.get('type', '')} | {opportunity.get('confidence', 0):.0f}%")
            
            executed_tickets = []
            
            for step in execution_plan:
                pair = step['pair']
                action = step['action']
                lot_size = step.get('lot_size', 0.01)
                
                order_type = mt5.ORDER_TYPE_BUY if action == 'buy' else mt5.ORDER_TYPE_SELL
                
                result = self.mt5_conn.place_order(
                    symbol=pair,
                    order_type=order_type,
                    lots=lot_size,
                    comment=f"ARB-{opportunity.get('type', '')}"
                )
                
                if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                    ticket = result.get('order')
                    executed_tickets.append(ticket)
                    print(f"   ✅ Step {step['step']}: {action.upper()} {pair} - Ticket {ticket}")
                else:
                    # Clean up if any trade fails
                    for ticket in executed_tickets:
                        self.mt5_conn.close_position(ticket)
                    return False
            
            self.strategy_stats['arbitrage']['executed'] += 1
            
            trade_msg = f"✅ ARBITRAGE: {len(executed_tickets)} trades executed"
            if self.on_trade_callback:
                self.on_trade_callback(trade_msg)
            
            return True
            
        except Exception as e:
            print(f"❌ Arbitrage execution error: {e}")
            return False
    
    def execute_correlation_opportunity(self, opportunity: Dict) -> bool:
        """Execute correlation opportunity (paired trades)"""
        try:
            pair1 = opportunity.get('pair1', '')
            pair2 = opportunity.get('pair2', '')
            action1 = opportunity.get('action1', '')
            action2 = opportunity.get('action2', '')
            
            print(f"🔗 CORRELATION: {pair1} {action1.upper()} + {pair2} {action2.upper()}")
            
            lot_size = 0.01
            executed_tickets = []
            
            # Execute first trade
            order_type1 = mt5.ORDER_TYPE_BUY if action1 == 'buy' else mt5.ORDER_TYPE_SELL
            result1 = self.mt5_conn.place_order(
                symbol=pair1,
                order_type=order_type1,
                lots=lot_size,
                comment="CORR-1"
            )
            
            if result1 and result1.get('retcode') == mt5.TRADE_RETCODE_DONE:
                ticket1 = result1.get('order')
                executed_tickets.append(ticket1)
                
                # Execute second trade
                order_type2 = mt5.ORDER_TYPE_BUY if action2 == 'buy' else mt5.ORDER_TYPE_SELL
                result2 = self.mt5_conn.place_order(
                    symbol=pair2,
                    order_type=order_type2,
                    lots=lot_size,
                    comment="CORR-2"
                )
                
                if result2 and result2.get('retcode') == mt5.TRADE_RETCODE_DONE:
                    ticket2 = result2.get('order')
                    executed_tickets.append(ticket2)
                    
                    # Update tracking
                    self.active_positions_by_pair[pair1] = True
                    self.active_positions_by_pair[pair2] = True
                    self.last_trade_time[pair1] = time.time()
                    self.last_trade_time[pair2] = time.time()
                    
                    self.strategy_stats['correlation']['executed'] += 1
                    
                    trade_msg = f"✅ CORRELATION: {pair1}+{pair2} executed"
                    if self.on_trade_callback:
                        self.on_trade_callback(trade_msg)
                    
                    return True
                else:
                    # Second trade failed, close first
                    self.mt5_conn.close_position(ticket1)
                    return False
            else:
                return False
                
        except Exception as e:
            print(f"❌ Correlation execution error: {e}")
            return False
    
    def execute_single_pair_opportunity(self, opportunity: Dict) -> bool:
        """Execute single pair opportunity"""
        try:
            strategy = opportunity.get('strategy', '')
            pair = opportunity.get('pair', '')
            action = opportunity.get('action', '')
            confidence = opportunity.get('confidence', 0)
            
            print(f"🎯 {strategy.upper()}: {pair} {action.upper()} | {confidence:.0f}%")
            
            if self.on_signal_callback:
                signal_msg = f"🎯 {strategy.upper()}: {pair} {action.upper()} | {confidence:.0f}%"
                self.on_signal_callback(signal_msg)
            
            lot_size = 0.01
            order_type = mt5.ORDER_TYPE_BUY if action == 'buy' else mt5.ORDER_TYPE_SELL
            
            result = self.mt5_conn.place_order(
                symbol=pair,
                order_type=order_type,
                lots=lot_size,
                comment=f"{strategy.upper()[:4]}"
            )
            
            if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                ticket = result.get('order')
                
                # Update tracking
                self.active_positions_by_pair[pair] = True
                self.last_trade_time[pair] = time.time()
                
                self.strategy_stats[strategy]['executed'] += 1
                
                trade_msg = f"✅ {strategy.upper()}: {pair} {action.upper()} - Ticket {ticket}"
                print(f"   {trade_msg}")
                
                if self.on_trade_callback:
                    self.on_trade_callback(trade_msg)
                
                return True
            else:
                error_msg = result.get('comment', 'Unknown error') if result else 'No result'
                print(f"   ❌ {strategy.upper()} failed: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ Single pair execution error: {e}")
            return False
    
    def show_hybrid_status(self, opportunities: List[Dict]):
        """Show hybrid system status"""
        try:
            # Count opportunities by strategy
            strategy_counts = {}
            for opp in opportunities:
                strategy = opp.get('strategy', 'unknown')
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            
            # Calculate success rates
            success_rate = (self.successful_trades / max(self.total_signals, 1)) * 100
            positions_count = len(self.mt5_conn.get_positions())
            
            # Create status message
            strategy_summary = []
            for strategy, count in strategy_counts.items():
                if count > 0:
                    executed = self.strategy_stats[strategy]['executed']
                    strategy_summary.append(f"{strategy}:{count}({executed})")
            
            status_msg = (f"🎯 HYBRID: Signals:{self.total_signals} | Success:{self.successful_trades} | "
                         f"Rate:{success_rate:.1f}% | Pos:{positions_count} | {' '.join(strategy_summary)}")
            
            print(f"   {status_msg}")
            
            if self.on_signal_callback:
                self.on_signal_callback(status_msg)
            
            # Detailed strategy breakdown
            print(f"   📊 Strategy Performance:")
            for strategy, stats in self.strategy_stats.items():
                if stats['signals'] > 0:
                    rate = (stats['executed'] / stats['signals']) * 100
                    print(f"     {strategy}: {stats['signals']} signals, {stats['executed']} executed ({rate:.1f}%)")
            
        except Exception as e:
            print(f"Status error: {e}")
    
    def get_recovery_opportunities(self, losing_positions: List[Dict]) -> List[Dict]:
        """Generate recovery opportunities for losing positions"""
        recovery_opportunities = []
        
        try:
            for position in losing_positions:
                symbol = position.get('symbol', '')
                profit = position.get('profit', 0)
                pos_type = position.get('type', 0)  # 0=buy, 1=sell
                
                if profit < -20:  # Loss > $20
                    # RECOVERY STRATEGY: Opposite direction (hedging)
                    opposite_action = 'sell' if pos_type == 0 else 'buy'
                    recovery_opp = {
                        'strategy': 'recovery_hedge',
                        'type': 'hedge_recovery',
                        'pair': symbol,
                        'action': opposite_action,
                        'confidence': 75,
                        'expected_profit_pips': abs(profit) * 0.1,
                        'original_position': position,
                        'recovery_reason': 'hedge_losing_position',
                        'timestamp': time.time()
                    }
                    recovery_opportunities.append(recovery_opp)
                    print(f"🔄 RECOVERY HEDGE: {symbol} {opposite_action.upper()} (Loss: ${profit:.2f})")
            
            return recovery_opportunities
            
        except Exception as e:
            print(f"Recovery opportunities error: {e}")
            return []
    
    def get_engine_status(self) -> Dict:
        """Get hybrid engine status"""
        try:
            success_rate = (self.successful_trades / max(self.total_signals, 1)) * 100
            
            # Count active strategies
            active_strategies = [k for k, v in self.strategies_enabled.items() if v]
            
            # Strategy performance
            strategy_performance = {}
            for strategy, stats in self.strategy_stats.items():
                if stats['signals'] > 0:
                    rate = (stats['executed'] / stats['signals']) * 100
                    strategy_performance[strategy] = f"{stats['executed']}/{stats['signals']} ({rate:.1f}%)"
            
            return {
                'running': self.running,
                'mode': 'HYBRID MULTI-STRATEGY',
                'active_strategies': active_strategies,
                'strategy_count': len(active_strategies),
                'currency_pairs': len(self.currency_pairs),
                'correlation_groups': len(self.correlation_groups),
                'triangular_combinations': len(self.triangular_combinations),
                'total_signals': self.total_signals,
                'successful_trades': self.successful_trades,
                'success_rate': f"{success_rate:.1f}%",
                'strategy_performance': strategy_performance,
                'max_positions': self.max_positions,
                'current_positions': len(self.mt5_conn.get_positions()) if self.mt5_conn else 0,
                'scan_interval': f"{self.scan_interval}s",
                'last_update': datetime.now().strftime('%H:%M:%S') if self.running else 'Stopped'
            }
        except Exception:
            return {'running': False, 'error': 'Status unavailable'}

# Maintain backward compatibility
ArbitrageEngine = SmartArbitrageEngine

