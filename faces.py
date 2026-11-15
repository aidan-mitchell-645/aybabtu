# -*- coding: utf-8 -*-
"""
faces.py -- the pwnagotchi-style mascot.

A little "CATS" cat drawn in 3 lines of text-art that swaps expression based on
what the launcher is doing, plus an All-Your-Base taunt for each mood. Kept as
plain-ish ASCII so it renders in the Beepy's console font (no exotic glyphs).

Usage:
    art, say = faces.get("scanning")
    # art is a list of 3 strings; say is a one-line taunt
"""

import random

# each mood -> 3 lines of art (same width) + a pool of taunts
_FACES = {
    "boot": ([
        r" /\_/\ ",
        r"( o.o )",
        r" > ^ < ",
    ], ["BOOTING UP US THE BOMB", "CATS IS WAKING"]),

    "idle": ([
        r" /\_/\ ",
        r"( -.- )",
        r" >(_)< ",
    ], ["ALL YOUR BASE ARE BELONG TO US",
        "WE GET SIGNAL", "CATS IS WATCHING"]),

    "scanning": ([
        r" /\_/\ ",
        r"( O.O )",
        r" >...< ",
    ], ["SOMEBODY SET UP US THE SCAN", "MAIN SCREEN TURN ON",
        "WE GET SIGNAL"]),

    "hit": ([
        r" /\_/\ ",
        r"( ^.^ )",
        r" >\_/< ",
    ], ["HOW ARE YOU GENTLEMEN", "ALL THEIR PORTS ARE BELONG TO US",
        "FOR GREAT JUSTICE"]),

    "pwn": ([
        r" /\_/\ ",
        r"( @.@ )",
        r" >VVV< ",
    ], ["YOU HAVE NO CHANCE TO SURVIVE", "MAKE YOUR TIME",
        "TAKE OFF EVERY EXPLOIT"]),

    "empty": ([
        r" /\_/\ ",
        r"( u.u )",
        r" > _ < ",
    ], ["WHAT YOU SAY !!", "NOTHING. CATS IS DISAPPOINT",
        "NO BASE FOR US"]),

    "fail": ([
        r" /\_/\ ",
        r"( x.x )",
        r" >###< ",
    ], ["ABORTED FOR GREAT JUSTICE", "YOU KNOW WHAT YOU DOING?",
        "NO SCOPE NO BASE"]),

    "sleep": ([
        r" /\_/\ ",
        r"( -.- )",
        r" >zzz< ",
    ], ["CATS IS SLEEPING", "ZzZ..."]),
}

# moods that should pulse/animate (eyes flip to this each other frame)
_BLINK = {
    "idle":     r"( =.= )",
    "scanning": r"( o.o )",
}


def moods():
    return list(_FACES.keys())


def get(mood, frame=0):
    """Return (art_lines, taunt) for a mood. `frame` toggles a blink."""
    art, taunts = _FACES.get(mood, _FACES["idle"])
    art = list(art)
    if mood in _BLINK and frame % 2 == 1:
        art[1] = _BLINK[mood]
    say = random.choice(taunts)
    return art, say


def width():
    return max(len(l) for art, _ in _FACES.values() for l in art)
