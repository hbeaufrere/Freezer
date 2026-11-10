"""Reference-interval statistics, kept current as the table grows.

House rules, which are not the textbook decision tree:

- Nonparametric throughout: the 2.5th and 97.5th percentiles, for every
  group at every n. At small n normality tests cannot be trusted and the
  robust method can return impossible negative limits (Le Boedec 2016);
  percentiles are bounded by the data.
- The percentile is R's quantile type 6, the p(n+1) rank rule of CLSI and
  of the referenceIntervals package, so these numbers match R.
- Fewer than 40 animals is *preliminary*: reported, flagged, not switched
  to another method.
- Outliers are flagged by Dixon's range statistic with Reed's criterion
  (the gap to the nearest value exceeds one third of the range), the form
  the ASVCP guideline describes and the only form defined at any n. They
  are flagged and retained, never dropped silently.
- 90% confidence intervals on each limit by bootstrap, seeded so the same
  table always gives the same numbers.

These figures keep the study honest day to day. The numbers in a manuscript
still come from the R workflow.
"""

import math
import random

PRELIMINARY_BELOW = 40
BOOT_RESAMPLES = 1000
BOOT_MIN_N = 10
SEED = 42


def quantile6(sorted_x, p):
    """R quantile(type = 6): rank h = p(n + 1), linear between neighbours,
    clamped to the observed range."""
    n = len(sorted_x)
    if n == 0:
        return None
    h = (n + 1) * p
    if h <= 1:
        return sorted_x[0]
    if h >= n:
        return sorted_x[-1]
    lo = int(math.floor(h))
    return sorted_x[lo - 1] + (h - lo) * (sorted_x[lo] - sorted_x[lo - 1])


def dixon_reed(sorted_x):
    """Indices (into the sorted list) of values flagged as outliers: the
    lowest and/or highest value when its gap to the next exceeds a third of
    the whole range."""
    n = len(sorted_x)
    if n < 3:
        return []
    spread = sorted_x[-1] - sorted_x[0]
    if spread <= 0:
        return []
    flagged = []
    if (sorted_x[1] - sorted_x[0]) / spread > 1 / 3:
        flagged.append(0)
    if (sorted_x[-1] - sorted_x[-2]) / spread > 1 / 3:
        flagged.append(n - 1)
    return flagged


def _bootstrap_limits(x, resamples=BOOT_RESAMPLES, seed=SEED):
    rng = random.Random(seed)
    n = len(x)
    lows, highs = [], []
    for _ in range(resamples):
        s = sorted(rng.choices(x, k=n))
        lows.append(quantile6(s, 0.025))
        highs.append(quantile6(s, 0.975))
    lows.sort()
    highs.sort()
    return ([quantile6(lows, 0.05), quantile6(lows, 0.95)],
            [quantile6(highs, 0.05), quantile6(highs, 0.95)])


def summarize(points):
    """points: list of (value, tag). Returns the summary for one analyte;
    tags come back on the outliers so the page can say whose value it is."""
    points = sorted(points, key=lambda p: p[0])
    x = [p[0] for p in points]
    n = len(x)
    if n == 0:
        return {'n': 0}
    mean = sum(x) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in x) / (n - 1)) if n > 1 else None
    out = {
        'n': n, 'mean': mean, 'sd': sd, 'median': quantile6(x, 0.5),
        'min': x[0], 'max': x[-1],
        'ri_low': quantile6(x, 0.025), 'ri_high': quantile6(x, 0.975),
        'preliminary': n < PRELIMINARY_BELOW,
        'ci_low': None, 'ci_high': None,
        'outliers': [{'value': x[i], 'tag': points[i][1], 'side': 'low' if i == 0 else 'high'}
                     for i in dixon_reed(x)],
    }
    if n >= BOOT_MIN_N:
        out['ci_low'], out['ci_high'] = _bootstrap_limits(x)
    return out
