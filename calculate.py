# calculate.py, sugar calculator, by:
#   Reinier Heeres <reinier@heeres.eu>
#   Miguel Alvarez <miguel@laptop.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
# Change log:
#    2007-07-03: rwh, first version

import types
import os
from gettext import gettext as _
import string

import logging
_logger = logging.getLogger('calc-activity')

import gobject
import pygtk
pygtk.require('2.0')
import gtk
import pango

from sugar.activity import activity
import sugar.profile
from sugar.graphics.canvasicon import CanvasIcon
from sugar.graphics.xocolor import XoColor
from sugar.graphics import color
try:
    from sugar.graphics import font
except:
    #Nothing
    pass
from layout import CalcLayout
from mathlib import MathLib
from eqnparser import EqnParser

class Equation:
    def __init__(self, label, eqn, res, col):
        self.label = label
        self.equation = eqn
        self.result = res
        self.color = col

class Calculate(activity.Activity):

    TYPE_FUNCTION = 1
    TYPE_OP_PRE = 2
    TYPE_OP_POST = 3
    TYPE_TEXT = 4
    
    FONT_SMALL = "sans 10"
    FONT_SMALL_NARROW = "sans italic 10"
    FONT_BIG = "sans bold 16"
    FONT_BIG_NARROW = "sans italic 16"
    FONT_BIGGER = "sans bold 22"
   
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        self.set_title("Calc2")
        self.connect("key_press_event", self.keypress_cb)
        self.connect("destroy", self.cleanup_cb)
        self.color = sugar.profile.get_color()
##        self.icon = CanvasIcon(
##            icon_name = 'theme:stock-buddy',
##            xo_color = XoColor(self.color))     
        self.layout = CalcLayout(self)
        self.label_entry = self.layout.label_entry
        self.text_entry = self.layout.text_entry
        self.history = self.layout.history
        self.last_eq = self.layout.last_eq.get_buffer()
        
        self.old_eqs = []           # List of Equation objects
        self.old_changed = False    # This variable should be thrown out somehow
        self.show_vars = False
        self.reset()

        self.ml = MathLib()
        self.parser = EqnParser(self.ml)

    def ignore_key_cb(self, widget, event):
        return True

    def cleanup_cb(self, arg):
        _logger.debug('Cleaning up...')

    def equation_pressed_cb(self, n):
        """Callback for when an equation box is clicked"""
        if len(self.old_eqs) <= n:
            return True
        if len(self.old_eqs[n].label) > 0:
            text = self.old_eqs[n].label
        else:
            text = self.old_eqs[n].equation
        self.button_pressed(self.TYPE_TEXT, text)
        return True

    def format_last_eq_buf(self, buf, res, offset):
        eq_start = buf.get_start_iter()
        eq_middle = buf.get_iter_at_line(1)
        eq_end = buf.get_end_iter()
        buf.apply_tag(buf.create_tag(font=self.FONT_BIG_NARROW),
            eq_start, eq_middle)
        buf.apply_tag(buf.create_tag(font=self.FONT_BIGGER,
            justification=gtk.JUSTIFY_RIGHT), eq_middle, eq_end)

        if res is None:
            eq_start.forward_chars(offset)
            end = self.last_eq.get_start_iter()
            end.forward_chars(offset+1)
            self.last_eq.apply_tag(self.last_eq.create_tag(foreground='#FF0000'),
                eq_start, end)
            self.last_eq.apply_tag(self.last_eq.create_tag(foreground='#FF0000'),
                eq_middle, eq_end)

    def set_last_equation(self, eqn):
        text = ""
        if len(eqn.label) > 0:
            text += eqn.label + ': ' + eqn.equation
            offset = len(eqn.label) + 2
        else:
            text += eqn.equation
            offset = 0

        if eqn.result is not None:
            text += '\n= ' + self.ml.format_number(eqn.result)
            self.text_entry.set_text('')
            self.parser.set_var('Ans', self.ml.format_number(eqn.result))
            if len(eqn.label) > 0:
                self.label_entry.set_text('')
                self.parser.set_var(eqn.label, eqn.equation)
        else:
            pos = self.parser.get_error_offset()
            if pos == len(text) - 1:
                text += '_'
            offset += pos
            text += '\nError at %d' % pos

        self.last_eq.set_text(text)
        self.format_last_eq_buf(self.last_eq, eqn.result, offset)

    def process(self):
        s = self.text_entry.get_text()
        label = self.label_entry.get_text()
        _logger.debug('process(): parsing \'%s\', label: \'%s\'', s, label)
        res = self.parser.parse(s)
        eqn = Equation(label, s, res, self.color)
        self.set_last_equation(eqn)

        if res is not None:
            self.old_eqs.insert(0, eqn)
            self.old_changed = True
            self.refresh_bar()

        return res is not None

    def refresh_bar(self):
        _logger.debug('Refreshing right bar...')
        if self.layout.varbut.selected == 0:
            self.refresh_history()
        else:
            self.refresh_vars()
    
    def format_var_buf(self, buf):
        iter_start = buf.get_start_iter()
        iter_end = buf.get_end_iter()
        buf.apply_tag(buf.create_tag(font=self.FONT_SMALL_NARROW),
            iter_start, iter_end)
        buf.apply_tag(buf.create_tag(foreground=self.color.get_fill_color()), 
            iter_start, iter_end)

    def refresh_vars(self):
        list = []
        for name, value in self.parser.get_vars():
            if name == "Ans":
                continue
            w = gtk.TextView()
            b = w.get_buffer()
            b.set_text(name + ":\t" + value)
            self.format_var_buf(b)
            list.append(w)
        self.layout.show_history(list)
        self.old_changed = True

    def format_history_buf(self, buf):
        iter_start = buf.get_start_iter()
        iter_colon = buf.get_start_iter()
        iter_end = buf.get_end_iter()
        iter_middle = buf.get_iter_at_line(1)
        try:
            pos = buf.get_text(iter_start, iter_end).index(':')
            iter_colon.forward_chars(pos)
        except:
            buf.apply_tag(buf.create_tag(font=self.FONT_SMALL),
                          iter_start, iter_middle)
        else:

            buf.apply_tag(buf.create_tag(font=self.FONT_SMALL_NARROW),
                          iter_start, iter_colon)
            buf.apply_tag(buf.create_tag(font=self.FONT_SMALL),
                          iter_colon, iter_middle)
            
        buf.apply_tag(buf.create_tag(font=self.FONT_BIG,
            justification=gtk.JUSTIFY_RIGHT), iter_middle, iter_end)
        buf.apply_tag(buf.create_tag(foreground=self.color.get_fill_color()), 
            iter_start, iter_end)
    
    def refresh_history(self):
        if not self.old_changed:
            return
        list = []

        if len(self.old_eqs) > 1:
            i = 1
            for e in self.old_eqs[1:]:
                text = ""
                if len(e.label) > 0:
                    text += str(e.label) + ": "
                r = self.ml.format_number(e.result)
                text += str(e.equation) + "\n=" + r
                w = gtk.TextView()
                w.connect('button-press-event', lambda w, e, j: self.equation_pressed_cb(j), i)
                b = w.get_buffer()
##                  b.modify_bg(gtk.STATE_ACTIVE | gtk.STATE_NORMAL,
##                  gtk.gdk.color_parse(self.color.get_fill_color()))
                b.set_text(text)
                self.format_history_buf(b)
                list.append(w)
                i += 1

        self.layout.show_history(list)
        self.old_changed = False

    def clear(self):
        _logger.debug('Clearing...')
        self.text_entry.set_text('')
        self.text_entry.grab_focus()
        return True

    def reset(self):
        _logger.debug('Resetting...')
        self.clear()
        return True

##########################################
# User interaction functions
##########################################

    def remove_character(self, dir):
        pos = self.text_entry.get_position()
        print 'Position: %d, dir: %d, len: %d' % (pos, dir, len(self.text_entry.get_text()))
        if pos + dir <= len(self.text_entry.get_text()) and pos + dir >= 0:
            if dir < 0:
                self.text_entry.delete_text(pos+dir, pos)
            else:
                self.text_entry.delete_text(pos, pos+dir)

    def move_left(self):
        pos = self.text_entry.get_position()
        if pos > 0:
            self.text_entry.set_position(pos - 1)

    def move_right(self):
        pos = self.text_entry.get_position()
        if pos < len(self.text_entry.get_text()):
            self.text_entry.set_position(pos + 1)

    def label_entered(self):
        if len(self.label_entry.get_text()) > 0:
            return
        pos = self.text_entry.get_position()
        str = self.text_entry.get_text()
        self.label_entry.set_text(str[:pos])
        self.text_entry.set_text(str[pos:])

    def keypress_cb(self, widget, event):
        if self.label_entry.is_focus():
            return

        key = gtk.gdk.keyval_name(event.keyval)
        _logger.debug('Key: %s (%r)', key, event.keyval)

        allowed_chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ "
        if key in allowed_chars:
            self.add_text(key)

        keymap = {
            'Return': lambda: self.process(),
            'period': '.',
            'equal': '=',
            'plus': '+',
            'minus': '-',
            'asterisk': '*',
            'slash': '/',
            'BackSpace': lambda: self.remove_character(-1),
            'Delete': lambda: self.remove_character(1),
            'parenleft': '(',
            'parenright': ')',
            'exclam': '!',
            'ampersand': '&',
            'bar': '|',
            'asciicircum': '^',
            'less': '<',
            'greater': '>',
            'Left': lambda: self.move_left(),
            'Right': lambda: self.move_right(),
            'colon': lambda: self.label_entered(),
            'Home': lambda: self.text_entry.set_position(0),
            'End': lambda: self.text_entry.set_position(len(self.text_entry.get_text()))
        }
        if keymap.has_key(key):
            f = keymap[key]
            if type(f) is types.StringType:
                self.add_text(f)
            else:
                return f()

        return True

    def add_text(self, c):
        pos = self.text_entry.get_position()
        tlen = len(self.text_entry.get_text())
        if tlen == 0 and c in self.parser.get_diadic_operators():
            c = 'Ans' + c
        self.text_entry.insert_text(c, pos)
        self.text_entry.grab_focus()
        self.text_entry.set_position(pos + len(c))

# This function should be split up properly
    def button_pressed(self, type, str):
        sel = self.text_entry.get_selection_bounds()
        pos = self.text_entry.get_position()
        self.text_entry.grab_focus()
        if len(sel) == 2:
            (start, end) = sel
            text = self.text_entry.get_text()
        elif len(sel) != 0:
            _logger.error('button_pressed(): len(sel) != 0 or 2')
            return False

        if type == self.TYPE_FUNCTION:
            if sel is ():
                self.text_entry.insert_text(str + '()', pos)
                self.text_entry.set_position(pos + len(str) + 1)
            else:
                self.text_entry.set_text(text[:start] + str + '(' + text[start:end] + ')' + text[end:])
                self.text_entry.set_position(end + len(str) + 2)

        elif type == self.TYPE_OP_PRE:
            if len(sel) is 2:
                pos = start
            elif pos == 0:
                str = 'Ans' + str
            self.text_entry.insert_text(str, pos)
            self.text_entry.set_position(pos + len(str))

        elif type == self.TYPE_OP_POST:
            if len(sel) is 2:
                pos = end
            self.text_entry.insert_text(str, pos)
            self.text_entry.set_position(pos + len(str))

        elif type == self.TYPE_TEXT:
            if len(sel) is 2:
                self.text_entry.set_text(text[:start] + str + text[end:])
                self.text_entry.set_position(pos + start - end + len(str))
            else:
                self.text_entry.insert_text(str, pos)
                self.text_entry.set_position(pos + len(str))

        else:
            _logger.error('Calculate.button_pressed(): invalid type')

def main():
    win = gtk.Window(gtk.WINDOW_TOPLEVEL)
    t = Calc(win)
    gtk.main()
    return 0

if __name__ == "__main__":
    main()
