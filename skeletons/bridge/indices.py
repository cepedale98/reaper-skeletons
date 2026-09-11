"""Translate between REAPER's three index spaces.

Web API track indices are 1-based with 0 = master.
OSC `@` wildcards are 1-based.
ReaScript GetTrack / TrackFX indices are 0-based.

Every cross-channel call goes through here so a 1 vs 0 slip cannot leak into
the UI layer.
"""

from __future__ import annotations


class Indices:
    @staticmethod
    def web_to_reaper(web_index: int) -> int | None:
        if web_index <= 0:
            return None  # master
        return web_index - 1

    @staticmethod
    def reaper_to_web(reaper_index: int) -> int:
        return reaper_index + 1

    @staticmethod
    def osc_to_reaper(osc_index: int) -> int:
        return osc_index - 1

    @staticmethod
    def reaper_to_osc(reaper_index: int) -> int:
        return reaper_index + 1

    @staticmethod
    def osc_fx_to_reaper(osc_fx: int) -> int:
        return osc_fx - 1

    @staticmethod
    def reaper_fx_to_osc(reaper_fx: int) -> int:
        return reaper_fx + 1

    @staticmethod
    def osc_param_to_reaper(osc_param: int) -> int:
        return osc_param - 1

    @staticmethod
    def reaper_param_to_osc(reaper_param: int) -> int:
        return reaper_param + 1
