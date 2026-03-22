# coding=utf-8
from __future__ import absolute_import

import os
import pty
import threading
import serial
import time
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

    def __init__(self):
        self._running = False
        self._real_serial = None
        self._pty_fd = None
        self._virtual_port = None

    # -------------------------------------------------------------------------
    # OctoPrint Plugin Lifecycle
    # -------------------------------------------------------------------------

    def on_startup(self, host, port):
        real_port = self._settings.get(["real_port"])
        baudrate = self._settings.get_int(["baudrate"])

        if not real_port:
            self._logger.error("[Proxy4Artisan] Kein realer Port konfiguriert (Einstellung 'real_port').")
            return

        try:
            self._logger.info(f"[Proxy4Artisan] Verbinde mit echtem Drucker: {real_port} @ {baudrate} Baud")
            self._real_serial = serial.Serial(real_port, baudrate, timeout=0)
        except Exception as e:
            self._logger.exception(f"[Proxy4Artisan] Konnte realen Port nicht öffnen: {e}")
            return

        # Virtuellen Port (PTY) erzeugen
        master_fd, slave_fd = pty.openpty()
        self._virtual_port = os.ttyname(slave_fd)
        self._pty_fd = os.fdopen(master_fd, "rb+", buffering=0)

        self._logger.info(f"[Proxy4Artisan] Virtueller Port erstellt: {self._virtual_port}")

        # Threads starten
        self._running = True
        threading.Thread(target=self._pty_to_real_loop, daemon=True).start()
        threading.Thread(target=self._real_to_pty_loop, daemon=True).start()

    def on_shutdown(self):
        self._running = False
        try:
            if self._real_serial is not None and self._real_serial.is_open:
                self._real_serial.close()
        except Exception:
            pass

        try:
            if self._pty_fd is not None:
                self._pty_fd.close()
        except Exception:
            pass

        self._logger.info("[Proxy4Artisan] Plugin heruntergefahren.")


    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            "real_port": "/dev/ttyUSB0",
            "baudrate": 115200,
        }

    def get_template_configs(self):
        return [
            dict(
                type="settings",
                name="Proxy4Artisan",
                custom_bindings=False
            )
        ]

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/Proxy4Artisan.js"],
            "css": ["css/Proxy4Artisan.css"],
            "less": ["less/Proxy4Artisan.less"]
        }

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

    # -------------------------------------------------------------------------
    # Serial Port Integration
    # -------------------------------------------------------------------------

    def get_additional_serial_ports(self, *args, **kwargs):
        if self._virtual_port:
            return [(self._virtual_port, "Proxy4Artisan Virtueller Proxy-Port")]
        return []

    # -------------------------------------------------------------------------
    # Proxy-Loops
    # -------------------------------------------------------------------------

    def _pty_to_real_loop(self):
        self._logger.info("[Proxy4Artisan] Starte PTY -> Real Loop")
        try:
            while self._running and self._pty_fd and self._real_serial:
                try:
                    data = self._pty_fd.read(1)
                    if data:
                        self._real_serial.write(data)
                except Exception as e:
                    self._logger.exception(f"[Proxy4Artisan] Fehler im PTY->Real Loop: {e}")
                    time.sleep(0.1)
        finally:
            self._logger.info("[Proxy4Artisan] PTY -> Real Loop beendet")


    def _real_to_pty_loop(self):
        self._logger.info("[Proxy4Artisan] Starte Real -> PTY Loop")
        buffer = b""
        try:
            while self._running and self._pty_fd and self._real_serial:
                try:
                    data = self._real_serial.read(1)
                    if not data:
                        time.sleep(0.01)
                        continue

                    buffer += data

                    if data == b"\n":
                        try:
                            line = buffer.decode(errors="ignore").rstrip("\r\n")

                            if "B0:" in line:
                                line_modified = line.replace("B0:", "B:", 1)
                                if line_modified != line:
                                    self._logger.debug(
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

                            out = (line + "\n").encode()
                            self._pty_fd.write(out)

                            # Filamentsensor ausgelöst
                            if line == "filament_state: 0x0 -> 0x1":
                                self._logger.info("[Proxy4Artisan] Filamentsensor ausgelöst – sende Pause-Befehl")
                                self._pty_fd.write(b"//action:pause\n")

                        except Exception as e:
                            self._logger.exception(f"[Proxy4Artisan] Fehler bei Zeilenverarbeitung: {e}")

                        buffer = b""
                except Exception as e:
                    self._logger.exception(f"[Proxy4Artisan] Fehler im Real->PTY Loop: {e}")
                    time.sleep(0.1)
        finally:
            self._logger.info("[Proxy4Artisan] Real -> PTY Loop beendet")


# Set the Python version your plugin is compatible with below. Recommended is Python 3 only for all new plugins.
# OctoPrint 1.4.0 - 1.7.x run under both Python 3 and the end-of-life Python 2.
# OctoPrint 1.8.0 onwards only supports Python 3.
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Proxy4artisanPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
