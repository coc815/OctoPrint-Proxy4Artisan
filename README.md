## OctoPrint-Proxy4Artisan

This plugin enables OctoPrint to handle Snapmaker Artisan

What the plugin does

- manipulates temperature responses, for OctoPrint to be able to show a bed temperature: 'B0:' -> 'B:' (just the first occurrence per line)
- Filament runout will pause the print
- Output of M114 command is reordered, for OctoPrint to correctly recognize position and set pause_position variable, to be safely used in OctoPrint's GCODE scripts
-    original order X: Y: Z: A: B: E: Count X: Y: Z: A: B:
-    new order  X: Y: Z: E: A: B: Count X: Y: Z: A: B:

What the plugin does not
- Unfortunately it will not enable Octoprint to differenciate the two bed zones of Snapmaker Artisan

## Disclaimer

Use the plugin on your own risk
I must not be held liable for any damage caused by the usage of this plugin

## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/main/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/coc815/OctoPrint-Proxy4Artisan/archive/main.zip

## Configuration

Extra config for pausing, resuming etc.

I defined some GCODE scripts in OctoPrint, which work fine for me. Please feel free to use for yourself

afterPrintCancelled

    ; retract filament, move Z slightly upwards
    G91
    G0 Z1
    M83
    G1 Z+5 E-5 F4500

    ; move to end position
    G90
    G0 X400 Y400 Z400
    M400

    ; disable motors
    M84

    ;disable all heaters
    {% snippet 'disable_hotends' %}
    {% snippet 'disable_bed' %}
    ;disable fan
    M106 S0

afterPrintPaused

    {% if pause_position.x is not none %}
    ; relative XYZE
    G91
    M83

    ; retract filament, move Z slightly upwards
    G1 Z+5 E-5 F4500

	; absolute XYZ
    G90

    ; move to a safe rest position, adjust as necessary
    G0 X0 Y0 Z400
    {% endif %}

beforePrintResumed

    {% if pause_position.x is not none %}

    M140 S{{ pause_temperature.b.target }}
    M104 T0 S{{ pause_temperature.0.target }}
    M104 T1 S{{ pause_temperature.1.target }}
    {% if pause_temperature.0.target > 0 %}M109 T0 R{{ pause_temperature.0.target }} C2{% endif %}
    {% if pause_temperature.1.target > 0 %}M109 T1 R{{ pause_temperature.1.target }} C2{% endif %}
    M190 R{{ pause_temperature.b.target }}

    ; relative extruder
    M83

    ; prime nozzle
    G1 E-5 F4500
    G1 E50 F500
    M400

    ;absolute XYZ
    G90

    ;move back to pause position XYZ
    G0 X{{ pause_position.x }} Y{{ pause_position.y }} F4500
    M400
    G0 Z{{ pause_position.z }} F4500
    M400

    ; relative extruder
    M83

	{% endif %}

