#!/usr/bin/env python3
import argparse
import ctypes
import time


X = ctypes.cdll.LoadLibrary("libX11.so.6")
X.XOpenDisplay.argtypes = [ctypes.c_char_p]
X.XOpenDisplay.restype = ctypes.c_void_p
X.XCloseDisplay.argtypes = [ctypes.c_void_p]
X.XCloseDisplay.restype = ctypes.c_int
X.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
X.XDefaultRootWindow.restype = ctypes.c_ulong
X.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
X.XInternAtom.restype = ctypes.c_ulong
X.XChangeProperty.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.c_int,
]
X.XChangeProperty.restype = ctypes.c_int
X.XGetWindowProperty.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.c_long,
    ctypes.c_long,
    ctypes.c_int,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
]
X.XGetWindowProperty.restype = ctypes.c_int
X.XFree.argtypes = [ctypes.c_void_p]
X.XQueryTree.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
    ctypes.POINTER(ctypes.c_uint),
]
X.XQueryTree.restype = ctypes.c_int
X.XMoveResizeWindow.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
    ctypes.c_uint,
]
X.XLowerWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XFlush.argtypes = [ctypes.c_void_p]

XA_ATOM = 4
XA_STRING = 31
PROP_MODE_REPLACE = 0
SUCCESS = 0


def get_property(display, window, atom, atom_type):
    actual_type = ctypes.c_ulong()
    actual_format = ctypes.c_int()
    item_count = ctypes.c_ulong()
    bytes_after = ctypes.c_ulong()
    prop = ctypes.POINTER(ctypes.c_ubyte)()

    result = X.XGetWindowProperty(
        display,
        window,
        atom,
        0,
        1024,
        False,
        atom_type,
        ctypes.byref(actual_type),
        ctypes.byref(actual_format),
        ctypes.byref(item_count),
        ctypes.byref(bytes_after),
        ctypes.byref(prop),
    )
    if result != SUCCESS or not prop:
        return ""

    try:
        return ctypes.string_at(prop, item_count.value).decode("utf-8", errors="ignore")
    finally:
        X.XFree(prop)


def children(display, window):
    root = ctypes.c_ulong()
    parent = ctypes.c_ulong()
    child_array = ctypes.POINTER(ctypes.c_ulong)()
    child_count = ctypes.c_uint()

    ok = X.XQueryTree(
        display,
        window,
        ctypes.byref(root),
        ctypes.byref(parent),
        ctypes.byref(child_array),
        ctypes.byref(child_count),
    )
    if not ok or not child_array:
        return []

    try:
        return [child_array[index] for index in range(child_count.value)]
    finally:
        X.XFree(child_array)


def find_window(display, root, title, net_wm_name, utf8_string, wm_name):
    stack = list(reversed(children(display, root)))
    while stack:
        window = stack.pop()
        name = get_property(display, window, net_wm_name, utf8_string)
        if not name:
            name = get_property(display, window, wm_name, XA_STRING)
        if name == title:
            return window
        stack.extend(reversed(children(display, window)))
    return None


def set_atom_list(display, window, property_atom, values):
    atom_array = (ctypes.c_ulong * len(values))(*values)
    X.XChangeProperty(
        display,
        window,
        property_atom,
        XA_ATOM,
        32,
        PROP_MODE_REPLACE,
        atom_array,
        len(values),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--x", type=int, required=True)
    parser.add_argument("--y", type=int, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    display = X.XOpenDisplay(None)
    if not display:
        raise SystemExit("Could not open X display")

    root = X.XDefaultRootWindow(display)
    net_wm_name = X.XInternAtom(display, b"_NET_WM_NAME", False)
    utf8_string = X.XInternAtom(display, b"UTF8_STRING", False)
    wm_name = X.XInternAtom(display, b"WM_NAME", False)
    net_wm_state = X.XInternAtom(display, b"_NET_WM_STATE", False)
    net_wm_state_below = X.XInternAtom(display, b"_NET_WM_STATE_BELOW", False)
    net_wm_state_skip_taskbar = X.XInternAtom(display, b"_NET_WM_STATE_SKIP_TASKBAR", False)
    net_wm_state_skip_pager = X.XInternAtom(display, b"_NET_WM_STATE_SKIP_PAGER", False)

    deadline = time.time() + args.timeout
    window = None
    while time.time() < deadline:
        window = find_window(display, root, args.title, net_wm_name, utf8_string, wm_name)
        if window:
            break
        time.sleep(0.05)

    if not window:
        raise SystemExit(f"Could not find X11 window titled {args.title!r}")

    set_atom_list(
        display,
        window,
        net_wm_state,
        [net_wm_state_below, net_wm_state_skip_taskbar, net_wm_state_skip_pager],
    )
    X.XMoveResizeWindow(display, window, args.x, args.y, args.width, args.height)
    X.XLowerWindow(display, window)
    X.XFlush(display)
    X.XCloseDisplay(display)


if __name__ == "__main__":
    main()
