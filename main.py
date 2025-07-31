import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import json
from datetime import datetime
from mt5_connection import MT5Connection
import logging

class TriangularArbitrageGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎯 Triangular Arbitrage System")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2b2b2b')
        
        # Initialize components
        self.mt5_conn = None
        self.system_running = False
        self.update_thread = None
        
        # Load config
        self.config = self.load_config()
        
        # Initialize MT5 connection
        self.init_mt5_connection()
        
        # Create GUI
        self.create_widgets()
        
        # Start update loop
        self.start_update_loop()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def load_config(self):
        """Load configuration"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to load config.json: {e}")
            return {}
    
    def init_mt5_connection(self):
        """Initialize MT5 connection"""
        try:
            self.mt5_conn = MT5Connection()
        except Exception as e:
            messagebox.showerror("MT5 Error", f"Failed to initialize MT5: {e}")
    
    def create_widgets(self):
        """Create all GUI widgets"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_positions_tab()
        self.create_settings_tab()
        self.create_log_tab()
    
    def create_dashboard_tab(self):
        """Create main dashboard tab"""
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="📊 Dashboard")
        
        # Connection Status Frame
        conn_frame = ttk.LabelFrame(self.dashboard_frame, text="🔗 MT5 Connection Status")
        conn_frame.pack(fill='x', padx=10, pady=5)
        
        # Connection status labels
        self.conn_status_label = ttk.Label(conn_frame, text="❌ Disconnected", font=('Arial', 12, 'bold'))
        self.conn_status_label.pack(pady=5)
        
        self.conn_details_label = ttk.Label(conn_frame, text="Connection details will appear here")
        self.conn_details_label.pack(pady=2)
        
        # Connection buttons
        conn_btn_frame = ttk.Frame(conn_frame)
        conn_btn_frame.pack(pady=5)
        
        self.connect_btn = ttk.Button(conn_btn_frame, text="🔌 Connect MT5", command=self.connect_mt5)
        self.connect_btn.pack(side='left', padx=5)
        
        self.disconnect_btn = ttk.Button(conn_btn_frame, text="🔌 Disconnect", command=self.disconnect_mt5, state='disabled')
        self.disconnect_btn.pack(side='left', padx=5)
        
        self.test_btn = ttk.Button(conn_btn_frame, text="🧪 Test Connection", command=self.test_connection)
        self.test_btn.pack(side='left', padx=5)
        
        # Account Info Frame
        account_frame = ttk.LabelFrame(self.dashboard_frame, text="💰 Account Information")
        account_frame.pack(fill='x', padx=10, pady=5)
        
        # Account info grid
        info_grid = ttk.Frame(account_frame)
        info_grid.pack(fill='x', padx=10, pady=5)
        
        # Balance info
        ttk.Label(info_grid, text="Balance:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=5)
        self.balance_label = ttk.Label(info_grid, text="$0.00", font=('Arial', 10))
        self.balance_label.grid(row=0, column=1, sticky='w', padx=5)
        
        ttk.Label(info_grid, text="Equity:", font=('Arial', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=5)
        self.equity_label = ttk.Label(info_grid, text="$0.00", font=('Arial', 10))
        self.equity_label.grid(row=0, column=3, sticky='w', padx=5)
        
        ttk.Label(info_grid, text="P&L:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=5)
        self.pnl_label = ttk.Label(info_grid, text="$0.00", font=('Arial', 10))
        self.pnl_label.grid(row=1, column=1, sticky='w', padx=5)
        
        ttk.Label(info_grid, text="Free Margin:", font=('Arial', 10, 'bold')).grid(row=1, column=2, sticky='w', padx=5)
        self.margin_label = ttk.Label(info_grid, text="$0.00", font=('Arial', 10))
        self.margin_label.grid(row=1, column=3, sticky='w', padx=5)
        
        # Position Sizing Frame
        sizing_frame = ttk.LabelFrame(self.dashboard_frame, text="📏 Position Sizing Controls")
        sizing_frame.pack(fill='x', padx=10, pady=5)
        
        sizing_grid = ttk.Frame(sizing_frame)
        sizing_grid.pack(fill='x', padx=10, pady=5)
        
        # Risk % control
        ttk.Label(sizing_grid, text="Risk %:").grid(row=0, column=0, sticky='w', padx=5)
        self.risk_var = tk.DoubleVar(value=self.config.get('position_sizing', {}).get('risk_percent', 2.0))
        self.risk_scale = ttk.Scale(sizing_grid, from_=1.0, to=5.0, variable=self.risk_var, orient='horizontal')
        self.risk_scale.grid(row=0, column=1, sticky='ew', padx=5)
        self.risk_label = ttk.Label(sizing_grid, text="2.0%")
        self.risk_label.grid(row=0, column=2, padx=5)
        
        # Max lot size control
        ttk.Label(sizing_grid, text="Max Lot Size:").grid(row=1, column=0, sticky='w', padx=5)
        self.max_lot_var = tk.DoubleVar(value=self.config.get('position_sizing', {}).get('max_lot_size', 1.0))
        self.max_lot_entry = ttk.Entry(sizing_grid, textvariable=self.max_lot_var, width=10)
        self.max_lot_entry.grid(row=1, column=1, sticky='w', padx=5)
        
        # Dynamic sizing checkbox
        self.dynamic_var = tk.BooleanVar(value=self.config.get('position_sizing', {}).get('dynamic_sizing', True))
        self.dynamic_check = ttk.Checkbutton(sizing_grid, text="Dynamic Sizing", variable=self.dynamic_var)
        self.dynamic_check.grid(row=1, column=2, padx=5)
        
        sizing_grid.columnconfigure(1, weight=1)
        
        # System Control Frame
        control_frame = ttk.LabelFrame(self.dashboard_frame, text="🎛️ System Control")
        control_frame.pack(fill='x', padx=10, pady=5)
        
        control_grid = ttk.Frame(control_frame)
        control_grid.pack(fill='x', padx=10, pady=5)
        
        self.start_btn = ttk.Button(control_grid, text="🚀 Start System", command=self.start_system, state='disabled')
        self.start_btn.pack(side='left', padx=5)
        
        self.stop_btn = ttk.Button(control_grid, text="⏹️ Stop System", command=self.stop_system, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        self.emergency_btn = ttk.Button(control_grid, text="🚨 Emergency Stop", command=self.emergency_stop, state='disabled')
        self.emergency_btn.pack(side='left', padx=5)
        
        # Status indicator
        self.status_label = ttk.Label(control_grid, text="System: Stopped", font=('Arial', 10, 'bold'))
        self.status_label.pack(side='right', padx=5)
        
        # Market Data Frame
        market_frame = ttk.LabelFrame(self.dashboard_frame, text="📈 Market Data")
        market_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Market data treeview
        columns = ('Symbol', 'Bid', 'Ask', 'Spread', 'Last Update')
        self.market_tree = ttk.Treeview(market_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            self.market_tree.heading(col, text=col)
            self.market_tree.column(col, width=100)
        
        market_scroll = ttk.Scrollbar(market_frame, orient='vertical', command=self.market_tree.yview)
        self.market_tree.configure(yscrollcommand=market_scroll.set)
        
        self.market_tree.pack(side='left', fill='both', expand=True)
        market_scroll.pack(side='right', fill='y')
    
    def create_positions_tab(self):
        """Create positions tab"""
        self.positions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.positions_frame, text="📋 Positions")
        
        # Positions treeview
        pos_columns = ('Ticket', 'Symbol', 'Type', 'Lots', 'Open Price', 'Current', 'Pips', 'Profit', 'Time')
        self.positions_tree = ttk.Treeview(self.positions_frame, columns=pos_columns, show='headings')
        
        for col in pos_columns:
            self.positions_tree.heading(col, text=col)
            self.positions_tree.column(col, width=80)
        
        pos_scroll = ttk.Scrollbar(self.positions_frame, orient='vertical', command=self.positions_tree.yview)
        self.positions_tree.configure(yscrollcommand=pos_scroll.set)
        
        self.positions_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        pos_scroll.pack(side='right', fill='y', pady=10)
        
        # Position control buttons
        pos_btn_frame = ttk.Frame(self.positions_frame)
        pos_btn_frame.pack(side='bottom', fill='x', padx=10, pady=5)
        
        ttk.Button(pos_btn_frame, text="🔄 Refresh", command=self.refresh_positions).pack(side='left', padx=5)
        ttk.Button(pos_btn_frame, text="❌ Close Selected", command=self.close_selected_position).pack(side='left', padx=5)
        ttk.Button(pos_btn_frame, text="❌ Close All", command=self.close_all_positions).pack(side='left', padx=5)
    
    def create_settings_tab(self):
        """Create settings tab"""
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="⚙️ Settings")
        
        # Settings will be added here
        ttk.Label(self.settings_frame, text="Settings configuration will be implemented here", 
                 font=('Arial', 12)).pack(pady=50)
    
    def create_log_tab(self):
        """Create log tab"""
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="📝 Log")
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, height=30)
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Log control buttons
        log_btn_frame = ttk.Frame(self.log_frame)
        log_btn_frame.pack(side='bottom', fill='x', padx=10, pady=5)
        
        ttk.Button(log_btn_frame, text="🗑️ Clear Log", command=self.clear_log).pack(side='left', padx=5)
        ttk.Button(log_btn_frame, text="💾 Save Log", command=self.save_log).pack(side='left', padx=5)
    
    def connect_mt5(self):
        """Connect to MT5"""
        try:
            self.log_message("🔌 Attempting to connect to MT5...")
            
            if self.mt5_conn and self.mt5_conn.connect():
                self.log_message("✅ Successfully connected to MT5!")
                self.connect_btn.config(state='disabled')
                self.disconnect_btn.config(state='normal')
                self.start_btn.config(state='normal')
                self.emergency_btn.config(state='normal')
                
                # Start monitoring
                if self.mt5_conn.start_monitoring():
                    self.log_message("📊 Started MT5 monitoring thread")
                
                self.update_connection_status()
            else:
                self.log_message("❌ Failed to connect to MT5")
                messagebox.showerror("Connection Failed", "Could not connect to MT5. Please check:\n"
                                   "1. MT5 is installed and running\n"
                                   "2. Login credentials in config.json\n"
                                   "3. Demo account is active")
        except Exception as e:
            self.log_message(f"❌ Connection error: {e}")
            messagebox.showerror("Connection Error", f"Error connecting to MT5: {e}")
    
    def disconnect_mt5(self):
        """Disconnect from MT5"""
        try:
            if self.mt5_conn:
                self.mt5_conn.disconnect()
                self.log_message("🔌 Disconnected from MT5")
            
            self.connect_btn.config(state='normal')
            self.disconnect_btn.config(state='disabled')
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='disabled')
            self.emergency_btn.config(state='disabled')
            
            self.update_connection_status()
        except Exception as e:
            self.log_message(f"❌ Disconnect error: {e}")
    
    def test_connection(self):
        """Test MT5 connection and display diagnostics"""
        self.log_message("🧪 Testing MT5 connection...")
        
        try:
            import MetaTrader5 as mt5
            
            # Test MT5 initialization
            if not mt5.initialize():
                self.log_message("❌ MT5 initialize() failed")
                error = mt5.last_error()
                self.log_message(f"❌ Last error: {error}")
                return
            
            self.log_message("✅ MT5 initialize() successful")
            
            # Test terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info:
                self.log_message(f"📊 Terminal: {terminal_info.name}")
                self.log_message(f"📊 Path: {terminal_info.path}")
                self.log_message(f"📊 Connected: {terminal_info.connected}")
            
            # Test login
            config = self.config.get('mt5', {})
            login = config.get('login')
            password = config.get('password')
            server = config.get('server')
            
            if all([login, password, server]):
                self.log_message(f"🔐 Attempting login to {server}...")
                if mt5.login(login, password, server):
                    self.log_message("✅ Login successful!")
                    
                    # Test account info
                    account = mt5.account_info()
                    if account:
                        self.log_message(f"💰 Account: {account.name}")
                        self.log_message(f"💰 Balance: ${account.balance:.2f}")
                        self.log_message(f"💰 Server: {account.server}")
                else:
                    error = mt5.last_error()
                    self.log_message(f"❌ Login failed: {error}")
            else:
                self.log_message("❌ Missing login credentials in config.json")
            
            mt5.shutdown()
            
        except ImportError:
            self.log_message("❌ MetaTrader5 module not installed")
            messagebox.showerror("Missing Module", "MetaTrader5 module is not installed.\n"
                               "Install it using: pip install MetaTrader5")
        except Exception as e:
            self.log_message(f"❌ Test error: {e}")
    
    def start_system(self):
        """Start the arbitrage system"""
        self.system_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_label.config(text="System: Running", foreground='green')
        self.log_message("🚀 Arbitrage system started")
    
    def stop_system(self):
        """Stop the arbitrage system"""
        self.system_running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="System: Stopped", foreground='red')
        self.log_message("⏹️ Arbitrage system stopped")
    
    def emergency_stop(self):
        """Emergency stop - close all positions"""
        if messagebox.askyesno("Emergency Stop", "This will close ALL open positions!\nAre you sure?"):
            try:
                if self.mt5_conn:
                    closed = self.mt5_conn.close_all_positions()
                    self.log_message(f"🚨 Emergency stop: Closed {closed} positions")
                self.stop_system()
            except Exception as e:
                self.log_message(f"❌ Emergency stop error: {e}")
    
    def refresh_positions(self):
        """Refresh positions display"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            return
        
        try:
            # Clear existing items
            for item in self.positions_tree.get_children():
                self.positions_tree.delete(item)
            
            # Get current positions
            positions = self.mt5_conn.get_positions()
            
            for pos in positions:
                ticket = pos.get('ticket', '')
                symbol = pos.get('symbol', '')
                pos_type = 'BUY' if pos.get('type', 0) == 0 else 'SELL'
                lots = pos.get('volume', 0)
                open_price = pos.get('price_open', 0)
                current_price = pos.get('price_current', 0)
                profit = pos.get('profit', 0)
                
                # Calculate pips (simplified)
                if 'JPY' in symbol:
                    pips = (current_price - open_price) * 100
                else:
                    pips = (current_price - open_price) * 10000
                
                if pos_type == 'SELL':
                    pips = -pips
                
                open_time = datetime.fromtimestamp(pos.get('time', 0)).strftime('%H:%M:%S')
                
                self.positions_tree.insert('', 'end', values=(
                    ticket, symbol, pos_type, f"{lots:.2f}", f"{open_price:.5f}",
                    f"{current_price:.5f}", f"{pips:.1f}", f"${profit:.2f}", open_time
                ))
        
        except Exception as e:
            self.log_message(f"❌ Error refreshing positions: {e}")
    
    def close_selected_position(self):
        """Close selected position"""
        selection = self.positions_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a position to close")
            return
        
        item = self.positions_tree.item(selection[0])
        ticket = item['values'][0]
        
        if messagebox.askyesno("Close Position", f"Close position {ticket}?"):
            try:
                if self.mt5_conn and self.mt5_conn.close_position(int(ticket)):
                    self.log_message(f"✅ Closed position {ticket}")
                    self.refresh_positions()
                else:
                    self.log_message(f"❌ Failed to close position {ticket}")
            except Exception as e:
                self.log_message(f"❌ Error closing position: {e}")
    
    def close_all_positions(self):
        """Close all positions"""
        if messagebox.askyesno("Close All", "Close ALL open positions?"):
            try:
                if self.mt5_conn:
                    closed = self.mt5_conn.close_all_positions()
                    self.log_message(f"✅ Closed {closed} positions")
                    self.refresh_positions()
            except Exception as e:
                self.log_message(f"❌ Error closing positions: {e}")
    
    def update_connection_status(self):
        """Update connection status display"""
        if self.mt5_conn and self.mt5_conn.connected:
            self.conn_status_label.config(text="✅ Connected", foreground='green')
            status = self.mt5_conn.get_connection_status()
            details = f"Account: {self.mt5_conn.account_info.get('name', 'Unknown') if self.mt5_conn.account_info else 'Not logged in'}"
            details += f" | Last Update: {status.get('last_update', 'Never')}"
            self.conn_details_label.config(text=details)
        else:
            self.conn_status_label.config(text="❌ Disconnected", foreground='red')
            self.conn_details_label.config(text="Not connected to MT5")
    
    def update_account_info(self):
        """Update account information display"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            return
        
        try:
            summary = self.mt5_conn.get_account_summary()
            
            self.balance_label.config(text=f"${summary.get('balance', 0):.2f}")
            self.equity_label.config(text=f"${summary.get('equity', 0):.2f}")
            
            profit = summary.get('profit', 0)
            color = 'green' if profit >= 0 else 'red'
            self.pnl_label.config(text=f"${profit:.2f}", foreground=color)
            
            self.margin_label.config(text=f"${summary.get('free_margin', 0):.2f}")
            
        except Exception as e:
            self.log_message(f"❌ Error updating account info: {e}")
    
    def update_market_data(self):
        """Update market data display"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            return
        
        try:
            # Clear existing items
            for item in self.market_tree.get_children():
                self.market_tree.delete(item)
            
            # Get market data for configured symbols
            symbols = self.config.get('arbitrage', {}).get('currency_pairs', [])[:10]  # Limit to 10
            
            for symbol in symbols:
                tick = self.mt5_conn.get_tick(symbol)
                if tick:
                    bid = tick.get('bid', 0)
                    ask = tick.get('ask', 0)
                    spread = (ask - bid) * (10000 if 'JPY' not in symbol else 100)
                    last_time = datetime.fromtimestamp(tick.get('time', 0)).strftime('%H:%M:%S')
                    
                    self.market_tree.insert('', 'end', values=(
                        symbol, f"{bid:.5f}", f"{ask:.5f}", f"{spread:.1f}", last_time
                    ))
        
        except Exception as e:
            self.log_message(f"❌ Error updating market data: {e}")
    
    def update_risk_label(self, *args):
        """Update risk percentage label"""
        risk_pct = self.risk_var.get()
        self.risk_label.config(text=f"{risk_pct:.1f}%")
    
    def start_update_loop(self):
        """Start the GUI update loop"""
        def update_loop():
            while True:
                try:
                    if self.mt5_conn and self.mt5_conn.connected:
                        self.root.after(0, self.update_connection_status)
                        self.root.after(0, self.update_account_info)
                        self.root.after(0, self.update_market_data)
                        self.root.after(0, self.refresh_positions)
                    
                    self.root.after(0, lambda: self.risk_label.config(text=f"{self.risk_var.get():.1f}%"))
                    
                    time.sleep(2)  # Update every 2 seconds
                except Exception as e:
                    print(f"Update loop error: {e}")
                    time.sleep(5)
        
        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()
    
    def log_message(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Add to GUI log
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # Also print to console
        print(log_entry.strip())
    
    def clear_log(self):
        """Clear the log"""
        self.log_text.delete(1.0, tk.END)
    
    def save_log(self):
        """Save log to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"arbitrage_log_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))
            
            self.log_message(f"💾 Log saved to {filename}")
            messagebox.showinfo("Save Log", f"Log saved to {filename}")
        except Exception as e:
            self.log_message(f"❌ Error saving log: {e}")
    
    def on_closing(self):
        """Handle window closing"""
        if self.system_running:
            if messagebox.askokcancel("Quit", "System is running. Stop and quit?"):
                self.stop_system()
                if self.mt5_conn:
                    self.mt5_conn.disconnect()
                self.root.destroy()
        else:
            if self.mt5_conn:
                self.mt5_conn.disconnect()
            self.root.destroy()
    
    def run(self):
        """Start the GUI"""
        self.log_message("🎯 Triangular Arbitrage System Started")
        self.log_message("📋 Please connect to MT5 to begin")
        self.root.mainloop()

if __name__ == "__main__":
    try:
        app = TriangularArbitrageGUI()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")