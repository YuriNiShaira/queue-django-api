"""
ESC/POS thermal printer utilities using python-escpos library
UPDATED: Compatible with current Ticket model (no ticket.service)
"""

import os
from escpos.printer import Dummy
from escpos.exceptions import Error
from django.conf import settings
from django.utils.timezone import localtime


class TicketPrinter:
    """Handle ticket printing with ESC/POS"""

    @staticmethod
    def generate_escpos_commands(ticket):
        """Generate ESC/POS commands for a queue ticket"""
        printer = Dummy()
        local_time = localtime(ticket.created_at)

        # ===== INITIALIZE =====
        printer.set(align='center')

        # ===== TITLE =====
        printer.set(font='b', width=2, height=2)
        printer.textln("QUEUE TICKET")

        printer.set(font='a', width=1, height=1)
        printer.text("=" * 32 + "\n")

        # ===== SERVICE =====
        printer.set(align='left')
        printer.textln(f"Service:  {ticket.service_name}")

        # ===== QUEUE NUMBER =====
        printer.set(align='center', font='b', width=4, height=4)
        printer.textln(f"#{ticket.get_display_number()}")

        # ===== DATE & TIME =====
        printer.set(align='left', font='a', width=1, height=1)
        printer.textln(f"Date:     {ticket.ticket_date}")
        printer.textln(f"Time:     {local_time.strftime('%I:%M %p')}")

        printer.text("=" * 32 + "\n")

        # ===== FOOTER =====
        printer.set(align='center')
        printer.textln("Scan QR to check")
        printer.textln("your status\n")
        printer.textln("Thank you for waiting!")

        # ===== CUT =====
        printer.cut(mode='part')

        raw_bytes = printer.output
        human_readable = TicketPrinter._bytes_to_human_readable(raw_bytes)
        preview_html = TicketPrinter._generate_html_preview(ticket)

        return raw_bytes, human_readable, preview_html

    @staticmethod
    def _bytes_to_human_readable(data):
        """Convert ESC/POS bytes to human-readable text (debug)"""
        result = []
        i = 0

        while i < len(data):
            byte = data[i]

            if byte == 0x1B and i + 1 < len(data):  # ESC
                if data[i + 1] == 0x40:
                    result.append("[INIT]\n")
                    i += 1
            elif byte == 0x1D and i + 1 < len(data):  # GS
                if data[i + 1] == 0x56:
                    result.append("[CUT]\n")
                    i += 2
            elif byte == 0x0A:
                result.append("\n")
            elif 32 <= byte <= 126:
                result.append(chr(byte))

            i += 1

        return "".join(result)

    @staticmethod
    def _generate_html_preview(ticket):
        """Generate HTML preview for browser"""
        local_time = localtime(ticket.created_at)

        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
        }}
        .ticket {{
            width: 80mm;
            font-family: 'Courier New', monospace;
            border: 2px dashed #333;
            padding: 15px;
            margin: auto;
            background: white;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h2 style="text-align:center;">Ticket Preview</h2>
    <div class="ticket">
        <h2>QUEUE TICKET</h2>
        <hr>
        <p style="text-align:left;"><strong>Service:</strong> {ticket.service_name}</p>
        <p style="text-align:left;"><strong>Date:</strong> {ticket.ticket_date}</p>

        <h1 style="font-size:3em;">#{ticket.get_display_number()}</h1>

        <p style="text-align:left;"><strong>Time:</strong> {local_time.strftime('%I:%M %p')}</p>
        <hr>
        <p>Scan QR to check status</p>
        <p><strong>Thank you for waiting!</strong></p>
    </div>
</body>
</html>
"""

    @staticmethod
    def save_for_testing(ticket, raw_bytes, human_readable):
        """Save ESC/POS output files for testing"""
        test_dir = os.path.join(settings.BASE_DIR, 'test_prints')
        os.makedirs(test_dir, exist_ok=True)

        base_name = f"ticket_{ticket.queue_number:03d}"

        raw_path = os.path.join(test_dir, f"{base_name}.bin")
        with open(raw_path, 'wb') as f:
            f.write(raw_bytes)

        human_path = os.path.join(test_dir, f"{base_name}_readable.txt")
        with open(human_path, 'w', encoding='utf-8') as f:
            f.write(human_readable)

        hex_path = os.path.join(test_dir, f"{base_name}_hex.txt")
        with open(hex_path, 'w') as f:
            f.write(' '.join(f'{b:02X}' for b in raw_bytes))

        return {
            'raw_file': raw_path,
            'readable_file': human_path,
            'hex_file': hex_path
        }


class MockPrinter:
    """Mock printer for development (no physical printer required)"""

    @staticmethod
    def print_ticket(ticket, save_to_file=True):
        try:
            raw_bytes, human_readable, preview_html = (
                TicketPrinter.generate_escpos_commands(ticket)
            )

            result = {
                'success': True,
                'preview_html': preview_html,
                'length_bytes': len(raw_bytes),
            }

            if save_to_file:
                result['saved_files'] = TicketPrinter.save_for_testing(
                    ticket, raw_bytes, human_readable
                )

            return result

        except Error as e:
            return {
                'success': False,
                'error': str(e),
                'fallback_text': f"""
QUEUE TICKET
================
Service:  {ticket.service_name}
Date:     {ticket.ticket_date}
Number:   #{ticket.get_display_number()}
Time:     {localtime(ticket.created_at).strftime('%I:%M %p')}
================
"""
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"ESC/POS failed: {str(e)}",
                'fallback_text': f"""
QUEUE TICKET
================
Service:  {ticket.service_name}
Date:     {ticket.ticket_date}
Number:   #{ticket.get_display_number()}
================
"""
            }
