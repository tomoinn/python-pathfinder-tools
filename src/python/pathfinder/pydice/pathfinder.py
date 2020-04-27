from pathfinder.pydice import D


def weapon_damage(hit_on: int, damage: D, critical_damage: D, critical=20) -> D:
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


def reroll_distribution(roll=None, hit=None, depth=4) -> D:
    """
    Create a distribution based on cumulative re-rolls when rolling the highest value in the supplied distribution, i.e.
    if you have a d6 roll where you keep rolling and adding dice if you roll a 6. Used to represent pathfinder rolls
    such as panache.

    :param roll:
        The distribution to roll. If not specified defaults to a D6 uniform distribution
    :param hit:
        The value on which re-rolls should happen, the probability of a re-roll is the probability of at least this
        value being rolled on the supplied distribution. If not specified defaults to the highest value in the supplied
        distribution.
    :param depth:
        The maximum number of re-rolls, defaults to 4 which seems to converge closely enough for most purposes. Setting
        this to zero means no re-rolls and will just return the original distribution. Defaults to 4, which seems enough
        to converge sensibly although up to 10 or 20 will show increasing convergence.
    :return:
        A distribution representing the results of applying these re-roll rules at most depth times
    """
    if roll is None:
        d = D(6)
    elif isinstance(roll, D):
        d = roll
    else:
        d = D(roll)
    if hit is None:
        hit = d.max
    if depth < 0:
        raise ValueError('Depth parameter must be non-negative')

    def r(i):
        if i == 0:
            return d
        return D.pick([
            (d.extract(max=hit - 1), d.p(max=hit - 1)),
            (d.extract(min=hit) + r(i=i - 1), d.p(min=hit))
        ])

    return r(depth)
