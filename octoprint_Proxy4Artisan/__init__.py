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
    Proxy4Artisan: 
    - manipulates temperature responses, for OctoPrint to be able to show a bed temperature: 'B0:' -> 'B:' (just the first occurrence per line)
    - swaps position of occurances of T0 temperatures in temperature responses, because otherwise temperature shown in octoprint may get faulty 
    - Filament runout will pause the print and show a notification in optoprint 
    - Output of M114 command is reordered, for OctoPrint to correctly recognize position and set pause_position variable, to be safely used in OctoPrint's GCODE scripts
    -    original order X: Y: Z: A: B: E: Count X: Y: Z: A: B:
    -    new order      X: Y: Z: E: A: B: Count X: Y: Z: A: B:
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
            
            # replace B0 with B in temperature report
            if "B0:" in line:
                line_modified = line.replace("B0:", "B:", 1)

            # swaps position of T0 occurances in temperature report
            # original order leads to erroneous display in temperature graph in some situations
            matches = re.findall(r"(T0:\s*\d+\.\d+\s*/\s*\d+\.\d+)", line_modified)
            if len(matches) >= 2:
                first = matches[0]
                second = matches[1]
                line_modified = line_modified.replace(first, "__TEMP_SWAP_1__", 1)
                line_modified = line_modified.replace(second, first, 1)
                line_modified = line_modified.replace("__TEMP_SWAP_1__", second, 1)
            
            # handle output from M114 command
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
                # reorder
                line_modified = f"X:{X} Y:{Y} Z:{Z} E:{E} A:{A} B:{B} Count {count}"
    
            # Filament sensor triggert
            if (("filament_state: 0x0 -> 0x1" in line)
                    or ("filament_state: 0x2 -> 0x3" in line)):
                self._logger.info("[Proxy4Artisan] filament sensor triggered for extruder 0 –> pause print")
                self._printer.pause_print()
                self._printer.commands(["M118 A1 action:notification Extruder 0: Filament runout"])
                        
            if (("filament_state: 0x0 -> 0x2" in line)
                    or ("filament_state: 0x1 -> 0x3" in line)):
                self._logger.info("[Proxy4Artisan] filament sensor triggered for extruder 1 –> pause print")
                self._printer.pause_print()
                self._printer.commands(["M118 A1 action:notification Extruder 1: Filament runout"])
    
        except Exception as e:
            self._logger.exception(f"[Proxy4Artisan] Error in output handling: {e}")
            
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
