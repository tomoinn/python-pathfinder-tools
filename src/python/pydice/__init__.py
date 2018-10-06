import copy
import fractions


def weapon_damage(hit_on, damage, critical_damage, critical=20):
    """
    Uses the Pathfinder game mechanics to calculate the distribution of damage done by a single attack, taking into
    account the possibility of missing, hitting, critical hit with confirmation and critical hit without confirmation.
    A miss happens if either the D20 roll is lower than the hit_on value or, where hit_on is adjusted to be a minimum
    of 2 because a 1 is always a miss. The critical threat range of the weapon is specified as the minimum D20 roll to
    cause a critical threat, defaulting to 20. The damage and critical damage are both distributions and can be
    specified as e.g. 2*D(6)+1 using the class in this package.

    :param hit_on:
        The minimum value on a D20 to hit the target. If this is over 20 then only criticals will hit, if this is under
        2 it is set to 2 as rolls of 1 are always misses.
    :param damage:
        The distribution used to calculate damage for a regular hit
    :param critical_damage:
        The distribution used to calculate damage for a confirmed critical
    :param critical:
        The critical threat range of the weapon, defaults to 20
    :return:
        A distribution representing damage values for this single attack. For iteratives etc, just add this result to
        that from other calls to this function.
    """
    if hit_on <= 1:
        hit_on = 2
    p_miss = D(20).p(max=hit_on - 1)
    p_hit = D(20).p(min=hit_on, max=critical - 1)
    p_critical = D(20).p(min=critical)
    p_confirm_critical = D(20).p(min=min(hit_on, critical))

    d_critical = D.pick([
        (critical_damage, p_confirm_critical),
        (damage, 1 - p_confirm_critical)
    ])

    return D.pick([
        (0, p_miss),
        (damage, p_hit),
        (d_critical, p_critical)
    ])


class D:
    """
    Represents a set of integers with associated fractions representing their respective probabilities
    """

    def __init__(self, distribution):
        if isinstance(distribution, int):
            self._dict = {value + 1: fractions.Fraction(1, distribution) for value in range(distribution)}
        else:
            self._dict = copy.deepcopy(distribution)

    @staticmethod
    def fixed(value):
        return D(distribution={value: fractions.Fraction(1, 1)})

    def __add__(self, other):
        if isinstance(other, int):
            return D.add(self, D.fixed(value=other))
        return D.add(self, other)

    def __radd__(self, other):
        return self.__add__(other)

    def __mul__(self, other):
        if not isinstance(other, int):
            raise ValueError('Can only multiply a distribution with an integer.')
        if other == 0:
            return D.fixed(value=0)
        if other < 0:
            raise ValueError('Cannot multiply a distribution by a negative integer.')
        if other == 1:
            return self
        else:
            return self + self * (other - 1)

    def __rmul__(self, other):
        return self.__mul__(other)

    @staticmethod
    def add(a: 'D', b: 'D'):
        d = {}
        for va, pa in a._dict.items():
            for vb, pb in b._dict.items():
                value = va + vb
                prob = pa * pb
                if value in d:
                    d[value] = d[value] + prob
                else:
                    d[value] = prob
        return D(distribution=d)

    def __repr__(self):
        return '[' + ', '.join('{}:{}/{}'.format(key, self._dict[key].numerator, self._dict[key].denominator) for key in
                               sorted(self._dict)) + ']'

    @property
    def mean(self):
        return sum([key * self._dict[key] for key in self._dict])

    @property
    def float_mean(self):
        return float(self.mean)

    def p(self, min=None, max=None):
        def check(value):
            if min is not None and value < min:
                return False
            if max is not None and value > max:
                return False
            return True

        return sum([self._dict[value] for value in self._dict if check(value)])

    def scale(self, s):
        if not isinstance(s, fractions.Fraction):
            s = fractions.Fraction(s)
        return D(distribution={value: self._dict[value] * s for value in self._dict})

    @staticmethod
    def pick(l: []) -> 'D':
        def dist_for(item):
            if isinstance(item, int):
                return D.fixed(item)
            else:
                return item

        d = {}
        for (a, b) in l:
            a = dist_for(a).scale(b)
            for value in a._dict:
                prob = a._dict[value]
                if value in d:
                    d[value] = d[value] + prob
                else:
                    d[value] = prob
        return D(distribution=d)
