#  Gnome15 - Suite of tools for the Logitech G series keyboards and headsets
#  Copyright (C) 2011 Brett Smith <tanktarta@blueyonder.co.uk>
#  Copyright (C) 2013 Brett Smith <tanktarta@blueyonder.co.uk>
#                     Nuno Araujo <nuno.araujo@russo79.com>
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
_ = g15locale.get_translation("lcdshot", modfile = __file__).gettext

import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
from gi.repository import GObject

from gnome15 import g15driver
from gnome15 import g15devices
from gnome15 import g15globals
from gnome15 import g15actions
import os.path
from gnome15.util import g15convert
from gnome15 import g15notify
from gnome15.util import g15uigconf
from gnome15.util import g15gconf
from gnome15.util import g15os
from gnome15.util import g15cairo
import subprocess
import shutil
from threading import Thread
 
# Logging
import logging
logger = logging.getLogger(__name__)

# Custom actions
SCREENSHOT = "screenshot"

# Register the action with all supported models
g15devices.g15_action_keys[SCREENSHOT] = g15actions.ActionBinding(SCREENSHOT, [ g15driver.G_KEY_MR ], g15driver.KEY_STATE_HELD)
g15devices.g19_action_keys[SCREENSHOT] = g15actions.ActionBinding(SCREENSHOT, [ g15driver.G_KEY_MR ], g15driver.KEY_STATE_HELD)
 
# Plugin details - All of these must be provided
id="lcdshot"
name=_("LCD Screenshot")
description=_("Takes either a still screenshot or a video of the LCD\n\
and places it in the configured directory.")
author="Brett Smith <tanktarta@blueyonder.co.uk>"
copyright=_("Copyright (C)2010 Brett Smith")
site="http://www.russo79.com/gnome15"
has_preferences=True
unsupported_models = [ g15driver.MODEL_G110, g15driver.MODEL_G11, g15driver.MODEL_MX5500, g15driver.MODEL_G930, g15driver.MODEL_G35, g15driver.MODEL_Z10 ]
actions={ 
         SCREENSHOT : "Take LCD screenshot"
         }


''' 
This simple plugin takes a screenshot of the LCD
'''

def create(gconf_key, gconf_client, screen):
    return G15LCDShot(screen, gconf_client, gconf_key)

def show_preferences(parent, driver, gconf_client, gconf_key):
    LCDShotPreferences(parent, driver, gconf_client, gconf_key)
    
class LCDShotPreferences():
    def __init__(self, parent, driver, gconf_client, gconf_key):
        self.gconf_client = gconf_client
        self.gconf_key = gconf_key
        widget_tree = Gtk.Builder()
        widget_tree.add_from_file(os.path.join(os.path.dirname(__file__), "lcdshot.ui"))
        dialog = widget_tree.get_object("LCDShotDialog")
        dialog.set_transient_for(parent)        
        chooser = Gtk.FileChooserDialog("Open..",
                               None,
                               Gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                               (Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
                                Gtk.STOCK_OPEN, Gtk.RESPONSE_OK))
        chooser.set_default_response(Gtk.RESPONSE_OK)
        chooser_button = widget_tree.get_object("FileChooserButton")        
        chooser_button.dialog = chooser 
        chooser_button.connect("file-set", self._file_set)
        chooser_button.connect("file-activated", self._file_activated)
        chooser_button.connect("current-folder-changed", self._file_activated)
        bg_img = g15gconf.get_string_or_default(self.gconf_client, "%s/folder" % self.gconf_key, os.path.expanduser("~/Desktop"))
        chooser_button.set_current_folder(bg_img)

        # Reset the value of the mode setting to 'still' if mencoder is not installed
        mencoder_is_installed = g15os.is_program_in_path('mencoder')
        if not mencoder_is_installed:
            gconf_client.set_string("%s/mode" % self.gconf_key, "still")

        # Initialize the mode combobox content
        modes = widget_tree.get_object("ModeModel")
        modes.clear()
        modes.append(('still','Still', True))
        modes.append(('video','Video', mencoder_is_installed))

        # Display a warning message to the user if mencoder is not installed
        warning = widget_tree.get_object("NoVideoMessage")
        warning.set_visible(not mencoder_is_installed)

        g15uigconf.configure_combo_from_gconf(self.gconf_client, "%s/mode" % self.gconf_key, "Mode", "still", widget_tree)
        mode = widget_tree.get_object("Mode")
        mode.connect("changed", self._mode_changed)

        g15uigconf.configure_spinner_from_gconf(self.gconf_client, "%s/fps" % gconf_key, "FPS", 10, widget_tree, False)
        self._spinner = widget_tree.get_object("FPS")
        self._mode_changed(mode)

        dialog.run()
        dialog.hide()
                    
    def _mode_changed(self, widget):
        self._spinner.set_sensitive(widget.get_active() == 1)
        
    def _file_set(self, widget):
        self.gconf_client.set_string(self.gconf_key + "/folder", widget.get_filename())  
        
    def _file_activated(self, widget):
        self.gconf_client.set_string(self.gconf_key + "/folder", widget.get_filename())
        
            
class G15LCDShot():
    
    def __init__(self, screen, gconf_client, gconf_key):
        self._screen = screen
        self._gconf_client = gconf_client
        self._gconf_key = gconf_key
        self._recording = False

    def activate(self):
        self._screen.key_handler.action_listeners.append(self) 
    
    def deactivate(self):
        self._screen.key_handler.action_listeners.remove(self)
        
    def destroy(self):
        pass
    
    def action_performed(self, binding):
        # TODO better key
        if binding.action == SCREENSHOT:
            mode = g15gconf.get_string_or_default(self._gconf_client, "%s/mode" % self._gconf_key, "still")
            if mode == "still":
                return self._take_still()
            else:
                if self._recording:
                    self._stop_recording()
                else:
                    self._start_recording()
                    
    def _encode(self):
        cmd = ["mencoder", "-really-quiet", "mf://%s.tmp/*.jpeg" % self._record_to, "-mf", \
                         "w=%d:h=%d:fps=%d:type=jpg" % (self._screen.device.lcd_size[0],self._screen.device.lcd_size[1],self._record_fps), "-ovc", "lavc", \
                         "-lavcopts", "vcodec=mpeg4", "-oac", "copy", "-o", self._record_to]
        try:
            ret = subprocess.call(cmd)
            if ret == 0:
                g15notify.notify(_("LCD Screenshot"), _("Video encoding complete. Result at %s" % self._record_to), "dialog-info", timeout = 0)
                shutil.rmtree("%s.tmp" % self._record_to, True)
            else:
                logger.error("Video encoding failed with status %d", ret)
                g15notify.notify(_("LCD Screenshot"), _("Video encoding failed."), "dialog-error", timeout = 0)
        except Exception as e:
                logger.error("Video encoding failed.", exc_info = e)
                g15notify.notify(_("LCD Screenshot"), _("Video encoding failed. Do you have mencoder installed?"), "dialog-error", timeout = 0)
                    
    def _stop_recording(self):
        self._recording = False
        g15notify.notify(_("LCD Screenshot"), _("Video recording stopped. Now encoding"), "dialog-info", timeout = 0)
        t = Thread(target = self._encode);
        t.setName("LCDScreenshotEncode")
        t.start()
                    
    def _start_recording(self):
        self._record_fps = g15gconf.get_int_or_default(self._gconf_client, "%s/fps" % self._gconf_key, 10)
        path = self._find_next_free_filename("avi", _("Gnome15_Video"))
        g15notify.notify(_("LCD Screenshot"), _("Started recording video"), "dialog-info")
        g15os.mkdir_p("%s.tmp" % path)
        self._frame_no = 1
        self._recording = True
        self._record_to = path
        self._frame()
        
    def _frame(self):
        if self._recording:
            try:
                self._screen.draw_lock.acquire()
                try:
                    path = os.path.join("%s.tmp" % self._record_to, "%012d.jpeg" % self._frame_no)
                    pixbuf = g15cairo.surface_to_pixbuf(self._screen.old_surface)
                finally:
                    self._screen.draw_lock.release()
                    
                pixbuf.save(path, "jpeg", {"quality":"100"})
                self._frame_no += 1
            except Exception as e:
                logger.error("Failed to save screenshot.", exc_info = e)
                self._screen.error_on_keyboard_display(_("Failed to save screenshot to %s. %s") % (dir, str(e)))
                self._recording = False
            
            self._recording_timer = GObject.timeout_add(1000 / self._record_fps, self._frame)
            
    def _find_next_free_filename(self, ext, title):
        dir_path = g15gconf.get_string_or_default(self._gconf_client, "%s/folder" % \
                    self._gconf_key, os.path.expanduser("~/Desktop"))
        for i in range(1, 9999):
            path = "%s/%s-%s-%d.%s" % ( dir_path, \
                                        g15globals.name, title, i, ext )
            if not os.path.exists(path):
                return path
        raise Exception("Too many screenshots/videos in destination directory")
            
    def _take_still(self):
        if self._screen.old_surface:
            self._screen.draw_lock.acquire()
            try:
                path = self._find_next_free_filename("png", self._screen.get_visible_page().title)
                self._screen.old_surface.write_to_png(path)
                logger.info("Written to screenshot to %s", path)
                g15notify.notify(_("LCD Screenshot"), _("Screenshot saved to %s") % path, "dialog-info", timeout = 0)
                return True
            except Exception as e:
                logger.error("Failed to save screenshot.", exc_info = e)
                self._screen.error_on_keyboard_display(_("Failed to save screenshot to %s. %s") % (dir, str(e)))
            finally:
                self._screen.draw_lock.release()
                
            return True
        
