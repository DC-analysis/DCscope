def connect_pp_mod_signals(parent, child):
    """The sender-receiver signal pyramid

    Each widget that implements the `pp_mod_send` and `pp_mod_recv`
    may be part of the sender-receiver pipeline modifications pyramid.
    The tip of the pyramid is the main class.
    When a widget changes something about the pipeline, it sends a dictionary
    through the `pp_mod_send` signal up the pyramid. At the top of the
    pyramid this signal is connected to the `pp_mod_recv` side of the
    pyramid.
    Every widget can send and receive any kind of pipeline change.
    Receiving widgets are responsible for filtering out what they need.
    This approach makes it easy to synchronize widgets.
    """
    parent.pp_mod_recv.connect(child.pp_mod_recv)
    child.pp_mod_send.connect(parent.pp_mod_send)
