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
_ = g15locale.get_translation("cairo-clock", modfile = __file__).gettext

import gi
gi.require_version('Rsvg', '2.0')
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import Rsvg as rsvg

from gnome15 import g15screen
from gnome15 import g15theme
from gnome15.util import g15uigconf
from gnome15.util import g15gconf
from gnome15.util import g15cairo
from gnome15.util import g15pythonlang
from gnome15 import g15driver
from gnome15 import g15globals
from gnome15 import g15text
from gnome15 import g15plugin
import datetime
from threading import Timer
import time
import os
import sys
import cairo
import locale
import xdg.BaseDirectory

# Plugin details - All of these must be provided
id="cairo-clock"
name=_("Cairo Clock")
description=_("Port of MacSlow's SVG clock to Gnome15. Standard cairo-clock \
themes may be used on a G19, however, for all other models \
you must use specially crafted themes (using GIF files instead of SVG). \
One default theme for low resolution screens is provided.")
author="Brett Smith <tanktarta@blueyonder.co.uk>"
copyright=_("Copyright (C)2010 Brett Smith")
site="http://www.russo79.com/gnome15"
has_preferences=True
default_enabled=True
unsupported_models = [ g15driver.MODEL_G110, g15driver.MODEL_G11, g15driver.MODEL_G930, g15driver.MODEL_G35 ]

def create(gconf_key, gconf_client, screen):
    return G15CairoClock(gconf_key, gconf_client, screen)

def changed(widget, key, gconf_client):
    gconf_client.set_bool(key, widget.get_active())
    
def show_preferences(parent, driver, gconf_client, gconf_key):
    G15CairoClockPreferences(parent, driver, gconf_key, gconf_client)
    
def get_theme_dir(model_name, gconf_key, gconf_client, theme_name):
    for dir in get_theme_dirs(model_name, gconf_key, gconf_client):
        full_path = "%s/%s" % ( dir, theme_name)
        if os.path.exists(full_path):
            return full_path
    
def get_theme_dirs(model_name, gconf_key, gconf_client):
    dirs = []
    model_dir = "g15"
    if model_name == g15driver.MODEL_G19:
        model_dir = "g19"
    elif model_name == g15driver.MODEL_MX5500:
        model_dir = "mx5500"
    dirs.append(os.path.join(os.path.dirname(__file__), model_dir))
    dirs.append(os.path.join(g15globals.user_data_dir, "cairo-clock", model_dir))
    theme_dir = gconf_client.get(gconf_key + "/theme_dir")
    if theme_dir != None:
        dirs.append(theme_dir.get_string())
    if model_name == g15driver.MODEL_G19:
        dirs.append(os.path.join(xdg.BaseDirectory.xdg_data_home, "cairo-clock"))
        dirs.append("/usr/share/cairo-clock/themes")
    return dirs

class G15CairoClockPreferences():
    
    def __init__(self, parent, driver, gconf_key, gconf_client):
        widget_tree = Gtk.Builder()
        widget_tree.add_from_file(os.path.join(os.path.dirname(__file__), "cairo-clock.ui"))
        
        dialog = widget_tree.get_object("ClockDialog")
        dialog.set_transient_for(parent)
        
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/display_seconds" % gconf_key, "DisplaySecondsCheckbox", True, widget_tree)
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/display_date" % gconf_key, "DisplayDateCheckbox", True, widget_tree)
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/twenty_four_hour" % gconf_key, "TwentyFourHourCheckbox", True, widget_tree)
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/display_digital_time" % gconf_key, "DisplayDigitalTimeCheckbox", True, widget_tree)
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/display_year" % gconf_key, "DisplayYearCheckbox", True, widget_tree)
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/second_sweep" % gconf_key, "SecondSweep", False, widget_tree)
        g15uigconf.configure_checkbox_from_gconf(gconf_client, "%s/twenty_four_hour_digital" % gconf_key, "TwentyFourHourDigitalCheckbox", True, widget_tree)
    
        e = gconf_client.get(gconf_key + "/theme")
        theme_name = "default"
        if e != None:
            theme_name = e.get_string()
        theme_model = widget_tree.get_object("ThemeModel")
        theme = widget_tree.get_object("ThemeCombo")
        
        def _theme_changed(widget, key):
            gconf_client.set_string(key, theme_model[widget.get_active()][0])
            
        theme.connect("changed", _theme_changed, gconf_key + "/theme")
        
        theme_dirs = get_theme_dirs(driver.get_model_name(), gconf_key, gconf_client)
        themes = {}
        for d in theme_dirs:
            if os.path.exists(d):
                for fname in os.listdir(d):
                    if os.path.isdir(os.path.join(d, fname)) and not fname in themes and ( driver.get_bpp() == 16 or fname == "default" ) :
                        theme_model.append([fname])
                        themes[fname] = True
                        if fname == theme_name:
                            theme.set_active(len(theme_model) - 1) 
        
        dialog.run()
        dialog.hide()
        
    
class G15CairoClock(g15plugin.G15RefreshingPlugin):
    
    def __init__(self, gconf_key, gconf_client, screen):
        g15plugin.G15RefreshingPlugin.__init__(self, gconf_client, gconf_key, screen, [ "cairo-clock", "clock", "gnome-panel-clock", "time", "xfce4-clock", "rclock" ], id, name)
        self.revert_timer = None
        self.display_date = False
        self.display_seconds = False        
        self.only_refresh_when_visible = False
    
    def activate(self): 
        self._load_surfaces()     
        self.panel_text = g15text.new_text(self.screen)
        self.time_text = g15text.new_text(self.screen)
        g15plugin.G15RefreshingPlugin.activate(self)
        self.watch(None, self.config_changed)
        self.do_refresh()
        
    def create_theme(self):
        # Painting is done using cairo and cairo-clock themes, no need for a theme
        return None
            
    def config_changed(self, client, connection_id, entry, args):
        self._load_surfaces()
        self.screen.set_priority(self.page, g15screen.PRI_HIGH, revert_after = 3.0)
        self.do_refresh()
        
    def refresh(self):
        pass
        
    def get_next_tick(self):
        now = datetime.datetime.now()
        
        if self.second_sweep:
            next_tick = now + datetime.timedelta(0, 0.1)
        elif self.display_seconds:
            next_tick = now + datetime.timedelta(0, 1.0)
            next_tick = datetime.datetime(next_tick.year,next_tick.month,next_tick.day,next_tick.hour, next_tick.minute, int(next_tick.second))
        else:
            next_tick = now + datetime.timedelta(0, 60.0)
            next_tick = datetime.datetime(next_tick.year,next_tick.month,next_tick.day,next_tick.hour, next_tick.minute, 0)
            
        return g15pythonlang.total_seconds( next_tick - now )
    
    
    '''
    Private
    '''
    
    def _load_surfaces(self):
        self.display_date = g15gconf.get_bool_or_default(self.gconf_client, "%s/display_date" % self.gconf_key, True)
        self.display_seconds = g15gconf.get_bool_or_default(self.gconf_client, "%s/display_seconds" % self.gconf_key, True)
        self.display_date = g15gconf.get_bool_or_default(self.gconf_client, "%s/display_date" % self.gconf_key, True)
        self.display_year = g15gconf.get_bool_or_default(self.gconf_client, "%s/display_year" % self.gconf_key, True)
        self.display_digital_time = g15gconf.get_bool_or_default(self.gconf_client, "%s/display_digital_time" % self.gconf_key, True)
        self.second_sweep = g15gconf.get_bool_or_default(self.gconf_client, "%s/second_sweep" % self.gconf_key, False)
        self.twenty_four_hour = g15gconf.get_bool_or_default(self.gconf_client, "%s/twenty_four_hour" % self.gconf_key, False)
        self.twenty_four_hour_digital = g15gconf.get_bool_or_default(self.gconf_client, "%s/twenty_four_hour_digital" % self.gconf_key, True)
        
        self.gconf_client.get_bool(self.gconf_key + "/twenty_four_hour")
        
        self.svg_size = None
        self.width = self.screen.width
        self.height = self.screen.height
        
        theme = self.gconf_client.get_string(self.gconf_key + "/theme")
        if theme == None:
            theme = "default"
            
        self.clock_theme_dir = get_theme_dir(self.screen.driver.get_model_name(), self.gconf_key, self.gconf_client, theme)
        if not self.clock_theme_dir:
            self.clock_theme_dir = get_theme_dir(self.screen.driver.get_model_name(), self.gconf_key, self.gconf_client, "default")
            if not self.clock_theme_dir:
                raise Exception("No themes could be found.")
        self.behind_hands = self._load_surface_list(["clock-drop-shadow", "clock-face", "clock-marks"])
        self.hour_surfaces = self._load_surface_list(["clock-hour-hand-shadow", "clock-hour-hand"])
        self.minute_surfaces = self._load_surface_list(["clock-minute-hand-shadow", "clock-minute-hand"])
        self.second_surfaces = self._load_surface_list(["clock-secondhand-shadow", "clock-second-hand"])
        self.above_hands = self._load_surface_list([ "clock-face-shadow", "clock-glass", "clock-frame" ])
            
    def _load_surface_list(self, names):
        list = []        
        for i in names:
            path = self.clock_theme_dir + "/" + i + ".svg"
            if os.path.exists(path):  
                svg = rsvg.Handle(path)
                try: 
                    if self.svg_size == None:
                        self.svg_size = svg.get_dimension_data()[2:4]
                        
                    svg_size = self.svg_size
                         
                    sx = self.width / svg_size[0]
                    sy = self.height / svg_size[1]
                    scale = min(sx, sy)                      
                    surface = cairo.SVGSurface(None, svg_size[0] * scale * 2,svg_size[1] * scale * 2)  
                    context = cairo.Context(surface)
                    self.screen.configure_canvas(context)
                    context.scale(scale, scale)
                    context.translate(svg_size[0], svg_size[1])
                    svg.render_cairo(context)
                    context.translate(-svg_size[0], -svg_size[1])
                    list.append(((svg_size[0] * scale, svg_size[1] * scale), surface))
                finally:
                    svg.close()
                
            path = self.clock_theme_dir + "/" + i + ".gif"
            if os.path.exists(path):
                img_surface = g15cairo.load_surface_from_file(path, self.height)
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_surface.get_width() * 2, img_surface.get_height() * 2)  
                context = cairo.Context(surface)
                self.screen.configure_canvas(context)
                context.translate(img_surface.get_width(), img_surface.get_height())
                context.set_source_surface(img_surface)
                context.paint()
                list.append(((img_surface.get_width(), img_surface.get_height()), surface))
        return list
    
    def _paint_thumbnail(self, canvas, allocated_size, horizontal):
        scale = allocated_size / self.height
        canvas.scale(scale, scale)
        self._do_paint(canvas, self.width, self.height, False)
        canvas.scale(1 / scale, 1 / scale)
        return allocated_size 
    
    def _paint_panel(self, canvas, allocated_size, horizontal):
        if not self.screen.is_visible(self.page):
            self.panel_text.set_canvas(canvas)
            
            # Don't display the date or seconds on mono displays, not enough room as it is
            if self.screen.driver.get_bpp() == 1:
                text = self._get_time_text(False)
                font_size = 8
                factor = 2
                font_name = g15globals.fixed_size_font_name
                x = 1
                gap = 1
            else:
                factor = 1 if horizontal else 2
                font_name = "Sans"
                if self.display_date:
                    text = "%s\n%s" % ( self._get_time_text(), self._get_date_text() ) 
                    font_size = allocated_size / 3
                else:
                    text = self._get_time_text()
                    font_size = allocated_size / 2
                x = 4
                gap = 8
                
            self.panel_text.set_attributes(text, align = Pango.Alignment.CENTER, font_desc = font_name, font_absolute_size = font_size * Pango.SCALE / factor)
            x, y, width, height = self.panel_text.measure()
            if horizontal: 
                if self.screen.driver.get_bpp() == 1:
                    y = 0
                else:
                    y = (allocated_size / 2) - height / 2
            else:      
                x = (allocated_size / 2) - width / 2
                y = 0
            self.panel_text.draw(x, y)
            if horizontal:
                return width + gap
            else:
                return height + 4
        
    def _paint(self, canvas, draw_date = True):
            
        width = float(self.screen.width)
        height = float(self.screen.height)
            
        self._do_paint(canvas, width, height, self.display_date, self.display_digital_time)
        
    def _get_time_text(self, display_seconds = None):
        if display_seconds == None:
            display_seconds = self.display_seconds
        if self.twenty_four_hour_digital:
            return g15locale.format_time_24hour(datetime.datetime.now(), self.gconf_client, display_seconds)
        else:
            return g15locale.format_time(datetime.datetime.now(), self.gconf_client, display_seconds)
    
    def _get_date_text(self):
        if self.display_year:
            return datetime.datetime.now().strftime(locale.nl_langinfo(locale.D_FMT))
        else:
            dformat = locale.nl_langinfo(locale.D_FMT)
            for s in [ "/%y", "/%Y", ".%y", ".%Y", ".%y", ".%Y" ]:
                dformat = dformat.replace(s, "")
            return datetime.datetime.now().strftime(dformat)    
        
    def _do_paint(self, canvas, width, height, draw_date = True, draw_time = True): 
        canvas.save()   
        self._do_paint_clock(canvas, width, height, draw_date and self.screen.driver.get_bpp() != 1, draw_time and self.screen.driver.get_bpp() != 1)
        canvas.restore()        
        self.time_text.set_canvas(canvas)
        
        if self.screen.driver.get_bpp() == 1:
            
            rgb = self.screen.driver.get_color_as_ratios(g15driver.HINT_FOREGROUND, ( 0, 0, 0 ))
            canvas.set_source_rgb(rgb[0],rgb[1],rgb[2])
                
            if draw_date:        
                date_text = self._get_date_text()
                self.time_text.set_attributes(pxwidth = 56, text = date_text, align = Pango.Alignment.CENTER, font_desc = "Fixed", font_absolute_size = 12 * Pango.SCALE)
                self.time_text.draw(0, 15)
                
            if draw_time:        
                time_text = self._get_time_text()                
                self.time_text.set_attributes(pxwidth = 56, text = time_text, align = Pango.Alignment.CENTER, font_desc = "Fixed", font_absolute_size = 12 * Pango.SCALE)
                self.time_text.draw(self.width - 56, 15)
        
    def _do_paint_clock(self, canvas, width, height, draw_date = True, draw_time = True):
            
        now = datetime.datetime.now()
        properties = { }
        
        time = self._get_time_text()
            
        clock_width = min(width, height)
        clock_height = min(width, height)
        
        drawing_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(clock_width), int(clock_height))
        drawing_context = cairo.Context(drawing_surface)
        self.screen.configure_canvas(drawing_context)
        
        # Below hands          
        for svg_size, surface in self.behind_hands:
            drawing_context.save()
            drawing_context.translate(-svg_size[0], -svg_size[1])
            drawing_context.set_source_surface(surface)
            drawing_context.paint()
            drawing_context.restore()
            
        # Date
        t_offset = 0
        if draw_date:
            drawing_context.save()
            date_text = self._get_date_text()
            drawing_context.select_font_face("Liberation Sans",
                        cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            drawing_context.set_font_size(27.0)
            x_bearing, y_bearing, text_width, text_height = drawing_context.text_extents(date_text)[:4]
            rgb = self.screen.driver.get_color_as_ratios(g15driver.HINT_FOREGROUND, ( 0, 0, 0 ))
            drawing_context.set_source_rgb(rgb[0],rgb[1],rgb[2])            
            tx = ( ( clock_width - text_width ) / 2 ) - x_bearing
            ty = clock_height * 0.665
            t_offset += text_height + 4
            drawing_context.move_to( tx, ty )

            drawing_context.show_text(date_text)
            drawing_context.restore()
            
        # Date
        if draw_time:
            drawing_context.save()
            time_text = self._get_time_text()
            drawing_context.select_font_face("Liberation Sans",
                        cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            drawing_context.set_font_size(27.0)
            x_bearing, y_bearing, text_width, text_height = drawing_context.text_extents(time_text)[:4]
            rgb = self.screen.driver.get_color_as_ratios(g15driver.HINT_FOREGROUND, ( 0, 0, 0 ))
            drawing_context.set_source_rgb(rgb[0],rgb[1],rgb[2])            
            tx = ( ( clock_width - text_width ) / 2 ) - x_bearing
            ty = ( clock_height * 0.665 ) + t_offset
            drawing_context.move_to( tx, ty )

            drawing_context.show_text(time_text)
            drawing_context.restore()
            
        # The hand
        if self.second_sweep:
            ms_deg = ( ( float(now.microsecond) / 10000.0 ) * ( 6.0 / 100.0 ) )
            s_deg = ( now.second * 6 ) + ms_deg
        else:
            s_deg = now.second * 6
        m_deg = now.minute * 6 + ( now.second * ( 6.0 / 60.0 ) )
        
        if self.twenty_four_hour:
            h_deg = float(now.hour) * 15.0 + (  float ( now.minute * 0.25 ) )
        else:
            h_deg = float( now.hour % 12 ) * 30.0 + (  float ( now.minute * 0.5 ) )
            
        self._draw_hand(drawing_context, self.hour_surfaces, clock_width, clock_height, h_deg)
        self._draw_hand(drawing_context, self.minute_surfaces, clock_width, clock_height, m_deg)
        if self.display_seconds:
            self._draw_hand(drawing_context, self.second_surfaces, clock_width, clock_height, s_deg)
            
        # Above hands          
        for svg_size, surface in self.above_hands:
            drawing_context.save()
            drawing_context.translate(-svg_size[0], -svg_size[1])
            drawing_context.set_source_surface(surface)
            drawing_context.paint()
            drawing_context.restore()
        
        # Paint to clock, centering it on the screen
        canvas.translate( int(( width - height)  / 2), 0)
        canvas.set_source_surface(drawing_surface)
        canvas.paint()
        
        
    def _draw_hand(self, drawing_context, hand_surfaces, width, height, deg):
        for svg_size, surface in hand_surfaces:
            drawing_context.save()
            drawing_context.translate(svg_size[0] / 2.0, svg_size[1] / 2.0)
            g15cairo.rotate(drawing_context, -90)
            g15cairo.rotate(drawing_context, deg)
            drawing_context.translate(-svg_size[0], -svg_size[1])
            drawing_context.set_source_surface(surface)
            drawing_context.paint()
            drawing_context.restore()
