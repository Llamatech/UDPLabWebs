# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os
import sys

from qtpy.compat import to_qvariant
from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (QMenu,
                            QToolButton,
                            QAction)


class UDPAppAction(QAction):
    """Spyder QAction class wrapper to handle cross platform patches."""

    def __init__(self, *args, **kwargs):
        """QAction class wrapper to handle cross platform patches."""
        super(UDPAppAction, self).__init__(*args, **kwargs)
        self._action_no_icon = None

        if sys.platform == 'darwin':
            self._action_no_icon = QAction(*args, **kwargs)
            self._action_no_icon.setIcon(QIcon())
            self._action_no_icon.triggered.connect(self.triggered)
            self._action_no_icon.toggled.connect(self.toggled)
            self._action_no_icon.changed.connect(self.changed)
            self._action_no_icon.hovered.connect(self.hovered)
        else:
            self._action_no_icon = self

    def __getattribute__(self, name):
        """Intercept method calls and apply to both actions, except signals."""
        attr = super(UDPAppAction, self).__getattribute__(name)

        if hasattr(attr, '__call__') and name not in ['triggered', 'toggled',
                                                      'changed', 'hovered']:
            def newfunc(*args, **kwargs):
                result = attr(*args, **kwargs)
                if name not in ['setIcon']:
                    action_no_icon = self.__dict__['_action_no_icon']
                    attr_no_icon = super(QAction,
                                         action_no_icon).__getattribute__(name)
                    attr_no_icon(*args, **kwargs)
                return result
            return newfunc
        else:
            return attr

    @property
    def no_icon_action(self):
        """Return the action without an Icon."""
        return self._action_no_icon


def add_actions(target, actions, insert_before=None):
    """Add actions to a QMenu or a QToolBar."""
    previous_action = None
    target_actions = list(target.actions())
    if target_actions:
        previous_action = target_actions[-1]
        if previous_action.isSeparator():
            previous_action = None
    for action in actions:
        if (action is None) and (previous_action is not None):
            if insert_before is None:
                target.addSeparator()
            else:
                target.insertSeparator(insert_before)
        elif isinstance(action, QMenu):
            if insert_before is None:
                target.addMenu(action)
            else:
                target.insertMenu(insert_before, action)
        elif isinstance(action, QAction):
            if insert_before is None:
                target.addAction(action)
            else:
                target.insertAction(insert_before, action)
        previous_action = action


def create_toolbutton(parent, text=None, shortcut=None, icon=None, tip=None,
                      toggled=None, triggered=None,
                      autoraise=True, text_beside_icon=False):
    """Create a QToolButton"""
    button = QToolButton(parent)
    if text is not None:
        button.setText(text)
    if icon is not None:
        # if is_text_string(icon):
            # icon = get_icon(icon)
        button.setIcon(icon)
    if text is not None or tip is not None:
        button.setToolTip(text if tip is None else tip)
    if text_beside_icon:
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    button.setAutoRaise(autoraise)
    if triggered is not None:
        button.clicked.connect(triggered)
    if toggled is not None:
        button.toggled.connect(toggled)
        button.setCheckable(True)
    if shortcut is not None:
        button.setShortcut(shortcut)
    return button


def create_action(parent, text, shortcut=None, icon=None, tip=None,
                  toggled=None, triggered=None, data=None, menurole=None,
                  context=Qt.WindowShortcut):
    """Create a QAction"""
    action = UDPAppAction(text, parent)
    if triggered is not None:
        action.triggered.connect(triggered)
    if toggled is not None:
        action.toggled.connect(toggled)
        action.setCheckable(True)
        # action.setIcon(icon)
    if tip is not None:
        action.setToolTip(tip)
        action.setStatusTip(tip)
    if data is not None:
        action.setData(to_qvariant(data))
    if menurole is not None:
        action.setMenuRole(menurole)

    # Workround for Mac because setting context=Qt.WidgetShortcut
    # there doesn't have any effect
    if sys.platform == 'darwin':
        action._shown_shortcut = None
        if context == Qt.WidgetShortcut:
            if shortcut is not None:
                action._shown_shortcut = shortcut
            else:
                # This is going to be filled by
                # main.register_shortcut
                action._shown_shortcut = 'missing'
        else:
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.setShortcutContext(context)
    else:
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.setShortcutContext(context)

    return action
