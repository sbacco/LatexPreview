#!/usr/bin/python3
"""
Quickly convert a LaTeX formula to a gif image,
preview it, copy it to the clipboard, or save it.
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from gi.repository.GLib import Error as GLibError

from typing import Iterable
import os
import shutil
import subprocess
import json

# Set dark GTK theme
try:
    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-application-prefer-dark-theme", True)
except AttributeError:
    print("Failed to get GTK settings")

CWD = os.getcwd()
PATH = os.path.dirname(os.path.realpath(__file__))
CONF_FILE = os.path.join(PATH, '.conf.json')
ADD_PACK_MSG = "<add a LaTeX package>"
os.chdir('/tmp/')

TEX_FOOT = r"""
$$
\end{document}
"""

# handlers and objects as defined in the UI file
HANDLERS = [
    "on_save",
    "on_copy",
    "on_resolution_changed",
    "on_preview",
    "on_log",
    "on_packages",
    "on_color_set",
    "on_quit"
]
OBJS = [
    "resolution_spin",
    "editor",
    "color_btn",
    "packages_pop",
    "preview",
    "preview_box",
    "window"
]


def tex_head(packages: Iterable[str]) -> str:
    """
    Compute the appropriate header given a list of packages
    """
    r = r"""\documentclass[12pt]{article}
"""

    for p in packages:
        r += r"\usepackage{" + p + "}\n"

    r += r"""\pagestyle{empty}
\begin{document}
$$
"""
    return r


def call(command: list[str], stdin: str = "") -> Exception | None:
    """Call an external program"""
    print("Calling subprocess:", end=' ')
    for s in command:
        print(s, end=' ')
    print('')
    try:
        subprocess.check_output(
            command, stderr=subprocess.STDOUT, input=stdin
        )
    except OSError as e:
        print("Failed to run {}:\n{}".format(command[0], e))
        error_dialog("Failed to run {}:\n{}".format(command[0], e))
    except subprocess.CalledProcessError as e:
        print("{} terminated with exit status {}:\n{}".format(
            e.cmd[0], e.returncode, e.output.decode("ascii")))
        return e
    return None


def strip(string: str) -> str:
    """
    LaTeX doesn't like empty lines at the start and end of mathematical
    expressions for some reason, so we must strip those away.
    """
    if not string: return '\pi^2=g'
    while string[-1] == '\n':
        string = string[:-1]
    while string[0] == '\n':
        string = string[1:]
    return string


def error_dialog(e: str) -> None:
    dialog = Gtk.MessageDialog(
        parent                 = None,
        message_type           = Gtk.MessageType.ERROR,
        buttons                = Gtk.ButtonsType.OK,
        text                   = e)
    dialog.set_title('Error!')
    dialog.show()
    dialog.run()
    dialog.destroy()


class LogWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__()
        self.set_title("/tmp/latexpreview.log")
        self.sw = Gtk.ScrolledWindow()
        self.log = Gtk.TextView()
        self.log.set_editable(False)
        self.sw.set_size_request(750,400)
        buff = Gtk.TextBuffer()

        try:
            with open('latexpreview.log', 'r') as file:
                buff.set_text(file.read())
            self.log.set_buffer(buff)
        except FileNotFoundError:
            print("File not found: /tmp/latexpreview.log (This is fine)")
        except OSError as e:
            print(f"Could not read from /tmp/latexpreview.log: {e}")
            error_dialog(
                f"Could not read from /tmp/latexpreview.log: {e}")

        self.sw.add(self.log)
        self.add(self.sw)


class MainWindow:
    def __init__(self) -> None:
        # load up UI
        builder = Gtk.Builder()
        try: builder.add_from_file(
                os.path.join(PATH, "latexpreview.ui"))
        except GLibError as e:
            error_dialog(e)
            self.good = False
            return
        self.good = True
        builder.connect_signals(
            {k: getattr(self, k) for k in HANDLERS}
        )
        for p in OBJS:
            setattr(self, p, builder.get_object(p))

        self.state = False # whether we are showing an image or not

        # initialize clipboard and drag'n'drop
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.preview_box.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
            [], Gdk.DragAction.COPY)
        self.preview_box.drag_source_add_image_targets()
        self.preview_box.connect("drag-data-get", self.on_drag_data_get)
        self.preview_box.connect("drag-begin", self.on_drag_begin)

        # initialize the packages pop-over
        renderer = Gtk.CellRendererText()
        renderer.set_property("editable", True)
        renderer.connect("edited", self.refresh_packages)
        column = Gtk.TreeViewColumn("packages", renderer, text=0)
        self.packages = Gtk.ListStore(str)
        packages_tree = Gtk.TreeView(model=self.packages)
        packages_tree.append_column(column)
        self.packages_pop.add(packages_tree)
        self.packages.append([ADD_PACK_MSG])

        self.window.show_all()

    def generate(self) -> bool:
        """
        Generate the preview
        Return True if the compilation was successful,
        False otherwise
        """
        latex = [
            "latex",
            "-output-format=dvi"
            "-interaction=nonstopmode",
            "latexpreview.tex"
        ]
        color = self.color_btn.get_rgba()
        dvipng = [
            "dvipng",
            "latexpreview.dvi",
            '-D',
            str(self.resolution_spin.get_value()),
            '-fg', f'rgb {color.red} {color.green} {color.blue}',
            '-T', 'tight', '-bg', 'Transparent', '-o', 'latexpreview.png'
        ]
        print("Generating /tmp/latexpreview.tex")
        with open('latexpreview.tex', 'w') as tex:
            buff = self.editor.get_buffer()
            tex.write(tex_head(
                [row[0] for row in self.packages][:-1]) + strip(buff.get_text(
                buff.get_start_iter(), buff.get_end_iter(), True)
            ) + TEX_FOOT)
        print("Building /tmp/latexpreview.tex")
        e = call(latex)
        if e is not None:
            self.preview.set_from_icon_name("emblem-unreadable", 6)
            self.state = False
            return False
        print("converting /tmp/latexpreview.dvi to /tmp/latexpreview.png")
        e = call(dvipng)
        if e is not None:
            error_dialog("{} terminated with exit status {}:\n{}".format(
                e.cmd[0], e.returncode, e.output.decode("ascii")))
        # update preview
        self.preview.set_from_file('latexpreview.png')
        self.state = True
        return True

    def on_save(self, widget) -> None:
        if not self.generate(): return

        os.chdir(CWD) # so we don't pop up in the /tmp folder

        dialog = Gtk.FileChooserDialog(title="Please choose a file",
            action=Gtk.FileChooserAction.SAVE)

        dialog.add_filter(self.builder.get_object('PNG'))
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.OK)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            shutil.copy('/tmp/latexpreview.png', file_path)
            print(f"Moved /tmp/latexpreview.png to {file_path}")

        dialog.destroy()
        os.chdir('/tmp/')

    def on_copy(self, widget) -> None:
        if not self.generate(): return
        self.clipboard.set_image(self.preview.get_pixbuf())
        print("Copied /tmp/latexpreview.png to clipboard")

    def on_drag_begin(self, widget, context) -> None:
        if not self.state: return
        widget.drag_source_set_icon_pixbuf(
            self.preview.get_pixbuf())

    def on_drag_data_get(self, widget, drag_context, data, info, time) -> None:
        if not self.state: return
        data.set_pixbuf(self.preview.get_pixbuf())

    def on_quit(self, widget) -> None:
        # write the new packages to disk
        print(f"Saving application state to {CONF_FILE}")
        with open(CONF_FILE, 'w') as f:
            self.to_json(f)

        Gtk.main_quit()

    def refresh_packages(self, renderer, path, new_str) -> None:
        idx = int(path)
        it = self.packages.get_iter_from_string(path)
        if new_str.isspace() or not new_str:
            if idx == len(self.packages)-1: return
            self.packages.remove(it)
            return
        if idx == len(self.packages)-1:
            if new_str == ADD_PACK_MSG: return
            self.packages.append([ADD_PACK_MSG])
        self.packages.set_value(it, 0, new_str)

    def on_resolution_changed(self, widget) -> None:
        self.generate()

    def on_preview(self, widget) -> None:
        self.generate()

    def on_log(self, widget) -> None:
        w = LogWindow()
        w.show_all()

    def on_color_set(self, widget) -> None:
        self.generate()

    def on_packages(self, widget) -> None:
        self.packages_pop.show_all()

    def to_json(self, file: str) -> None:
        d = {}
        buff = self.editor.get_buffer()
        d['code'] = buff.get_text(
            buff.get_start_iter(), buff.get_end_iter(), True)
        d['resolution'] = self.resolution_spin.get_value()
        color = self.color_btn.get_rgba()
        d['color'] = {
            'red': color.red,
            'green': color.green,
            'blue': color.blue
        }
        d['packages'] = [row[0] for row in self.packages]
        d['packages'] = d['packages'][:-1]
        json.dump(d, file)

    @classmethod
    def from_json(cls, file: str):
        w = cls()
        buffer = Gtk.TextBuffer()
        try:
            d = json.load(file)
        except json.JSONDecodeError:
            print(f"File corrupted: {CONF_FILE} (This is fine)")
            return w

        buffer.set_text(d['code'])
        w.editor.set_buffer(buffer)
        w.color_btn.set_rgba(Gdk.RGBA(**d['color']))
        w.resolution_spin.set_value(d['resolution'])
        for p in reversed(d['packages']):
            w.packages.prepend([p])
        w.generate()
        return w


if __name__ == '__main__':
    print("Starting Latex Preview")
    try:
        with open(CONF_FILE, 'r') as f:
            print(f"Loading application state from {CONF_FILE}")
            w = MainWindow.from_json(f)
    except FileNotFoundError:
        print(f"File not found: {CONF_FILE} (This is fine)")
        w = MainWindow()
    if w.good: Gtk.main()
    print("Quitting Latex Preview")
