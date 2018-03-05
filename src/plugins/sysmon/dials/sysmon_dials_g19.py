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

import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg as rsvg

from gnome15.util import g15convert
from gnome15.util import g15cairo
import os
import cairo
      
needles = {
        "cpu_pc"        : (170, 90,    rsvg.Handle(os.path.join(os.path.dirname(__file__), "g19-large-needle.svg"))),
        "net_send_pc"   : (82, 198,     rsvg.Handle(os.path.join(os.path.dirname(__file__), "g19-tiny-needle.svg"))), 
        "net_recv_pc"   : (82, 198,     rsvg.Handle(os.path.join(os.path.dirname(__file__), "g19-small-needle.svg"))), 
        "mem_used_pc"   : (254, 198,    rsvg.Handle(os.path.join(os.path.dirname(__file__), "g19-small-needle.svg"))),
        "mem_cached_pc" : (254, 198,    rsvg.Handle(os.path.join(os.path.dirname(__file__), "g19-tiny-needle.svg")))
           }

def paint_foreground(theme, canvas, properties, attributes, *args): 
    for key in list(needles.keys()):
        needle = needles[key]
        svg = needle[2]      
        surface = create_needle_surface(svg, ( ( 180.0 / 100.0 ) * float(properties[key]) ) )
        canvas.save()
        svg_size = svg.get_dimension_data()[2:4]  
        canvas.translate (needle[0] - svg_size[0], needle[1] - svg_size[1])
        canvas.set_source_surface(surface)
        canvas.paint()
        canvas.restore()
        
def create_needle_surface(svg, degrees):
    svg_size = svg.get_dimension_data()[2:4]  
    surface = cairo.SVGSurface(None, svg_size[0] * 2,svg_size[1] *2)
    context = cairo.Context(surface)
    context.translate(svg_size[0], svg_size[1])
    g15cairo.rotate(context, -180)
    g15cairo.rotate(context, degrees)
    svg.render_cairo(context)
    context.translate(-svg_size[0], -svg_size[1])
    return surface
