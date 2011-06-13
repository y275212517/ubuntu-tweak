import logging

from collections import OrderedDict

import apt
import apt_pkg
import gobject
from gi.repository import Gtk, Gdk, Pango

from ubuntutweak.gui import GuiBuilder
from ubuntutweak.utils import icon, filesizeformat
from ubuntutweak.modules import ModuleLoader
from ubuntutweak.settings import GSetting

log = logging.getLogger('Janitor')

class CruftObject(object):
    def __init__(self, name, path=None, size=0):
        self.name = name
        self.path = path
        self.size = size

    def __str__(self):
        return self.get_name()

    def get_name(self):
        return self.name

    def get_size(self):
        return int(self.size)

    def get_size_display(self):
        return ''

    def get_icon(self):
        return None


class PackageObject(CruftObject):
    def __init__(self, name, package_name, size):
        self.name = name
        self.package_name = package_name
        self.size = size

    def get_size_display(self):
        return filesizeformat(self.size)

    def get_icon(self):
        return icon.get_from_name('deb')

    def get_package_name(self):
        return self.package_name


class JanitorPlugin(gobject.GObject):
    __title__ = ''
    __category__ = ''
    __utmodule__ = ''
    __utactive__ = True

    cache = None

    __gsignals__ = {
        'cleaned': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
    }

    @classmethod
    def get_name(cls):
        return cls.__name__

    @classmethod
    def get_title(cls):
        return cls.__title__

    @classmethod
    def get_category(cls):
        return cls.__category__

    def get_cruft(self):
        return ()

    def get_cache(self):
        try:
            self.update_apt_cache()
        except Exception, e:
            self.is_apt_broken = True
            self.apt_broken_message = e
            log.error("Error happened when get_cache(): %s" % str(e))
            return None
        else:
            return self.cache

    def get_summary(self, count, size):
        return self.get_title()

    def update_apt_cache(self, init=False):
        '''if init is true, force to update, or it will update only once'''
        if init or not getattr(self, 'cache'):
            apt_pkg.init()
            self.cache = apt.Cache()

    def clean_cruft(self, parent, cruft_list):
        '''Clean all the cruft, you must emit the "cleaned" signal to tell the
        main thread your task is finished

        :param parent: the toplevel window, use for transient
        :param cruft_list: a list contains all the cruft objects to be clean
        :param rescan_handler: the handler to rescan the result, must be called
            after the clean task is done
        '''
        pass


class JanitorPage(Gtk.VBox, GuiBuilder):
    (JANITOR_CHECK,
     JANITOR_ICON,
     JANITOR_NAME,
     JANITOR_DISPLAY,
     JANITOR_PLUGIN,
     JANITOR_SPINNER_ACTIVE,
     JANITOR_SPINNER_PULSE) = range(7)

    (RESULT_CHECK,
     RESULT_ICON,
     RESULT_NAME,
     RESULT_DISPLAY,
     RESULT_DESC,
     RESULT_PLUGIN,
     RESULT_CRUFT) = range(7)

    max_janitor_view_width = 0

    def __init__(self):
        gobject.GObject.__init__(self)
        self.set_border_width(6)
        GuiBuilder.__init__(self, 'janitorpage.ui')

        self.loader = ModuleLoader('janitor')
        self.autoscan_setting = GSetting('com.ubuntu-tweak.tweak.auto-scan')

        self.pack_start(self.vbox1, True, True, 0)

        self.connect('realize', self.setup_ui_tasks)
        self.janitor_view.get_selection().connect('changed', self.on_janitor_selection_changed)
        self.show()

    def is_auto_scan(self):
        return self.autoscan_button.get_active()

    def setup_ui_tasks(self, widget):
        self.janitor_model.set_sort_column_id(self.JANITOR_NAME, Gtk.SortType.ASCENDING)

        #add janitor columns
        janitor_column = Gtk.TreeViewColumn()

        self.janitor_check_renderer = Gtk.CellRendererToggle()
        self.janitor_check_renderer.connect('toggled', self.on_janitor_check_button_toggled)
        janitor_column.pack_start(self.janitor_check_renderer, False)
        janitor_column.add_attribute(self.janitor_check_renderer, 'active', self.JANITOR_CHECK)

        self.janitor_view.append_column(janitor_column)

        janitor_column = Gtk.TreeViewColumn()

        renderer = Gtk.CellRendererPixbuf()
        janitor_column.pack_start(renderer, False)
        janitor_column.add_attribute(renderer, 'pixbuf', self.JANITOR_ICON)
        janitor_column.set_cell_data_func(renderer,
                                          self.icon_column_view_func,
                                          self.JANITOR_ICON)

        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', Pango.EllipsizeMode.MIDDLE)
        janitor_column.pack_start(renderer, True)
        janitor_column.add_attribute(renderer, 'markup', self.JANITOR_DISPLAY)

        renderer = Gtk.CellRendererSpinner()
        janitor_column.pack_start(renderer, False)
        janitor_column.add_attribute(renderer, 'active', self.JANITOR_SPINNER_ACTIVE)
        janitor_column.add_attribute(renderer, 'pulse', self.JANITOR_SPINNER_PULSE)

        self.janitor_view.append_column(janitor_column)
        #end janitor columns

        #add result columns
        result_column = Gtk.TreeViewColumn()

        renderer = Gtk.CellRendererToggle()
        renderer.connect('toggled', self.on_result_check_renderer_toggled)
        result_column.pack_start(renderer, False)
        result_column.add_attribute(renderer, 'active', self.RESULT_CHECK)

        renderer = Gtk.CellRendererPixbuf()
        result_column.pack_start(renderer, False)
        result_column.add_attribute(renderer, 'pixbuf', self.RESULT_ICON)
        result_column.set_cell_data_func(renderer,
                                         self.icon_column_view_func,
                                         self.RESULT_ICON)

        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        result_column.pack_start(renderer, True)
        result_column.add_attribute(renderer, 'markup', self.RESULT_DISPLAY)

        renderer = Gtk.CellRendererText()
        result_column.pack_start(renderer, False)
        result_column.add_attribute(renderer, 'text', self.RESULT_DESC)

        self.result_view.append_column(result_column)
        #end result columns

        auto_scan = self.autoscan_setting.get_value()
        log.info("Auto scan status: %s", auto_scan)

        self.scan_button.set_visible(not auto_scan)
        self.autoscan_button.set_active(auto_scan)

        self.update_model()
        self.janitor_view.expand_all()
        if self.max_janitor_view_width:
            self.janitor_view.set_size_request(self.max_janitor_view_width, -1)

    def set_busy(self):
        self.get_toplevel().window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))

    def unset_busy(self):
        self.get_toplevel().window.set_cursor(None)

    def on_janitor_selection_changed(self, selection):
        model, iter = selection.get_selected()
        if iter:
            if self.janitor_model.iter_has_child(iter):
                iter = self.janitor_model.iter_children(iter)

            plugin = model[iter][self.JANITOR_PLUGIN]

            for row in self.result_model:
                if row[self.RESULT_PLUGIN] == plugin:
                    self.result_view.get_selection().select_path(row.path)
                    self.result_view.scroll_to_cell(row.path)

    def on_janitor_check_button_toggled(self, cell, path):
        iter = self.janitor_model.get_iter(path)
        checked = self.janitor_model[iter][self.JANITOR_CHECK]

        if self.janitor_model.iter_has_child(iter):
            child_iter = self.janitor_model.iter_children(iter)
            while child_iter:
                self.janitor_model[child_iter][self.JANITOR_CHECK] = not checked

                child_iter = self.janitor_model.iter_next(child_iter)

        self.janitor_model[iter][self.JANITOR_CHECK] = not checked

        self.check_child_is_all_the_same(self.janitor_model, iter,
                                         self.JANITOR_CHECK, not checked)

        if self.is_auto_scan():
            self.scan_cruft(iter, not checked)

    def _update_clean_button_sensitive(self):
        self.clean_button.set_sensitive(False)

        for row in self.result_model:
            for child_row in row.iterchildren():
                if child_row[self.RESULT_CHECK]:
                    self.clean_button.set_sensitive(True)
                    break

    def on_result_check_renderer_toggled(self, cell, path):

        iter = self.result_model.get_iter(path)
        checked = self.result_model[iter][self.RESULT_CHECK]

        if self.result_model.iter_has_child(iter):
            child_iter = self.result_model.iter_children(iter)
            while child_iter:
                self.result_model[child_iter][self.RESULT_CHECK] = not checked

                child_iter = self.result_model.iter_next(child_iter)

        self.result_model[iter][self.RESULT_CHECK] = not checked

        self.check_child_is_all_the_same(self.result_model, iter,
                                         self.RESULT_CHECK, not checked)

        self._update_clean_button_sensitive()

    def check_child_is_all_the_same(self, model, iter, column_id, status):
        iter = model.iter_parent(iter)

        if iter:
            child_iter = model.iter_children(iter)

            while child_iter:
                if status != model[child_iter][column_id]:
                    model[iter][column_id] = False
                    break
                child_iter = model.iter_next(child_iter)
            else:
                model[iter][column_id] = status

    def on_scan_button_clicked(self, widget=None):
        self.result_model.clear()
        self.clean_button.set_sensitive(False)

        for row in self.janitor_model:
            for child_row in row.iterchildren():
                checked = child_row[self.JANITOR_CHECK]

                self.scan_cruft(child_row.iter, checked)

    def scan_cruft(self, iter, checked):
        self.set_busy()
        if self.janitor_model.iter_has_child(iter):
            log.info('Scan cruft for all plugins')
            #Scan cruft for children
            child_iter = self.janitor_model.iter_children(iter)

            while child_iter:
                self.do_plugin_scan(child_iter, checked)
                child_iter = self.janitor_model.iter_next(child_iter)
        else:
            self.do_plugin_scan(iter, checked)
        self.unset_busy()

    def do_plugin_scan(self, plugin_iter, checked):
        #Scan cruft for current iter
        plugin = self.janitor_model[plugin_iter][self.JANITOR_PLUGIN]

        iter = self.result_model.get_iter_first()
        count = 0
        for row in self.result_model:
            if row[self.RESULT_PLUGIN] == plugin:
                self.result_model.remove(row.iter)

        if checked:
            log.info('Scan cruft for plugin: %s' % plugin.get_name())

            iter = self.result_model.append(None, (None,
                                                   None,
                                                   plugin.get_title(),
                                                   "<b>%s</b>" % plugin.get_title(),
                                                   None,
                                                   plugin,
                                                   None))

            self.janitor_model[plugin_iter][self.JANITOR_SPINNER_ACTIVE] = True
            self.janitor_model[plugin_iter][self.JANITOR_SPINNER_PULSE] = 0

            total_size = 0
            for i, cruft in enumerate(plugin.get_cruft()):
                while Gtk.events_pending():
                    Gtk.main_iteration()

                self.janitor_model[plugin_iter][self.JANITOR_SPINNER_PULSE] = i + 1

                total_size += cruft.get_size()

                child_iter = self.result_model.append(iter, (False,
                                                cruft.get_icon(),
                                                cruft.get_name(),
                                                cruft.get_name(),
                                                cruft.get_size_display(),
                                                plugin,
                                                cruft))

                self.result_view.get_selection().select_iter(child_iter)
                self.result_view.scroll_to_cell(self.result_model.get_path(child_iter))

                if i == 0:
                    self.result_view.expand_row(self.result_model.get_path(iter), True)
            count = self.janitor_model[plugin_iter][self.JANITOR_SPINNER_PULSE]
            self.janitor_model[plugin_iter][self.JANITOR_SPINNER_ACTIVE] = False
            self.result_model[iter][self.RESULT_DISPLAY] = "<b>%s</b>" % plugin.get_summary(count, total_size)

        # Update the janitor title
        for row in self.janitor_model:
            for child_row in row.iterchildren():

                if child_row[self.JANITOR_PLUGIN] == plugin:
                    if count and checked:
                        child_row[self.JANITOR_DISPLAY] = "<b>%s (%d) </b>" % (plugin.get_title(), count)
                    elif checked:
                        child_row[self.JANITOR_DISPLAY] = "%s (%d)" % (plugin.get_title(), count)
                    else:
                        child_row[self.JANITOR_DISPLAY] = plugin.get_title()

    def on_clean_button_clicked(self, widget):
        self.plugin_to_run = 0
        plugin_dict = OrderedDict()
        for row in self.result_model:
            plugin = row[self.RESULT_PLUGIN]
            cruft_list = []

            for child_row in row.iterchildren():
                checked = child_row[self.RESULT_CHECK]

                if checked:
                    cruft = child_row[self.RESULT_CRUFT]
                    cruft_list.append(cruft)

            if cruft_list:
                plugin_dict[plugin] = cruft_list

        self.do_real_clean_task(list(plugin_dict.items()))
        log.debug("All finished!")

    def do_real_clean_task(self, plugin_tasks):
        plugin, cruft_list = plugin_tasks.pop(0)

        log.debug("Call %s to clean cruft" % plugin)
        self._plugin_handler = plugin.connect('cleaned', self.on_plugin_cleaned, plugin_tasks)
        plugin.clean_cruft(self.get_toplevel(), cruft_list)

    def on_plugin_cleaned(self, plugin, cleaned, plugin_tasks):
        #TODO if the clean is not finished
        if plugin.handler_is_connected(self._plugin_handler):
            log.debug("Disconnect the cleaned signal, or it will clean many times")
            plugin.disconnect(self._plugin_handler)

        if len(plugin_tasks) == 0:
            self.on_scan_button_clicked()
        else:
            gobject.timeout_add(300, self.do_real_clean_task, plugin_tasks)

    def on_autoscan_button_toggled(self, widget):
        if widget.get_active():
            self.autoscan_setting.set_value(True)
            self.scan_button.hide()
        else:
            self.autoscan_setting.set_value(False)
            self.scan_button.show()

    def icon_column_view_func(self, cell_layout, renderer, model, iter, id):
        if model[iter][id] == None:
            renderer.set_property("visible", False)
        else:
            renderer.set_property("visible", True)

    def update_model(self):
        size_list = []

        system_text = _('System')
        iter = self.janitor_model.append(None, (None,
                                                icon.get_from_name('ubuntu-logo'),
                                                system_text,
                                                "<b><big>%s</big></b>" % system_text,
                                                None,
                                                None,
                                                None))

        for plugin in self.loader.get_modules_by_category('system'):
            size_list.append(Gtk.Label(plugin.get_title()).get_layout().get_pixel_size()[0])
            self.janitor_model.append(iter, (False,
                                             None,
                                             plugin.get_title(),
                                             plugin.get_title(),
                                             plugin(),
                                             None,
                                             None))

        personal_text = _('Personal')

        iter = self.janitor_model.append(None, (None,
                                                icon.get_from_name('system-users'),
                                                personal_text,
                                                "<b><big>%s</big></b>" % personal_text,
                                                None,
                                                None,
                                                None))

        for plugin in self.loader.get_modules_by_category('personal'):
            size_list.append(Gtk.Label(plugin.get_title()).get_layout().get_pixel_size()[0])
            self.janitor_model.append(iter, (False,
                                             None,
                                             plugin.get_title(),
                                             plugin.get_title(),
                                             plugin(),
                                             None,
                                             None))
        if size_list:
            self.max_janitor_view_width = max(size_list) + 80