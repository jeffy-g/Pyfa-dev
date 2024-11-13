# ===============================================================================
# Copyright (C) 2010 Diego Duclos
#
# This file is part of eos.
#
# eos is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# eos is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with eos.  If not, see <http://www.gnu.org/licenses/>.
# ===============================================================================


import math
from collections import defaultdict

from eos.utils.float import floatUnerr
from utils.repr import makeReprStr


def _t(x):
    return x


class BreacherInfo:

    def __init__(self, absolute, relative):
        self.absolute = absolute
        self.relative = relative

    def __mul__(self, mul):
        return type(self)(absolute=self.absolute * mul, relative=self.relative * mul)

    def __imul__(self, mul):
        if mul == 1:
            return self
        self.absolute *= mul
        self.relative *= mul
        return self


class DmgTypes:
    """
    Container for volley stats, which stores breacher pod data
    in raw form, before application of it to target profile.
    """

    def __init__(self, em, thermal, kinetic, explosive):
        self._em = em
        self._thermal = thermal
        self._kinetic = kinetic
        self._explosive = explosive
        self._breachers = defaultdict(lambda: [])
        self.profile = None

    def add_breacher(self, key, data):
        self._breachers[key].append(data)

    @classmethod
    def default(cls):
        return cls(0, 0, 0, 0)

    @property
    def em(self):
        dmg = self._em
        if self.profile is not None:
            dmg *= 1 - getattr(self.profile, "emAmount", 0)
        return dmg

    @property
    def thermal(self):
        dmg = self._thermal
        if self.profile is not None:
            dmg *= 1 - getattr(self.profile, "thermalAmount", 0)
        return dmg

    @property
    def kinetic(self):
        dmg = self._kinetic
        if self.profile is not None:
            dmg *= 1 - getattr(self.profile, "kineticAmount", 0)
        return dmg

    @property
    def explosive(self):
        dmg = self._explosive
        if self.profile is not None:
            dmg *= 1 - getattr(self.profile, "explosiveAmount", 0)
        return dmg

    @property
    def pure(self):
        if self.profile is None:
            return sum(
                max((b.absolute for b in bs), default=0)
                for bs in self._breachers.values())
        return sum(
            max((min(b.absolute, b.relative * getattr(self.profile, "hp", math.inf)) for b in bs), default=0)
            for bs in self._breachers.values())

    @property
    def total(self):
        return self.em + self.thermal + self.kinetic + self.explosive + self.pure

    # Iterator is needed to support tuple-style unpacking
    def __iter__(self):
        yield self.em
        yield self.thermal
        yield self.kinetic
        yield self.explosive
        yield self.pure
        yield self.total

    def __eq__(self, other):
        if not isinstance(other, DmgTypes):
            return NotImplemented
        # Round for comparison's sake because often damage profiles are
        # generated from data which includes float errors
        return (
                floatUnerr(self._em) == floatUnerr(other._em) and
                floatUnerr(self._thermal) == floatUnerr(other._thermal) and
                floatUnerr(self._kinetic) == floatUnerr(other._kinetic) and
                floatUnerr(self._explosive) == floatUnerr(other._explosive) and
                sorted(self._breachers) == sorted(other._breachers),
                self.profile == other.profile)

    def __add__(self, other):
        new = type(self)(
            em=self._em + other._em,
            thermal=self._thermal + other._thermal,
            kinetic=self._kinetic + other._kinetic,
            explosive=self._explosive + other._explosive)
        new.profile = self.profile
        for k, v in self._breachers.items():
            new._breachers[k].extend(v)
        for k, v in other._breachers.items():
            new._breachers[k].extend(v)
        return new

    def __iadd__(self, other):
        self._em += other._em
        self._thermal += other._thermal
        self._kinetic += other._kinetic
        self._explosive += other._explosive
        for k, v in other._breachers.items():
            self._breachers[k].extend(v)
        return self

    def __mul__(self, mul):
        new = type(self)(
            em=self._em * mul,
            thermal=self._thermal * mul,
            kinetic=self._kinetic * mul,
            explosive=self._explosive * mul)
        new.profile = self.profile
        for k, v in self._breachers.items():
            new._breachers[k] = [b * mul for b in v]
        return new

    def __imul__(self, mul):
        if mul == 1:
            return self
        self._em *= mul
        self._thermal *= mul
        self._kinetic *= mul
        self._explosive *= mul
        for v in self._breachers.values():
            for b in v:
                b *= mul
        return self

    def __bool__(self):
        return any((
            self._em, self._thermal, self._kinetic, self._explosive,
            any(b.absolute or b.relative for b in self._breachers)))

    def __repr__(self):
        class_name = type(self).__name__
        return (f'<{class_name}(em={self._em}, thermal={self._thermal}, kinetic={self._kinetic}, '
                f'explosive={self._explosive}, breachers={len(self._breachers)})>')

    @staticmethod
    def names(short=None, postProcessor=None, includePure=False):

        value = [_t('em'), _t('th'), _t('kin'), _t('exp')] if short else [_t('em'), _t('thermal'), _t('kinetic'), _t('explosive')]
        if includePure:
            value += [_t('pure')]

        if postProcessor:
            value = [postProcessor(x) for x in value]

        return value


class DmgInflicted(DmgTypes):

    @classmethod
    def from_dmg_types(cls, dmg_types):
        return cls(em=dmg_types.em, thermal=dmg_types.thermal, kinetic=dmg_types.kinetic, explosive=dmg_types.explosive, breacher=dmg_types.breacher)

    def __add__(self, other):
        return type(self)(
            em=self.em + other.em,
            thermal=self.thermal + other.thermal,
            kinetic=self.kinetic + other.kinetic,
            explosive=self.explosive + other.explosive,
            breacher=self.breacher + other.breacher)

    def __iadd__(self, other):
        self.em += other.em
        self.thermal += other.thermal
        self.kinetic += other.kinetic
        self.explosive += other.explosive
        self.breacher += other.breacher
        self._calcTotal()
        return self


class RRTypes:
    """Container for tank data stats."""

    def __init__(self, shield, armor, hull, capacitor):
        self.shield = shield
        self.armor = armor
        self.hull = hull
        self.capacitor = capacitor

    # Iterator is needed to support tuple-style unpacking
    def __iter__(self):
        yield self.shield
        yield self.armor
        yield self.hull
        yield self.capacitor

    def __eq__(self, other):
        if not isinstance(other, RRTypes):
            return NotImplemented
        # Round for comparison's sake because often tanking numbers are
        # generated from data which includes float errors
        return (
                floatUnerr(self.shield) == floatUnerr(other.shield) and
                floatUnerr(self.armor) == floatUnerr(other.armor) and
                floatUnerr(self.hull) == floatUnerr(other.hull) and
                floatUnerr(self.capacitor) == floatUnerr(other.capacitor))

    def __bool__(self):
        return any((self.shield, self.armor, self.hull, self.capacitor))

    def __add__(self, other):
        return type(self)(
            shield=self.shield + other.shield,
            armor=self.armor + other.armor,
            hull=self.hull + other.hull,
            capacitor=self.capacitor + other.capacitor)

    def __iadd__(self, other):
        self.shield += other.shield
        self.armor += other.armor
        self.hull += other.hull
        self.capacitor += other.capacitor
        return self

    def __mul__(self, mul):
        return type(self)(
            shield=self.shield * mul,
            armor=self.armor * mul,
            hull=self.hull * mul,
            capacitor=self.capacitor * mul)

    def __imul__(self, mul):
        if mul == 1:
            return
        self.shield *= mul
        self.armor *= mul
        self.hull *= mul
        self.capacitor *= mul
        return self

    def __truediv__(self, div):
        return type(self)(
            shield=self.shield / div,
            armor=self.armor / div,
            hull=self.hull / div,
            capacitor=self.capacitor / div)

    def __itruediv__(self, div):
        if div == 1:
            return self
        self.shield /= div
        self.armor /= div
        self.hull /= div
        self.capacitor /= div
        return self

    def __repr__(self):
        spec = RRTypes.names(False)
        return makeReprStr(self, spec)

    @staticmethod
    def names(ehpOnly=True, postProcessor=None):
        value = ['shield', 'armor', 'hull']

        if not ehpOnly:
            value.append('capacitor')

        if postProcessor:
            value = [postProcessor(x) for x in value]

        return value
