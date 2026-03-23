# coding=utf-8
from __future__ import absolute_import

import logging
import octoprint.plugin

"""
Proxy4Artisan: Virtueller USB-Proxy-Port für einen echten Drucker.
- Verbindet sich mit einem realen seriellen Port (z.B. /dev/ttyUSB0)
- Erzeugt einen virtuellen Port (PTY), den OctoPrint als Drucker-Port nutzen kann
- Leitet Daten bidirektional weiter
- Manipuliert Temperaturzeilen: 'B0:' -> 'B:' (nur erstes Vorkommen)
- Filament Runout triggert Pause
- Ausgabe von M114 wird umsortiert
-    von X: Y: Z: A: B: E: Count X: Y: Z: A: B:
-    zu  X: Y: Z: E: A: B: Count X: Y: Z: A: B:
"""

def proxy_recv(comm, line, *args, **kwargs):
    try:
        if "B0:" in line:
            line_modified = line.replace("B0:", "B:", 1)
            if line_modified != line:
                logging.getLogger("octoprint.plugin." + __name__).debug(
                    f"[Proxy4Artisan] Temperaturzeile angepasst: '{line}' -> '{line_modified}'"
                )
                line = line_modified

        # M114-Zeile erkennen
        m114 = re.match(
            r"X:(?P<X>\S+)\s+Y:(?P<Y>\S+)\s+Z:(?P<Z>\S+)\s+A:(?P<A>\S+)\s+B:(?P<B>\S+)\s+E:(?P<E>\S+)\s+Count\s+(?P<count>.*)",
            line
        )
        if m114:
            X = m114.group("X")
            Y = m114.group("Y")
            Z = m114.group("Z")
            A = m114.group("A")
            B = m114.group("B")
            E = m114.group("E")
            count = m114.group("count")
            # Neu zusammensetzen in der gewünschten Reihenfolge
            line = f"X:{X} Y:{Y} Z:{Z} E:{E} A:{A} B:{B} Count {count}"

        # Filamentsensor ausgelöst
        if line == "filament_state: 0x0 -> 0x1":
            logging.getLogger("octoprint.plugin." + __name__).info("[Proxy4Artisan] Filamentsensor ausgelöst – sende Pause-Befehl")
            line = "//action:pause"

    except Exception as e:
        logging.getLogger("octoprint.plugin." + __name__).exception(f"[Proxy4Artisan] Fehler bei Zeilenverarbeitung: {e}")
        
    finally:
        return line


# Set the Python version your plugin is compatible with below. Recommended is Python 3 only for all new plugins.
# OctoPrint 1.4.0 - 1.7.x run under both Python 3 and the end-of-life Python 2.
# OctoPrint 1.8.0 onwards only supports Python 3.
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3

def __plugin_load__():
    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
    __plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.received": proxy_recv
    }
