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

class Key(object):
    '''Static container containing all keys.'''

    # G/M keys
    # light switch
    LIGHT, \
    M1, \
    M2, \
    M3, \
    MR, \
    G01, \
    G02, \
    G03, \
    G04, \
    G05, \
    G06, \
    G07, \
    G08, \
    G09, \
    G10, \
    G11, \
    G12 = list(range(17))

    # special keys at display
    BACK, \
    DOWN, \
    LEFT, \
    MENU, \
    OK, \
    RIGHT, \
    SETTINGS, \
    UP = list(range(G12 + 1, G12 + 9))

    # multimedia keys
    WINKEY_SWITCH, \
    NEXT, \
    PREV, \
    STOP, \
    PLAY, \
    MUTE, \
    SCROLL_UP, \
    SCROLL_DOWN = list(range(UP + 1, UP + 9))
    
    displayKeys = set([
        BACK,
        DOWN,
        LEFT,
        MENU,
        OK,
        RIGHT,
        SETTINGS,
        UP
                       ])

    mmKeys = set([
            WINKEY_SWITCH,
            NEXT,
            PREV,
            STOP,
            PLAY,
            MUTE,
            SCROLL_UP,
            SCROLL_DOWN])

    gmKeys = set([
            G01,
            G02,
            G03,
            G04,
            G05,
            G06,
            G07,
            G08,
            G09,
            G10,
            G11,
            G12,
            LIGHT,
            M1,
            M2,
            M3,
            MR])


class Data(object):
    '''Static container with all data values for all keys.'''

    ##
    ## display keys
    ##

    # special keys at display
    # The current state of pressed keys is an OR-combination of the following
    # codes.
    # Incoming data always has 0x80 appended, e.g. pressing and releasing the menu
    # key results in two INTERRUPT transmissions: [0x04, 0x80] and [0x00, 0x80]
    # Pressing (and holding) UP and OK at the same time results in [0x88, 0x80].
    displayKeys = {}
    displayKeys[0x01] = Key.SETTINGS
    displayKeys[0x02] = Key.BACK
    displayKeys[0x04] = Key.MENU
    displayKeys[0x08] = Key.OK
    displayKeys[0x10] = Key.RIGHT
    displayKeys[0x20] = Key.LEFT
    displayKeys[0x40] = Key.DOWN
    displayKeys[0x80] = Key.UP


    ##
    ## G- and M-Keys
    ##

    # these are the bit fields for setting the currently illuminated keys
    # (see set_enabled_m_keys())
    LIGHT_KEY_M1 = 0x80
    LIGHT_KEY_M2 = 0x40
    LIGHT_KEY_M3 = 0x20
    LIGHT_KEY_MR = 0x10

    # specific codes sent by M- and G-keys
    # received as [0x02, keyL, keyH, 0x40]
    # example: G3: [0x02, 0x04, 0x00, 0x40]
    #          G1 + G2 + G11: [0x02, 0x03, 0x04, 0x40]
    KEY_G01 = 0x000001
    KEY_G02 = 0x000002
    KEY_G03 = 0x000004
    KEY_G04 = 0x000008
    KEY_G05 = 0x000010
    KEY_G06 = 0x000020
    KEY_G07 = 0x000040
    KEY_G08 = 0x000080
    KEY_G09 = 0x000100
    KEY_G10 = 0x000200
    KEY_G11 = 0x000400
    KEY_G12 = 0x000800
    KEY_M1 = 0x001000
    KEY_M2 = 0x002000
    KEY_M3 = 0x004000
    KEY_MR = 0x008000

    # light switch
    # this on is similar to G-keys:
    # down: [0x02, 0x00, 0x00, 0x48]
    # up:   [0x02, 0x00, 0x00, 0x40]
    KEY_LIGHT = 0x080000

    gmKeys = {}
    gmKeys[KEY_G01] = Key.G01
    gmKeys[KEY_G02] = Key.G02
    gmKeys[KEY_G03] = Key.G03
    gmKeys[KEY_G04] = Key.G04
    gmKeys[KEY_G05] = Key.G05
    gmKeys[KEY_G06] = Key.G06
    gmKeys[KEY_G07] = Key.G07
    gmKeys[KEY_G08] = Key.G08
    gmKeys[KEY_G09] = Key.G09
    gmKeys[KEY_G10] = Key.G10
    gmKeys[KEY_G11] = Key.G11
    gmKeys[KEY_G12] = Key.G12
    gmKeys[KEY_G12] = Key.G12
    gmKeys[KEY_M1] = Key.M1
    gmKeys[KEY_M2] = Key.M2
    gmKeys[KEY_M3] = Key.M3
    gmKeys[KEY_MR] = Key.MR
    gmKeys[KEY_LIGHT] = Key.LIGHT


    ##
    ## MM-keys
    ##

    # multimedia keys
    # received as [0x01, key]
    # example: NEXT+SCROLL_UP:       [0x01, 0x21]
    #          after scroll stopped: [0x01, 0x01]
    #          after release:        [0x01, 0x00]
    mmKeys = {}
    mmKeys[0x01] = Key.NEXT
    mmKeys[0x02] = Key.PREV
    mmKeys[0x04] = Key.STOP
    mmKeys[0x08] = Key.PLAY
    mmKeys[0x10] = Key.MUTE
    mmKeys[0x20] = Key.SCROLL_UP
    mmKeys[0x40] = Key.SCROLL_DOWN

    # winkey switch to winkey off: [0x03, 0x01]
    # winkey switch to winkey on:  [0x03, 0x00]
    KEY_WIN_SWITCH = 0x0103

