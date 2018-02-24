#!/usr/bin/env python
 
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
 
from gnome15 import g15theme
from gnome15 import g15screen
from gnome15 import g15driver
import os

# Plugin details - All of these must be provided
id="nm"
name="Network Manager"
description="Displays current status of your network connections."
author="Brett Smith <tanktarta@blueyonder.co.uk>"
copyright="Copyright (C)2010 Brett Smith"
site="http://www.gnome15.org/"
has_preferences=False
unsupported_models = [ g15driver.MODEL_G110 ]

def create(gconf_key, gconf_client, screen):
    return G15NM(gconf_client, gconf_key, screen)

class MenuItem():
    
    def __init__(self, page):
        self.page = page
        self.thumbnail = None

class G15NM():
    
    def __init__(self, gconf_client, gconf_key, screen):
        self.screen = screen
        self.gconf_client = gconf_client
        self.gconf_key = gconf_key
    
    def activate(self):
        self._reload_theme()
        self.page = self.screen.new_page(self.paint, id=id, priority = g15screen.PRI_EXCLUSIVE)
        self.screen.redraw(self.page)
    
    def deactivate(self):
        if self.page != None:
            self.screen.del_page(self.page)
            self.page = None
        
    def destroy(self):
        pass
    
    def paint(self, canvas):
        self.theme.draw(canvas, {})
        
    def _reload_theme(self):        
        self.theme = g15theme.G15Theme(os.path.join(os.path.dirname(__file__), "default"), self.screen)
