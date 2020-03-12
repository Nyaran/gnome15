#  Gnome15 - Suite of tools for the Logitech G series keyboards and headsets
#  Copyright (C) 2010 Brett Smith <tanktarta@blueyonder.co.uk>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 
from gnome15 import g15locale
_ = g15locale.get_translation("screensaver", modfile = __file__).gettext

import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk

from gnome15 import g15screen
from gnome15 import g15driver
from gnome15.util import g15uigconf
from gnome15.util import g15gconf
from gnome15.util import g15icontools
from gnome15 import g15theme
from threading import Timer
import dbus
import logging
import os.path
logger = logging.getLogger(__name__)

# Plugin details - All of these must be provided
id="screensaver"
name=_("Screensaver")
description=_("Dim the keyboard and display a message (on models with an LCD screen) when the desktop screen saver activates.")
author="Brett Smith <tanktarta@blueyonder.co.uk>"
copyright=_("Copyright (C)2010 Brett Smith")
site="http://www.russo79.com/gnome15"
has_preferences=True
unsupported_models = [ g15driver.MODEL_G930, g15driver.MODEL_G35 ]


''' 
This plugin displays a high priority screen when the screensaver activates
'''

def create(gconf_key, gconf_client, screen):
    return G15ScreenSaver(gconf_key, gconf_client, screen)

def show_preferences(parent, driver, gconf_client, gconf_key):
    widget_tree = Gtk.Builder()
    widget_tree.add_from_file(os.path.join(os.path.dirname(__file__), "screensaver.ui"))
    
    dialog = widget_tree.get_object("ScreenSaverDialog")
    dialog.set_transient_for(parent)

    g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/dim_keyboard" % gconf_key,"DimKeyboardCheckbox", True, widget_tree)
    
    if driver.get_bpp() == 0:
        widget_tree.get_object("MessageFrame").hide()
        
    text_buffer = widget_tree.get_object("TextBuffer")
    text = gconf_client.get_string(gconf_key + "/message_text")
    if text == None:
        text = ""
    text_buffer.set_text(text)
    text_h = text_buffer.connect("changed", changed, gconf_key + "/message_text", gconf_client)
    
    dialog.run()
    dialog.hide()
    text_buffer.disconnect(text_h)
    
def changed(widget, key, gconf_client):
    if key.endswith("/dim_keyboard"):
        gconf_client.set_bool(key, widget.get_active())
    else:
        bounds = widget.get_bounds()
        gconf_client.set_string(key, widget.get_text(bounds[0],bounds[1]))
        pass
            
class G15ScreenSaver():
    
    def __init__(self, gconf_key, gconf_client, screen):
        self._screen = screen
        self._session_bus = None
        self._in_screensaver = False
        self._page = None
        self._gconf_client = gconf_client
        self._gconf_key = gconf_key
        self.dimmed = False

    def activate(self):      
        self._controls = []
        self._control_values  = []
        for control in self._screen.driver.get_controls():
            if control.hint & g15driver.HINT_DIMMABLE != 0 or  control.hint & g15driver.HINT_SHADEABLE != 0:
                self._controls.append(control)
        self._dbus_name = "org.gnome.ScreenSaver"
        self._dbus_interface = "org.gnome.ScreenSaver"
        self._in_screen_saver = False
                
        if self._session_bus == None:
            screen_saver = None
            try:
                self._session_bus = dbus.SessionBus()
            except Exception as e:
                self._session_bus = None
                logger.error("Error. Retrying in 10 seconds", exc_info = e)
                Timer(10, self.activate, ()).start()
                return
            
            # Paths vary from desktop to desktop
            screensavers = [
                            ("org.gnome.ScreenSaver", "org.gnome.ScreenSaver", "/"),
                            ("org.gnome.ScreenSaver", "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver"),
                            ("org.kde.screensaver", "org.freedesktop.ScreenSaver", "/ScreenSaver"),
                            ("org.mate.ScreenSaver", "org.mate.ScreenSaver", "/"),
                            ]
            
            for dbus_name, interface, path in screensavers:
                try :
                    logger.debug("Searching for screensaver. " \
                                 "dbus_name: %s, dbus_interface: %s, dbus_object: %s",
                                 dbus_name,
                                 interface,
                                 path)
                    screen_saver = dbus.Interface(self._session_bus.get_object(dbus_name, path), interface)
                    self._dbus_interface = interface
                    self._dbus_name = dbus_name
                    self._session_bus.add_signal_receiver(self._screensaver_changed_handler, dbus_interface = self._dbus_interface, signal_name = "ActiveChanged")
                    self._in_screensaver = screen_saver.GetActive()
                    break
                except Exception as e:
                    logger.debug("Could not find screensaver", exc_info = e)
                    screen_saver = None
                    pass
                
            if screen_saver is None:
                raise Exception("No supported DBUS screen saver interface found.")
            
        self._activated = True
        self._check_page()
    
    def deactivate(self):
        if self._in_screensaver:
            if self._gconf_client.get_bool(self._gconf_key + "/dim_keyboard"):
                self._light_keyboard()
        self._remove_page()
        self._activated = False
        
    def destroy(self):
        if self._session_bus:
            self._session_bus.remove_signal_receiver(self._screensaver_changed_handler, dbus_interface = self._dbus_interface, signal_name = "ActiveChanged")
        
    def handle_key(self, keys, state, post):
        # Sinks all keyboard events when the page is active
        return self._page is not None
        
    ''' Functions specific to plugin
    ''' 
    
    def _remove_page(self):
        if self._page != None:
            self._screen.del_page(self._page)
            self._page = None
            
    def _check_page(self):
        if self._in_screensaver:
            if self._screen.driver.get_bpp() != 0 and self._page == None:
                self._reload_theme()
                self._page = g15theme.G15Page(id, self._screen, priority = g15screen.PRI_EXCLUSIVE, \
                                              title = name, theme = self._theme,
                                              theme_properties_callback = self._get_theme_properties,
                                              originating_plugin = self)
                self._page.key_handlers.append(self)
                self._screen.add_page(self._page)
                self._screen.redraw(self._page)
            if not self.dimmed and g15gconf.get_bool_or_default(self._gconf_client, "%s/dim_keyboard" % self._gconf_key, True):
                self._dim_keyboard()
        else:
            if self._screen.driver.get_bpp() != 0:
                self._remove_page()
            if self.dimmed and g15gconf.get_bool_or_default(self._gconf_client,"%s/dim_keyboard" % self._gconf_key, True):
                self._light_keyboard()
        
    def _screensaver_changed_handler(self, value):
        if self._activated:
            self._in_screensaver = bool(value)
            self._check_page()
        
    def _dim_keyboard(self):
        self._acquisitions  = []
        for c in self._controls:
            acquisition = self._screen.driver.acquire_control(c, val = c.value)
            self._acquisitions.append(acquisition)
            acquisition.fade(100.0 if c.hint & g15driver.HINT_DIMMABLE != 0 else 0.5, 3.0)
        self.dimmed = True
    
    def _light_keyboard(self):
        for c in self._acquisitions:
            self._screen.driver.release_control(c)
        self.dimmed = False
            
    def _reload_theme(self):        
        text = self._gconf_client.get_string(self._gconf_key + "/message_text")
        variant = ""
        if text == None or text == "":
            variant = "nobody"
        self._theme = g15theme.G15Theme(self, variant)
        
    def _get_theme_properties(self):
        
        properties = {}
        properties["title"] = _("Workstation Locked")
        properties["body"] = self._gconf_client.get_string(self._gconf_key + "/message_text")
        properties["icon"] = g15icontools.get_icon_path("sleep", self._screen.height)
        
        return properties
