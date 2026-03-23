# coding=utf-8
from __future__ import absolute_import

import re
import octoprint.plugin

class Proxy4artisanPlugin(octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin
):

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

    ##~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/main/bundledplugins/softwareupdate.html
        # for details.
        return {
            "Proxy4Artisan": {
                "displayName": "Proxy4artisan Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "coc815",
                "repo": "OctoPrint-Proxy4Artisan",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/coc815/OctoPrint-Proxy4Artisan/archive/{target_version}.zip",
            }
        }

    def proxy_recv(self, comm, line, *args, **kwargs):
        try:
            line_modified = line
            if "B0:" in line:
                line_modified = line.replace("B0:", "B:", 1)
                if line_modified != line:
                    self._logger.debug(
                        f"[Proxy4Artisan] Temperaturzeile angepasst: '{line}' -> '{line_modified}'"
                    )
    
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
                line_modified = f"X:{X} Y:{Y} Z:{Z} E:{E} A:{A} B:{B} Count {count}"
    
            # Filamentsensor ausgelöst
            if line == "filament_state: 0x0 -> 0x1":
                self._logger.info("[Proxy4Artisan] Filamentsensor ausgelöst – sende Pause-Befehl")
                self._printer.pause_print()
    
        except Exception as e:
            self._logger.exception(f"[Proxy4Artisan] Fehler bei Zeilenverarbeitung: {e}")
            
        finally:
            return line_modified
    
# Set the Python version your plugin is compatible with below. Recommended is Python 3 only for all new plugins.
# OctoPrint 1.4.0 - 1.7.x run under both Python 3 and the end-of-life Python 2.
# OctoPrint 1.8.0 onwards only supports Python 3.
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Proxy4artisanPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.received": __plugin_implementation__.proxy_recv
    }
