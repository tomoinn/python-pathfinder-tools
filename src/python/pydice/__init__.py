import copy
import fractions


def weapon_damage(hit_on: int, damage: 'D', critical_damage: 'D', critical=20) -> 'D':
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
    # Force hit_on to be between 2 and 20 inclusive, because 1 is always a miss
    hit_on = min(max(hit_on, 2), 20)
    # Critical hit range cannot extend below the to_hit value, so make it the max of the critical range and to_hit
    critical = max(hit_on, critical)
    # Misses on anything below the to_hit value
    p_miss = D(20).p(max=hit_on - 1)
    # Non-critical hit on anything between hit_on and below the critical range
    p_hit = D(20).p(min=hit_on, max=critical - 1)
    # Critical hit on anything at least the critical range, this is guaranteed to also be at least the to_hit value
    p_critical = D(20).p(min=critical)
    # Critical confirmation on at least the hit_on, ignoring the critical range
    p_confirm_critical = D(20).p(min=hit_on)

    # Critical damage distribution is the critical damage with the probability of confirming the hit, and the non-crit
    # damage along with the regular damage distribution
    d_critical = D.pick([
        (critical_damage, p_confirm_critical),
        (damage, 1 - p_confirm_critical)
    ])

    # Pick either a flat 0 distribution representing a miss, with p_miss, damage distribution with a regular non-crit
    # hit, or the critical distribution (including checking for confirmation) defined above.
    return D.pick([
        (0, p_miss),
        (damage, p_hit),
        (d_critical, p_critical)
    ])


class D:
    """
    Represents a set of integers with associated probabilities as Fraction objects

    These can be added, in which case the result is a new distribution representing the results of rolling each
    distribution and adding the values. They can also be multiplied by a positive integer value, in which case this is
    equivalent to repeatedly adding the distribution to itself (with multiplication by 0 resulting in a flat
    distribution of 0 with probability one). Adding an integer is treated as equivalent to adding a flat distribution,
    and coercion to fixed distributions happens automatically, so you can do e.g. D(6)+1 to get the distribution
    corresponding to rolling a six sided dice and adding one, or you can do either D(6)+D(6) or D(6)*2 to get the result
    of rolling two six sided dice and adding the values rolled.

    Instances of this class can either be constructed with a dict of int -> Fraction, in which case the dict is copied
    and used as the internal map of values to probabilities, or through the convenience method that takes an integer and
    constructs a probability distribution with n values from 1 to n with even probabilities. This is equivalent to the
    distribution of a dice with n sides, so D(6) is a regular six sided dice and so on.
    """

    def __init__(self, distribution: {}):
        """
        Create a new distribution

        :param distribution:
            A dict where keys are integers, and values are Fraction objects representing the probability of that integer
            being 'rolled' in a random pick from the distribution.
        """
        if isinstance(distribution, int):
            self._dict = {value + 1: fractions.Fraction(1, distribution) for value in range(distribution)}
        else:
            self._dict = copy.deepcopy(distribution)

    @staticmethod
    def fixed(value: int) -> 'D':
        """
        Create a new distribution with a single possible value at probability one.

        :param value:
            The value to use as the single possible return from this distribution
        :return:
            The resultant fixed distribution
        """
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
    def add(a: 'D', b: 'D') -> 'D':
        """
        Add two distributions to create a new one representing the distribution created by independently 'rolling' each
        of the inputs and adding the values together. This is used by the __add__ and __radd__ as well as __mul__ and
        __rmul__

        :param a:
            A distribution to add
        :param b:
            The other distribution to add
        :return:
            The derived distribution
        """
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
    def mean(self) -> fractions.Fraction:
        """
        Calculate the mean, defined as the sum of products of values and probabilities for all values in the dict.

        :return:
            The mean as a Fraction object
        """
        return sum([key * self._dict[key] for key in self._dict])

    @property
    def float_mean(self) -> float:
        """
        As with the mean, but coercing to a float for convenience

        :return:
            The mean as a float
        """
        return float(self.mean)

    def p(self, min=None, max=None) -> fractions.Fraction:
        """
        Return the probability, as a Fraction, of a given range of values.

        :param min:
            The minimum allowed value, defaulting to None to not specify a lower bouond
        :param max:
            The maximum allowed value, defaulting to None to not specify an upper bound
        :return:
            The probability of a single 'roll' of this distribution returning a value in the specified range, defined
            as a Fraction
        """

        def check(value):
            if min is not None and value < min:
                return False
            if max is not None and value > max:
                return False
            return True

        return sum([self._dict[value] for value in self._dict if check(value)])

    def _scale(self, s) -> 'D':
        """
        Scales all the probability values by the specified value, which can be either a float or, preferably, a Fraction
        object. This returns a new distribution which won't really make sense in itself as its probability values won't
        actually add up to one. This is really only used with the pick function.

        :param s:
            A float or Fraction value by which all probabilities in the distribution should be scaled
        :return:
            A new distribution containing the scaled probabilities
        """
        if not isinstance(s, fractions.Fraction):
            s = fractions.Fraction(s)
        return D(distribution={value: self._dict[value] * s for value in self._dict})

    @staticmethod
    def pick(l: []) -> 'D':
        """
        Create and return a new distribution representing the results of picking exactly one of a set of distributions
        with associated probabilities. These are specified as a list of tuples, where each tuple is a (distribution, p)
        pair. The p values should sum to 1 across the entire list, although this isn't currently checked. This is used
        to represent choice points, such as using a different distribution to represent miss damage, hit damage, or
        critical damage with probabilities for selecting each one.

        :param l:
            A list of (distribution, p) tuples representing mutually exclusive choices
        :return:
            The resultant distribution from that list of possible choices and probabilities
        """

        def dist_for(item):
            if isinstance(item, int):
                return D.fixed(item)
            else:
                return item

        d = {}
        for (a, b) in l:
            a = dist_for(a)._scale(b)
            for value in a._dict:
                prob = a._dict[value]
                if value in d:
                    d[value] = d[value] + prob
                else:
                    d[value] = prob
        return D(distribution=d)
