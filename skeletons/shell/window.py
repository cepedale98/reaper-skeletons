from __future__ import annotations

from collections.abc import Callable

from skeletons.gi_init import Gdk, Gtk

from skeletons.gtkutil import add_class
from skeletons.paths import css_path
from skeletons.shell.footer import Footer
from skeletons.shell.livepage import LivePage
from skeletons.shell.siderail import SideRail
from skeletons.shell.statusbar import StatusBar
from skeletons.shell.tabrow import TabRow
from skeletons.widgets.scope import Oscilloscope
from skeletons.widgets.tuner import Tuner


def load_css() -> None:
    provider = Gtk.CssProvider()
    path = css_path()
    if path.is_file():
        provider.load_from_path(str(path))
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )


class AppWindow(Gtk.ApplicationWindow):
    """Chrome: status bar, side I/O rails, tab chain, stage, centered footer."""

    def __init__(
        self,
        title: str,
        tabs: list[tuple[str, str]],
        page_factory: Callable[[str], Gtk.Widget],
        width: int = 1180,
        height: int = 840,
        application: Gtk.Application | None = None,
    ):
        super().__init__(title=title, application=application)
        self.set_default_size(width, height)
        self.set_name("skeletons")
        load_css()

        self.status = StatusBar(title)
        self.in_rail = SideRail("IN")
        self.out_rail = SideRail("OUT")

        self.tabs = TabRow(tabs)
        tabs_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        add_class(tabs_bar, "section-tabs")
        tabs_bar.set_hexpand(True)
        self.tabs.set_hexpand(True)
        tabs_bar.append(self.tabs)

        self.footer = Footer()

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_vexpand(True)
        self.tuner = Tuner()
        self.scope = Oscilloscope()
        self.live = LivePage()
        self.pages: dict[str, Gtk.Widget] = {}
        for role, _label in tabs:
            page = page_factory(role)
            self.pages[role] = page
            self.stack.add_named(page, role)
        self.stack.add_named(self.tuner, "__tuner")
        self.stack.add_named(self.scope, "__scope")
        self.stack.add_named(self.live, "__live")

        stage = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        add_class(stage, "section-stage")
        stage.set_vexpand(True)
        stage.set_hexpand(True)
        stage.append(self.stack)

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        center.set_hexpand(True)
        center.set_vexpand(True)
        center.append(tabs_bar)
        center.append(stage)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        add_class(body, "section-body")
        body.set_vexpand(True)
        body.append(self.in_rail)
        body.append(center)
        body.append(self.out_rail)

        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        v.append(self.status)
        v.append(body)
        v.append(self.footer)
        self.set_child(v)

        self.tabs.on_select = self._on_tab
        self.footer.tuner_btn.connect("toggled", self._on_tuner)
        self.footer.scope_btn.connect("toggled", self._on_scope)
        self.footer.mode_btn.connect("toggled", lambda *_: self.show_stage())
        self.footer._on_address = self._on_info
        if tabs:
            self.tabs.select(tabs[0][0], notify=True)

    def _on_info(self, active: bool) -> None:
        self.status.address.set_visible(active)

    def _set_tuner(self, active: bool) -> None:
        self.footer.tuner_btn.handler_block_by_func(self._on_tuner)
        self.footer.tuner_btn.set_active(active)
        self.footer.tuner_btn.handler_unblock_by_func(self._on_tuner)

    def _set_scope(self, active: bool) -> None:
        self.footer.scope_btn.handler_block_by_func(self._on_scope)
        self.footer.scope_btn.set_active(active)
        self.footer.scope_btn.handler_unblock_by_func(self._on_scope)

    def _on_tab(self, _role: str) -> None:
        self._set_tuner(False)
        self._set_scope(False)
        self.show_stage()

    def _on_tuner(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self._set_scope(False)
        self.show_stage()

    def _on_scope(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self._set_tuner(False)
        self.show_stage()

    def show_stage(self) -> None:
        if self.footer.tuner_btn.get_active():
            self.stack.set_visible_child_name("__tuner")
        elif self.footer.scope_btn.get_active():
            self.stack.set_visible_child_name("__scope")
        elif self.footer.mode_btn.get_active():
            self.stack.set_visible_child_name("__live")
        elif self.tabs.active:
            self.stack.set_visible_child_name(self.tabs.active)

    def show_banner(self, text: str | None) -> None:
        self.status.set_warning(text)
