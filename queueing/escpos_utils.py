"""
ESC/POS thermal printer utilities using python-escpos library
FIXED: Updated for current python-escpos API
"""

import os
from escpos.printer import Dummy
from escpos.exceptions import Error
from django.conf import settings
from django.utils.timezone import localtime


class TicketPrinter:
    """Handle ticket printing with ESC/POS - FIXED API"""
     
    @staticmethod
    def generate_escpos_commands(ticket):
        """Generate ESC/POS commands for a queue ticket"""
        printer = Dummy()
        local_time = localtime(ticket.created_at)
        
        # ===== TICKET FORMATTING =====
        
        # Initialize and center align
        printer.set(align='center')
        
        # Title (bold, double size)
        printer.set(font='b', width=2, height=2, align='center')
        printer.textln("QUEUE TICKET")
        
        # Separator line
        printer.set(font='a', width=1, height=1)
        printer.text("=" * 32 + "\n")
        
        # Service (left aligned)
        printer.set(align='left')
        printer.textln(f"Service:  {ticket.service.get_name_display()}")
        
        # Queue Number (BIG and centered)
        printer.set(align='center', font='b', width=4, height=4)
        printer.textln(f"#{ticket.get_display_number()}")
        
        # Date/Time (left aligned)
        printer.set(align='left', font='a', width=1, height=1)
        printer.textln(f"Date:     {ticket.ticket_date}")
        printer.textln(f"Time:     {local_time.strftime('%I:%M %p')}")
        
        # Separator
        printer.text("=" * 32 + "\n")
        
        # Instructions (centered)
        printer.set(align='center')
        printer.textln("Scan QR to check")
        printer.textln("your status")
        printer.textln("\n")
        printer.textln("Thank you for waiting!")
        
        # Cut paper (partial cut)
        printer.cut(mode='part')
        
        raw_bytes = printer.output
        human_readable = TicketPrinter._bytes_to_human_readable(raw_bytes)
        preview_html = TicketPrinter._generate_html_preview(ticket)
        
        return raw_bytes, human_readable, preview_html
    
    @staticmethod
    def _bytes_to_human_readable(data):
        """Convert ESC/POS bytes to human-readable string for debugging"""
        result = []
        i = 0
        while i < len(data):
            byte = data[i]
            
            # Check for ESC/POS commands
            if byte == 0x1B:  # ESC
                if i + 1 < len(data):
                    next_byte = data[i + 1]
                    if next_byte == 0x40:
                        result.append("[INIT]\n")
                        i += 1
                    elif next_byte == 0x61:
                        if i + 2 < len(data):
                            align = data[i + 2]
                            align_text = {0: 'Left', 1: 'Center', 2: 'Right'}.get(align, 'Unknown')
                            result.append(f"[Align: {align_text}]\n")
                            i += 2
            elif byte == 0x1D:  # GS
                if i + 1 < len(data) and data[i + 1] == 0x56:  # Cut command
                    result.append("[CUT]\n")
                    i += 2  # Skip cut parameters
            elif byte == 0x0A:  # LF (Line feed)
                result.append("\n")
            elif 32 <= byte <= 126:  # Printable ASCII
                result.append(chr(byte))
            
            i += 1
        
        return "".join(result)
    
    @staticmethod
    def _generate_html_preview(ticket):
        """Generate HTML for browser preview"""
        local_time = localtime(ticket.created_at)
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .ticket {{
                    width: 80mm;
                    font-family: 'Courier New', monospace;
                    border: 2px dashed #333;
                    padding: 15px;
                    margin: 20px auto;
                    background: white;
                    text-align: center;
                }}
                .preview-title {{
                    text-align: center;
                    color: #666;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <h2 class="preview-title">Ticket Preview (80mm width)</h2>
            <div class="ticket">
                <h2 style="margin: 0; font-size: 1.5em;">QUEUE TICKET</h2>
                <hr style="border: 1px solid #000;">
                <div style="text-align: left; margin: 15px 0;">
                    <p style="margin: 5px 0;"><strong>Service:</strong> {ticket.service.get_name_display()}</p>
                    <p style="margin: 5px 0;"><strong>Date:</strong> {ticket.ticket_date}</p>
                </div>
                <h1 style="font-size: 3em; margin: 20px 0; letter-spacing: 2px;">
                    #{ticket.get_display_number()}
                </h1>
                <div style="text-align: left; margin: 15px 0;">
                    <p style="margin: 5px 0;"><strong>Time:</strong> {local_time.strftime('%I:%M %p')}</p>
                </div>
                <hr style="border: 1px solid #000;">
                <p>Scan QR code to check status</p>
                <br>
                <p><strong>Thank you for waiting!</strong></p>
            </div>
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="window.print()">Print Preview</button>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def save_for_testing(ticket, raw_bytes, human_readable):
        """Save ESC/POS output to files for testing"""
        test_dir = os.path.join(settings.BASE_DIR, 'test_prints')
        os.makedirs(test_dir, exist_ok=True)
        
        # Save raw bytes
        raw_path = os.path.join(test_dir, f"ticket_{ticket.queue_number:03d}.bin")
        with open(raw_path, 'wb') as f:
            f.write(raw_bytes)
        
        # Save human readable version
        human_path = os.path.join(test_dir, f"ticket_{ticket.queue_number:03d}_readable.txt")
        with open(human_path, 'w', encoding='utf-8') as f:
            f.write(human_readable)
        
        # Save as hex for inspection
        hex_path = os.path.join(test_dir, f"ticket_{ticket.queue_number:03d}_hex.txt")
        with open(hex_path, 'w') as f:
            hex_str = ' '.join(f'{b:02X}' for b in raw_bytes)
            f.write(hex_str)
        
        return {
            'raw_file': raw_path,
            'readable_file': human_path,
            'hex_file': hex_path
        }


class MockPrinter:
    """
    Mock printer for development without physical printer.
    """
    
    @staticmethod
    def print_ticket(ticket, save_to_file=True):
        """Generate and optionally save ticket for testing"""
        try:
            # Generate ESC/POS commands
            raw_bytes, human_readable, preview_html = TicketPrinter.generate_escpos_commands(ticket)
            
            result = {
                'success': True,
                'raw_bytes': raw_bytes,
                'human_readable': human_readable,
                'preview_html': preview_html,
                'hex_string': ' '.join(f'{b:02X}' for b in raw_bytes),
                'length_bytes': len(raw_bytes),
            }
            
            if save_to_file:
                files = TicketPrinter.save_for_testing(ticket, raw_bytes, human_readable)
                result['saved_files'] = files
            
            return result
            
        except Error as e:
            return {
                'success': False,
                'error': str(e),
                'fallback_text': f"""
                QUEUE TICKET
                ================
                Service:  {ticket.service.get_name_display()}
                Date:     {ticket.ticket_date}
                Number:   #{ticket.get_display_number()}
                Time:     {localtime(ticket.created_at).strftime('%I:%M %p')}
                ================
                Scan QR to check status
                """
            }
        except Exception as e:
            # Catch any other exceptions (like API changes)
            return {
                'success': False,
                'error': f"ESC/POS generation failed: {str(e)}",
                'fallback_text': f"""
                QUEUE TICKET
                ================
                Service:  {ticket.service.get_name_display()}
                Date:     {ticket.ticket_date}
                Number:   #{ticket.get_display_number()}
                ================
                ESC/POS Error - Using fallback format
                """
            }