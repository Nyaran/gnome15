#  Gnome15 - Suite of tools for the Logitech G series keyboards and headsets
#  Copyright (C) 2012 Brett Smith <tanktarta@blueyonder.co.uk>
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
_ = g15locale.get_translation("profiles", modfile = __file__).gettext

from gnome15 import g15driver
from gnome15 import g15theme
from gnome15 import g15plugin
from gnome15 import g15devices
from gnome15 import g15actions
from gnome15.util import g15scheduler
from gnome15.util import g15pythonlang
from gnome15.util import g15icontools
import logging
import os
import re
logger = logging.getLogger(__name__)

ICONS = [ "display", "gnome-display-properties", "system-config-display", "video-display", "xfce4-display", "display-capplet" ]

# Custom actions
SELECT_PROFILE = "select-profile"

# Register the action with all supported models
g15devices.g15_action_keys[SELECT_PROFILE] = g15actions.ActionBinding(SELECT_PROFILE, [ g15driver.G_KEY_L1 ], g15driver.KEY_STATE_HELD)
g15devices.z10_action_keys[SELECT_PROFILE] = g15actions.ActionBinding(SELECT_PROFILE, [ g15driver.G_KEY_L1 ], g15driver.KEY_STATE_HELD)
g15devices.g19_action_keys[SELECT_PROFILE] = g15actions.ActionBinding(SELECT_PROFILE, [ g15driver.G_KEY_BACK ], g15driver.KEY_STATE_HELD)

# Plugin details - All of these must be provided
id="display"
name=_("Display Resolution")
description=_("Allows selection of the resolution for your display.")
author="Brett Smith <tanktarta@blueyonder.co.uk>"
copyright=_("Copyright (C)2012 Brett Smith")
site="http://www.russo79.com/gnome15"
has_preferences=False
default_enabled=True
unsupported_models = [ g15driver.MODEL_G110, g15driver.MODEL_G11, g15driver.MODEL_MX5500, g15driver.MODEL_G930, g15driver.MODEL_G35 ]
actions={ 
         g15driver.PREVIOUS_SELECTION : _("Previous item"), 
         g15driver.NEXT_SELECTION : _("Next item"),
         g15driver.NEXT_PAGE : _("Next page"),
         g15driver.PREVIOUS_PAGE : _("Previous page"),
         g15driver.SELECT : _("Select resolution")
         }

def create(gconf_key, gconf_client, screen):
    return G15XRandR(gconf_client, gconf_key, screen)

"""
Represents a resolution as a single item in a menu
"""
class ResolutionMenuItem(g15theme.MenuItem):    
    def __init__(self, index, size, refresh_rate, plugin, id, display):
        g15theme.MenuItem.__init__(self, id, group = False)
        self.current = False
        self.size = size
        self.index = index
        self.refresh_rate = refresh_rate
        self._plugin = plugin
        self.display = display
        
    def get_theme_properties(self):
        item_properties = g15theme.MenuItem.get_theme_properties(self)
        item_properties["item_name"] = "%s x %s @ %s" % ( self.size[0], self.size[1], self.refresh_rate) 
        item_properties["item_radio"] = True
        item_properties["item_radio_selected"] = self.current
        item_properties["item_alt"] = ""
        return item_properties
    
    def activate(self):
        os.system("xrandr --auto --output %s --mode %sx%s -r %s" % (self.display, self.size[0], self.size[1], self.refresh_rate ))
        self._plugin._reload_menu()
        

"""
XRANDR plugin class
"""
class G15XRandR(g15plugin.G15MenuPlugin):
    
    def __init__(self, gconf_client, gconf_key, screen):
        g15plugin.G15MenuPlugin.__init__(self, gconf_client, gconf_key, screen, ICONS, id, _("Display"))
    
    def activate(self):
        self._current_active = None
        self._last_items = -1
        g15plugin.G15MenuPlugin.activate(self)
        
    def deactivate(self): 
        g15plugin.G15MenuPlugin.deactivate(self)
        
    def load_menu_items(self):
        items = []
        display = "Default"
        i = 0
        status, output = self._get_status_output("xrandr")
        if status == 0:
            old_active = self._current_active
            new_active = []
            for line in output.split('\n'):
                arr = re.findall(r'\S+', line)
                if line.startswith("  "):
                    size = self._parse_size(arr[0])
                    for a in range(1, len(arr)):
                        word = arr[a]
                        refresh_string = ''.join( c for c in word if  c not in '*+' )
                        if len(refresh_string) > 0:
                            refresh_rate = float(refresh_string)
                            i += 1
                            item = ResolutionMenuItem(i, size, refresh_rate, self, "profile-%d-%s" % ( i, refresh_rate ), display )      
                            item.current = "*" in word
                            items.append(item)
                            if item.current:
                                new_active.append(item)
                elif "connected" in line:
                    i += 1
                    display = arr[0]
                    item = g15theme.MenuItem("display-%s" % i, True, arr[0], activatable=False, icon = g15icontools.get_icon_path(ICONS))
                    items.append(item)
                    
                    
            if len(items) != self._last_items or old_active is None or self._differs(new_active, old_active):
                self.menu.set_children(items)
                self._last_items = len(items)
                
                if new_active is not None:
                    self.menu.set_selected_item(new_active[0])
                    self._current_active = new_active
                
            self._schedule_check()
        else:
            raise Exception("Failed to query XRandR. Is the xrandr command installed, and do you have the XRandR extension enabled in your X configuration?")
        
    '''
    Private
    '''         
    def _differs(self, old_active, new_active):
        if ( old_active is None and new_active is not None ) or \
            ( old_active is not None and new_active is None ):
            return True
        if old_active is not None:
            it = iter(old_active)
            try:
                for i in new_active:
                    if i.id != next(it).id:
                        return True
            except StopIteration:
                return True
        
    def _schedule_check(self):
        if self.active == True:
            g15scheduler.schedule("CheckResolution", 10.0, self.load_menu_items)
        
    def _parse_size(self, line):
        arr = line.split("x")
        return int(arr[0].strip()), int(arr[1].strip())

    def _reload_menu(self):
        self.load_menu_items()
        self.screen.redraw(self.page)
            
    def _get_item_for_current_resolution(self):
        return g15pythonlang.find(lambda m: m.current, self.menu.get_children())

    def _get_status_output(self, cmd):
        # TODO something like this is used in sense.py as well, make it a utility
        pipe = os.popen('{ ' + cmd + '; } 2>/dev/null', 'r')
        text = pipe.read()
        sts = pipe.close()
        if sts is None: sts = 0
        if text[-1:] == '\n': text = text[:-1]
        return sts, text        
