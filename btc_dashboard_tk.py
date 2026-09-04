"""
btc_dashboard.py - BTC Indicators Dashboard with Email Button
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import threading
import webbrowser
from datetime import datetime
import os
import sys

# Import btc_indicators
try:
    from btc_indicators import BTCIndicators
except ImportError:
    print("❌ btc_indicators.py not found!")
    sys.exit(1)

# Import email sender
try:
    from btc_email_sender import BTCEmailSender
except ImportError:
    print("❌ btc_email_sender.py not found!")
    sys.exit(1)

class BTCDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 BTC Indicators Dashboard")
        self.root.geometry("1400x800")
        self.root.configure(bg='#1a1a2e')
        
        # Variables
        self.results = None
        self.indicators = None
        self.email_sender = None
        
        # Colors
        self.colors = {
            'bg': '#1a1a2e',
            'card': '#16213e',
            'card2': '#0f3460',
            'text': '#ffffff',
            'text2': '#e0e0e0',
            'gold': '#f7931a',
            'green': '#00ff88',
            'red': '#ff4757',
            'yellow': '#ffd93d'
        }
        
        # Create main container
        self.create_main_container()
        
        # Load initial data
        self.load_indicators()
        
        # Auto refresh every 5 minutes
        self.auto_refresh()
    
    def create_main_container(self):
        """Create main container with header"""
        # Main frame
        self.main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        self.create_header()
        
        # Content frame (scrollable)
        self.create_content_frame()
        
        # Bottom buttons
        self.create_bottom_buttons()
    
    def create_header(self):
        """Create header with title and time"""
        header_frame = tk.Frame(self.main_frame, bg=self.colors['bg'])
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        title_label = tk.Label(
            header_frame,
            text="🚀 BTC Indicators Dashboard",
            font=('Arial', 28, 'bold'),
            fg=self.colors['gold'],
            bg=self.colors['bg']
        )
        title_label.pack(side=tk.LEFT)
        
        # Time
        self.time_label = tk.Label(
            header_frame,
            text=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            font=('Arial', 14),
            fg=self.colors['text2'],
            bg=self.colors['bg']
        )
        self.time_label.pack(side=tk.RIGHT)
        
        # Update time every second
        self.update_time()
    
    def update_time(self):
        """Update time label"""
        self.time_label.config(text=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self.root.after(1000, self.update_time)
    
    def create_content_frame(self):
        """Create scrollable content frame"""
        # Canvas for scrolling
        self.canvas = tk.Canvas(self.main_frame, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.colors['bg'])
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Content area (will be filled)
        self.content_area = tk.Frame(self.scrollable_frame, bg=self.colors['bg'])
        self.content_area.pack(fill=tk.BOTH, expand=True)
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def create_bottom_buttons(self):
        """Create bottom buttons"""
        button_frame = tk.Frame(self.main_frame, bg=self.colors['bg'])
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Refresh button
        refresh_btn = tk.Button(
            button_frame,
            text="🔄 Refresh Data",
            font=('Arial', 12, 'bold'),
            bg=self.colors['gold'],
            fg='white',
            padx=20,
            pady=10,
            cursor='hand2',
            command=self.load_indicators
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Email button
        self.email_btn = tk.Button(
            button_frame,
            text="📧 Send Email Report",
            font=('Arial', 12, 'bold'),
            bg='#00b894',
            fg='white',
            padx=20,
            pady=10,
            cursor='hand2',
            command=self.send_email_report,
            state=tk.DISABLED
        )
        self.email_btn.pack(side=tk.LEFT, padx=5)
        
        # Export JSON button
        export_btn = tk.Button(
            button_frame,
            text="💾 Export JSON",
            font=('Arial', 12, 'bold'),
            bg='#0984e3',
            fg='white',
            padx=20,
            pady=10,
            cursor='hand2',
            command=self.export_json
        )
        export_btn.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = tk.Label(
            button_frame,
            text="✅ Ready",
            font=('Arial', 11),
            fg=self.colors['green'],
            bg=self.colors['bg']
        )
        self.status_label.pack(side=tk.RIGHT, padx=10)
    
    def load_indicators(self):
        """Load indicators in background thread"""
        self.status_label.config(text="⏳ Loading indicators...", fg=self.colors['yellow'])
        self.email_btn.config(state=tk.DISABLED)
        
        # Run in thread
        thread = threading.Thread(target=self._load_indicators_thread)
        thread.daemon = True
        thread.start()
    
    def _load_indicators_thread(self):
        """Load indicators in thread"""
        try:
            # Clear content
            self.root.after(0, self.clear_content)
            
            # Get indicators
            indicator = BTCIndicators()
            results = indicator.calculate_all_indicators()
            indicator.close()
            
            if results:
                self.results = results
                self.root.after(0, self.display_indicators)
                self.root.after(0, lambda: self.status_label.config(text="✅ Data loaded successfully", fg=self.colors['green']))
                self.root.after(0, lambda: self.email_btn.config(state=tk.NORMAL))
            else:
                self.root.after(0, lambda: self.status_label.config(text="❌ Failed to load indicators", fg=self.colors['red']))
                self.root.after(0, self.show_error)
                
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text=f"❌ Error: {str(e)}", fg=self.colors['red']))
            self.root.after(0, self.show_error)
    
    def clear_content(self):
        """Clear content area"""
        for widget in self.content_area.winfo_children():
            widget.destroy()
    
    def display_indicators(self):
        """Display all indicators"""
        if not self.results:
            return
        
        # Create grid of cards
        row = 0
        col = 0
        
        # Current Price Card
        self.create_price_card(row, col)
        col += 1
        
        # Signal Card
        if col == 2:
            col = 0
            row += 1
        self.create_signal_card(row, col)
        col += 1
        
        # Support & Resistance Card
        if col == 2:
            col = 0
            row += 1
        self.create_sr_card(row, col)
        col += 1
        
        # Moving Averages Card
        if col == 2:
            col = 0
            row += 1
        self.create_ma_card(row, col)
        col += 1
        
        # RSI & MACD Card
        if col == 2:
            col = 0
            row += 1
        self.create_rsi_macd_card(row, col)
        col += 1
        
        # Bollinger Bands Card
        if col == 2:
            col = 0
            row += 1
        self.create_bb_card(row, col)
        col += 1
        
        # Fibonacci Card
        if col == 2:
            col = 0
            row += 1
        self.create_fib_card(row, col)
        col += 1
        
        # Pivot Points Card
        if col == 2:
            col = 0
            row += 1
        self.create_pivot_card(row, col)
        col += 1
        
        # Liquidity Card
        if col == 2:
            col = 0
            row += 1
        self.create_liquidity_card(row, col)
        col += 1
        
        # ATR Card
        if col == 2:
            col = 0
            row += 1
        self.create_atr_card(row, col)
    
    def create_card(self, parent, title, row, col, width=2):
        """Create a card"""
        card = tk.Frame(
            parent,
            bg=self.colors['card'],
            relief=tk.RAISED,
            bd=2
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Title
        title_label = tk.Label(
            card,
            text=title,
            font=('Arial', 14, 'bold'),
            fg=self.colors['gold'],
            bg=self.colors['card']
        )
        title_label.pack(pady=(10, 5))
        
        # Separator
        separator = tk.Frame(card, height=2, bg=self.colors['gold'])
        separator.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        return card
    
    def create_price_card(self, row, col):
        """Create price card"""
        card = self.create_card(self.content_area, "💰 Current Price", row, col)
        
        if 'current_price' in self.results:
            price = self.results['current_price']
            
            price_label = tk.Label(
                card,
                text=f"${price:,.2f}",
                font=('Arial', 36, 'bold'),
                fg=self.colors['gold'],
                bg=self.colors['card']
            )
            price_label.pack(pady=10)
            
            date_label = tk.Label(
                card,
                text=f"Date: {self.results.get('date', 'N/A')}",
                font=('Arial', 11),
                fg=self.colors['text2'],
                bg=self.colors['card']
            )
            date_label.pack(pady=5)
            
            time_label = tk.Label(
                card,
                text=f"Updated: {self.results.get('timestamp', 'N/A')}",
                font=('Arial', 10),
                fg=self.colors['text2'],
                bg=self.colors['card']
            )
            time_label.pack(pady=5)
    
    def create_signal_card(self, row, col):
        """Create signal card"""
        card = self.create_card(self.content_area, "🎯 Overall Signal", row, col)
        
        if 'overall_signal' in self.results:
            signal = self.results['overall_signal']
            direction = signal.get('direction', 'NEUTRAL')
            score = signal.get('score', 0)
            
            # Signal color
            if 'BUY' in direction:
                color = self.colors['green']
            elif 'SELL' in direction:
                color = self.colors['red']
            else:
                color = self.colors['yellow']
            
            signal_label = tk.Label(
                card,
                text=direction,
                font=('Arial', 28, 'bold'),
                fg=color,
                bg=self.colors['card']
            )
            signal_label.pack(pady=10)
            
            score_label = tk.Label(
                card,
                text=f"Score: {score}",
                font=('Arial', 14),
                fg=self.colors['text2'],
                bg=self.colors['card']
            )
            score_label.pack(pady=5)
            
            # Factors
            if 'factors' in signal:
                factors_text = "\n".join([f"• {f}" for f in signal['factors'][:5]])
                factors_label = tk.Label(
                    card,
                    text=factors_text,
                    font=('Arial', 10),
                    fg=self.colors['text2'],
                    bg=self.colors['card'],
                    justify=tk.LEFT
                )
                factors_label.pack(pady=5)
    
    def create_sr_card(self, row, col):
        """Create Support & Resistance card"""
        card = self.create_card(self.content_area, "🎯 Support & Resistance", row, col)
        
        if 'support_resistance' in self.results:
            sr = self.results['support_resistance']
            
            # Nearest levels
            support = sr.get('nearest_support', {})
            resistance = sr.get('nearest_resistance', {})
            
            support_price = support.get('price', 0) if support else 0
            resistance_price = resistance.get('price', 0) if resistance else 0
            
            # Support
            support_label = tk.Label(
                card,
                text=f"Support: ${support_price:,.2f}",
                font=('Arial', 14),
                fg=self.colors['green'],
                bg=self.colors['card']
            )
            support_label.pack(pady=5)
            
            # Resistance
            resistance_label = tk.Label(
                card,
                text=f"Resistance: ${resistance_price:,.2f}",
                font=('Arial', 14),
                fg=self.colors['red'],
                bg=self.colors['card']
            )
            resistance_label.pack(pady=5)
            
            # Top levels
            levels_text = ""
            if 'support_levels' in sr and sr['support_levels']:
                levels_text += "Supports: "
                levels_text += ", ".join([f"${s['price']:,.0f}" for s in sr['support_levels'][:2]])
            
            if 'resistance_levels' in sr and sr['resistance_levels']:
                if levels_text:
                    levels_text += " | "
                levels_text += "Resistances: "
                levels_text += ", ".join([f"${r['price']:,.0f}" for r in sr['resistance_levels'][:2]])
            
            if levels_text:
                levels_label = tk.Label(
                    card,
                    text=levels_text,
                    font=('Arial', 10),
                    fg=self.colors['text2'],
                    bg=self.colors['card']
                )
                levels_label.pack(pady=5)
    
    def create_ma_card(self, row, col):
        """Create Moving Averages card"""
        card = self.create_card(self.content_area, "📈 Moving Averages", row, col)
        
        if 'moving_averages' in self.results:
            ma = self.results['moving_averages']
            
            for period, data in list(ma.items())[:5]:
                text = f"{period}: ${data['value']:,.2f} ({data.get('trend', 'Neutral')})"
                color = self.colors['green'] if data.get('trend') == 'Bullish' else self.colors['red'] if data.get('trend') == 'Bearish' else self.colors['yellow']
                
                label = tk.Label(
                    card,
                    text=text,
                    font=('Arial', 11),
                    fg=color,
                    bg=self.colors['card']
                )
                label.pack(anchor=tk.W, padx=10, pady=2)
    
    def create_rsi_macd_card(self, row, col):
        """Create RSI & MACD card"""
        card = self.create_card(self.content_area, "📊 RSI & MACD", row, col)
        
        # RSI
        if 'rsi' in self.results:
            rsi = self.results['rsi']
            color = self.colors['green'] if rsi.get('status') == 'Oversold' else self.colors['red'] if rsi.get('status') == 'Overbought' else self.colors['yellow']
            
            rsi_label = tk.Label(
                card,
                text=f"RSI: {rsi.get('value', 0):.1f} ({rsi.get('status', 'Neutral')})",
                font=('Arial', 12, 'bold'),
                fg=color,
                bg=self.colors['card']
            )
            rsi_label.pack(anchor=tk.W, padx=10, pady=2)
        
        # MACD
        if 'macd' in self.results:
            macd = self.results['macd']
            color = self.colors['green'] if macd.get('signal_status') == 'Bullish' else self.colors['red']
            
            macd_label = tk.Label(
                card,
                text=f"MACD: {macd.get('signal_status', 'Neutral')}",
                font=('Arial', 12, 'bold'),
                fg=color,
                bg=self.colors['card']
            )
            macd_label.pack(anchor=tk.W, padx=10, pady=2)
            
            # MACD values
            values_text = f"Signal: {macd.get('signal', 0):.2f} | Hist: {macd.get('histogram', 0):.2f}"
            values_label = tk.Label(
                card,
                text=values_text,
                font=('Arial', 10),
                fg=self.colors['text2'],
                bg=self.colors['card']
            )
            values_label.pack(anchor=tk.W, padx=10, pady=2)
    
    def create_bb_card(self, row, col):
        """Create Bollinger Bands card"""
        card = self.create_card(self.content_area, "📊 Bollinger Bands", row, col)
        
        if 'bollinger_bands' in self.results:
            bb = self.results['bollinger_bands']
            
            labels = [
                (f"Upper: ${bb.get('upper_band', 0):,.2f}", self.colors['red']),
                (f"Middle: ${bb.get('middle_band', 0):,.2f}", self.colors['yellow']),
                (f"Lower: ${bb.get('lower_band', 0):,.2f}", self.colors['green']),
                (f"Position: {bb.get('position', 'Inside Bands')}", self.colors['text2']),
                (f"Squeeze: {bb.get('squeeze', 'No')}", self.colors['text2'])
            ]
            
            for text, color in labels:
                label = tk.Label(
                    card,
                    text=text,
                    font=('Arial', 11),
                    fg=color,
                    bg=self.colors['card']
                )
                label.pack(anchor=tk.W, padx=10, pady=2)
    
    def create_fib_card(self, row, col):
        """Create Fibonacci card"""
        card = self.create_card(self.content_area, "📊 Fibonacci Levels", row, col)
        
        if 'fibonacci' in self.results:
            fib = self.results['fibonacci']
            
            # Show key levels
            fib_levels = fib.get('fib_levels', {})
            key_levels = ['0.0', '0.236', '0.382', '0.5', '0.618', '0.786', '1.0']
            
            for level in key_levels:
                if level in fib_levels:
                    text = f"{level}: ${fib_levels[level]:,.2f}"
                    color = self.colors['gold'] if level == '0.5' else self.colors['text2']
                    
                    label = tk.Label(
                        card,
                        text=text,
                        font=('Arial', 10),
                        fg=color,
                        bg=self.colors['card']
                    )
                    label.pack(anchor=tk.W, padx=10, pady=1)
            
            if fib.get('current_fib_level'):
                current_label = tk.Label(
                    card,
                    text=f"Current Level: {fib['current_fib_level']}",
                    font=('Arial', 10, 'bold'),
                    fg=self.colors['gold'],
                    bg=self.colors['card']
                )
                current_label.pack(anchor=tk.W, padx=10, pady=5)
    
    def create_pivot_card(self, row, col):
        """Create Pivot Points card"""
        card = self.create_card(self.content_area, "📊 Pivot Points", row, col)
        
        if 'pivot_points' in self.results:
            pivot = self.results['pivot_points']
            
            labels = [
                (f"Pivot: ${pivot.get('pivot', 0):,.2f}", self.colors['gold']),
                (f"R1: ${pivot.get('resistance_1', 0):,.2f} | S1: ${pivot.get('support_1', 0):,.2f}", self.colors['text2']),
                (f"R2: ${pivot.get('resistance_2', 0):,.2f} | S2: ${pivot.get('support_2', 0):,.2f}", self.colors['text2']),
                (f"Position: {pivot.get('current_position', 'N/A')}", self.colors['text2'])
            ]
            
            for text, color in labels:
                label = tk.Label(
                    card,
                    text=text,
                    font=('Arial', 11),
                    fg=color,
                    bg=self.colors['card']
                )
                label.pack(anchor=tk.W, padx=10, pady=2)
    
    def create_liquidity_card(self, row, col):
        """Create Liquidity card"""
        card = self.create_card(self.content_area, "💧 Liquidity", row, col)
        
        if 'liquidity' in self.results:
            liq = self.results['liquidity']
            
            labels = [
                (f"30-Day Avg Volume: {liq.get('avg_volume_30d', 0):,.0f}", self.colors['text2']),
                (f"Volume Ratio: {liq.get('volume_ratio', 0):.2f}x", self.colors['text2'])
            ]
            
            for text, color in labels:
                label = tk.Label(
                    card,
                    text=text,
                    font=('Arial', 11),
                    fg=color,
                    bg=self.colors['card']
                )
                label.pack(anchor=tk.W, padx=10, pady=2)
            
            # High volume nodes
            if 'high_volume_nodes' in liq and liq['high_volume_nodes']:
                nodes_text = "High Volume Nodes:"
                for node in liq['high_volume_nodes'][:2]:
                    nodes_text += f"\n  {node.get('price_range', 'N/A')}"
                
                nodes_label = tk.Label(
                    card,
                    text=nodes_text,
                    font=('Arial', 9),
                    fg=self.colors['text2'],
                    bg=self.colors['card'],
                    justify=tk.LEFT
                )
                nodes_label.pack(anchor=tk.W, padx=10, pady=2)
    
    def create_atr_card(self, row, col):
        """Create ATR card"""
        card = self.create_card(self.content_area, "📊 Volatility (ATR)", row, col)
        
        if 'atr' in self.results:
            atr = self.results['atr']
            
            labels = [
                (f"ATR Value: ${atr.get('atr', 0):,.2f}", self.colors['text2']),
                (f"ATR %: {atr.get('atr_percent', 0):.2f}%", self.colors['text2']),
                (f"Status: {atr.get('volatility_status', 'Normal')}", self.colors['text2'])
            ]
            
            for text, color in labels:
                label = tk.Label(
                    card,
                    text=text,
                    font=('Arial', 11),
                    fg=color,
                    bg=self.colors['card']
                )
                label.pack(anchor=tk.W, padx=10, pady=2)
    
    def send_email_report(self):
        """Send email report"""
        if not self.results:
            messagebox.showerror("Error", "No data available to send!")
            return
        
        self.status_label.config(text="📧 Sending email...", fg=self.colors['yellow'])
        self.email_btn.config(state=tk.DISABLED)
        
        # Run in thread
        thread = threading.Thread(target=self._send_email_thread)
        thread.daemon = True
        thread.start()
    
    def _send_email_thread(self):
        """Send email in thread"""
        try:
            # Create email sender
            email_sender = BTCEmailSender()
            
            # Use existing results
            email_sender.results = self.results
            
            # Create email content
            html_content = email_sender.create_html_email()
            
            if html_content:
                # Send email
                subject = f"🚀 BTC Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
                success = email_sender.send_email(subject, html_content)
                
                if success:
                    self.root.after(0, lambda: self.status_label.config(text="✅ Email sent successfully!", fg=self.colors['green']))
                    self.root.after(0, lambda: messagebox.showinfo("Success", "Email sent successfully!"))
                else:
                    self.root.after(0, lambda: self.status_label.config(text="❌ Failed to send email", fg=self.colors['red']))
                    self.root.after(0, lambda: messagebox.showerror("Error", "Failed to send email!"))
            else:
                self.root.after(0, lambda: self.status_label.config(text="❌ Failed to create email content", fg=self.colors['red']))
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to create email content!"))
                
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text=f"❌ Error: {str(e)}", fg=self.colors['red']))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        finally:
            self.root.after(0, lambda: self.email_btn.config(state=tk.NORMAL))
    
    def export_json(self):
        """Export results to JSON"""
        if not self.results:
            messagebox.showerror("Error", "No data to export!")
            return
        
        try:
            filename = f"btc_indicators_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Convert numpy types
            def convert(obj):
                if hasattr(obj, 'item'):
                    return obj.item()
                return obj
            
            with open(filename, 'w') as f:
                json.dump(self.results, f, default=convert, indent=2)
            
            messagebox.showinfo("Success", f"Data exported to {filename}")
            self.status_label.config(text=f"✅ Exported to {filename}", fg=self.colors['green'])
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")
            self.status_label.config(text=f"❌ Export failed: {str(e)}", fg=self.colors['red'])
    
    def show_error(self):
        """Show error message"""
        messagebox.showerror(
            "Error",
            "Failed to load indicators!\nPlease check database connection."
        )
    
    def auto_refresh(self):
        """Auto refresh every 5 minutes"""
        self.root.after(300000, self.load_indicators)  # 5 minutes

def main():
    """Main function"""
    root = tk.Tk()
    app = BTCDashboard(root)
    root.mainloop()

if __name__ == "__main__":
    main()