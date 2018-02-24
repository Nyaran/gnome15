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
_ = g15locale.get_translation("menu", modfile = __file__).gettext

from gnome15 import g15theme
from gnome15 import g15driver
from gnome15 import g15screen
from gnome15 import g15plugin
from gnome15.util.g15pythonlang import find
import sys
import cairo
import base64
from io import BytesIO
import logging
logger = logging.getLogger(__name__)

# Plugin details - All of these must be provided
id="menu"
name=_("Menu")
description=_("Allows selections of any currently active screen through a menu on the LCD.")
author="Brett Smith <tanktarta@blueyonder.co.uk>"
copyright=_("Copyright (C)2010 Brett Smith")
site="http://www.russo79.com/gnome15"
has_preferences=False
default_enabled=True
unsupported_models = [ g15driver.MODEL_G110, g15driver.MODEL_G11, g15driver.MODEL_G930, g15driver.MODEL_G35 ]
actions={ 
         g15driver.PREVIOUS_SELECTION : _("Previous item"), 
         g15driver.NEXT_SELECTION : _("Next item"),
         g15driver.NEXT_PAGE : _("Next page"),
         g15driver.PREVIOUS_PAGE : _("Previous page"),
         g15driver.SELECT : _("Show selected item"),
         g15driver.MENU : _("Show menu")
         }


def create(gconf_key, gconf_client, screen):
    return G15Menu(gconf_client, gconf_key, screen)

class MenuItem(g15theme.MenuItem):
    
    
    def __init__(self, item_page, plugin, id):
        g15theme.MenuItem.__init__(self, id)
        self._item_page = item_page
        self.thumbnail = None
        self.plugin = plugin
        
    def get_page(self):
        return self._item_page
        
    def activate(self):
        self.plugin.hide_menu()
        self.plugin.screen.raise_page(self._item_page)
        self.plugin.screen.resched_cycle()
        
    def get_theme_properties(self):        
        item_properties = g15theme.MenuItem.get_theme_properties(self)
        item_properties["item_name"] = self._item_page.title 
        item_properties["item_alt"] = ""
        item_properties["item_type"] = ""
        item_properties["item_icon"] = self.thumbnail
        return item_properties

class G15Menu(g15plugin.G15MenuPlugin):
    
    def __init__(self, gconf_client, gconf_key, screen):
        g15plugin.G15MenuPlugin.__init__(self, gconf_client, gconf_key, screen, [ "gnome-main-menu", "gnome-window-manager", "gnome-gmenu", "kmenuedit" ], id, name)
        self._show_on_activate = False
    
    def activate(self):
        self.delete_timer = None  
        g15plugin.G15MenuPlugin.activate(self)
        self.reload_theme()
        self.listener = MenuScreenChangeListener(self)
        self.screen.add_screen_change_listener(self.listener)
        self.screen.key_handler.action_listeners.append(self)
        
    def deactivate(self): 
        g15plugin.G15MenuPlugin.deactivate(self)
        self.screen.key_handler.action_listeners.remove(self)
        self.screen.remove_screen_change_listener(self.listener)
        
    def action_performed(self, binding):
        if self.page is not None:
            self._reset_delete_timer()
        if binding.action == g15driver.MENU:
            if self.page is not None:
                self.hide_menu()
                return True
            else:
                self.show_menu()
                self.page.set_priority(g15screen.PRI_HIGH)
                return True
                
    def hide_menu(self):
        g15plugin.G15MenuPlugin.hide_menu(self)   
                
    def show_menu(self):
        visible_page = self.screen.get_visible_page()
        g15plugin.G15MenuPlugin.show_menu(self)
        self._reset_delete_timer()
        if visible_page:
            item = find(lambda m: m._item_page == visible_page, self.menu.get_children())
            if item:
                self.menu.set_selected_item(item)

    def load_menu_items(self):
        items = []
        for page in self.screen.pages:
            if page != self.page and page.priority > g15screen.PRI_INVISIBLE:
                items.append(MenuItem(page, self, "menuitem-%s" % page.id ))
        items = sorted(items, key=lambda item: item._item_page.title)
        self.menu.set_children(items)
        if len(items) > 0:
            self.menu.selected = items[0]
        else:
            self.menu.selected = None               
        for item in items:
            self._load_item_icon(item)
        
    '''
    Private
    '''
    def _load_item_icon(self, item):
        if item._item_page.thumbnail_painter != None:
            img = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.screen.height, self.screen.height)
            thumb_canvas = cairo.Context(img)
            try :
                if item._item_page.thumbnail_painter(thumb_canvas, self.screen.height, True):
                    img_data = BytesIO()
                    img.write_to_png(img_data)
                    item.thumbnail = base64.b64encode(img_data.getvalue()).decode()                    
                    
            except Exception as e:
                logger.warning("Problem with painting thumbnail in %s",
                               item._item_page.id,
                               exc_info = e)
                    
    def _reset_delete_timer(self):
        if self.delete_timer:
            self.delete_timer.cancel()        
        self.delete_timer = self.screen.delete_after(10.0, self.page)
                    
    def _reload_menu(self):
        self.load_menu_items()
        self.screen.redraw(self.page)
        
class MenuScreenChangeListener(g15screen.ScreenChangeAdapter):
    def __init__(self, plugin):
        self.plugin = plugin
        
    def new_page(self, page):
        if self.plugin.page != None and page != self.plugin.page and page.priority > g15screen.PRI_INVISIBLE:
            items = self.plugin.menu.get_children()
            item = MenuItem(page, self.plugin, "menuitem-%s" % page.id )
            self.plugin._load_item_icon(item)
            items.append(item)
            items = sorted(items, key=lambda item: item._item_page.title)            
            self.plugin.menu.set_children(items)
            self.plugin.page.redraw()
        
    def title_changed(self, page, title):
        if self.plugin.page != None and page != self.plugin.page:
            self.plugin.page.redraw()
    
    def deleted_page(self, page):
        if self.plugin.page != None and page != self.plugin.page:
            self.plugin.menu.remove_child(self.plugin.menu.get_child_by_id("menuitem-%s" % page.id))
            self.plugin.page.redraw()
