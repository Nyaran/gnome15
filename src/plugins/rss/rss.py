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
_ = g15locale.get_translation("rss", modfile = __file__).gettext

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GConf

from gnome15.util import g15convert
from gnome15.util import g15pythonlang
from gnome15.util import g15scheduler
from gnome15.util import g15uigconf
from gnome15.util import g15gconf
from gnome15.util import g15cairo
from gnome15.util import g15icontools
from gnome15 import g15theme
from gnome15 import g15driver
from gnome15 import g15desktop
import subprocess
import time
import os
import feedparser
import logging
logger = logging.getLogger(__name__)

# Plugin details - All of these must be provided
id = "rss"
name = _("RSS")
description = _("A simple RSS reader. Multiple feeds may be added, with a screen being \
allocated to each one once it has loaded.\n\n\
\
Warning: This plugin has a small memory leak. If you experience problems, \
try reducing the update interval time.")
author = "Brett Smith <tanktarta@blueyonder.co.uk>"
copyright = _("Copyright (C)2010 Brett Smith")
site = "http://www.russo79.com/gnome15"
has_preferences = True
needs_network = True
unsupported_models = [ g15driver.MODEL_G110, g15driver.MODEL_G11, g15driver.MODEL_G930, g15driver.MODEL_G35 ]
actions={ 
         g15driver.PREVIOUS_SELECTION : _("Previous news item"), 
         g15driver.NEXT_SELECTION : _("Next news items"),
         g15driver.NEXT_PAGE : _("Next page"),
         g15driver.PREVIOUS_PAGE : _("Previous page"),
         g15driver.SELECT : _("Open item in browser")
         }
 
def create(gconf_key, gconf_client, screen):
    return G15RSS(gconf_client, gconf_key, screen)

def show_preferences(parent, driver, gconf_client, gconf_key):
    G15RSSPreferences(parent, driver, gconf_client, gconf_key)

def changed(widget, key, gconf_client):
    gconf_client.set_bool(key, widget.get_active())
    
class G15RSSPreferences():
    
    def __init__(self, parent, driver, gconf_client, gconf_key):
        self._gconf_client = gconf_client
        self._gconf_key = gconf_key
        
        widget_tree = Gtk.Builder()
        widget_tree.add_from_file(os.path.join(os.path.dirname(__file__), "rss.ui"))
        
        # Feeds
        self.feed_model = widget_tree.get_object("FeedModel")
        self.reload_model()
        self.feed_list = widget_tree.get_object("FeedList")
        self.url_renderer = widget_tree.get_object("URLRenderer")
        
        # Optins
        self.update_adjustment = widget_tree.get_object("UpdateAdjustment")
        self.update_adjustment.set_value(g15gconf.get_int_or_default(self._gconf_client, "%s/update_time" % self._gconf_key, 60))
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/twenty_four_hour_times" % gconf_key, "TwentyFourHourTimes", True, widget_tree)
        
        # Connect to events
        self.update_adjustment.connect("value-changed", self.update_time_changed)
        self.url_renderer.connect("edited", self.url_edited)
        widget_tree.get_object("NewURL").connect("clicked", self.new_url)
        widget_tree.get_object("RemoveURL").connect("clicked", self.remove_url)
        
        # Display
        
        # Show dialog
        dialog = widget_tree.get_object("RSSDialog")
        dialog.set_transient_for(parent)
        
        ah = gconf_client.notify_add(gconf_key + "/urls", self.urls_changed);
        dialog.run()
        dialog.hide()
        gconf_client.notify_remove(ah);
        
    def update_time_changed(self, widget):
        self._gconf_client.set_int(self._gconf_key + "/update_time", int(widget.get_value()))
        
    def url_edited(self, widget, row_index, value):
        row = self.feed_model[row_index] 
        if value != "":
            urls = self._gconf_client.get_list(self._gconf_key + "/urls", GConf.VALUE_STRING)
            if row[0] in urls:
                urls.remove(row[0])
            urls.append(value)
            self._gconf_client.set_list(self._gconf_key + "/urls", GConf.VALUE_STRING, urls)
        else:
            self.feed_model.remove(self.feed_model.get_iter(row_index))
        
    def urls_changed(self, client, connection_id, entry, *args):
        self.reload_model()
        
    def reload_model(self):
        self.feed_model.clear()
        for url in self._gconf_client.get_list(self._gconf_key + "/urls", GConf.VALUE_STRING):
            self.feed_model.append([ url, True ])
        
    def new_url(self, widget):
        self.feed_model.append(["", True])
        self.feed_list.set_cursor_on_cell(str(len(self.feed_model) - 1), focus_column=self.feed_list.get_column(0), focus_cell=self.url_renderer, start_editing=True)
        self.feed_list.grab_focus()
        
    def remove_url(self, widget):        
        (model, path) = self.feed_list.get_selection().get_selected()
        url = model[path][0]
        urls = self._gconf_client.get_list(self._gconf_key + "/urls", GConf.VALUE_STRING)
        if url in urls:
            urls.remove(url)
            self._gconf_client.set_list(self._gconf_key + "/urls", GConf.VALUE_STRING, urls)   
        
class G15FeedsMenuItem(g15theme.MenuItem):
    def __init__(self, component_id, entry, gconf_client, gconf_key):
        g15theme.MenuItem.__init__(self, component_id)
        self.entry = entry
        self.gconf_client = gconf_client
        self.gconf_key = gconf_key
        if "icon" in self.entry:
            self.icon = self.entry["icon"]
        elif "image" in self.entry:
            img = self.entry["image"]
            if "url" in img:
                self.icon = img["url"]
            elif "link" in img:
                self.icon = img["link"]
        else:
            self.icon = None
        
    def on_configure(self):
        self.set_theme(g15theme.G15Theme(self.parent.get_theme().dir, "menu-entry"))
        
    def get_theme_properties(self):  
        
        use_twenty_four_hour = g15gconf.get_bool_or_default(self.gconf_client, "%s/twenty_four_hour_times" % self.gconf_key, True)
              
        element_properties = g15theme.MenuItem.get_theme_properties(self)
        element_properties["ent_title"] = self.entry.title
        element_properties["ent_link"] = self.entry.link
        if g15pythonlang.attr_exists(self.entry, "description"):
            element_properties["ent_description"] = self.entry.description
            
        if hasattr(self.entry, 'date_parsed'):
            dt = self.entry.date_parsed
        elif hasattr(self.entry, 'published_parsed'):
            logger.debug("Could not get date_parsed attribute. Trying published_parsed")
            dt = self.entry.published_parsed
        else:
            logger.debug("Could not get publish_parsed attribute. Using current time.")
            dt = time.localtime()
        
        element_properties["ent_locale_date_time"] = time.strftime("%x %X", dt)            
        element_properties["ent_locale_time"] = time.strftime("%X", dt)            
        element_properties["ent_locale_date"] = time.strftime("%x", dt)
        element_properties["ent_time_24"] = time.strftime("%H:%M", dt) 
        if use_twenty_four_hour:
            element_properties["ent_time"] = g15locale.format_time_24hour(time, self.gconf_client, False)
        else:             
            element_properties["ent_time"] = g15locale.format_time(time, self.gconf_client, False)
        element_properties["ent_full_time_24"] = time.strftime("%H:%M:%S", dt)
        if use_twenty_four_hour:
            element_properties["ent_full_time"] = g15locale.format_time_24hour(time, self.gconf_client, True)
        else:
            element_properties["ent_full_time"] = g15locale.format_time(time, self.gconf_client, True)
        element_properties["ent_time_12"] = time.strftime("%I:%M %p", dt) 
        element_properties["ent_full_time_12"] = time.strftime("%I:%M:%S %p", dt)
        element_properties["ent_short_date"] = time.strftime("%a %d %b", dt)
        element_properties["ent_full_date"] = time.strftime("%A %d %B", dt)
        element_properties["ent_month_year"] = time.strftime("%m/%y", dt)
                        
        return element_properties 
    
    def activate(self):
        g15desktop.browse(self.entry.link)
        return True
        
class G15FeedPage(g15theme.G15Page):
    
    def __init__(self, plugin, url):   
        
        self._gconf_client = plugin._gconf_client        
        self._gconf_key = plugin._gconf_key
        self._screen = plugin._screen
        self._icon_surface = None
        self._icon_embedded = None
        self._selected_icon_embedded = None
        self.url = url
        self.index = -1
        self._menu = g15theme.Menu("menu")
        self._menu.on_selected = self._on_selected
        g15theme.G15Page.__init__(self, "Feed " + str(plugin._page_serial), self._screen,
                                     thumbnail_painter=self._paint_thumbnail,
                                     theme=g15theme.G15Theme(self, "menu-screen"), 
                                     theme_properties_callback=self._get_theme_properties,
                                     originating_plugin = plugin)
        self.add_child(self._menu)
        self.add_child(g15theme.MenuScrollbar("viewScrollbar", self._menu))
        plugin._page_serial += 1
        self._reload() 
        self._screen.add_page(self)
        self._screen.redraw(self)
            
    """
    Private
    """
    def _on_selected(self):
        self._selected_icon_embedded = None
        if self._menu.selected is not None and self._menu.selected.icon is not None:
            try :
                icon_surface = g15cairo.load_surface_from_file(self._menu.selected.icon)
                self._selected_icon_embedded = g15icontools.get_embedded_image_url(icon_surface)
            except Exception as e:
                logger.warning("Failed to get icon %s", str(self._menu.selected.icon), exc_info = e)
        
    def _reload(self):
        self.feed = feedparser.parse(self.url)
        icon = None
        if "icon" in self.feed["feed"]:
            icon = self.feed["feed"]["icon"]
        elif "image" in self.feed["feed"]:
            img = self.feed["feed"]["image"]
            if "url" in img:
                icon = img["url"]
            elif "link" in img:
                icon = img["link"]
                
        title = self.feed["feed"]["title"] if "title" in self.feed["feed"] else self.url
        if icon is None and title.endswith("- Twitter Search"):
            title = title[:-16]
            icon = g15icontools.get_icon_path("gnome15")
        if icon is None:
            icon = g15icontools.get_icon_path(["application-rss+xml","gnome-mime-application-rss+xml"], self._screen.height)
            
        if icon == None:
            self._icon_surface = None
            self._icon_embedded = None
        else:
            try :
                icon_surface = g15cairo.load_surface_from_file(icon)
                self._icon_surface = icon_surface
                self._icon_embedded = g15icontools.get_embedded_image_url(icon_surface)
            except Exception as e:
                logger.warning("Failed to get icon %s", str(icon), exc_info = e)
                self._icon_surface = None
                self._icon_embedded = None
        self.set_title(title)
        self._subtitle = self.feed["feed"]["subtitle"] if "subtitle" in self.feed["feed"] else ""
        self._menu.remove_all_children()
        i = 0
        for entry in self.feed.entries:
            self._menu.add_child(G15FeedsMenuItem("feeditem-%d" % i, entry, self._gconf_client, self._gconf_key))
            i += 1
            
    def _get_theme_properties(self):
        properties = {}
        properties["title"] = self.title
        if self._selected_icon_embedded is not None:
            properties["icon"] = self._selected_icon_embedded
        else:
            properties["icon"] = self._icon_embedded
        properties["subtitle"] = self._subtitle
        properties["no_news"] = self._menu.get_child_count() == 0
        properties["alt_title"] = ""
        try:
            update_time = self.feed.updated
            if isinstance(self.feed.updated, str):
                update_time =  self.feed.updated_parsed
            
            properties["updated"] = "%s %s" % (time.strftime("%H:%M", update_time), time.strftime("%a %d %b", update_time))
        except AttributeError as ae:
            logger.debug("Could not get attribute", exc_info = ae)
            pass
        return properties 
        
    def _paint_thumbnail(self, canvas, allocated_size, horizontal):
        if self._icon_surface:
            return g15cairo.paint_thumbnail_image(allocated_size, self._icon_surface, canvas)
        
class G15RSS():
    
    def __init__(self, gconf_client, gconf_key, screen):
        self._screen = screen;
        self._gconf_key = gconf_key
        self._gconf_client = gconf_client
        self._page_serial = 1
        self._refresh_timer = None

    def activate(self):
        self._pages = {}       
        self._schedule_refresh() 
        self._update_time_changed_handle = self._gconf_client.notify_add(self._gconf_key + "/update_time", self._update_time_changed)
        self._urls_changed_handle = self._gconf_client.notify_add(self._gconf_key + "/urls", self._urls_changed)
        g15scheduler.schedule("LoadFeeds", 0, self._load_feeds)
    
    def deactivate(self):
        self._cancel_refresh()
        self._gconf_client.notify_remove(self._update_time_changed_handle);
        self._gconf_client.notify_remove(self._urls_changed_handle);
        for page in self._pages:
            self._screen.del_page(self._pages[page])
        self._pages = {}
    
    '''
    Private
    '''
        
    def _schedule_refresh(self):
        schedule_seconds = g15gconf.get_int_or_default(self._gconf_client, "%s/update_time" % self._gconf_key, 60) * 60.0
        self._refresh_timer = g15scheduler.schedule("FeedRefreshTimer", schedule_seconds, self._refresh)
        
    def _refresh(self):
        logger.info("Refreshing RSS feeds")
        for page_id in list(self._pages):
            page = self._pages[page_id]        
            page._reload()
            page.redraw()
        self._schedule_refresh()
        
    def destroy(self):
        pass 
    
    def _update_time_changed(self, client, connection_id, entry, *args):
        self._cancel_refresh()
        self._schedule_refresh()
        
    def _cancel_refresh(self):
        if self._refresh_timer:        
            self._refresh_timer.cancel()
    
    def _urls_changed(self, client, connection_id, entry, *args):
        self._load_feeds()
    
    def _load_feeds(self):
        feed_list = self._gconf_client.get_list(self._gconf_key + "/urls", GConf.VALUE_STRING)
        
        # Add new pages
        for url in feed_list:
            if not url in self._pages:
                self._pages[url] = G15FeedPage(self, url)
                
        # Remove pages that no longer exist
        to_remove = []
        for page_url in self._pages:
            page = self._pages[page_url]
            if not page.url in feed_list:
                self._screen.del_page(page)
                to_remove.append(page_url)
        for page in to_remove:
            del self._pages[page]
            
