#        +-----------------------------------------------------------------------------+
#        | GPL                                                                         |
#        +-----------------------------------------------------------------------------+
#        | Copyright (c) Brett Smith <tanktarta@blueyonder.co.uk>                      |
#        |                                                                             |
#        | This program is free software; you can redistribute it and/or               |
#        | modify it under the terms of the GNU General Public License                 |
#        | as published by the Free Software Foundation; either version 2              |
#        | of the License, or (at your option) any later version.                      |
#        |                                                                             |
#        | This program is distributed in the hope that it will be useful,             |
#        | but WITHOUT ANY WARRANTY; without even the implied warranty of              |
#        | MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               |
#        | GNU General Public License for more details.                                |
#        |                                                                             |
#        | You should have received a copy of the GNU General Public License           |
#        | along with this program; if not, write to the Free Software                 |
#        | Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA. |
#        +-----------------------------------------------------------------------------+

"""
This module contains the classes required for accessing macro details, as
well as the functions to load and save new profiles. 

A number of utility functions are also supplied to do things such as 
getting the default or active profile.
"""

import gconf
import time
import g15util
import g15devices
import g15uinput
import ConfigParser
import codecs
import os.path
import errno
import pyinotify
import logging
import uinput
import re
import copy
import zipfile
from cStringIO import StringIO
 
logger = logging.getLogger("macros")
active_profile = None
conf_client = gconf.client_get_default()
    
'''
Watch for changes in macro configuration directory.
Observers can add a callback function to profile_listeners
to be informed when macro profiles change
'''
profile_listeners = []

wm = pyinotify.WatchManager()
mask = pyinotify.IN_DELETE | pyinotify.IN_MODIFY | pyinotify.IN_CREATE | pyinotify.IN_ATTRIB  # watched events

# Create macro profiles directory
conf_dir = os.path.expanduser("~/.config/gnome15/macro_profiles")
g15util.mkdir_p(conf_dir)

class EventHandler(pyinotify.ProcessEvent):
    """
    Event handle the listens for the inotify events and informs all callbacks
    that are registered in the profile_listeners variable
    """
    
    def _get_profile_ids(self, event):
        path = os.path.basename(event.pathname)
        device_uid = os.path.basename(os.path.dirname(event.pathname))
        if path.endswith(".macros") and not path.startswith("."):
            id_no = path.split(".")[0]
            if id_no.isdigit():
                return ( int(id_no), device_uid )
    
    def _notify(self, event):
        ids = self._get_profile_ids(event)
        if ids:
            for profile_listener in profile_listeners:
                profile_listener(ids[0], ids[1])
        
    def process_IN_MODIFY(self, event):
        self._notify(event)
        
    def process_IN_CREATE(self, event):
        self._notify(event)
        
    def process_IN_ATTRIB(self, event):
        self._notify(event)

    def process_IN_DELETE(self, event):
        self._notify(event)

notifier = pyinotify.ThreadedNotifier(wm, EventHandler())
notifier.name = "PyInotify"
notifier.setDaemon(True)
notifier.start()
wdd = wm.add_watch(conf_dir, mask, rec=True)


'''
Macro types. 
'''

MACRO_COMMAND="command"
MACRO_SIMPLE="simple"
MACRO_SCRIPT="script"
MACRO_MOUSE=g15uinput.MOUSE
MACRO_JOYSTICK=g15uinput.JOYSTICK
MACRO_DIGITAL_JOYSTICK=g15uinput.DIGITAL_JOYSTICK
MACRO_KEYBOARD=g15uinput.KEYBOARD
MACRO_ACTION="action"

'''
Repeat modes
'''
REPEAT_TOGGLE="toggle"
NO_REPEAT="none"
REPEAT_WHILE_HELD="held"

"""
Defaults
"""
DEFAULT_REPEAT_DELAY = -1.0

def get_profiles(device):
    '''
    Get list of all configured macro profiles for the specified device.
    
    Keyword arguments:
    device        -- device associated with profiles
    '''
    profiles = []
    for profile in os.listdir(get_profile_dir(device)):
        if not profile.startswith(".") and profile.endswith(".macros"):
            id = profile.split(".")[0]
            if id.isdigit():
                profiles.append(G15Profile(device, int(id)))
    return profiles

def create_default(device):
    """
    Create the default profile for the specified device.
    
    Keyword arguments:
    device        -- device associated with default profile
    """
    if not get_profile(device, 0):
        logger.info("No default macro profile. Creating one")
        default_profile = G15Profile(device, id = 0)
        default_profile.name = "Default"
        default_profile.device = device
        default_profile.activate_on_focus = True
        create_profile(default_profile)

def create_profile(profile):
    """
    Assign a profile object an ID, and save it to disk
    
    Keyword arguments:
    profile        --    profile to save
    """
    if profile.id == -1:
        profile.id = int(time.time())
    logger.info("Creating profile %d, %s" % ( profile.id, profile.name ))
    profile.save()
    
def get_profile(device, profile_id):
    """
    Get a profile given the device it is associated with and it's ID. The
    profile will be fully loaded on return. The object returned will be a 
    new instance.
    
    Keyword arguments:
    device        -- device associated with profile
    profile_id    -- ID of profile to load
    """
    path = "%s/%s/%d.macros" % ( conf_dir, device.uid, profile_id )
    if os.path.exists(path):
        return G15Profile(device, profile_id);

def get_active_profile(device):
    """
    Get the currently active profile for the specified device. This will
    be retrieved from the configuration backend.
    
    Keyword arguments:
    device        -- device associated with profile
    """
    val= conf_client.get("/apps/gnome15/%s/active_profile" % device.uid)
    if val != None:
        return get_profile(device, val.get_int())
    else:
        return get_default_profile(device)
      
def get_default_profile(device):
    """
    Get the default profile for the specified device. 
    
    Keyword arguments:
    device        -- device associated with default profile
    """
    return get_profile(device, 0)

def get_keys_from_key(key_list_key):
    """
    Utility function to convert the string format of the list of keys used
    in profile storage into a list of key codes as defined in g15driver 
    
    Keyword arguments:
    key_list_key        -- string of key sequence required to activate macro
    """
    return key_list_key.split("_")

def get_keys_key(keys):
    """
    Utility function function to convert the list of key codes as defined
    in g15driver into the key list string used in profile storage.
    
    Keyword arguments:
    keys        -- list of key codes to convert to string
    """
    return "_".join(keys)

def get_profile_dir(device):
    """
    Get the directory profiles for a particular device are stored.
    
    Keyword arguments:
    device        -- device
    """
    return "%s/%s" % (conf_dir, device.uid)

    
def is_uinput_type(macro_type):
    """
    Get if the macro type is a uinput mapping type
    
    Keyword arguments:
    macro_type    --    macro type
    """
    return macro_type in [ MACRO_MOUSE, \
                          MACRO_KEYBOARD, \
                          MACRO_JOYSTICK, \
                          MACRO_DIGITAL_JOYSTICK ]

class G15Macro:
    """
    Represents a single macro in a profile. A macro defines how it's used
    using the 'type', which may be one of MACRO_COMMAND, MACRO_SIMPLE,
    MACRO_SCRIPT, MACRO_MOUSE, MACRO_JOYSTICK, MACRO_DIGITAL_JOYSTICK,
    MACRO_KEYBOARD or MACRO_ACTION
    """
    def __init__(self, profile, memory, key_list_key):
        """
        Constructor
        
        Keyword arguments:
        profile        --    parent profile object
        memory         --    memory bank this macro exists in
        key_list_key   --    string representation of keys required to activate macro
        """
        self.keys = key_list_key.split("_")
        self.key_list_key = key_list_key
        self.memory = memory
        self.profile = profile
        self.name = ""
        self.macro = ""
        self.repeat_mode = REPEAT_WHILE_HELD
        self.type = MACRO_SCRIPT
        self.repeat_delay = DEFAULT_REPEAT_DELAY 
        section_name = "m%d" % self.memory
        if not self.profile.parser.has_section(section_name):
            self.profile.parser.add_section(section_name)
            
    def is_uinput(self):
        """
        Get if the macro type is a uinput mapping type
        
        Keyword arguments:
        macro_type    --    macro type
        """
        return is_uinput_type(self.type)
            
    def compare(self, o):
        """
        Compare this macro with another for sorting purposes. Macros will
        be ordered with the G keys being first in numeric order, followed by
        the memory bank keys in number order (MR is last), followed by the 
        'L1' - 'L5' keys and finally all other keys ordered alphabetically. 
        
        Keyword arguments:
        o    --    macro to compare this macro to
        """
        return self._get_total(self.keys) - self._get_total(o.keys)
        
    def get_uinput_code(self):
        """
        Get the uinput code of the key this macro is mapped to. If this 
        macro is not of a type that maps to a uinput key, an exception
        will be thrown
        """
        if not self.type in [ MACRO_MOUSE, MACRO_KEYBOARD, MACRO_JOYSTICK, MACRO_DIGITAL_JOYSTICK ]:
            raise Exception("Macro of type %s, is not a type that maps to a uinput code." % self.type)
        return uinput.capabilities.CAPABILITIES[self.macro] if self.macro in uinput.capabilities.CAPABILITIES else 0
    
    def set_keys(self, keys):
        """
        Set the list of keys this macro requires to activate.
        
        Keyword arguments:
        keys        --    list of keys required to activate macro
        """
        section_name = "m%d" % self.memory     
        self.profile._delete_key(section_name, self.key_list_key)
        self.keys = keys
        self.key_list_key = get_keys_key(keys)
        self.save()
        
    def save(self):
        """
        Save this macro. This triggers the whole profile that contains the
        macro to be saved as well.
        """
        self._store()
        self.profile.save()
        
    def delete(self):
        """
        Delete this macro
        """   
        self.profile.delete_macro(self.memory, self.key_list_key)
        
    """
    Private
    """
        
    def _remove_option(self, section_name, option_key):
        if self.profile.parser.has_option(section_name, option_key):
            self.profile.parser.remove_option(section_name, option_key)
        
    def _store(self): 
        section_name = "m%d" % self.memory
        pk = "keys_%s" % self.key_list_key 
        self.profile.parser.set(section_name, "%s_name" % pk, self._encode_val(self.name))
        self.profile.parser.set(section_name, "%s_type" % pk, self.type)
        
        self.profile.parser.set(section_name, "%s_repeatdelay" % pk, self.repeat_delay)
        self.profile.parser.set(section_name, "%s_repeatmode" % pk, self.repeat_mode)
        
        if self.profile.version == 1.0:
            
            if self.type in [ MACRO_KEYBOARD, MACRO_JOYSTICK, MACRO_DIGITAL_JOYSTICK, MACRO_MOUSE ]:
                self.profile.parser.set(section_name, "%s_type" % pk, "mapped-to-key")
                self.profile.parser.set(section_name, "%s_maptype" % pk, self.type)        
                self.profile.parser.set(section_name, "%s_mappedkey" % pk, self.macro)
                self.profile._remove_if_exists("%s_command" % pk, section_name)
                self.profile._remove_if_exists("%s_simplemacro" % pk, section_name)
                self.profile._remove_if_exists("%s_macro" % pk, section_name)
                self.profile._remove_if_exists("%s_action" % pk, section_name)             
            else:
                self.profile._remove_if_exists("%s_mappedkey" % pk, section_name)
                self.profile._remove_if_exists("%s_maptype" % pk, section_name)
                if self.type == MACRO_COMMAND:
                    self.profile.parser.set(section_name, "%s_command" % pk, self._encode_val(self.macro))
                else:
                    self.profile._remove_if_exists("%s_command" % pk, section_name)
                if self.type == MACRO_SIMPLE:
                    self.profile.parser.set(section_name, "%s_simplemacro" % pk, self._encode_val(self.macro))
                else:
                    self.profile._remove_if_exists("%s_simplemacro" % pk, section_name)
                if self.type == MACRO_SCRIPT:
                    self.profile.parser.set(section_name, "%s_macro" % pk, self._encode_val(self.macro))
                else:
                    self.profile._remove_if_exists("%s_macro" % pk, section_name)
                    
                """
                Actions aren't actually supported in < 0.8, but store it in it's
                own field anyway. Earlier versions will just not support that
                macro
                """                
                if self.type == MACRO_ACTION:
                    self.profile.parser.set(section_name, "%s_action" % pk, self._encode_val(self.macro))
                else:
                    self.profile._remove_if_exists("%s_action" % pk, section_name)
        else:
            """
            Store in the new more compact version 2.0 format
            """
            self.profile.parser.set(section_name, "%s_macro" % pk, self._encode_val(self.macro))
            self.profile._remove_if_exists("%s_maptype" % pk, section_name)
            self.profile._remove_if_exists("%s_mappedkey" % pk, section_name)
            self.profile._remove_if_exists("%s_command" % pk, section_name)
            self.profile._remove_if_exists("%s_simplemacro" % pk, section_name)
            self.profile._remove_if_exists("%s_action" % pk, section_name)
        
    def _encode_val(self, val):
        val = val.encode('utf8')
        return val
    
    def _decode_val(self, val):
        return val
        
    def _load(self):
        self.type = self._get("type", MACRO_SCRIPT)
        self.macro = self._decode_val(self._get("macro", ""))
        self.name = self._decode_val(self._get("name", ""))
        self.repeat_mode = self._decode_val(self._get("repeatmode", REPEAT_WHILE_HELD))
        self.repeat_delay = float(self._get("repeatdelay", DEFAULT_REPEAT_DELAY))
        if self.type == "mapped-to-key":
            self.macro = self._get("mappedkey", "")
            self.type = self._get("maptype", "")
        elif self.profile.version == 1.0:
            if self.type == MACRO_COMMAND:
                self.macro = self._decode_val(self._get("command", "")) 
            elif self.type == MACRO_SIMPLE:
                self.macro = self._decode_val(self._get("simplemacro", "")) 
            elif self.type == MACRO_ACTION:
                """
                Actions aren't actually supported in < 0.8, but this is how
                it's stored when the profile is in 1.0 mode.
                """
                self.macro = self._decode_val(self._get("action", ""))
        
    def _get(self, key, default_value):
        section_name = "m%d" % self.memory
        option_key = "keys_" + self.key_list_key + "_" + key
        return self.profile.parser.get(section_name, option_key) if self.profile.parser.has_option(section_name, option_key) else default_value
            
    def __ne__(self, macro):
        return not self.__eq__(macro)
    
    def __eq__(self, macro):
        return macro is not None and self.profile.id == macro.profile.id and self.key_list_key == macro.key_list_key
    
    def _get_total(self, keys):
        t = 0
        for i in range(0, len(keys)):
            if keys[i] != "":
                t += self._get_key_val(keys[i])
        return t
            
    def _get_key_val(self, key):
        if(key == ""):
            return 0        
        elif re.match("g[0-9]+.*", key):
            return int(key[1:])
        elif re.match("m[1-3]", key):
            return 50 + int(key[1:])
        elif key == "mr":
            return 55        
        elif re.match("l[0-9]+.*", key):
            return 100 + int(key[1:])
        else:
            ki = self.profile.device.get_key_index(key)
            if ki is None:
                ki = 200
            return 200 + ki
        
    def __repr__(self):
        return "[Macro %d/%s (%s)" % ( self.memory, self.name, self.key_list_key )
 
class G15Profile():
    """
    Encapsulates a single macro profile with 3 memory banks. This object
    contains all the general information about the profile, as well as the 
    list of macros themselves.
    """
    
    def __init__(self, device, id=-1):
        """
        Constructor
        
        Keyword arguments:
        device        -- device the profile is associated with
        id            -- profile ID 
        """
        
        self.id = id
        self.device = device
        self.parser = ConfigParser.ConfigParser({
                                                     })        
        self.name = None
        self.icon = None
        self.background = None
        self.author = ""
        self.macros = []        
        self.mkey_color = {}
        self.activate_on_focus = False
        self.window_name = ""
        self.base_profile = -1
        self.version = 2.0
        self.load()
        
    def export(self, filename):
        """
        Save this profile in a format that may be transmitted to another
        computer (as a zip file). All references to external images (for icon and background)
        are made relative and added to the archive.
        
        Keyword arguments:
        filename    --    file to save copy to
        """
        profile_copy = get_profile(self.device, self.id)
        
        archive_file = zipfile.ZipFile(filename, "w")
        try:
            # Icon
            if profile_copy.icon and os.path.exists(profile_copy.icon):
                base_path = "%d.resources/%s" % ( profile_copy.id, os.path.basename(profile_copy.icon) )
                archive_file.write(profile_copy.icon, base_path )  
                profile_copy.icon = base_path
                
            # Background            
            if profile_copy.background and os.path.exists(profile_copy.background):
                base_path = "%d.resources/%s" % ( profile_copy.id, os.path.basename(profile_copy.background) )
                archive_file.write(profile_copy.background, base_path)  
                profile_copy.background = base_path
                
            # Profile
            profile_data = StringIO()
            try:
                profile_copy.save(profile_data)
                archive_file.writestr("%d.macros" % profile_copy.id, profile_data.getvalue())
            finally:
                profile_data.close()
        finally:
            archive_file.close()
        
    def are_keys_in_use(self, memory, keys, exclude = None):
        """
        Get if the specified keys are currently in use for a macro in the
        supplied memory bank number. Optionally, a list of macros that 
        should be excluded from the search can be supplied (usually used
        to exclude the current macro when checking if other macros currently
        use a set of keys)
        
        Keyword arguments:
        memory        --    memory bank number
        keys          --    keys to search for
        exclude       --    list of macro objects to exclude
        """
        bank = self.macros[memory - 1]
        for macro in bank:
            if ( exclude == None or ( exclude != None and not self._is_excluded(exclude, macro) ) ) and sorted(keys) == sorted(macro.keys):
                return True
        return False

    def get_default(self):
        """
        Get if this profile is the default one
        """
        return self.id == 0
        
    def save(self, filename = None):
        """
        Save this profile to disk
        """
        logger.info("Saving macro profile %d, %s" % ( self.id, self.name ))
    
        if self.window_name == None:
            self.window_name = ""
        if self.icon == None:
            self.icon = ""
        
        # Set the profile options
        self.parser.set("DEFAULT", "name", self.name)
        self.parser.set("DEFAULT", "version", str(self.version))
        self.parser.set("DEFAULT", "icon", self.icon)
        self.parser.set("DEFAULT", "window_name", self.window_name)    
        self.parser.set("DEFAULT", "base_profile", str(self.base_profile))
        self.parser.set("DEFAULT", "icon", self.icon)
        self.parser.set("DEFAULT", "background", self.background)
        self.parser.set("DEFAULT", "author", self.author)
        self.parser.set("DEFAULT", "activate_on_focus", str(self.activate_on_focus))
        self.parser.set("DEFAULT", "send_delays", str(self.send_delays))
        self.parser.set("DEFAULT", "fixed_delays", str(self.fixed_delays))
        self.parser.set("DEFAULT", "press_delay", str(self.press_delay))
        self.parser.set("DEFAULT", "release_delay", str(self.release_delay))
        self.parser.set("DEFAULT", "model", str(self.device.model_id))
        
        # Remove and re-add the bank sections
        for i in range(1, 4): 
            section_name = "m%d" % i
            if not self.parser.has_section(section_name):
                self.parser.add_section(section_name) 
            col = self.mkey_color[i] if i in self.mkey_color else None
            if col:
                self.parser.set(section_name, "backlight_color", g15util.rgb_to_string(col))
            elif self.parser.has_option(section_name, "backlight_color"):
                self.parser.remove_option(section_name, "backlight_color")
                
        # Add the macros
        for i in range(1, 4):
            for macro in self.get_sorted_macros(i):
                macro._store()
                
        self._write(filename)
            
    def set_mkey_color(self, memory, rgb):
        """
        Set a tuple containing the red, green and blue values of the colour
        to use when the specifed bank is active
        
        Keyword arguments:
        memory     --     memory bank number
        rgb        --     colour to assign to bank
        """
        self.mkey_color[memory] = rgb
        
    def get_mkey_color(self, memory):
        """
        Get a tuple contain the red, green and blue values of the colour
        to use when the specifed bank is active
        
        Keyword arguments:
        memory    -- memory bank number
        """
        return self.mkey_color[memory] if memory in self.mkey_color else None
        
    def delete(self):
        """
        Delete this macro profile
        """
        os.remove(self._get_filename())
        
    def delete_macro(self, memory, keys):
        """
        Delete the macro that is activated by the specified keys in the 
        supplied memory bank number
        
        Keyword arguments:
        memory        -- memory bank number (starts at 1)
        keys          -- keys that activate the macro
        """
        section_name = "m%d" % memory     
        key_list_key = get_keys_key(keys)
        logger.info("Deleting macro M%d, for %s" % ( memory, key_list_key ))
        self._delete_key(section_name, key_list_key)
        self._write()
        bank_macros = self.macros[memory - 1] 
        for macro in bank_macros:
            if macro.key_list_key == key_list_key and macro in bank_macros:
                bank_macros.remove(macro)
        
    def get_profile_icon_path(self, height):
        """
        Get the icon for the profile. This will either be a specific icon
        path, or if none is available, the default profile icon. If the
        icon is a themed icon name, then that icon will be searched for and
        the full path returned
        
        Keyword arguments:
        height        --    preferred height
        """
        icon = self.icon
        if icon == None or icon == "":
            icon = "preferences-desktop-keyboard-shortcuts"
        return g15util.get_icon_path(icon, height)
        
    def create_macro(self, memory, keys, name, macro_type, macro):
        """
        Create a new macro
        
        Keyword arguments:
        memory        --     memory bank number (starts at 1)
        keys          --     list of keys that activate the macro
        name          --     name of macro
        type          --     macro type
        macro         --     content of macro
        """
        key_list_key = get_keys_key(keys)  
        logger.info("Creating macro M%d, for %s" % ( memory, key_list_key ))
        new_macro = G15Macro(self, memory, key_list_key)
        new_macro.name = name
        new_macro.type = macro_type
        new_macro.macro = macro
        self.macros[memory - 1].append(new_macro)
        new_macro.save()
        return new_macro
    
    def get_macro(self, memory, keys):
        """
        Get the macro given the memory bank number and the list of keys
        the macro requires to activate
        
        Keyword arguments:
        memory        --    memory bank number (starts at 1)
        keys          --    list of keys that activate the macro
        """
        bank = self.macros[memory - 1]
        for macro in bank:
            key_count = 0
            for k in macro.keys:
                if k in keys:
                    key_count += 1
            if key_count == len(macro.keys) and key_count == len(keys):
                return macro
        
    def make_active(self):
        """
        Make this the currently active profile
        """
        conf_client.set_int("/apps/gnome15/%s/active_profile" % self.device.uid, self.id)
        
    def load(self, filename = None):
        """
        Load the profile from disk
        """
                 
        # Initial values
        self.macros = []
        self.mkey_color = {}
        
        # Load macro file        
        if self.id != -1 or filename is not None:
            if filename is None:
                filename = self._get_filename()
            if isinstance(filename, str) and os.path.exists(filename):
                self.parser.readfp(codecs.open(filename, "r", "utf8"))
            else:
                self.parser.readfp(filename)
        
        # Macro file format version. Try to keep macro files backwardly and
        # forwardly compatible
        if self.parser.has_option("DEFAULT", "version"):
            self.version = float(self.parser.get("DEFAULT", "version").strip())
        else:
            self.version = 1.0
        
        # Info section
        self.name = self.parser.get("DEFAULT", "name").strip() if self.parser.has_option("DEFAULT", "name") else ""
        self.icon = self.parser.get("DEFAULT", "icon").strip() if self.parser.has_option("DEFAULT", "icon") else ""
        self.background = self.parser.get("DEFAULT", "background").strip() if self.parser.has_option("DEFAULT", "background") else ""
        self.author = self.parser.get("DEFAULT", "author").strip() if self.parser.has_option("DEFAULT", "author") else ""
        self.window_name = self.parser.get("DEFAULT", "window_name").strip() if self.parser.has_option("DEFAULT", "window_name") else ""
        
        self.activate_on_focus = self.parser.getboolean("DEFAULT", "activate_on_focus") if self.parser.has_option("DEFAULT", "activate_on_focus") else False
        self.send_delays = self.parser.getboolean("DEFAULT", "send_delays") if self.parser.has_option("DEFAULT", "send_delays") else False
        self.fixed_delays = self.parser.getboolean("DEFAULT", "fixed_delays") if self.parser.has_option("DEFAULT", "fixed_delays") else False
        
        self.base_profile = self._get_int("base_profile", -1, "DEFAULT")
        self.press_delay = self._get_int("press_delay", 50)
        self.release_delay = self._get_int("release_delay", 50)
        
        # Bank sections
        for i in range(1, 4):
            section_name = "m%d" % i
            if not self.parser.has_section(section_name):
                self.parser.add_section(section_name)
            self.mkey_color[i] = g15util.to_rgb(self.parser.get(section_name, "backlight_color")) if self.parser.has_option(section_name, "backlight_color") else None
            memory_macros = []
            self.macros.append(memory_macros)
            for option in self.parser.options(section_name):
                if option.startswith("keys_") and option.endswith("_name"):
                    key_list_key = option[5:-5]
                    macro_obj = G15Macro(self, i, key_list_key)
                    macro_obj._load()
                    memory_macros.append(macro_obj)
        
    def get_sorted_macros(self, memory_number):
        """
        Get the list of macros sorted
        
        Keyword arguments:
        memory_number        --    memory bank number to retrieve macros from  (starts at 1)
        """
        sm = list(self.macros[memory_number - 1])
        sm.sort(self._comparator)
        return sm
                    
    '''
    Private
    '''        
    def _comparator(self, o1, o2):
        return o1.compare(o2)
                    
    def _remove_if_exists(self, name, section = "DEFAULT"):
        if self.parser.has_option(section, name):
            self.parser.remove_option(section, name)
            
    def _get_int(self, name, default_value, section = "DEFAULT"):
        try:
            return self.parser.getint(section, name) if self.parser.has_option(section, name) else default_value
        except ValueError as v:
            return default_value
                    
    def __ne__(self, profile):
        return not self.__eq__(profile)
    
    def __eq__(self, profile):
        return profile is not None and self.id == profile.id
        
    def _write(self, filename = None):
        if filename is None and self.id == -1:
            raise Exception("Cannot save a profile without a filename or an id.")
        
        save_file = self._get_filename() if filename is None else filename
        if isinstance(save_file, str):
            dir_name = os.path.dirname(save_file)
            if not os.path.exists(dir_name):
                os.mkdir(dir_name)
            tmp_file = "%s.tmp" % save_file
            with open(tmp_file, 'wb') as configfile:
                self.parser.write(configfile)
            os.rename(tmp_file, save_file)
            fhandle = file(save_file, 'a')
            try:
                os.utime(save_file, None)
            finally:
                fhandle.close()
        else:
            self.parser.write(save_file)
        
    def _delete_key(self, section_name, key_list_key):
        for option in self.parser.options(section_name):
            if option.startswith("keys_" + key_list_key + "_"):
                self.parser.remove_option(section_name, option)
        
    def _get_filename(self):
        return "%s/%s/%d.macros" % ( conf_dir, self.device.uid, self.id )
    
    def _is_excluded(self, excluded, macro):
        for e in excluded:
            if e == macro:
                return True
        
# Create the default for all devices
for device in g15devices.find_all_devices():
    create_default(device)